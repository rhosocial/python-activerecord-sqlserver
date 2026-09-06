# Installation Guide

## System Requirements

- Python 3.9+
- SQL Server 2016 and later (see [Supported Versions](../introduction/supported_versions.md))
- An ODBC Driver for SQL Server (e.g., ODBC Driver 17/18)
- pip or poetry

## Installation Steps

### 1. Create a Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate  # Windows
```

### 2. Install Core Library and SQL Server Backend

```bash
# Install core library
pip install rhosocial-activerecord

# Install SQL Server backend
pip install rhosocial-activerecord-sqlserver
```

### 3. Install Async Support (Optional)

The async backend requires `aioodbc`:

```bash
pip install rhosocial-activerecord-sqlserver[async]
# or
pip install aioodbc
```

> **Note**: The async components are lazy-loaded. If you import `AsyncSQLServerBackend` without `aioodbc` installed, you will get an `ImportError`.

### 4. Install the ODBC Driver

The backend requires an ODBC Driver for SQL Server installed on the system:

```bash
# Ubuntu / Debian (Microsoft ODBC Driver 18)
curl https://packages.microsoft.com/keys/microsoft.asc | tee /etc/apt/trusted.gpg.d/microsoft.asc
curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list > /etc/apt/sources.list.d/mssql-release.list
apt-get update
ACCEPT_EULA=Y apt-get install -y msodbcsql18
```

## Verify Installation

```python
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend

backend = SQLServerBackend(
    host='localhost',
    port=1433,
    database='test_db',
    username='sa',
    password='password',
    trust_server_certificate=True,
)
backend.connect()
print(f"SQL Server version: {backend.get_server_version()}")
backend.disconnect()
```

💡 *AI Prompt:* "What is ODBC and why does SQL Server access require an ODBC driver?"
