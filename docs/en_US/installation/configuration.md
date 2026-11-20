# Connection Configuration

All connection settings live on `SQLServerConnectionConfig`, which subclasses
core's `ConnectionConfig`. It is passed to `SQLServerBackend` (or
`AsyncSQLServerBackend`) as `connection_config=`.

```python
from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig

config = SQLServerConnectionConfig(
    host="localhost",
    port=1433,
    database="myapp",
    username="sa",
    password="YourStrong!Passw0rd",
    driver="ODBC Driver 18 for SQL Server",
)
backend = SQLServerBackend(connection_config=config)
backend.connect()
```

## Authentication

Two modes are supported:

```python
# SQL Server Authentication
config = SQLServerConnectionConfig(
    host="db.example.com", database="myapp",
    username="app_user", password="secret",
)

# Windows / integrated authentication
config = SQLServerConnectionConfig(
    host="db.example.com", database="myapp",
    trusted_connection=True,
)
```

`validate_config()` enforces that either `trusted_connection=True` or both
`username` and `password` are supplied. The `repr` masks the password, so a
config can be logged safely.

## Connection string fields

`build_connection_string()` produces a semicolon-delimited ODBC string. The
fields map as follows:

| Field | Default | ODBC key / effect |
|-------|---------|-------------------|
| `host` | `localhost` | `SERVER=host,port` (a `(localdb)...` host is emitted verbatim) |
| `port` | `1433` | combined with `host` |
| `database` | `""` | `DATABASE=` |
| `username` / `password` | `None` | `UID=` / `PWD=` when not using trusted connection |
| `trusted_connection` | `False` | `Trusted_Connection=yes` |
| `driver` | `ODBC Driver 17 for SQL Server` | `DRIVER={...}` |
| `encrypt` | `True` | `Encrypt=yes/no` (omitted for legacy drivers) |
| `trust_server_certificate` | `False` | `TrustServerCertificate=yes/no` |
| `timeout` | `30` | `Connection Timeout=` |
| `charset` | `UTF-8` | `CharacterSet=` when not UTF-8 |
| `options` | `{}` | extra `key=value` pairs appended verbatim |

Legacy drivers (`SQL Server`, `SQL Server Native Client 11.0`) do not accept the
`Encrypt`/`TrustServerCertificate` keywords, so those two entries are skipped
for them.

## Encryption & TLS

Encryption defaults on (`encrypt=True`) and certificate validation defaults to
strict (`trust_server_certificate=False`). A development database using a
self-signed certificate usually needs:

```python
config = SQLServerConnectionConfig(
    host="localhost", database="dev", username="sa", password="secret",
    driver="ODBC Driver 18 for SQL Server",
    encrypt=True,
    trust_server_certificate=True,  # disables server-certificate validation
)
```

> ⚠️ `trust_server_certificate=True` together with `encrypt=True` emits a
> `UserWarning`: it disables certificate validation and is not recommended for
> production.

Mutual TLS and hostname overrides are supported through:

| Field | Purpose |
|-------|---------|
| `client_certificate` | filesystem path to a PEM/PFX client certificate |
| `client_key` | filesystem path to the client key (requires `client_certificate`) |
| `client_key_password` | password for the client key |
| `host_name_in_certificate` | name to match against the server certificate when it differs from `host` |

These are paths and settings the ODBC driver reads itself, not certificate
material held by the backend. `validate_config()` rejects a `client_key`
without a `client_certificate`.

The CLI exposes the same knobs as `--ssl` (`auto`, `require`, `verify-ca`,
`verify-full`, `disabled`), with `--encrypt`/`--no-encrypt` and
`--trust-server-certificate`/`--no-trust-server-certificate` taking precedence.

## Timeouts & connection pool

| Field | Default | Meaning |
|-------|---------|---------|
| `timeout` | `30` | connection timeout, seconds |
| `query_timeout` | `0` | per-query timeout, seconds (`0` = no limit) |
| `autocommit` | `True` | initial autocommit mode |
| `pool_size` | `5` | ODBC connection pool size |
| `pool_timeout` | `30` | pool checkout timeout, seconds |
| `deployment_target` | `"sqlserver"` | label used by capability gates |

`pool_size` / `pool_timeout` are passed through as ODBC pool settings; the
driver and connection manager handle the actual pooling.

## Named connection profiles (CLI)

For CLI use, connection parameters can be supplied as flags or environment
variables:

| Flag | Environment variable | Default |
|------|----------------------|---------|
| `--host` | `SQLSERVER_HOST` | `localhost` |
| `--port` | `SQLSERVER_PORT` | `1433` |
| `--database` | `SQLSERVER_DATABASE` | required for introspection |
| `--user` / `--username` | `SQLSERVER_USERNAME` | `sa` |
| `--password` | `SQLSERVER_PASSWORD` | empty |
| `--driver` | `SQLSERVER_DRIVER` | `ODBC Driver 18 for SQL Server` |
| `--trusted-connection` | — | Windows authentication |

A named connection profile (`--named-connection`) can stand in for `--database`.
See [CLI usage](../cli/README.md).
