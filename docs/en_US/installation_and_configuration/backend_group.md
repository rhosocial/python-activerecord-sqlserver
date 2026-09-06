# BackendGroup and BackendManager (SQL Server)

This document describes how to use `BackendGroup` and `BackendManager` with the SQL Server backend. For detailed API documentation, refer to the [core library documentation](../../../rhosocial-activerecord/docs/en_US/connection/connection_management.md).

## Quick Example

```python
from rhosocial.activerecord.connection import BackendGroup
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend, SQLServerConnectionConfig
from rhosocial.activerecord.model import ActiveRecord


class User(ActiveRecord):
    name: str
    email: str


# Using context manager
with BackendGroup(
    name="main",
    models=[User],
    config=SQLServerConnectionConfig(
        host="localhost",
        port=1433,
        database="myapp",
        username="sa",
        password="secret",
    ),
    backend_class=SQLServerBackend,
) as group:
    user = User(name="John", email="john@example.com")
    user.save()

# Using with multiple groups via BackendManager
from rhosocial.activerecord.connection import BackendManager

manager = BackendManager()
manager.create_group(
    name="main",
    models=[User],
    config=SQLServerConnectionConfig(host="localhost", database="main_db", username="sa", password="secret"),
    backend_class=SQLServerBackend,
)
manager.create_group(
    name="stats",
    config=SQLServerConnectionConfig(host="localhost", database="stats_db", username="sa", password="secret"),
    backend_class=SQLServerBackend,
)

main_backend = manager.get_group("main").get_backend()
stats_backend = manager.get_group("stats").get_backend()
```

## SQL Server-Specific Features

### Authentication Modes

SQL Server supports two authentication modes:

```python
# Windows Authentication
config = SQLServerConnectionConfig(
    host="localhost",
    database="myapp",
    trusted_connection=True,
)

# SQL Server Authentication
config = SQLServerConnectionConfig(
    host="localhost",
    database="myapp",
    username="sa",
    password="secret",
)
```

### SSL/Encryption Configuration

```python
config = SQLServerConnectionConfig(
    host="sqlserver.example.com",
    port=1433,
    database="myapp",
    username="sa",
    password="secret",
    encrypt=True,
    trust_server_certificate=False,
)
```

### Connection String

The config builds an ODBC connection string automatically:

```python
conn_str = config.build_connection_string()
# DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost,1433;DATABASE=myapp;UID=sa;PWD=secret;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30
```

## See Also

- [Connection Configuration](configuration.md) — full list of `SQLServerConnectionConfig` options
- [Connection Management](pool.md) — single-connection lifecycle and pooling
