# 事务隔离级别

## 概述

SQL Server 支持多种事务隔离级别，不同的隔离级别决定并发事务之间的可见性。

## 隔离级别对比

| 隔离级别 | 脏读 | 不可重复读 | 幻读 |
|-----------------|------------|---------------------|--------------|
| READ UNCOMMITTED | 可能 | 可能 | 可能 |
| READ COMMITTED（默认） | 不可能 | 可能 | 可能 |
| REPEATABLE READ | 不可能 | 不可能 | 可能 |
| SNAPSHOT | 不可能 | 不可能 | 不可能 |
| SERIALIZABLE | 不可能 | 不可能 | 不可能 |

## SQL Server 隔离级别

SQL Server 在 `SQLServerIsolationLevel` 中定义了以下隔离级别：

| 级别 | T-SQL 值 | 描述 |
|-------|-------------|-------------|
| READ_UNCOMMITTED | `READ UNCOMMITTED` | 无共享锁，可能读取未提交数据 |
| READ_COMMITTED | `READ COMMITTED` | 默认，只读取已提交数据 |
| REPEATABLE_READ | `REPEATABLE READ` | 共享锁保持到事务结束 |
| SNAPSHOT | `SNAPSHOT` | 行版本化，无阻塞 |
| SERIALIZABLE | `SERIALIZABLE` | 最高，范围锁防止幻读 |

## 设置隔离级别

### 通过事务管理器

```python
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend, SQLServerConnectionConfig
from rhosocial.activerecord.backend.transaction import IsolationLevel


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

with backend.transaction_manager.begin(isolation_level=IsolationLevel.READ_COMMITTED):
    # 事务操作以 READ COMMITTED 运行
    user = User.find_one(1)
    user.name = "new name"
    user.save()

backend.disconnect()
```

### 使用 SNAPSHOT 隔离级别

SNAPSHOT 级别是 SQL Server 特有的，可以直接选择：

```python
with backend.transaction_manager.begin(snapshot=True):
    # 以 SNAPSHOT 隔离运行
    user = User.find_one(1)
```

> **注意**：SNAPSHOT 隔离需要启用 `ALLOW_SNAPSHOT_ISOLATION` 数据库选项。

## 隔离级别详情

### READ COMMITTED（默认）

每次读取只获取已提交的数据：

```sql
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
```

SQL Server 的默认隔离级别，在并发和数据一致性之间取得平衡。

### SNAPSHOT

使用行版本化提供语句级读一致性而不阻塞写入者：

```sql
ALTER DATABASE myapp SET ALLOW_SNAPSHOT_ISOLATION ON;
SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
```

### SERIALIZABLE

最高隔离级别，通过范围锁强制顺序事务执行：

```sql
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
```

适用于要求极端数据一致性的场景，但并发性能较差。

## 不支持的功能

- **只读事务**：SQL Server 不支持 `TransactionMode.READ_ONLY`。使用锁定提示进行只读访问；请求此模式会抛出 `UnsupportedTransactionModeError`。

💡 *AI 提示词：* "什么是脏读、不可重复读和幻读？SQL Server 中 SNAPSHOT 隔离与 READ COMMITTED 有何不同？"
