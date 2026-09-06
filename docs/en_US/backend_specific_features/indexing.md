# Index Types

## Overview

SQL Server supports various index types for query optimization.

## Index Types

### Clustered Index

```python
from rhosocial.activerecord.backend.expression import CreateIndexExpression

# Clustered index (one per table)
create_idx = CreateIndexExpression(
    dialect,
    index_name="PK_users",
    table_name="users",
    columns=["id"],
    index_type="CLUSTERED",
)
```

### Non-Clustered Index

```python
# Non-clustered index
create_idx = CreateIndexExpression(
    dialect,
    index_name="idx_users_email",
    table_name="users",
    columns=["email"],
)
```

### Unique Index

```python
# Unique index
create_idx = CreateIndexExpression(
    dialect,
    index_name="idx_users_email_unique",
    table_name="users",
    columns=["email"],
    unique=True,
)
```

### Included Columns

```python
# Index with included columns
create_idx = CreateIndexExpression(
    dialect,
    index_name="idx_users_email_include",
    table_name="users",
    columns=["email"],
    include=["name", "created_at"],
)
```

### Filtered Index

```python
# Filtered index
create_idx = CreateIndexExpression(
    dialect,
    index_name="idx_users_active",
    table_name="users",
    columns=["email"],
    where="active = 1",
)
```

## Index Optimization

```sql
-- Rebuild index
ALTER INDEX ALL ON users REBUILD;

-- Reorganize index
ALTER INDEX idx_users_email ON users REORGANIZE;
```

## See Also

- [EXPLAIN](./explain.md) — Query execution plans

💡 *AI Prompt:* "When should I use clustered vs non-clustered indexes in SQL Server?"
