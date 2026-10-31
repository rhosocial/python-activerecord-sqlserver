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

| Type | `NAME` | Reads | Notes |
| :--- | :--- | :--- | :--- |
| `tables` | — | `sys.objects`, `sys.schemas` | Base tables and views in the schema. `--include-system` adds the engine's own. |
| `views` | view name, optional | `INFORMATION_SCHEMA.VIEWS` | Views with their `definition` and `is_updatable`; a name answers for one view. |
| `columns` | table name, **required** | `INFORMATION_SCHEMA.COLUMNS` | One table's columns: name, type, nullability, default, and the identity flag. |
| `indexes` | table name, **required** | `sys.indexes`, `sys.index_columns` | One table's indexes, including the primary key. |
| `foreign-keys` | table name, **required** | `sys.foreign_keys`, `sys.foreign_key_columns` | One table's constraints and the columns each side names. |
| `extended-properties` | table name, **required** | `sys.extended_properties`, `sys.tables` | One table's properties — `MS_Description` above all, which is where SQL Server keeps a table's comment. |
| `triggers` | table name, optional | `sys.triggers`, `sys.trigger_events` | Triggers, with their firing `events` and their `status` (`ENABLED` / `DISABLED`); a name narrows to one table. |
| `database` | — | `sys.databases`, `@@VERSION` | Instance version and the databases visible to this login. |
| `procedures` | — | `sys.procedures` | Stored procedures. |
| `functions` | — | `sys.objects` | Functions. |
| `sequences` | — | `sys.sequences` | Sequences with their current value and bounds. |
| `schemas` | — | `sys.schemas` | The schemas in the database, with their owners. |

`NAME` means different things for different types, so the column above is part
of the interface:

*   **required** — `columns`, `indexes`, `foreign-keys` and
    `extended-properties` cannot be answered without it; leaving it out exits 1.
*   **optional** — `views` takes a *view* name and `triggers` takes a *table*
    name. Given one, the type answers for that object; left out, it lists.
*   **refused** — every other type answers for the database or the schema, so a
    name is not a filter it could apply. `tables users` exits 2 rather than
    listing every table, because a silently ignored name reads as a filter that
    matched everything.

A name that names no object exits 1 (`views nope`, `extended-properties nope`).
Exit 2 is reserved for a request this server cannot serve: an unknown type, a
family the connected server does not support, or a name the type cannot use.

## Options

| Option | Default | Description |
| :--- | :--- | :--- |
| `-o, --output` | `table` | `table` (rich), `json`, `csv`, `tsv`. |
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
*   **The connection fixes the scope.** A run names one database, so the
    catalogue views are asked about that database; there is no second
    question about which schema to read. SQL Server's default schema is
    `dbo`, and a login that changes it changes it for the connection.
*   **`--driver` matters when the default is wrong.** The CLI's default driver
    string is a recent one; if your machine has only an older ODBC driver
    installed, pass it explicitly.
*   **One question per invocation.** A CLI process is one connection that
    opens, answers, and closes — there is no cache carried between runs.

## Examples

```bash
# The SQL Server-specific families
python -m rhosocial.activerecord.backend.impl.sqlserver introspect schemas --database sales
python -m rhosocial.activerecord.backend.impl.sqlserver introspect procedures --database sales
python -m rhosocial.activerecord.backend.impl.sqlserver introspect sequences -o json

# One table's catalogue: its columns, its indexes, its foreign keys
python -m rhosocial.activerecord.backend.impl.sqlserver introspect columns orders --database sales
python -m rhosocial.activerecord.backend.impl.sqlserver introspect foreign-keys orders --database sales

# The comment SQL Server keeps in sys.extended_properties
python -m rhosocial.activerecord.backend.impl.sqlserver introspect extended-properties orders --database sales

# One view, with its definition; one table's triggers, with their events
python -m rhosocial.activerecord.backend.impl.sqlserver introspect views active_orders --database sales
python -m rhosocial.activerecord.backend.impl.sqlserver introspect triggers orders --database sales

# Named connection saved by the named-connection subcommand
python -m rhosocial.activerecord.backend.impl.sqlserver introspect tables --named-connection prod --database sales
```
