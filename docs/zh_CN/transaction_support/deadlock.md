# 自动重试与死锁处理

## 概述

SQL Server 死锁是两个或多个事务互相等待对方释放锁的情况。SQL Server 自动检测死锁，选择一个事务作为**死锁牺牲者**并以错误 **1205** 将其回滚。牺牲者会收到 `DeadlockError`。

## 死锁错误检测

后端将 SQL Server 错误 1205 转换为 `DeadlockError`：

```python
from rhosocial.activerecord.backend.errors import DeadlockError
```

## 死锁处理策略

### 1. 使用事务重试装饰器

```python
from functools import wraps
import time
from rhosocial.activerecord.backend.errors import DeadlockError


def retry_on_deadlock(max_retries=3, delay=0.1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except DeadlockError as e:
                    last_exception = e
                    time.sleep(delay * (attempt + 1))
                    continue
            raise last_exception
        return wrapper
    return decorator


@retry_on_deadlock(max_retries=3)
def transfer_money(from_account, to_account, amount):
    with Account.transaction():
        # 借方和贷方逻辑
        pass
```

### 2. 捕获死锁错误

```python
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend
from rhosocial.activerecord.backend.errors import DeadlockError


backend = SQLServerBackend(
    host='localhost',
    port=1433,
    database='myapp',
    username='sa',
    password='password',
    trust_server_certificate=True,
)
backend.connect()

try:
    with Account.transaction():
        first = Account.find_one(1)
        second = Account.find_one(2)
        # 转账逻辑
except DeadlockError:
    print("发生死锁，将重试")
    # 重试逻辑
finally:
    backend.disconnect()
```

## 死锁优先级

使用 `set_deadlock_priority()` 控制发生死锁时哪个事务成为牺牲者：

```python
# 低优先级事务会先被牺牲
backend.transaction_manager.set_deadlock_priority("LOW")     # LOW, NORMAL, HIGH
backend.transaction_manager.set_deadlock_priority(-5)         # 或 -10 到 10
```

## 锁超时

为当前会话设置锁等待超时（毫秒）：

```python
# 锁最多等待 2000ms，然后报错
backend.transaction_manager.set_lock_timeout(2000)
# -1 = 无限等待，0 = 不等待
```

## 避免死锁的建议

1. **按固定顺序访问资源**：始终以相同的顺序访问表和行
2. **尽可能使用索引**：减少被锁定的行数
3. **保持事务短小**：减少锁的持续时间
4. **需要时使用较低隔离级别**：适当使用 READ COMMITTED 或 READ UNCOMMITTED
5. **设置死锁优先级**：对后台/批量任务使用 LOW 优先级，让面向用户的事务胜出

💡 *AI 提示词：* "什么是数据库死锁？SQL Server 的错误 1205 死锁牺牲者选择与 MySQL 有什么不同？"
