# Database Introspection

## Overview

SQL Server provides introspection capabilities to query database metadata.

## Basic Usage

```python
# Access introspector
introspector = backend.introspector

# List tables
tables = introspector.list_tables()

# Get table info
table_info = introspector.get_table_info("users")

# List columns
columns = introspector.list_columns("users")
```

## Introspection Methods

### Database Information

```python
# Get database info
db_info = introspector.get_database_info()
print(f"Database: {db_info.name}")
print(f"Version: {db_info.version}")
```

### Table Information

```python
# List all tables
tables = introspector.list_tables()

# Get table details
table_info = introspector.get_table_info("users")
print(f"Rows: {table_info.row_count}")
```

### Column Information

```python
# List columns
columns = introspector.list_columns("users")
for col in columns:
    print(f"{col.name}: {col.data_type}")
```

### Index Information

```python
# List indexes
indexes = introspector.list_indexes("users")
for idx in indexes:
    print(f"{idx.name}: {idx.columns} (clustered={idx.is_clustered})")
```

## System Views

```sql
-- Query system catalogs directly
SELECT * FROM sys.tables;
SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('users');
SELECT * FROM sys.indexes WHERE object_id = OBJECT_ID('users');
```

## See Also

- [Troubleshooting](../troubleshooting/README.md) — Debugging queries

💡 *AI Prompt:* "How to list all tables in a SQL Server database?"
