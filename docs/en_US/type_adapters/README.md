# Type Adapters

## Overview

Type adapters handle the conversion between SQL Server data types and Python types. rhosocial-activerecord provides built-in adapters for common types and allows you to create custom adapters for specialized use cases.

## Architecture: How Type Conversion Works

rhosocial-activerecord uses a **two-layer type system** for converting between Python types and SQL types:

### Layer 1: Core DataType Hierarchy

The core library defines generic `DataType` classes in `rhosocial.activerecord.backend.expression.types`:

```python
from rhosocial.activerecord.backend.expression.types import (
    IntegerType,
    VarCharType,
    BooleanType,
    TimestampType,
    JsonType,
)
```

These core types are **backend-agnostic** — they define the logical type without specifying exact SQL syntax.

### Layer 2: SQL Server-Specific DataType Subclasses

SQL Server extends core types with database-specific behavior:

| Core Type | SQL Server Type | Behavior |
|-----------|----------------|----------|
| `IntegerType` | `SQLServerTinyIntType` | Maps to TINYINT (0-255) |
| `IntegerType` | `SQLServerBitType` | Maps to BIT (0/1) |
| `VarCharType` | `SQLServerNVarCharType` | Unicode NVARCHAR |
| `VarCharType` | `SQLServerNCharType` | Unicode NCHAR |
| `VarCharType` | `SQLServerNVarCharMaxType` | NVARCHAR(MAX) |
| `BinaryType` | `SQLServerVarBinaryType` | VARBINARY(n) |
| `BinaryType` | `SQLServerVarBinaryMaxType` | VARBINARY(MAX) |
| `XmlType` | `SQLServerXmlType` | Native XML type |

### The Conversion Flow

```
Python field declaration
    ↓
Core DataType (e.g., IntegerType)
    ↓
Dialect.suggest_column_type() → maps to backend-specific type
    ↓
SQL Server DataType (e.g., SQLServerNVarCharType)
    ↓
Dialect.format_data_type() → generates SQL type string
    ↓
NVARCHAR(255)
```

### Type Adapter Registration

Type adapters register conversion functions between Python types and SQL types:

```python
# Built-in adapters are registered automatically
# Custom adapters extend the mapping for specialized types
```

## Contents

- [Type Mapping](mapping.md): SQL Server to Python type conversion table
- [Custom Adapters](custom.md): Extending type support with custom adapters
- [Timezone Handling](timezone.md): DATETIMEOFFSET and timezone configuration

## Checking Type Support

You can check if the backend supports a specific type at runtime:

```python
from rhosocial.activerecord.backend.dialect.protocols import JSONSupport

dialect = backend.dialect

# Check JSON support
if isinstance(dialect, JSONSupport) and dialect.supports_json_type():
    # JSON functions are available (SQL Server 2016+)
    ...
```

## See Also

- [Backend Specific Features: Field Types](../backend_specific_features/field_types.md) — DataType hierarchy and backend-specific types
- [Dialect Expressions](../backend_specific_features/dialect.md) — feature detection and protocol system
- [Core: Custom Types](https://github.com/Rhosocial/python-activerecord/tree/main/docs/en_US/modeling/custom_types)

💡 *AI Prompt:* "How does the type system convert between Python types and SQL Server types?"
