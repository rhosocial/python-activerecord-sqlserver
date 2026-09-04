# transactions tests

SQL Server transaction coverage: isolation levels and their actual effects, transaction access modes, nested transactions, savepoints, commit behavior and the set_deadlock_priority delegation.

## Key files

- `test_sqlserver_transaction_isolation.py` — isolation levels (SQL Server-specific)
- `test_transaction_backend.py` — commit behavior
- `test_transaction_backend_async.py` — async transactions
- `test_transaction_deadlock_priority.py` — deadlock priority delegation (offline, SQL Server-specific)
- `test_transaction_isolation_effect.py` — isolation effects and nesting
- `test_transaction_isolation_effect_async.py` — async isolation effects and nesting
- `test_transaction_savepoint.py` — savepoints
