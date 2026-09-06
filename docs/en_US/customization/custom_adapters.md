# Custom Type Adapters

## Overview

Type adapters convert between Python values and SQL Server database values. The SQL Server backend provides an adapter registry for registering custom adapters.

## Adapter Registry

The adapter registry manages all type conversions:

```python
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend

backend = SQLServerBackend(...)
registry = backend.adapter_registry
```

## Registering Custom Adapters

### Using the @handles Decorator

```python
from rhosocial.activerecord.backend.impl.sqlserver.types import SQLServerDataType

@SQLServerDataType.handles(MyClass)
class MyClassAdapter:
    @staticmethod
    def to_sql(value, dialect):
        """Convert Python MyClass to a SQL Server value."""
        return json.dumps(value.__dict__)

    @staticmethod
    def from_sql(value, dialect):
        """Convert SQL Server value back to Python MyClass."""
        return MyClass(**json.loads(value))
```

### Manual Registration

```python
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend

class MyAdapter:
    @staticmethod
    def to_sql(value, dialect):
        return str(value)

    @staticmethod
    def from_sql(value, dialect):
        return MyClass(value)

backend = SQLServerBackend(...)
backend.adapter_registry.register(MyClass, MyAdapter)
```

## TypeAdapter Protocol

SQL Server adapters implement the `TypeAdapter` protocol with two directions:

```python
class TypeAdapter(ABC):
    @property
    @abstractmethod
    def supported_types(self) -> Dict[Type, List[str]]:
        """Mapping of Python types to SQL Server types."""
        ...

    @abstractmethod
    def to_database(self, value, target_type=None, options=None):
        """Convert Python value to database value."""
        ...

    @abstractmethod
    def from_database(self, value, target_type=None, options=None):
        """Convert database value to Python value."""
        ...
```

## Built-in SQL Server Adapters

The backend registers these adapters automatically:

| Adapter | SQL Server Types |
|---------|------------------|
| `SQLServerUUIDAdapter` | uniqueidentifier |
| `SQLServerDateTimeAdapter` | datetime2, datetime, smalldatetime |
| `SQLServerDateTimeOffsetAdapter` | datetimeoffset |
| `SQLServerDateAdapter` | date |
| `SQLServerTimeAdapter` | time |
| `SQLServerJSONAdapter` | nvarchar(max), json |
| `SQLServerXMLAdapter` | xml |
| `SQLServerSpatialAdapter` | geography, geometry |
| `SQLServerHierarchyIdAdapter` | hierarchyid |
| `SQLServerDecimalAdapter` | decimal, numeric, money, smallmoney |

## Type Conversion Flow

```
Python Value
    │
    ▼
to_database(value, ...)
    │
    ▼
SQL Server Database Value
    │
    ▼
from_database(value, ...)
    │
    ▼
Python Value
```

## See Also

- [Type Mapping](../type_adapters/mapping.md) — SQL Server to Python type conversion table
- [Custom Type Adapters](../type_adapters/custom.md) — extending type support
- [Custom Data Types](custom_types.md) — defining new DataType subclasses

💡 *AI Prompt:* "How do I register a custom type adapter for a SQL Server-specific type like HIERARCHYID?"
