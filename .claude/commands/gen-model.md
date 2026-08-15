---
description: Generate ActiveRecord model with fields and configuration
agent: build
---

Generate a new ActiveRecord model for rhosocial-activerecord.

## Model Configuration

Ask the user for the following information:

1. **Model Name** (PascalCase, e.g., `User`, `OrderItem`)
2. **Sync or Async** (`sync` or `async`)
3. **Table Name** (snake_case, e.g., `users`, `order_items`)
4. **Primary Key** (default: `id`)
5. **Fields** (format: `name:type`, e.g., `name:str, age:int, email:str`)
6. **Mixins** (optional: `TimestampMixin`, `SoftDeleteMixin`, `VersionMixin`)

## Generated Model Structure

```python
from typing import ClassVar, Optional
from datetime import datetime
from pydantic import Field
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.base import FieldProxy
from rhosocial.activerecord.field import TimestampMixin  # if selected

class User(ActiveRecord):  # or AsyncActiveRecord
    __table_name__ = 'users'
    __primary_key__ = 'id'  # if not default
    
    # Fields
    name: str = Field(..., max_length=100)
    email: str
    age: int = 0
    
    # Required: Enable type-safe query building
    c: ClassVar[FieldProxy] = FieldProxy()
```

## Generated SQL Migration

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    age INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## After Generation

1. Save the model to `src/models/user.py`
2. Show the SQL migration to create the table
3. Remind the user to configure the backend:
   ```python
   from rhosocial.activerecord.backend.impl.sqlite import SQLiteBackend
   User.configure(SQLiteBackend("sqlite:///app.db"))
   ```

## Field Type Mappings

- `str` → VARCHAR (with optional max_length)
- `int` → INTEGER
- `float` → FLOAT/DOUBLE
- `bool` → BOOLEAN
- `datetime` → TIMESTAMP
- `date` → DATE
- `Optional[T]` → Nullable column
