# `introspect` — SQL Server metadata, from the command line

The `introspect` subcommand asks a live SQL Server instance what it holds, and
prints the answer. Every question runs through the backend's introspector, so
what the CLI reports is what the library sees — the same objects, the same
types, the same parsing — rather than a second implementation that can drift
from it.

```bash
python -m rhosocial.activerecord.backend.impl.sqlserver introspect <TYPE> [NAME] [OPTIONS]
```

## What it can ask about

| Type | Reads | Notes |
| :--- | :--- | :--- |
| `tables` | `sys.tables`, `sys.schemas` | Base tables in the schema asked about. `--include-system` adds the engine's own. |
| `views` | `sys.views` | Views, with their definitions. |
| `table` | several | One table by name, with its columns, indexes and foreign keys filled in. |
| `columns` | `sys.columns` | One table's columns: name, type, nullability, default, and identity/additional annotations. |
| `indexes` | `sys.indexes`, `sys.index_columns` | One table's indexes, including the primary key. |
| `foreign-keys` | `sys.foreign_keys`, `sys.foreign_key_columns` | One table's constraints and the columns each side names. |
| `triggers` | `sys.triggers` | Triggers, optionally narrowed to one table. |
| `procedures` | `sys.procedures` | Stored procedures. |
| `functions` | `sys.objects` | Functions. |
| `sequences` | `sys.sequences` | Sequences with their current value and bounds. |
| `schemas` | `sys.schemas` | The schemas in the database, with their owners. |
| `database` | `sys.databases`, `@@VERSION` | Instance version and the databases visible to this login. |

`NAME` is required for `table`, `columns`, `indexes` and `foreign-keys`. The
list types take no name.

## Options

| Option | Default | Description |
| :--- | :--- | :--- |
| `-o, --output` | `table` | `table` (rich), `json`, `csv`, `tsv`. |
| `--schema` | `dbo` | The schema to read. |
| `--include-system` | off | Include system objects. |
| `--host`, `--port`, `--database` | env or defaults | Connection endpoint. `SQLSERVER_*` env vars are honoured, and arguments override them. |
| `--user` / `--username`, `--password` | env | Credentials. |
| `--trusted-connection` | off | Use Windows integrated authentication. |
| `--driver` | _None_ | ODBC driver name. |
| `--encrypt` / `--no-encrypt` | _per driver_ | TLS for the connection. |
| `--trust-server-certificate` / `--no-trust-server-certificate` | _per driver_ | Whether to verify the server certificate. |
| `--async` | off | Drive the asynchronous backend. |
| `--rich-ascii` | off | ASCII characters for table borders. |

## Notes

*   **Read-only.** `introspect` never writes. It does not create, drop, or
    alter anything, so it is safe to run against an instance whose schema
    matters.
*   **The schema is explicit.** `--schema` defaults to `dbo`; the catalogue
    views are then asked about that schema rather than resolving names
    through the login's default schema, which differs between logins.
*   **`--driver` matters when the default is wrong.** The CLI's default driver
    string is a recent one; if your machine has only an older ODBC driver
    installed, pass it explicitly.
*   **One question per invocation.** A CLI process is one connection that
    opens, answers, and closes — there is no cache carried between runs.

## Examples

```bash
# The SQL Server-specific families
python -m rhosocial.activerecord.backend.impl.sqlserver introspect schemas --database sales
python -m rhosocial.activerecord.backend.impl.sqlserver introspect procedures --schema dbo --database sales
python -m rhosocial.activerecord.backend.impl.sqlserver introspect sequences --schema dbo -o json

# One table in full
python -m rhosocial.activerecord.backend.impl.sqlserver introspect table orders --schema dbo --database sales

# Named connection saved by the named-connection subcommand
python -m rhosocial.activerecord.backend.impl.sqlserver introspect tables --named-connection prod --database sales
```
