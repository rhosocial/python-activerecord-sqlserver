# Custom Type Adapters

## Overview

While the SQL Server backend provides out-of-the-box type mapping, you may need custom type conversion logic in some scenarios.

## Pydantic Custom Types

It is recommended to use Pydantic's custom validators for custom type conversion:

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
    address: str  # Stored as JSON string in NVARCHAR(MAX)

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

## Using Custom Types

```python
# Create user
user = User(
    name='Tom',
    address=Address(street='123 Main St', city='Beijing', country='China')
)
user.save()

# Read user
user = User.query().one()
address = user.get_address()
print(address.city)  # Beijing
```

## Custom Adapter Registration

For types that need backend-level conversion, register a custom adapter:

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

## See Also

- [Custom Type Adapters](../customization/custom_adapters.md) — registering custom converters
- [Type Mapping](mapping.md) — SQL Server to Python type conversion table

💡 *AI Prompt:* "What is the difference between Pydantic's field_validator and model_validator?"
