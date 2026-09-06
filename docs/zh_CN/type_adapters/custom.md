# 自定义类型适配器

## 概述

虽然 SQL Server 后端提供了开箱即用的类型映射，但在某些场景下你可能需要自定义类型转换逻辑。

## Pydantic 自定义类型

建议使用 Pydantic 的自定义验证器进行自定义类型转换：

```python
from typing import Any, ClassVar
import json
from pydantic import field_validator
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.base import FieldProxy
from rhosocial.activerecord.field import UUIDMixin, DefaultTimestampMixin


class Address:
    def __init__(self, street: str, city: str, country: str):
        self.street = street
        self.city = city
        self.country = country

    def __str__(self) -> str:
        return f"{self.street}, {self.city}, {self.country}"

    @classmethod
    def from_dict(cls, data: dict) -> 'Address':
        return cls(
            street=data.get('street', ''),
            city=data.get('city', ''),
            country=data.get('country', '')
        )


class User(UUIDMixin, DefaultTimestampMixin, ActiveRecord):
    name: str
    address: str  # 存储为 NVARCHAR(MAX) 中的 JSON 字符串

    c: ClassVar[FieldProxy] = FieldProxy()

    @field_validator('address', mode='before')
    @classmethod
    def parse_address(cls, v: Any) -> str:
        if isinstance(v, dict):
            return json.dumps(v)
        if isinstance(v, Address):
            return json.dumps({
                'street': v.street,
                'city': v.city,
                'country': v.country
            })
        return v

    def get_address(self) -> Address:
        if isinstance(self.address, str):
            return Address.from_dict(json.loads(self.address))
        return Address.from_dict(self.address)

    @classmethod
    def table_name(cls) -> str:
        return 'users'
```

## 使用自定义类型

```python
# 创建用户
user = User(
    name='Tom',
    address=Address(street='123 Main St', city='Beijing', country='China')
)
user.save()

# 读取用户
user = User.query().one()
address = user.get_address()
print(address.city)  # Beijing
```

## 自定义适配器注册

对于需要后端级别转换的类型，请注册自定义适配器：

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

## 另请参阅

- [自定义类型适配器](../customization/custom_adapters.md) — 注册自定义转换器
- [类型映射](mapping.md) — SQL Server 到 Python 类型转换表

💡 *AI 提示词：* "Pydantic 的 field_validator 和 model_validator 有什么区别？"
