# 自定义数据类型

## 概述

SQL Server 后端提供了一个类型系统，用于在 Python 类型和 SQL Server 列类型之间进行转换。你可以通过创建自定义 DataType 子类来为新的 Python 类型添加支持。

## 类型系统架构

类型系统有两层：

1. **核心 DataType 层次结构** — 用于类型转换的基类
2. **后端特定 DataType** — SQL Server 特定的类型处理

## 创建自定义数据类型

### 步骤 1：定义 DataType 子类

```python
from rhosocial.activerecord.backend.impl.sqlserver.types import SQLServerDataType

class GeometryDataType(SQLServerDataType):
    """用于空间几何的自定义数据类型。"""

    @staticmethod
    def to_sql(value, dialect):
        """将 Python Point 转换为 SQL Server GEOMETRY 字面量。"""
        if value is None:
            return None
        return f"geography::STGeomFromText('POINT({value.x} {value.y})', 4326)"

    @staticmethod
    def from_sql(value, dialect):
        """将 SQL Server GEOMETRY 转换为 Python Point。"""
        if value is None:
            return None
        coords = value.replace("POINT(", "").replace(")", "").split()
        return Point(float(coords[0]), float(coords[1]))
```

### 步骤 2：使用 @handles 装饰器注册

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

### 步骤 3：在模型中使用

```python
from rhosocial.activerecord import Model

class Location(Model):
    __tablename__ = "locations"
    id: int
    name: str
    coordinates: Point  # 使用自定义类型
```

## 类型参数

定义自定义类型时，请考虑这些参数：

| 参数 | 描述 | 示例 |
|-----------|-------------|---------|
| `precision` | 数值类型的总位数 | `DECIMAL(10, 2)` |
| `scale` | 小数点后的位数 | `DECIMAL(10, 2)` |
| `length` | 字符串类型的最大长度 | `NVARCHAR(255)` |
| `max` | 是否使用 MAX 变体 | `NVARCHAR(MAX)` |

## SQL Server 特定类型

SQL Server 后端提供以下内置类型：

| SQL Server 类型 | Python 类型 | 说明 |
|-----------------|-------------|-------|
| `NVARCHAR` | `str` | Unicode 可变长度字符串 |
| `NCHAR` | `str` | Unicode 固定长度字符串 |
| `NVARCHAR(MAX)` | `str` | Unicode 大对象 |
| `TINYINT` | `int` | 0-255 无符号整数 |
| `BIT` | `bool` | 布尔表示 |
| `VARBINARY(MAX)` | `bytes` | 二进制大对象 |
| `XML` | `str` | 原生 XML 类型 |
| `UNIQUEIDENTIFIER` | `uuid.UUID` | GUID 类型 |
| `DATETIMEOFFSET` | `datetime` | 时区感知的日期时间 |

## 另请参阅

- [SQL Server 字段类型](../backend_specific_features/field_types.md) — SQL Server 特定数据类型
- [类型映射](../type_adapters/mapping.md) — SQL Server 到 Python 类型转换表
- [自定义类型适配器](custom_adapters.md) — 注册自定义转换器

💡 *AI 提示词：* "如何在 SQL Server 中添加对自定义 Python 类型的支持？"
