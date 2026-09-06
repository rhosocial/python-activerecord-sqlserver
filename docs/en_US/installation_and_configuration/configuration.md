# Connection Configuration

## Basic Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| host | str | localhost | SQL Server hostname or IP |
| port | int | 1433 | SQL Server port |
| database | str | - | Database name |
| username | str | - | Username (SQL Authentication) |
| password | str | - | Password (SQL Authentication) |
| trusted_connection | bool | False | Use Windows Authentication |
| driver | str | ODBC Driver 17 for SQL Server | ODBC driver name |
| encrypt | bool | True | Encrypt the connection |
| trust_server_certificate | bool | False | Trust server certificate |
| timeout | int | 30 | Connection timeout (seconds) |
| query_timeout | int | 0 | Query timeout (0 = no limit) |
| autocommit | bool | True | Auto-commit mode |
| charset | str | UTF-8 | Character encoding |
| pool_size | int | 5 | Reserved connection pool size |
| pool_timeout | int | 30 | Reserved pool timeout |

## Advanced Configuration Options

```python
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig

config = SQLServerConnectionConfig(
    # Basic configuration
    host='localhost',
    port=1433,
    database='myapp',
    username='sa',
    password='mypassword',

    # Authentication
    trusted_connection=False,

    # SSL/Encryption
    driver='ODBC Driver 18 for SQL Server',
    encrypt=True,
    trust_server_certificate=False,

    # Timeouts
    timeout=30,
    query_timeout=60,
    autocommit=True,

    # Encoding
    charset='UTF-8',
)
```

## Authentication Modes

### SQL Server Authentication

```python
config = SQLServerConnectionConfig(
    host='localhost',
    database='myapp',
    username='sa',
    password='secret',
)
```

### Windows Authentication

```python
config = SQLServerConnectionConfig(
    host='localhost',
    database='myapp',
    trusted_connection=True,
)
```

## Using YAML Configuration

```yaml
# sqlserver_scenarios.yaml
scenarios:
  production:
    host: db.example.com
    port: 1433
    database: myapp_prod
    username: app_user
    password: ${SQLSERVER_PASSWORD}
    encrypt: true
    autocommit: true

  development:
    host: localhost
    port: 1433
    database: myapp_dev
    username: sa
    password: dev_password
    encrypt: false
    autocommit: true
```

## Connection String

The config can build the ODBC connection string directly:

```python
conn_str = config.build_connection_string()
# DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost,1433;DATABASE=myapp;UID=sa;PWD=mypassword;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30
```

💡 *AI Prompt:* "What is the difference between SQL Server Authentication and Windows Authentication (trusted connection)?"
