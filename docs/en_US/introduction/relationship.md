# Relationship with Core Library

## Architecture Overview

rhosocial-activerecord uses a modular design where the core library (`rhosocial-activerecord`) provides database-agnostic ActiveRecord implementations, and database backends exist as separate extension packages.

The SQL Server backend's namespace is located under `rhosocial.activerecord.backend.impl.sqlserver`, at the same level as other backends (such as `sqlite`, `mysql`, `dummy`). This means:

- Backends do not participate in ActiveRecord layer changes
- Backends strictly follow backend interface protocols
- Backend updates are decoupled from the core library's ActiveRecord functionality

```
rhosocial.activerecord
├── backend.impl.sqlite   # SQLite backend
├── backend.impl.dummy    # Dummy backend for testing
├── backend.impl.mysql    # MySQL backend
└── backend.impl.sqlserver  # SQL Server backend (this package)
    ├── SQLServerBackend
    ├── AsyncSQLServerBackend
    └── ...
```

## Backend Responsibilities

The SQL Server backend is responsible for the following:

### 1. T-SQL Dialect Generation

Converts generic query builders into SQL Server-specific SQL statements:

```python
# Core library: generic query building
query = User.query().where(User.c.age >= 18).order_by(User.c.created_at)

# SQL Server backend: converted to T-SQL
# SELECT * FROM [users] WHERE [age] >= ? ORDER BY [created_at]
```

SQL Server differences handled by the dialect:
- `TOP n` instead of `LIMIT n`
- Square bracket quoting `[column]` instead of backticks
- `?` parameter placeholder (pyodbc convention)
- `OUTPUT` clause instead of `RETURNING`
- `OFFSET ... FETCH` for pagination (SQL Server 2012+)

### 2. Data Type Mapping

Handles SQL Server-specific data types, including:

- TINYINT, SMALLINT, INT, BIGINT
- FLOAT, REAL, DECIMAL, MONEY
- CHAR, VARCHAR, NCHAR, NVARCHAR, NVARCHAR(MAX)
- DATE, TIME, DATETIME, DATETIME2, DATETIMEOFFSET
- BINARY, VARBINARY, IMAGE
- UNIQUEIDENTIFIER, XML, HIERARCHYID
- JSON stored as NVARCHAR(MAX)

### 3. Connection Management

Provides SQL Server connection establishment, disconnection, and other low-level operations via pyodbc.

### 4. Transaction Control

Implements SQL Server transaction logic: `BEGIN/COMMIT/ROLLBACK TRANSACTION`, savepoints, and isolation levels.

## Quick Start

### 1. Installation

```bash
pip install rhosocial-activerecord
pip install rhosocial-activerecord-sqlserver
```

### 2. Define Models

```python
import uuid
from typing import ClassVar
from pydantic import Field
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.base import FieldProxy
from rhosocial.activerecord.field import UUIDMixin, DefaultTimestampMixin


class User(UUIDMixin, DefaultTimestampMixin, ActiveRecord):
    username: str = Field(..., max_length=50)
    email: str

    c: ClassVar[FieldProxy] = FieldProxy()

    @classmethod
    def table_name(cls) -> str:
        return 'users'
```

### 3. Configure Backend

```python
from rhosocial.activerecord.backend.impl.sqlserver import (
    SQLServerBackend,
    SQLServerConnectionConfig,
)

# Configure SQL Server connection
config = SQLServerConnectionConfig(
    host='localhost',
    port=1433,
    database='myapp',
    username='sa',
    password='password',
    trust_server_certificate=True,
)

# Configure backend for the model
User.configure(config, SQLServerBackend)
```

### 4. CRUD Operations

```python
# Create
user = User(username='tom', email='tom@example.com')
user.save()

# Read
user = User.query().where(User.c.username == 'tom').one()

# Update
user.email = 'tom.new@example.com'
user.save()

# Delete
user.delete()
```

💡 *AI Prompt:* "What is the ActiveRecord pattern? What are its advantages and disadvantages?"
