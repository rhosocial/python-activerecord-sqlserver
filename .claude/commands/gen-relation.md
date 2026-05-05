---
description: Generate model relationships (belongs_to, has_one, has_many)
agent: build
---

Generate relationship definitions between ActiveRecord models.

## Relationship Configuration

Ask the user for the following information:

1. **Source Model** (e.g., `Order` - the model that will have the relationship)
2. **Relationship Type**:
   - `belongs_to` - Child references parent (contains foreign key)
   - `has_one` - Parent has one child
   - `has_many` - Parent has many children
   - `has_many_through` - Many-to-many via join table
3. **Target Model** (e.g., `User` - the related model)
4. **Foreign Key** (e.g., `user_id`, defaults to `{target}_id`)
5. **Inverse Of** (optional, e.g., `orders` - the reverse relationship name)
6. **Sync or Async** (affects both models)

## Generated Code Examples

### belongs_to (Order belongs to User)

```python
from typing import ClassVar
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.relation import BelongsTo

class Order(ActiveRecord):
    __table_name__ = 'orders'
    
    user_id: int
    total: float
    
    # Relationship
    user: ClassVar[BelongsTo['User']] = BelongsTo(
        foreign_key='user_id',
        inverse_of='orders'
    )
    
    c: ClassVar[FieldProxy] = FieldProxy()
```

### has_many (User has many Orders)

```python
from typing import ClassVar
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.relation import HasMany

class User(ActiveRecord):
    __table_name__ = 'users'
    
    name: str
    email: str
    
    # Relationship
    orders: ClassVar[HasMany['Order']] = HasMany(
        foreign_key='user_id',
        inverse_of='user'
    )
    
    c: ClassVar[FieldProxy] = FieldProxy()
```

### has_one (User has one Profile)

```python
from typing import ClassVar
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.relation import HasOne

class User(ActiveRecord):
    __table_name__ = 'users'
    
    name: str
    
    # Relationship
    profile: ClassVar[HasOne['Profile']] = HasOne(
        foreign_key='user_id',
        inverse_of='user'
    )
    
    c: ClassVar[FieldProxy] = FieldProxy()
```

### has_many_through (User has many Roles through UserRole)

```python
from typing import ClassVar
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.relation import HasManyThrough

class User(ActiveRecord):
    __table_name__ = 'users'
    
    name: str
    
    # Many-to-many relationship
    roles: ClassVar[HasManyThrough['Role']] = HasManyThrough(
        through='UserRole',  # Join model
        foreign_key='user_id',
        target_foreign_key='role_id',
        inverse_of='users'
    )
    
    c: ClassVar[FieldProxy] = FieldProxy()
```

## Relationship Matrix

| Type | Foreign Key Location | Example |
|------|---------------------|---------|
| belongs_to | Source model | Order has `user_id` |
| has_one | Target model | Profile has `user_id` |
| has_many | Target model | Order has `user_id` |
| has_many_through | Join table | UserRole has both IDs |

## Important Notes

1. **Use String References** for forward declarations to avoid circular imports:
   ```python
   orders: ClassVar[HasMany['Order']]  # Note the quotes
   ```

2. **Define both sides** of the relationship for bidirectional access:
   ```python
   # In Order:
   user: ClassVar[BelongsTo['User']] = BelongsTo(inverse_of='orders')
   
   # In User:
   orders: ClassVar[HasMany['Order']] = HasMany(inverse_of='user')
   ```

3. **Foreign key naming** follows convention `{related_model}_id`

4. **Async models** use `AsyncBelongsTo`, `AsyncHasOne`, `AsyncHasMany`

## Generated Migration

Include foreign key constraints in SQL:
```sql
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    total DECIMAL(10,2),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_orders_user_id ON orders(user_id);
```
