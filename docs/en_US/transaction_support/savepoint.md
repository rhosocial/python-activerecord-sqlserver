# Savepoint Support

## Overview

Savepoints allow creating intermediate checkpoints within a transaction, enabling partial rollbacks. SQL Server uses `SAVE TRANSACTION` syntax, and the transaction manager wraps this for both sync and async usage.

## Using Savepoints

SQL Server does not have a `RELEASE SAVEPOINT` command — savepoints are automatically released on commit/rollback. Rollback to a savepoint uses `ROLLBACK TRANSACTION <name>`.

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
    # Operation 1
    user1 = User(username='Alice')
    user1.save()

    # Create a savepoint
    sp = backend.transaction_manager.savepoint("sp1")

    try:
        # Operation 2 (may fail)
        user2 = User(username='Bob')
        user2.save()
    except Exception:
        # Roll back to the savepoint, keeping operation 1
        backend.transaction_manager.rollback(savepoint=sp)

backend.disconnect()
```

## Nested Transactions as Savepoints

The base transaction manager treats nested `begin()` calls as creating a savepoint on the outer transaction:

```python
with User.transaction():          # outer BEGIN TRANSACTION
    user = User(username='alice')
    user.save()
    with User.transaction():      # creates a SAVE TRANSACTION (nested)
        # inner operations
        ...
    # inner scope commits or rolls back to the savepoint
# outer commit
```

## Auto-Generated Savepoint Names

If you don't provide a name, the manager auto-generates one:

```python
sp = backend.transaction_manager.savepoint()   # auto-named sp_1, sp_2, ...
```

## Transaction Manager API

| Method | Description |
|--------|-------------|
| `savepoint(name=None)` | Create a savepoint, returns its name |
| `rollback(savepoint=name)` | Roll back to a specific savepoint |
| `release_savepoint(name)` | Mark a savepoint released (no-op in SQL Server) |
| `savepoints()` | List current savepoint names |

## See Also

- [Transaction Overview](README.md) — transaction manager API
- [Isolation Levels](isolation_level.md) — isolation semantics

💡 *AI Prompt:* "What is a database savepoint? How does it differ from a full rollback?"
