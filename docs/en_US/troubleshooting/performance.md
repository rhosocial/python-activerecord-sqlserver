# Performance Issues

## Overview

This section covers SQL Server performance issues and optimization methods.

## Slow Query Analysis

### Using SQL Server Profiler / Extended Events

SQL Server uses Extended Events (not MySQL's slow query log) for query monitoring:

```sql
-- Create an extended events session to capture slow queries
CREATE EVENT SESSION slow_queries ON SERVER
ADD EVENT sqlserver.sql_statement_completed
WHERE duration > 1000000  -- 1 second in microseconds
ADD TARGET package0.ring_buffer;
```

### Using EXPLAIN to Analyze Queries

The backend provides an `ExplainExpression` class for generating execution plan statements. **Do not execute raw EXPLAIN SQL** — use the expression system instead:

```python
from rhosocial.activerecord.backend.expression.statements.explain import (
    ExplainExpression,
    ExplainOptions,
    ExplainFormat,
)

# Build a query expression
query = User.query().where(User.c.name == "Tom").select(User.c.id, User.c.name)

# Basic EXPLAIN
explain = ExplainExpression(dialect, statement=query)
sql, params = explain.to_sql()
# sql: SET SHOWPLAN_ALL ON ...

# EXPLAIN with JSON format (execution plan as JSON)
explain_json = ExplainExpression(
    dialect,
    statement=query,
    options=ExplainOptions(format=ExplainFormat.JSON),
)
```

## Common Performance Issues

### 1. Missing Index

SQL Server creates **clustered** (default on primary key) and **non-clustered** indexes:

```sql
-- Add a non-clustered index
CREATE NONCLUSTERED INDEX idx_name ON [users] ([name]);
```

Use the backend's indexing support — see [Indexing](../backend_specific_features/indexing.md).

### 2. SELECT *

```python
# Avoid SELECT *, only query required columns
users = User.query().select(User.c.id, User.c.name).all()
```

### 3. N+1 Query Problem

Use `with_()` to eagerly load related data and avoid N+1 queries:

```python
# Eagerly load related posts
users = User.query().with_('posts').all()

# Load nested relations
users = User.query().with_('posts.comments').all()

# Load with query modifier
users = User.query().with_(('posts', lambda q: q.top(5))).all()
```

### 4. NVARCHAR vs VARCHAR

Using the wrong string type causes implicit conversions and lost index usage:

| Concern | Recommendation |
|---------|----------------|
| Unicode text | Use `NVARCHAR` (the dialect defaults to NVARCHAR) |
| Non-Unicode, ASCII-only | `VARCHAR` is fine and more compact |
| Implicit conversion | Avoid comparing NVARCHAR and VARCHAR columns — forces scans |

### 5. Parameter Sniffing

SQL Server caches query plans based on the first parameter values. For widely-varying parameters, use `OPTION (RECOMPILE)` or query hints.

## Connection Timeouts

```python
config = SQLServerConnectionConfig(
    timeout=30,
    query_timeout=60,
)
```

## See Also

- [Indexing](../backend_specific_features/indexing.md) — clustered/non-clustered indexes
- [EXPLAIN](../backend_specific_features/explain.md) — execution plan analysis

💡 *AI Prompt:* "How to optimize SQL Server query performance?"
