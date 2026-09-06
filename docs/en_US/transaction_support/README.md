# Transaction Support

## Overview

rhosocial-activerecord provides a transaction manager that wraps SQL Server's transaction semantics. This section covers isolation levels, savepoints, and deadlock handling for the sqlserver backend.

## Transaction Manager

### Synchronous

```python
# Using the transaction manager
with User.transaction():
    user = User(username='alice')
    user.save()
    # Transaction commits on successful exit
    # Transaction rolls back on exception
```

### Asynchronous

```python
# Using the async transaction manager
async with User.transaction():
    user = User(username='alice')
    await user.save()
    # Transaction commits on successful exit
    # Transaction rolls back on exception
```

The transaction manager has both sync and async variants:
- `SQLServerTransactionManager` — synchronous
- `AsyncSQLServerTransactionManager` — asynchronous

The API is identical — the only difference is `async with` vs `with`.

## Contents

- [Isolation Levels](isolation_level.md): SQL Server-specific isolation semantics
- [Savepoint](savepoint.md): Nested transactions and conditional rollback
- [Deadlock Handling](deadlock.md): SQL Server deadlock detection, error codes, and retry strategies

## See Also

- [Core: Parallel Worker Patterns](https://github.com/Rhosocial/python-activerecord/tree/main/docs/en_US/scenarios/parallel_workers) — deadlock prevention principles

💡 *AI Prompt:* "How do isolation levels affect concurrent transactions in SQL Server?"
