# SQL Server 字段类型

## 概述

SQL Server 提供多种数据类型用于不同场景。

## 数据类型分类

### 数值类型

| 类型 | 大小 | 范围 |
|------|------|------|
| TINYINT | 1 字节 | 0 到 255 |
| SMALLINT | 2 字节 | -32768 到 32767 |
| INT | 4 字节 | -2147483648 到 2147483647 |
| BIGINT | 8 字节 | -9223372036854775808 到 9223372036854775807 |
| DECIMAL | 5-17 字节 | 精确精度 |
| FLOAT | 4/8 字节 | 近似精度 |
| MONEY | 8 字节 | 货币 |

### 字符串类型

| 类型 | 最大长度 |
|------|----------|
| CHAR | 8000 字节 |
| VARCHAR | 8000 字节 (MAX: 2GB) |
| TEXT | 2GB (已弃用) |
| NCHAR | 4000 字节 |
| NVARCHAR | 4000 字节 (MAX: 2GB) |
| NTEXT | 2GB (已弃用) |

### 时间类型

| 类型 | 格式 |
|------|------|
| DATE | YYYY-MM-DD |
| TIME | HH:MM:SS |
| DATETIME | YYYY-MM-DD HH:MM:SS |
| DATETIME2 | YYYY-MM-DD HH:MM:SS.FFFFFF |
| DATETIMEOFFSET | YYYY-MM-DD HH:MM:SS.FFFFFF +HH:MM |
| SMALLDATETIME | YYYY-MM-DD HH:MM |

### 二进制类型

| 类型 | 最大长度 |
|------|----------|
| BINARY | 8000 字节 |
| VARBINARY | 8000 字节 (MAX: 2GB) |
| IMAGE | 2GB (已弃用) |

### JSON 类型

```python
class Product(ActiveRecord):
    __table_name__ = "products"
    name: str
    attributes: str    # JSON 存储为 NVARCHAR
```

## 另请参阅

- [类型适配器](../type_adapters/README.md) — 类型转换

💡 *AI 提示：* "SQL Server 中 VARCHAR 和 NVARCHAR 有什么区别？"
