# Migrations on SQL Server

> 📖 **Scope**: This page covers **only what is specific to running ActiveRecord migrations on this backend** — configuring the SQL Server (pyodbc) backend, transactional DDL behaviour, version gating, and how the two authoring APIs are wired to this backend's CLI.
>
> The migration **system itself** — the two APIs, vocabulary, ordering and dependency validation, version records, dry-run capture, the exception hierarchy, and the core `migrate` CLI — belongs to the [core migration chapter](https://github.com/rhosocial/python-activerecord/blob/main/docs/en_US/migration/README.md). It is **not** restated here. Read that chapter first if you are new to migrations.
>
> All examples on this page and in [docs/examples/migration/](../../examples/migration/README.md) use SQL Server.

Contents:

1. [Configuring the backend](#1-configuring-the-backend)
2. [Transactional DDL on SQL Server](#2-transactional-ddl-on-sql-server)
3. [Version-gated features and types](#3-version-gated-features-and-types)
4. [Function-style migrations (`run_migration_group`)](#4-function-style-migrations-run_migration_group)
5. [Class-style migrations and the `named-migration` CLI](#5-class-style-migrations-and-the-named-migration-cli)
6. [Local examples](#6-local-examples)

> 💡 **AI Prompt**: "I have an `@migration`-decorated function. Show me how to run it as a dry run against SQL Server, then for real, without re-explaining how the migration system works."

## 1. Configuring the backend

A migration uses the same backend and connection config as any other operation. Construct `SQLServerConnectionConfig`, pass it to `SQLServerBackend`, connect, and refresh the detected server version:

```python
from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig

config = SQLServerConnectionConfig(
    host="localhost",
    port=1433,
    database="myapp",
    username="sa",
    password="...",            # or trusted_connection=True
    driver="ODBC Driver 18 for SQL Server",
)
backend = SQLServerBackend(connection_config=config)
backend.connect()
backend.introspect_and_adapt()   # refresh the detected version before any version gate
```

Backend-specific points:

- The synchronous path uses `pyodbc` via `SQLServerBackend`; the asynchronous path uses `aioodbc` via `AsyncSQLServerBackend` and `run_migration_group_async()`. See [Connection configuration](../installation/configuration.md) for the full config surface, including Windows authentication, ODBC drivers and TLS.
- Do not hard-code credentials. The examples read connection details from `SQLSERVER_*` environment variables; the CLI accepts `--named-connection` for the same purpose.
- Call `backend.introspect_and_adapt()` before rendering version-gated DDL in application code. Gates consult the *detected* server version, and a stale version answers for the wrong floor. This backend's CLI does it on entry; a script must do it itself.
- Leave the connection's `autocommit` setting at its default. Transaction boundaries for a migration group are decided by `transaction_mode` (next section), not by the connection-level flag.

## 2. Transactional DDL on SQL Server

**SQL Server supports transactional DDL in general.** Ordinary schema statements — `CREATE TABLE`, `ALTER TABLE`, `DROP TABLE`, `CREATE INDEX` and the like — participate in a user transaction and are rolled back when it rolls back. Consequently the migration group's default `TransactionMode.AUTO` gives you an atomic group on this backend: a failure part-way through applies nothing and writes no version record. The SQL Server dialect has no `supports_transactional_ddl()` override, so the runner reports DDL as transactional (the default), which matches this behaviour.

Caveats that matter when authoring migrations here:

- **Not every statement may appear inside an explicit transaction.** Server- and database-scoped operations such as `CREATE DATABASE`, `DROP DATABASE`, `RESTORE DATABASE` and several `DBCC` commands are rejected inside a transaction. Keep such statements out of a migration group, or run them explicitly outside one; do not assume that "DDL is transactional" makes every `CREATE ...` safe.
- **Long DDL takes locks.** A migration can block on an exclusive schema lock. Bound the run with `query_timeout` on the connection config (default `0` means no limit) instead of relying on a client-side timeout.
- **`SNAPSHOT` is not automatic.** If you select snapshot isolation for a migration transaction, the database must already have `ALLOW_SNAPSHOT_ISOLATION ON`; this backend does not change that setting for you. See [Transactions](../transactions/README.md) for isolation mapping, savepoints and deadlock retries.

The meaning of `TransactionMode.AUTO` / `STEP` / `NONE`, version-record writes, and the failure metadata (`transactional_ddl`, `executed`, ...) are described in the core chapter; this page only states what those modes *do* on SQL Server.

## 3. Version-gated features and types

The dialect answers capability questions with `supports_*` probes and `version_at_least(...)`, using the constants in `mixins/version_constants.py`. A few floors that commonly affect DDL:

- sequences — 2012 (`SQL_SERVER_2012`)
- JSON functions / `supports_json_type()` — 2016 (`SQL_SERVER_2016`)
- temporal tables / `supports_system_versioning()` — 2016
- SQL Graph (node/edge tables) / `supports_sql_graph()` — 2017 (`SQL_SERVER_2017`)
- graph shortest path — 2019 (`SQL_SERVER_2019`)
- `ORDER (...)` on columnstore indexes — 2022 (`SQL_SERVER_2022`)

Check the gate **before** generating version-gated DDL; a closed gate means the expression will not render (or raises `UnsupportedFeatureError`, surfaced by the migration layer as `MigrationDialectError`):

```python
from rhosocial.activerecord.backend.impl.sqlserver.mixins.version_constants import SQL_SERVER_2016

backend.introspect_and_adapt()
dialect = backend.dialect

if dialect.supports_system_versioning() and dialect.version_at_least(SQL_SERVER_2016):
    ...  # safe to emit version-gated DDL
else:
    ...  # take a deliberate fallback, or fail deliberately
```

Note that a gate answers whether the *server* can be asked, not whether this login has grants. See [Capability gates](../capabilities/README.md) for the full floor table and the distinction between a closed gate, a version floor, and a permanently unsupported statement.

## 4. Function-style migrations (`run_migration_group`)

New work should use the function-style API. This backend contributes only the connection and dialect; the decorator, group runner, record store, ordering rules and dry-run semantics are all core features documented in the [core migration chapter](https://github.com/rhosocial/python-activerecord/blob/main/docs/en_US/migration/README.md).

The minimal SQL Server shape is:

```python
@migration("v001_create_users", description="create the initial users table")
def create_users(ctx):
    if ctx.direction == MigrationDirection.UP:
        ctx.apply(User.create_table_statement(backend=ctx.backend))
    else:
        ctx.apply(User.drop_table_statement(if_exists=True, backend=ctx.backend))


backend = SQLServerBackend(connection_config=config)
backend.connect()
backend.introspect_and_adapt()

# dry run — renders T-SQL through this backend's dialect, writes nothing
preview = run_migration_group(backend, [f"{__name__}:create_users"], dry_run=True)
print(preview.dry_run_sql, preview.dry_run_total)

# real run — applies the DDL inside a transaction and writes a version record
result = run_migration_group(backend, [f"{__name__}:create_users"], record_store=store)
```

Because DDL is rendered by this backend's dialect, the dry-run SQL you inspect is the actual T-SQL that would run — including `[bracketed]` identifiers, `IDENTITY(1,1)` and this server's type spelling. There is no backend-specific dry-run flag; `dry_run=True` is the same core option described in the core chapter.

A complete, syntax-checked script is [`01_function_migration.py`](../../examples/migration/01_function_migration.py).

## 5. Class-style migrations and the `named-migration` CLI

The class-style (`NamedMigration`) path is maintained for compatibility. This backend wires it into its own CLI through [`cli/named_migration.py`](../../../src/rhosocial/activerecord/backend/impl/sqlserver/cli/named_migration.py): the subcommand builds `SQLServerBackend` from the shared connection arguments and calls `introspect_and_adapt()` before delegating to core's `handle_named_migration`.

```bash
python -m rhosocial.activerecord.backend.impl.sqlserver named-migration \
    myapp.migrations.v001.CreateUsersTable \
    --host localhost --database myapp --user sa --password '...' \
    --direction up --record-store ./migrations.json --dry-run
```

The parser takes a **dotted** `module.Class` qualified name (not the `module:function` form of the function API) plus `--direction up|down`, `--record-store`, `--dry-run`, `--describe`, `--list`, `--param KEY=VALUE`, `--all`, `--single-transaction` and `--async`. Connection may also come from `--named-connection`. `--single-transaction` wraps a whole batch and writes records only after the final commit — useful precisely because SQL Server can roll ordinary DDL back.

Two wiring rules worth repeating here:

- Passing a `NamedMigration` class FQN to the *function-style* API (`run_migration_group`, or the core `migrate` CLI) is an error with a hint to use this backend's `named-migration` command. Use the matching API from the [core comparison table](https://github.com/rhosocial/python-activerecord/blob/main/docs/en_US/migration/README.md#1-two-apis-two-entry-points).
- For `MigrationRunner` (class API), `dry_run_sql` is assembled from the named-expression callback only; the function-style runner captures both statement paths. This is a core-level caveat, noted again so it is not missed when choosing an API.

A complete class-style demo is [`02_named_migration.py`](../../examples/migration/02_named_migration.py).

## 6. Local examples

| Script | Demonstrates |
|---|---|
| [`01_function_migration.py`](../../examples/migration/01_function_migration.py) | SQL Server config + `@migration` + `run_migration_group`: dry run → real UP → DOWN with a `JSONFileMigrationRecordStore` |
| [`02_named_migration.py`](../../examples/migration/02_named_migration.py) | a `NamedMigration` subclass driven by `MigrationRunner` on SQL Server, plus the `named-migration` CLI wiring |

These scripts are syntax-checked but require a reachable SQL Server to execute; see [docs/examples/README.md](../../examples/README.md) for the connection environment variables.
