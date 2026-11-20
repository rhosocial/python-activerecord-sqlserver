# Runnable Examples

Three small scripts show this backend's classes and SQL Server-specific
behaviour. They are **syntax-checked** with `python -m py_compile` but are not
executed by the documentation build: a reachable SQL Server is required.

They use environment variables for connection details, so no credentials are
hard-coded:

| Variable | Meaning | Default used here |
|----------|---------|-------------------|
| `SQLSERVER_HOST` | server host | `localhost` |
| `SQLSERVER_PORT` | server port | `1433` |
| `SQLSERVER_DATABASE` | database | `test_db` |
| `SQLSERVER_USERNAME` / `SQLSERVER_PASSWORD` | SQL authentication | `sa` / empty |
| `SQLSERVER_DRIVER` | ODBC driver name | `ODBC Driver 18 for SQL Server` |

Run a script from the repository root:

```bash
$env:SQLSERVER_DATABASE = 'demo'
python docs/examples/01_connection_and_config.py
```

> ⚠️ Use a scratch database. The DDL example creates and drops a table.

## Scripts

| Script | What it demonstrates |
|--------|----------------------|
| [`01_connection_and_config.py`](01_connection_and_config.py) | `SQLServerConnectionConfig`, ODBC connection string, connect/disconnect, version-aware capability probing |
| [`02_declarative_model_crud.py`](02_declarative_model_crud.py) | declarative `ActiveRecord` model bound with `configure(..., SQLServerBackend)`, `create_table`, `save`, typed queries, SQL preview |
| [`03_introspection_and_partition.py`](03_introspection_and_partition.py) | `backend.introspector` catalogue reads, capability gates, `SQLServerPartitionPlan` and `SQLServerPartitionMaintenance` |

For the theory behind these scripts, see the
[en_US documentation](../en_US/README.md).
