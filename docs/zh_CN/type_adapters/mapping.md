# SQL Server 到 Python 类型映射

## 概述

SQL Server 后端负责将 SQL Server 数据库数据类型转换为 Python 对象，并将 Python 对象转换回 SQL Server 可识别的格式。

## 类型映射表

### 数值类型

| SQL Server 类型 | Python 类型 | 描述 |
|-----------------|-------------|-------------|
| TINYINT | int | 8 位无符号整数（0-255） |
| SMALLINT | int | 16 位整数 |
| INT | int | 32 位整数 |
| BIGINT | int | 64 位整数 |
| FLOAT | float | 近似精度 |
| REAL | float | 单精度浮点数 |
| DECIMAL | Decimal | 精确数值 |
| NUMERIC | Decimal | 精确数值 |
| MONEY | Decimal | 货币 |
| SMALLMONEY | Decimal | 货币 |

### 字符串类型

| SQL Server 类型 | Python 类型 | 描述 |
|-----------------|-------------|-------------|
| CHAR | str | 固定长度非 Unicode |
| VARCHAR | str | 可变长度非 Unicode |
| NCHAR | str | 固定长度 Unicode |
| NVARCHAR | str | 可变长度 Unicode（推荐） |
| NVARCHAR(MAX) | str | Unicode 大对象 |
| TEXT | str | 已弃用的大对象 |
| NTEXT | str | 已弃用的 Unicode 大对象 |

### 日期和时间类型

| SQL Server 类型 | Python 类型 | 描述 |
|-----------------|-------------|-------------|
| DATE | date | 日期 |
| TIME | time | 时间 |
| DATETIME | datetime | 日期和时间（3.33ms 精度） |
| DATETIME2 | datetime | 高精度（100ns） |
| SMALLDATETIME | datetime | 分钟精度 |
| DATETIMEOFFSET | datetime | 时区感知的日期/时间 |

### 二进制类型

| SQL Server 类型 | Python 类型 | 描述 |
|-----------------|-------------|-------------|
| BINARY | bytes | 固定长度二进制 |
| VARBINARY | bytes | 可变长度二进制 |
| VARBINARY(MAX) | bytes | 二进制大对象 |
| IMAGE | bytes | 已弃用的二进制大对象 |

### 特殊类型

| SQL Server 类型 | Python 类型 | 描述 |
|-----------------|-------------|-------------|
| BIT | bool | 布尔值 |
| UNIQUEIDENTIFIER | uuid.UUID | GUID |
| XML | str | 原生 XML 文档 |
| JSON（NVARCHAR） | dict/list | 存储为 NVARCHAR(MAX) 的 JSON |
| GEOGRAPHY | str | 基于地球的空间数据（WKT） |
| GEOMETRY | str | 平面空间数据（WKT） |
| HIERARCHYID | str | 分层数据 |

## 使用示例

```python
from typing import ClassVar
from decimal import Decimal
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.base import FieldProxy
from rhosocial.activerecord.field import UUIDMixin, DefaultTimestampMixin


class Product(UUIDMixin, DefaultTimestampMixin, ActiveRecord):
    name: str
    price: Decimal  # 自动映射到 DECIMAL
    description: str  # 自动映射到 NVARCHAR(MAX)
    metadata: dict  # 自动映射到 NVARCHAR(MAX) JSON
    is_active: bool  # 自动映射到 BIT

    c: ClassVar[FieldProxy] = FieldProxy()

    @classmethod
    def table_name(cls) -> str:
        return 'products'
```

## JSON 类型处理

SQL Server 没有原生的 JSON 类型——JSON 存储为 `NVARCHAR(MAX)`。`SQLServerJSONAdapter` 负责序列化：

```python
from rhosocial.activerecord.backend.impl.sqlserver.adapters import SQLServerJSONAdapter

adapter = SQLServerJSONAdapter()
data = {"name": "Tom", "tags": ["admin", "user"]}

# 将 Python dict/list 转换为 JSON 字符串进行存储
db_value = adapter.to_database(data, dict)
# 输出: '{"name": "Tom", "tags": ["admin", "user"]}'

# 转换回 Python dict/list
python_value = adapter.from_database(db_value, dict)
# 输出: {'name': 'Tom', 'tags': ['admin', 'user']}
```

SQL Server 2016+ 提供 JSON 函数（`JSON_VALUE`、`JSON_QUERY`、`OPENJSON`）来查询此数据。

## DATETIME2 精度

SQL Server 的 `DATETIME2` 提供 100ns 精度。ODBC 可能以带七位小数位的字符串形式传递 `datetime2` 值；`SQLServerDateTimeAdapter` 会将它们规范化为具有正确精度的 Python `datetime` 对象。

💡 *AI 提示词：* "为什么存储货币值推荐使用 DECIMAL 而不是 FLOAT？DATETIME 和 DATETIME2 有什么区别？"
