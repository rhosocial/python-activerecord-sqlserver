---
description: Generate preset ActiveQuery methods for a model
agent: build
---

Generate preset query methods for an existing ActiveRecord model.

## Query Configuration

Ask the user for the following information:

1. **Target Model** (e.g., `User`, `Order`)
2. **Query Name** (e.g., `active_users`, `recent_orders`)
3. **Query Type**:
   - `finder` - Single record lookup
   - `list` - Multiple records
   - `count` - Count records
   - `exists` - Check existence
4. **Conditions** (e.g., `status == 'active'`, `created_at >= 7_days_ago`)
5. **Ordering** (optional, e.g., `created_at DESC`, `name ASC`)
6. **Limit** (optional, e.g., `10`, `100`)

## Generated Code Examples

### Finder Query
```python
@classmethod
def find_active_by_email(cls, email: str) -> Optional['User']:
    """Find active user by email address."""
    return cls.query().where(
        (cls.c.email == email) & (cls.c.status == 'active')
    ).one()
```

### List Query
```python
@classmethod
def get_recent_orders(cls, days: int = 7) -> List['Order']:
    """Get orders from the last N days."""
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=days)
    return cls.query().where(
        cls.c.created_at >= cutoff
    ).order_by((cls.c.created_at, "DESC")).all()
```

### Count Query
```python
@classmethod
def count_active_users(cls) -> int:
    """Count active users."""
    result = cls.query().where(
        cls.c.status == 'active'
    ).count()
    return result
```

### Exists Query
```python
@classmethod
def has_admin_users(cls) -> bool:
    """Check if any admin users exist."""
    return cls.query().where(
        cls.c.role == 'admin'
    ).exists()
```

## Best Practices

1. **Use classmethod** for queries that don't require instance
2. **Return typed results** using `Optional['Model']` or `List['Model']`
3. **Use FieldProxy** (cls.c.column_name) for type-safe column references
4. **Wrap conditions in parentheses** when using & or |
5. **Add docstrings** describing the query purpose
6. **Handle edge cases** (empty results, None values)

## Naming Conventions

- **find_*** - Single record lookup (returns Optional[Model])
- **get_*** - Multiple records (returns List[Model])
- **count_*** - Count operation (returns int)
- **has_*** / **exists_*** - Existence check (returns bool)
- **active_*** - Filter by status
- **recent_*** - Time-based filtering
- **by_*** - Lookup by specific field
