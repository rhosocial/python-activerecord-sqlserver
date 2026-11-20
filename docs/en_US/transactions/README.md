# Transactions

SQL Server transactions are handled by `SQLServerTransactionManager` (and its
async counterpart). It extends core's `TransactionManager` with SNAPSHOT
isolation, `SAVE TRANSACTION` savepoints and SQL Server-specific isolation
mapping. The core transaction protocol is described in the core docs; this page
covers only this backend's portion.

```python
with backend.transaction():
    user = User(name="Alice")
    user.save()
    # commit on normal exit, rollback on exception
```

## Isolation levels

The backend defines `SQLServerIsolationLevel` with five values and maps core's
`IsolationLevel` onto them:

| `SQLServerIsolationLevel` | Core mapping | Notes |
|---------------------------|--------------|-------|
| `READ_UNCOMMITTED` | `IsolationLevel.READ_UNCOMMITTED` | |
| `READ_COMMITTED` | `IsolationLevel.READ_COMMITTED` | SQL Server default |
| `REPEATABLE_READ` | `IsolationLevel.REPEATABLE_READ` | |
| `SERIALIZABLE` | `IsolationLevel.SERIALIZABLE` | |
| `SNAPSHOT` | — (backend-specific) | row-versioning isolation |

`SNAPSHOT` has no portable equivalent, so it is selected with the dedicated
`snapshot=True` argument on `begin()` (or the corresponding transaction
context option). When a level is chosen, the manager emits
`SET TRANSACTION ISOLATION LEVEL <level>` before the real `BEGIN TRANSACTION`.
`SNAPSHOT` requires `ALLOW_SNAPSHOT_ISOLATION ON` on the database — a server
setting the backend does not change on the caller's behalf.

> 💡 *AI prompt: "What extra database setting must be enabled before SNAPSHOT isolation works, and why is it not the backend's job to enable it?"*

## Savepoints

Nested transactions use SQL Server's `SAVE TRANSACTION` syntax rather than a new
`BEGIN`. The manager tracks active savepoint names and supports:

- `savepoint(name=None)` — create one (an auto name `sp_N` is generated when
  none is given);
- `rollback(savepoint=name)` — roll back to it via `ROLLBACK TRANSACTION name`;
- release — a no-op on SQL Server, since savepoints need no explicit release.

Creating a savepoint outside an active transaction raises `TransactionError`.
A repeated name is rejected. Only the `UPDATE` lock strength is supported by
the locking mixin (see [OUTPUT, MERGE and Query Dialect](../querying/output_and_merge.md)).

## Deadlocks and retries

SQL Server errors are translated from `pyodbc` exceptions into the framework's
error hierarchy by `error_mapping.py`; the async path has the same mapping.
Deadlocks and timeouts therefore surface as framework errors that callers can
catch and retry at the unit-of-work level. Keep retry logic around the whole
transaction context — re-running a half-completed unit of work is only safe when
the transaction rolled back cleanly.

`query_timeout` on the connection config (default `0`, no limit) bounds how long
a statement may run; see [Connection configuration](../installation/configuration.md#timeouts--connection-pool).

## Async parity

`AsyncSQLServerTransactionManager` mirrors the sync manager using `aioodbc`.
Isolation levels, savepoints and the snapshot flag behave identically; only
`await` differs. The backend's test suite runs the same isolation-effect tests
through both paths.
