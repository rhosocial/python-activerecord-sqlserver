# SQL Server Field Types

## Overview

SQL Server provides various data types for different use cases.

## Data Type Categories

### Numeric Types

| Type | Size | Range |
|------|------|-------|
| TINYINT | 1 byte | 0 to 255 |
| SMALLINT | 2 bytes | -32768 to 32767 |
| INT | 4 bytes | -2147483648 to 2147483647 |
| BIGINT | 8 bytes | -9223372036854775808 to 9223372036854775807 |
| DECIMAL | 5-17 bytes | Exact precision |
| FLOAT | 4/8 bytes | Approximate precision |
| MONEY | 8 bytes | Currency |

### String Types

| Type | Max Length |
|------|------------|
| CHAR | 8000 bytes |
| VARCHAR | 8000 bytes (MAX: 2GB) |
| TEXT | 2GB (deprecated) |
| NCHAR | 4000 bytes |
| NVARCHAR | 4000 bytes (MAX: 2GB) |
| NTEXT | 2GB (deprecated) |

### Temporal Types

| Type | Format |
|------|--------|
| DATE | YYYY-MM-DD |
| TIME | HH:MM:SS |
| DATETIME | YYYY-MM-DD HH:MM:SS |
| DATETIME2 | YYYY-MM-DD HH:MM:SS.FFFFFF |
| DATETIMEOFFSET | YYYY-MM-DD HH:MM:SS.FFFFFF +HH:MM |
| SMALLDATETIME | YYYY-MM-DD HH:MM |

### Binary Types

| Type | Max Length |
|------|------------|
| BINARY | 8000 bytes |
| VARBINARY | 8000 bytes (MAX: 2GB) |
| IMAGE | 2GB (deprecated) |

### JSON Type

```python
class Product(ActiveRecord):
    __table_name__ = "products"
    name: str
    attributes: str    # JSON stored as NVARCHAR
```

## See Also

- [Type Adapters](../type_adapters/README.md) — Type conversion

💡 *AI Prompt:* "What are the differences between VARCHAR and NVARCHAR in SQL Server?"
