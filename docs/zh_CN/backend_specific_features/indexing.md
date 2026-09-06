# 索引类型

## 概述

SQL Server 支持多种索引类型用于查询优化。

## 索引类型

### 聚集索引

```python
from rhosocial.activerecord.backend.expression import CreateIndexExpression

# 聚集索引（每表一个）
create_idx = CreateIndexExpression(
    dialect,
    index_name="PK_users",
    table_name="users",
    columns=["id"],
    index_type="CLUSTERED",
)
```

### 非聚集索引

```python
# 非聚集索引
create_idx = CreateIndexExpression(
    dialect,
    index_name="idx_users_email",
    table_name="users",
    columns=["email"],
)
```

### 唯一索引

```python
# 唯一索引
create_idx = CreateIndexExpression(
    dialect,
    index_name="idx_users_email_unique",
    table_name="users",
    columns=["email"],
    unique=True,
)
```

### 包含列索引

```python
# 包含列索引
create_idx = CreateIndexExpression(
    dialect,
    index_name="idx_users_email_include",
    table_name="users",
    columns=["email"],
    include=["name", "created_at"],
)
```

### 筛选索引

```python
# 筛选索引
create_idx = CreateIndexExpression(
    dialect,
    index_name="idx_users_active",
    table_name="users",
    columns=["email"],
    where="active = 1",
)
```

## 索引优化

```sql
-- 重建索引
ALTER INDEX ALL ON users REBUILD;

-- 重组索引
ALTER INDEX idx_users_email ON users REORGANIZE;
```

## 另请参阅

- [EXPLAIN](./explain.md) — 查询执行计划

💡 *AI 提示：* "SQL Server 中何时应该使用聚集索引而不是非聚集索引？"
