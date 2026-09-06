# Introduction

## SQL Server Backend Overview

`rhosocial-activerecord-sqlserver` is the Microsoft SQL Server database backend implementation for the rhosocial-activerecord core library. It provides complete ActiveRecord pattern support, optimized specifically for SQL Server features including T-SQL syntax, OUTPUT clause, temporal tables, and enterprise-grade capabilities.

## Synchronous and Asynchronous

The sqlserver backend provides both synchronous and asynchronous APIs that are functionally equivalent. The documentation will use synchronous examples throughout, but the asynchronous API usage is identical — just replace method calls with their async equivalents.

### Naming Convention

The framework uses a consistent naming convention across all backends:

| Component | Sync | Async |
|-----------|------|-------|
| Backend class | `SQLServerBackend` | `AsyncSQLServerBackend` |
| Transaction manager | `SQLServerTransactionManager` | `AsyncSQLServerTransactionManager` |
| Connection config | `SQLServerConnectionConfig` | `SQLServerConnectionConfig` (shared) |
| Dialect | `SQLServerDialect` | `SQLServerDialect` (shared) |

The connection config and dialect are shared between sync and async — they are pure data objects, not active connections.

### Model Layer

The model layer provides two base classes with identical method names but different calling conventions:

| Operation | `ActiveRecord` (sync) | `AsyncActiveRecord` (async) |
|-----------|----------------------|----------------------------|
| Find one | `find_one()` | `async find_one()` |
| Find all | `find_all()` | `async find_all()` |
| Save | `save()` | `async save()` |
| Delete | `delete()` | `async delete()` |
| Query builder | `.query()` → `ActiveQuery` | `.query()` → `AsyncActiveQuery` |

The method names are **identical** — there is no `a` prefix convention. The distinction is at the class level, not the method level.

### Configuration

```python
# Synchronous
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig

class User(ActiveRecord):
    ...

User.configure(SQLServerConnectionConfig(...), SQLServerBackend)
user = User.find_one(1)

# Asynchronous
from rhosocial.activerecord.model import AsyncActiveRecord
from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig

class User(AsyncActiveRecord):
    ...

User.configure(SQLServerConnectionConfig(...), AsyncSQLServerBackend)
user = await User.find_one(1)
```

### Async Driver Requirements

SQL Server uses `pyodbc` for synchronous access and `aioodbc` for asynchronous access:

| Backend | Sync Driver | Async Driver | Notes |
|---------|-------------|--------------|-------|
| SQL Server | `pyodbc` | `aioodbc` | Separate async wrapper around pyodbc |

**Important**: The async components are lazy-loaded to avoid requiring `aioodbc` when only the sync API is used. If you import `AsyncSQLServerBackend` and `aioodbc` is not installed, you will get an `ImportError` at import time.

Install async support with:

```bash
pip install rhosocial-activerecord-sqlserver[async]
# or
pip install aioodbc
```

## Quick Links

- **[Relationship with Core Library](./relationship.md)**: Learn how the sqlserver backend works with the core library
- **[Supported Versions](./supported_versions.md)**: View supported SQL Server, Python, and dependency versions

## Known Limitations and Quirks

Every database has its own behavior that differs from the SQL standard. This section documents SQL Server-specific quirks that may surprise you.

| Quirk | Description |
|-------|-------------|
| @@IDENTITY vs SCOPE_IDENTITY() | The backend uses SCOPE_IDENTITY() to avoid trigger-generated value issues |
| OUTPUT clause | SQL Server uses OUTPUT instead of RETURNING for retrieving DML results |
| OFFSET FETCH requires 2012+ | Pre-2012 versions need ROW_NUMBER() for pagination |
| SET NOCOUNT ON | When enabled, cursor.rowcount may return -1 |
| NVARCHAR vs VARCHAR | NVARCHAR stores Unicode; VARCHAR does not. The dialect defaults to NVARCHAR for test compatibility |
| GO batch separator | SQL Server scripts use GO as batch separator, not semicolons |
| TOP instead of LIMIT | SQL Server uses TOP N syntax instead of LIMIT N |
| MERGE for UPSERT | SQL Server uses MERGE for upsert operations, not ON CONFLICT |
| No TRUNCATE CASCADE | TRUNCATE does not support CASCADE option |
| No partial indexes | SQL Server does not support partial/indexed WHERE clause on indexes |

💡 *AI Prompt:* "What is the ActiveRecord pattern? How does it differ from DataMapper pattern?"
