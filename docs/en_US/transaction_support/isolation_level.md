# Transaction Isolation Levels

## Overview

SQL Server supports multiple transaction isolation levels, and different isolation levels determine the visibility between concurrent transactions.

## Isolation Level Comparison

| Isolation Level | Dirty Read | Non-Repeatable Read | Phantom Read |
|-----------------|------------|---------------------|--------------|
| READ UNCOMMITTED | Possible | Possible | Possible |
| READ COMMITTED (Default) | Impossible | Possible | Possible |
| REPEATABLE READ | Impossible | Impossible | Possible |
| SNAPSHOT | Impossible | Impossible | Impossible |
| SERIALIZABLE | Impossible | Impossible | Impossible |

## SQL Server Isolation Levels

SQL Server defines these isolation levels in `SQLServerIsolationLevel`:

| Level | T-SQL Value | Description |
|-------|-------------|-------------|
| READ_UNCOMMITTED | `READ UNCOMMITTED` | No shared locks, may read uncommitted data |
| READ_COMMITTED | `READ COMMITTED` | Default, reads only committed data |
| REPEATABLE_READ | `REPEATABLE READ` | Shared locks held until end of transaction |
| SNAPSHOT | `SNAPSHOT` | Row versioning, no blocking |
| SERIALIZABLE | `SERIALIZABLE` | Highest, range locks prevent phantom reads |

## Setting Isolation Level

### Via the Transaction Manager

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
    # Transaction operations run at READ COMMITTED
    user = User.find_one(1)
    user.name = "new name"
    user.save()

backend.disconnect()
```

### Using the SNAPSHOT Isolation Level

The SNAPSHOT level is SQL Server-specific and can be selected directly:

```python
with backend.transaction_manager.begin(snapshot=True):
    # Runs at SNAPSHOT isolation
    user = User.find_one(1)
```

> **Note**: SNAPSHOT isolation requires the `ALLOW_SNAPSHOT_ISOLATION` database option to be enabled.

## Isolation Level Details

### READ COMMITTED (Default)

Each read fetches only committed data:

```sql
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
```

SQL Server's default isolation level, balancing concurrency and data consistency.

### SNAPSHOT

Uses row versioning to provide statement-level read consistency without blocking writers:

```sql
ALTER DATABASE myapp SET ALLOW_SNAPSHOT_ISOLATION ON;
SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
```

### SERIALIZABLE

The highest isolation level, enforces sequential transaction execution with range locks:

```sql
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
```

Suitable for scenarios requiring extreme data consistency, but with poorer concurrency performance.

## Unsupported Features

- **READ ONLY transactions**: SQL Server does not support `TransactionMode.READ_ONLY`. Use locking hints for read-only access; requesting this mode raises `UnsupportedTransactionModeError`.

💡 *AI Prompt:* "What are dirty reads, non-repeatable reads, and phantom reads? How does SNAPSHOT isolation differ from READ COMMITTED in SQL Server?"
