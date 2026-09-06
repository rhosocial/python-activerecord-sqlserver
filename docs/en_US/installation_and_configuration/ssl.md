# SSL/TLS Configuration

## Overview

SQL Server encrypts connections by default in modern configurations. The backend exposes `encrypt` and `trust_server_certificate` options to control connection encryption behavior.

## Basic Usage

```python
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend

# Encryption is enabled by default (encrypt=True)
backend = SQLServerBackend(
    host='sqlserver.example.com',
    port=1433,
    database='myapp',
    username='sa',
    password='password',
)
backend.connect()
```

## SSL Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| encrypt | bool | True | Encrypt the connection |
| trust_server_certificate | bool | False | Trust server certificate (skip validation) |
| driver | str | ODBC Driver 17 for SQL Server | ODBC driver (drivers 17/18 differ in encryption defaults) |

## Self-Signed Certificates

For development environments using self-signed certificates, you must trust the server certificate:

```python
config = SQLServerConnectionConfig(
    host='sqlserver.example.com',
    port=1433,
    database='myapp',
    username='sa',
    password='password',
    encrypt=True,
    trust_server_certificate=True,  # Development only — disables certificate validation
)
backend = SQLServerBackend(connection_config=config)
```

⚠️ **Warning**: `trust_server_certificate=True` disables certificate validation and is **not recommended for production**. The config class emits a `UserWarning` when `encrypt=True` and `trust_server_certificate=True` are combined.

## Production Best Practices

For production, use a certificate signed by a trusted CA and keep validation enabled:

```python
config = SQLServerConnectionConfig(
    host='sqlserver.example.com',
    port=1433,
    database='myapp',
    username='sa',
    password='password',
    encrypt=True,               # Encrypt connection
    trust_server_certificate=False,  # Validate server certificate
)
```

## Verify SSL Connection

```python
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend

backend = SQLServerBackend(
    host='sqlserver.example.com',
    port=1433,
    database='myapp',
    username='sa',
    password='password',
    encrypt=True,
)
backend.connect()
print(f"Connected to: {backend.config.host}:{backend.config.port}")
backend.disconnect()
```

💡 *AI Prompt:* "What is the difference between `encrypt` and `trust_server_certificate` in SQL Server connections?"
