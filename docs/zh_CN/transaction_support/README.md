# 事务支持

## 概述

rhosocial-activerecord 提供事务管理器来封装 SQL Server 的事务语义。本节介绍 sqlserver 后端的隔离级别、保存点和死锁处理。

## 事务管理器

### 同步

```python
# 使用事务管理器
with User.transaction():
    user = User(username='alice')
    user.save()
    # 成功退出时提交事务
    # 异常时回滚事务
```

### 异步

```python
# 使用异步事务管理器
async with User.transaction():
    user = User(username='alice')
    await user.save()
    # 成功退出时提交事务
    # 异常时回滚事务
```

事务管理器有同步和异步两种变体：
- `SQLServerTransactionManager` — 同步
- `AsyncSQLServerTransactionManager` — 异步

API 完全相同——唯一的区别是 `async with` 与 `with`。

## 目录

- [隔离级别](isolation_level.md)：SQL Server 特定的隔离语义
- [保存点](savepoint.md)：嵌套事务和条件回滚
- [死锁处理](deadlock.md)：SQL Server 死锁检测、错误代码和重试策略

## 另请参阅

- [核心：并行 Worker 模式](https://github.com/Rhosocial/python-activerecord/tree/main/docs/en_US/scenarios/parallel_workers) — 死锁预防原则

💡 *AI 提示词：* "隔离级别如何影响 SQL Server 中的并发事务？"
