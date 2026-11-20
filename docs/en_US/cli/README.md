# Command Line

The backend installs the `rhosocial-activerecord-sqlserver` script and can also
be invoked as a module:

```bash
python -m rhosocial.activerecord.backend.impl.sqlserver <command>
```

Commands are registered under `cli/`: `info`, `query`, `status`, and the large
`introspect` family, plus named-connection, named-query and named-procedure
helpers.

## Connection flags

Connection parameters can be flags or environment variables:

| Flag | Environment variable | Default |
|------|----------------------|---------|
| `--host` | `SQLSERVER_HOST` | `localhost` |
| `--port` | `SQLSERVER_PORT` | `1433` |
| `--database` | `SQLSERVER_DATABASE` | required for introspection |
| `--user` / `--username` | `SQLSERVER_USERNAME` | `sa` |
| `--password` | `SQLSERVER_PASSWORD` | empty |
| `--driver` | `SQLSERVER_DRIVER` | `ODBC Driver 18 for SQL Server` |

`--trusted-connection` switches to Windows authentication. `--ssl` selects
`auto`, `require`, `verify-ca`, `verify-full` or `disabled`;
`--encrypt` / `--no-encrypt` and
`--trust-server-certificate` / `--no-trust-server-certificate` override it.
A named connection profile (`--named-connection`) may stand in for `--database`.
`--async` runs the same command through `AsyncSQLServerBackend`.

## Introspection

```bash
# Schema and tables
python -m rhosocial.activerecord.backend.impl.sqlserver introspect schemas --database mydb
python -m rhosocial.activerecord.backend.impl.sqlserver introspect tables --database mydb
python -m rhosocial.activerecord.backend.impl.sqlserver introspect columns orders --database mydb

# Operational readings and exact data profiles
python -m rhosocial.activerecord.backend.impl.sqlserver introspect unused-indexes --database mydb
python -m rhosocial.activerecord.backend.impl.sqlserver introspect runtime --database mydb
python -m rhosocial.activerecord.backend.impl.sqlserver introspect column-profiles orders --database mydb
```

Every introspect type is gated on its `supports_*` probe: a refused family exits
**2** with "not supported by this server" before a statement is sent. DDL
extraction is not offered at all because the probe is permanently `False`.
Output formats are `-o table` (default, rich), `json`, `csv` and `tsv`, with
`--rich-ascii` for plain table borders.

The complete list of introspection types, their name arguments and exit-code
rules is in [Database introspection](../introspection/README.md#command-line-introspection).

## Other commands

- `info` — connection and server information (name, version, collation, edition).
- `query` — run a statement and render results in the chosen output format.
- `status` — report the connected server's capabilities and settings.
- `named-connection`, `named-query`, `named-procedure` — manage and run saved
  definitions; see the `examples/cli` and `examples/named_*` scripts in the
  repository's `src/.../examples/` tree.

> 💡 *AI prompt: "Why does the CLI refuse a capability-gated family with exit code 2 rather than printing an empty table?"*
