# Migration Examples (SQL Server)

Runnable-style examples for migrations on the SQL Server backend. The
migration **system** is documented in the
[core migration chapter](https://github.com/rhosocial/python-activerecord/blob/main/docs/en_US/migration/README.md);
the SQL Server-specific concerns are in
[docs/en_US/migration/](../../en_US/migration/README.md) ([中文](../../zh_CN/migration/README.md)).

These scripts are **syntax-checked** with `python -m py_compile` but are not
executed by the documentation build: a reachable SQL Server is required. They
read connection details from the `SQLSERVER_*` environment variables described
in [docs/examples/README.md](../README.md), so no credentials are hard-coded.

Run a script from the repository root:

```bash
$env:SQLSERVER_DATABASE = 'demo'
python docs/examples/migration/01_function_migration.py
```

> ⚠️ Use a scratch database. The examples create and drop a table.

## Scripts

| Script | Demonstrates |
|---|---|
| [`01_function_migration.py`](01_function_migration.py) | `SQLServerConnectionConfig` + `SQLServerBackend`, `@migration` with `ctx.apply()`, and `run_migration_group`: dry run → real UP → DOWN with a `JSONFileMigrationRecordStore` |
| [`02_named_migration.py`](02_named_migration.py) | a `NamedMigration` subclass driven by `MigrationRunner` on SQL Server, plus the `named-migration` CLI wiring |
