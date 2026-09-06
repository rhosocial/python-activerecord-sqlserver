# 自定义类型适配器

## 概述

类型适配器用于在 Python 值和 SQL Server 数据库值之间进行转换。SQL Server 后端提供了一个适配器注册表来注册自定义适配器。

## 适配器注册表

适配器注册表管理所有类型转换：

```python
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend

backend = SQLServerBackend(...)
registry = backend.adapter_registry
```

## 注册自定义适配器

### 使用 @handles 装饰器

```python
from rhosocial.activerecord.backend.impl.sqlserver.types import SQLServerDataType

@SQLServerDataType.handles(MyClass)
class MyClassAdapter:
    @staticmethod
    def to_sql(value, dialect):
        """将 Python MyClass 转换为 SQL Server 值。"""
        return json.dumps(value.__dict__)

    @staticmethod
    def from_sql(value, dialect):
        """将 SQL Server 值转换回 Python MyClass。"""
        return MyClass(**json.loads(value))
```

### 手动注册

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

## TypeAdapter 协议

SQL Server 适配器实现 `TypeAdapter` 协议，包含两个方向：

```python
class TypeAdapter(ABC):
    @property
    @abstractmethod
    def supported_types(self) -> Dict[Type, List[str]]:
        """Python 类型到 SQL Server 类型的映射。"""
        ...

    @abstractmethod
    def to_database(self, value, target_type=None, options=None):
        """将 Python 值转换为数据库值。"""
        ...

    @abstractmethod
    def from_database(self, value, target_type=None, options=None):
        """将数据库值转换为 Python 值。"""
        ...
```

## 内置 SQL Server 适配器

后端自动注册以下适配器：

| 适配器 | SQL Server 类型 |
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

## 类型转换流程

```
Python 值
    │
    ▼
to_database(value, ...)
    │
    ▼
SQL Server 数据库值
    │
    ▼
from_database(value, ...)
    │
    ▼
Python 值
```

## 另请参阅

- [类型映射](../type_adapters/mapping.md) — SQL Server 到 Python 类型转换表
- [自定义类型适配器](../type_adapters/custom.md) — 扩展类型支持
- [自定义数据类型](custom_types.md) — 定义新的 DataType 子类

💡 *AI 提示词：* "如何为像 HIERARCHYID 这样的 SQL Server 特定类型注册自定义类型适配器？"
