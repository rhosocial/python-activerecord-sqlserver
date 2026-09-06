# Custom Data Types

## Overview

The SQL Server backend provides a type system for converting between Python types and SQL Server column types. You can add support for new Python types by creating custom DataType subclasses.

## Type System Architecture

The type system has two layers:

1. **Core DataType hierarchy** — base classes for type conversion
2. **Backend-specific DataType** — SQL Server-specific type handling

## Creating Custom Data Types

### Step 1: Define the DataType Subclass

```python
from rhosocial.activerecord.backend.impl.sqlserver.types import SQLServerDataType

class GeometryDataType(SQLServerDataType):
    """Custom data type for spatial geometry."""

    @staticmethod
    def to_sql(value, dialect):
        """Convert Python Point to a SQL Server GEOMETRY literal."""
        if value is None:
            return None
        return f"geography::STGeomFromText('POINT({value.x} {value.y})', 4326)"

    @staticmethod
    def from_sql(value, dialect):
        """Convert SQL Server GEOMETRY to Python Point."""
        if value is None:
            return None
        coords = value.replace("POINT(", "").replace(")", "").split()
        return Point(float(coords[0]), float(coords[1]))
```

### Step 2: Register with @handles Decorator

```python
from rhosocial.activerecord.backend.impl.sqlserver.types import SQLServerDataType

@SQLServerDataType.handles(Point)
class PointAdapter:
    @staticmethod
    def to_sql(value, dialect):
        return f"geography::STGeomFromText('POINT({value.x} {value.y})', 4326)"

    @staticmethod
    def from_sql(value, dialect):
        coords = value.replace("POINT(", "").replace(")", "").split()
        return Point(float(coords[0]), float(coords[1]))
```

### Step 3: Use in Models

```python
from rhosocial.activerecord import Model

class Location(Model):
    __tablename__ = "locations"
    id: int
    name: str
    coordinates: Point  # Uses custom type
```

## Type Parameters

When defining custom types, consider these parameters:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `precision` | Total digits for numeric types | `DECIMAL(10, 2)` |
| `scale` | Digits after decimal point | `DECIMAL(10, 2)` |
| `length` | Maximum length for string types | `NVARCHAR(255)` |
| `max` | Whether to use the MAX variant | `NVARCHAR(MAX)` |

## SQL Server-Specific Types

The SQL Server backend provides these built-in types:

| SQL Server Type | Python Type | Notes |
|-----------------|-------------|-------|
| `NVARCHAR` | `str` | Unicode variable-length string |
| `NCHAR` | `str` | Unicode fixed-length string |
| `NVARCHAR(MAX)` | `str` | Unicode large object |
| `TINYINT` | `int` | 0-255 unsigned integer |
| `BIT` | `bool` | Boolean representation |
| `VARBINARY(MAX)` | `bytes` | Binary large object |
| `XML` | `str` | Native XML type |
| `UNIQUEIDENTIFIER` | `uuid.UUID` | GUID type |
| `DATETIMEOFFSET` | `datetime` | Timezone-aware datetime |

## See Also

- [SQL Server Field Types](../backend_specific_features/field_types.md) — SQL Server-specific data types
- [Type Mapping](../type_adapters/mapping.md) — SQL Server to Python type conversion table
- [Custom Type Adapters](custom_adapters.md) — registering custom converters

💡 *AI Prompt:* "How do I add support for a custom Python type in SQL Server?"
