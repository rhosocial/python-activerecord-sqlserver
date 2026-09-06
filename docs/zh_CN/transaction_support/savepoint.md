# 保存点支持

## 概述

保存点允许在事务内创建中间检查点，从而实现部分回滚。SQL Server 使用 `SAVE TRANSACTION` 语法，事务管理器为同步和异步使用封装了此功能。

## 使用保存点

SQL Server 没有 `RELEASE SAVEPOINT` 命令——保存点会在提交/回滚时自动释放。回滚到保存点使用 `ROLLBACK TRANSACTION <name>`。

```python
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend, SQLServerConnectionConfig


config = SQLServerConnectionConfig(
    host='localhost',
    port=1433,
    database='myapp',
    username='sa',
    password='password',
    trust_server_certificate=True,
)

backend = SQLServerBackend(connection_config=config)
backend.connect()

with backend.transaction_manager.begin():
    # 操作 1
    user1 = User(username='Alice')
    user1.save()

    # 创建保存点
    sp = backend.transaction_manager.savepoint("sp1")

    try:
        # 操作 2（可能失败）
        user2 = User(username='Bob')
        user2.save()
    except Exception:
        # 回滚到保存点，保留操作 1
        backend.transaction_manager.rollback(savepoint=sp)

backend.disconnect()
```

## 嵌套事务作为保存点

基础事务管理器将嵌套的 `begin()` 调用视为在外部事务上创建保存点：

```python
with User.transaction():          # 外部 BEGIN TRANSACTION
    user = User(username='alice')
    user.save()
    with User.transaction():      # 创建一个 SAVE TRANSACTION（嵌套）
        # 内部操作
        ...
    # 内部作用域提交或回滚到保存点
# 外部提交
```

## 自动生成的保存点名称

如果你不提供名称，管理器会自动生成一个：

```python
sp = backend.transaction_manager.savepoint()   # 自动命名 sp_1, sp_2, ...
```

## 事务管理器 API

| 方法 | 描述 |
|--------|-------------|
| `savepoint(name=None)` | 创建保存点，返回其名称 |
| `rollback(savepoint=name)` | 回滚到特定保存点 |
| `release_savepoint(name)` | 标记保存点已释放（SQL Server 中为 no-op） |
| `savepoints()` | 列出当前保存点名称 |

## 另请参阅

- [事务概述](README.md) — 事务管理器 API
- [隔离级别](isolation_level.md) — 隔离语义

💡 *AI 提示词：* "什么是数据库保存点？它与完全回滚有何不同？"
