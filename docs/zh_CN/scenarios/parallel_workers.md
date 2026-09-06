# 并行 Worker：最佳实践（SQL Server）

在数据处理、任务队列和批量导入等场景中，开发者通常并行运行多个 worker 以提高吞吐量。本章重点介绍 SQL Server 的并行 worker 模式。

有关通用模式（多进程生命周期、异步行为、死锁预防原则、应用分离），请参阅[核心并行 Worker 模式](https://github.com/Rhosocial/python-activerecord/tree/main/docs/en_US/scenarios/parallel_workers.md)。

> **本章设计原则**：同步 `ActiveRecord` 和异步 `AsyncActiveRecord` 具有**相同的方法名**——`configure()`、`backend()`、`transaction()`、`save()` 等。异步版本只需 `await` 或 `async with`。

## 1. SQL Server 并发概述

SQL Server 在处理并发方面与 SQLite 有根本不同：

| 功能 | SQLite | SQL Server |
| --- | --- | --- |
| 锁粒度 | 文件级锁 | 行级锁 |
| 并发写入 | 串行化 | 默认支持（不同行同时写入） |
| 异步驱动 | `aiosqlite`（线程池） | `aioodbc`（pyodbc 的异步封装） |
| 死锁处理 | 超时等待 | 检测（错误 1205），一个牺牲者被回滚 |
| 连接类型 | 文件路径 | TCP 网络连接（host:port） |

### 单连接模型的不可变性

无论 SQL Server 的并发优势如何，**单个 `ActiveRecord` 类的 `__backend__` 仍然是单个连接**。在多线程环境中，并发访问同一个 `__backend__` 会破坏游标状态。pyodbc 连接不支持并发多线程使用。

> **不要在多个线程之间共享 ActiveRecord 配置。** 对于并行 worker 场景，多进程才是正确的选择。

## 2. 多进程：推荐方法

多进程是并行 worker 场景的推荐方法。每个进程都有独立的内存空间；`configure()` 在每个进程中独立执行，建立单独的 TCP 连接。

**同步（multiprocessing）**：

```python
import multiprocessing
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend, SQLServerConnectionConfig
from models import Comment, Post, User

def worker(post_ids: list[int]):
    # 1. 进程启动后，在进程内部配置连接。
    config = SQLServerConnectionConfig(
        host="localhost", port=1433, database="mydb",
        username="sa", password="secret",
        trust_server_certificate=True, autocommit=True,
    )
    User.configure(config, SQLServerBackend)
    Post.__backend__ = User.backend()
    Comment.__backend__ = User.backend()

    try:
        for post_id in post_ids:
            post = Post.find_one(post_id)
            if post is None:
                continue
            post.view_count = 1 + len([c for c in post.comments() if c.is_approved])
            post.save()
    finally:
        # 2. 进程退出前断开连接
        User.backend().disconnect()


if __name__ == "__main__":
    post_ids = list(range(1, 101))
    chunk_size = 25
    with multiprocessing.Pool(processes=4) as pool:
        chunks = [post_ids[i:i+chunk_size] for i in range(0, len(post_ids), chunk_size)]
        pool.map(worker, chunks)
```

**关键规则**：

- 必须在子进程内部调用 `configure()`，绝不能在任何 `fork` 之前调用
- SQL Server 连接是 TCP 连接；`fork` 后继承文件描述符是危险的
- 在单个进程内，异步协程自然串行访问数据库

## 3. 死锁：SQL Server 检测与重试

SQL Server 自动检测死锁。检测到死锁时，一个事务被选为**死锁牺牲者**并以错误 **1205** 回滚，另一个事务可以继续。牺牲者会收到 `DeadlockError`。

### 3.1 根本原因：不一致的行锁顺序

```python
# ❌ 错误：不同 worker 以相反顺序锁定行
def worker_a():
    with Post.transaction():
        post1 = Post.find_one(1)  # 先锁定 id=1
        post2 = Post.find_one(2)  # 请求 id=2（B 持有它）→ 死锁
```

### 3.2 预防：一致的锁顺序

```python
# ✅ 正确：始终以主键升序锁定资源
def transfer_safe(from_id: int, to_id: int, amount: float):
    first_id, second_id = min(from_id, to_id), max(from_id, to_id)
    with Account.transaction():
        first  = Account.find_one(first_id)
        second = Account.find_one(second_id)
        debit, credit = (first, second) if from_id < to_id else (second, first)
        debit.balance  -= amount
        credit.balance += amount
        debit.save()
        credit.save()
```

### 3.3 SQL Server 特定：捕获死锁并重试

SQL Server 通过 `set_deadlock_priority()` 影响哪个事务成为牺牲者：

```python
# 低优先级的事务会先成为牺牲者
backend.transaction_manager.set_deadlock_priority("LOW")   # LOW, NORMAL, HIGH 或 -10..10
```

推荐的**生产模式是捕获错误 1205 并重试**：

```python
import time
from rhosocial.activerecord.backend.errors import DeadlockError

def _is_deadlock(exc: Exception) -> bool:
    return isinstance(exc, DeadlockError)  # SQL Server 中的错误 1205

def claim_posts_with_retry(batch_size: int = 5, max_retry: int = 3) -> list:
    for attempt in range(max_retry):
        try:
            with Post.transaction():
                pending = (
                    Post.query()
                        .where(Post.c.status == "draft")
                        .order_by(Post.c.id)
                        .top(batch_size)      # TOP n 代替 LIMIT
                        .all()
                )
                if not pending:
                    return []
                for post in pending:
                    post.status = "processing"
                    post.save()
                return pending
        except DeadlockError:
            if attempt < max_retry - 1:
                time.sleep(0.05 * (attempt + 1))  # 指数退避
                continue
            raise
    return []
```

### 3.4 五项预防原则

| 原则 | 描述 |
| --- | --- |
| **数据分区** | 按 ID 范围或哈希分配数据，使 worker 永不会触碰相同行 |
| **一致的锁顺序** | 锁定多个资源时始终按固定顺序（例如主键升序） |
| **短事务** | 事务中只保留必要操作 |
| **原子声明** | 在一个事务内查询并更新任务状态 |
| **死锁重试** | 捕获 `DeadlockError`（错误 1205）并使用退避重试 |

> **SQL Server vs MySQL**：MySQL 使用 `innodb_lock_wait_timeout` 和 errno 1213。SQL Server 使用错误 1205 进行死锁检测，并使用 `SET LOCK_TIMEOUT`（毫秒）进行锁等待超时。

## 4. 示例代码

本章完整的可运行示例位于 MySQL 后端文档的 `docs/examples/chapter_08_scenarios/parallel_workers/` 目录中，已针对 SQL Server 进行调整。

## 5. 结论

1. **多进程是并行 worker 的正确方法**
2. **生产环境推荐死锁重试** —— 不依赖数据可分区性
3. **数据分区最有效** —— 无锁争用
4. **使用 `set_deadlock_priority()`** 控制在死锁中牺牲哪些事务
