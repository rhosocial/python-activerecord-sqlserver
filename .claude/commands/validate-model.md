---
description: Validate ActiveRecord model configuration
agent: build
---

Validate an existing ActiveRecord model for common configuration errors.

## Validation Checklist

Check the following aspects of the model:

### 1. Required Configuration
- [ ] `__table_name__` is defined
- [ ] `__primary_key__` is defined (or defaults to 'id')
- [ ] Backend is configured before use

### 2. FieldProxy Configuration
- [ ] `c: ClassVar[FieldProxy] = FieldProxy()` is present
- [ ] Used correctly in query building (not string references)

### 3. Field Definitions
- [ ] All fields have type annotations
- [ ] Field types are supported by the backend
- [ ] Optional fields use `Optional[T]`
- [ ] Default values match field types

### 4. Sync/Async Consistency
- [ ] Model inherits from correct base class (`ActiveRecord` vs `AsyncActiveRecord`)
- [ ] Query methods use appropriate syntax

### 5. Relationship Configuration
- [ ] Relationships use string forward references (`'ModelName'`)
- [ ] Foreign keys match relationship definitions
- [ ] Inverse relationships are defined

### 6. Import Statements
- [ ] Required imports are present
- [ ] No circular import issues

## Common Issues

### Missing FieldProxy
```python
# WRONG
class User(ActiveRecord):
    __table_name__ = 'users'
    name: str
    
    def find_by_name(self, name):
        return self.query().where("name = ?", name)  # Bad!

# CORRECT
class User(ActiveRecord):
    __table_name__ = 'users'
    name: str
    c: ClassVar[FieldProxy] = FieldProxy()
    
    def find_by_name(self, name):
        return self.query().where(self.c.name == name)  # Good!
```

### No Backend Configured
```python
# WRONG
user = User(name="John")  # Will raise "No backend configured"
user.save()

# CORRECT
from rhosocial.activerecord.backend.impl.sqlite import SQLiteBackend
User.configure(SQLiteBackend("sqlite:///app.db"))
user = User(name="John")
user.save()
```

### Incorrect Type Annotations
```python
# WRONG
class User(ActiveRecord):
    name = str  # Missing type annotation
    age: int = "0"  # Wrong default type

# CORRECT
class User(ActiveRecord):
    name: str
    age: int = 0
    email: Optional[str] = None
```

### String References in Queries
```python
# WRONG
User.query().where("age >= 18")  # Not type-safe

# CORRECT
User.query().where(User.c.age >= 18)  # Type-safe
```

## Validation Output

After validation, provide:

1. **Checklist results** - Pass/Fail for each validation point
2. **Issues found** - Specific problems with line numbers
3. **Suggested fixes** - Code examples showing corrections
4. **Best practices** - Recommendations for improvement

## Usage

Run validation on a model file:
```bash
# Check specific model
/validate:model src/models/user.py

# Check all models in directory
/validate:model src/models/
```
