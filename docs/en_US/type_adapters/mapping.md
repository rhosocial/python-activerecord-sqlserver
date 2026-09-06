# SQL Server to Python Type Mapping

## Overview

The SQL Server backend is responsible for converting SQL Server database data types to Python objects, and converting Python objects back to SQL Server-recognized formats.

## Type Mapping Table

### Numeric Types

| SQL Server Type | Python Type | Description |
|-----------------|-------------|-------------|
| TINYINT | int | 8-bit unsigned integer (0-255) |
| SMALLINT | int | 16-bit integer |
| INT | int | 32-bit integer |
| BIGINT | int | 64-bit integer |
| FLOAT | float | Approximate precision |
| REAL | float | Single-precision floating point |
| DECIMAL | Decimal | Exact numeric |
| NUMERIC | Decimal | Exact numeric |
| MONEY | Decimal | Currency |
| SMALLMONEY | Decimal | Currency |

### String Types

| SQL Server Type | Python Type | Description |
|-----------------|-------------|-------------|
| CHAR | str | Fixed-length non-Unicode |
| VARCHAR | str | Variable-length non-Unicode |
| NCHAR | str | Fixed-length Unicode |
| NVARCHAR | str | Variable-length Unicode (recommended) |
| NVARCHAR(MAX) | str | Unicode large object |
| TEXT | str | Deprecated large object |
| NTEXT | str | Deprecated Unicode large object |

### Date and Time Types

| SQL Server Type | Python Type | Description |
|-----------------|-------------|-------------|
| DATE | date | Date |
| TIME | time | Time |
| DATETIME | datetime | Date and time (3.33ms precision) |
| DATETIME2 | datetime | High precision (100ns) |
| SMALLDATETIME | datetime | Minute precision |
| DATETIMEOFFSET | datetime | Timezone-aware date/time |

### Binary Types

| SQL Server Type | Python Type | Description |
|-----------------|-------------|-------------|
| BINARY | bytes | Fixed-length binary |
| VARBINARY | bytes | Variable-length binary |
| VARBINARY(MAX) | bytes | Binary large object |
| IMAGE | bytes | Deprecated binary large object |

### Special Types

| SQL Server Type | Python Type | Description |
|-----------------|-------------|-------------|
| BIT | bool | Boolean value |
| UNIQUEIDENTIFIER | uuid.UUID | GUID |
| XML | str | Native XML document |
| JSON (NVARCHAR) | dict/list | JSON stored as NVARCHAR(MAX) |
| GEOGRAPHY | str | Earth-based spatial data (WKT) |
| GEOMETRY | str | Planar spatial data (WKT) |
| HIERARCHYID | str | Hierarchical data |

## Usage Example

```python
from typing import ClassVar
from decimal import Decimal
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.base import FieldProxy
from rhosocial.activerecord.field import UUIDMixin, DefaultTimestampMixin


class Product(UUIDMixin, DefaultTimestampMixin, ActiveRecord):
    name: str
    price: Decimal  # Automatically maps to DECIMAL
    description: str  # Automatically maps to NVARCHAR(MAX)
    metadata: dict  # Automatically maps to NVARCHAR(MAX) JSON
    is_active: bool  # Automatically maps to BIT

    c: ClassVar[FieldProxy] = FieldProxy()

    @classmethod
    def table_name(cls) -> str:
        return 'products'
```

## JSON Type Handling

SQL Server does not have a native JSON type — JSON is stored as `NVARCHAR(MAX)`. The `SQLServerJSONAdapter` handles serialization:

```python
from rhosocial.activerecord.backend.impl.sqlserver.adapters import SQLServerJSONAdapter

adapter = SQLServerJSONAdapter()
data = {"name": "Tom", "tags": ["admin", "user"]}

# Convert Python dict/list to a JSON string for storage
db_value = adapter.to_database(data, dict)
# Output: '{"name": "Tom", "tags": ["admin", "user"]}'

# Convert back to a Python dict/list
python_value = adapter.from_database(db_value, dict)
# Output: {'name': 'Tom', 'tags': ['admin', 'user']}
```

SQL Server 2016+ provides JSON functions (`JSON_VALUE`, `JSON_QUERY`, `OPENJSON`) for querying this data.

## DATETIME2 Precision

SQL Server `DATETIME2` provides 100ns precision. ODBC may deliver `datetime2` values as strings with seven fractional digits; the `SQLServerDateTimeAdapter` normalizes these into Python `datetime` objects with correct precision.

💡 *AI Prompt:* "Why is DECIMAL recommended over FLOAT for storing monetary values? What is the difference between DATETIME and DATETIME2?"
