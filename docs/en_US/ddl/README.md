# DDL Operations

## Overview

This section covers DDL (Data Definition Language) operations for the SQL Server backend. DDL defines your database schema — tables, indexes, views, and other objects.

**Important**: All DDL in rhosocial-activerecord is **expression-based**. You define your schema in Python, the framework generates the SQL, and you execute it via the backend. The examples below use `ActiveRecord` for brevity, but `AsyncActiveRecord` works identically — the DDL generation is pure computation with no I/O involved.

The DDL chapter is divided into two parts:

1. **Backend DDL Capabilities** — The complete set of DDL operations the SQL Server backend supports, expressed through backend-specific expression classes.
2. **ActiveRecord DDL Derivation** — What the framework can automatically generate from model class declarations.

---

# Part 1: Backend DDL Capabilities

The SQL Server backend supports the following DDL operations:

## Supported Operations

| Operation | SQL Server Support | Expression Class |
|-----------|-------------------|-----------------|
| CREATE TABLE | ✅ | `CreateTableExpression` |
| ALTER TABLE | ✅ | `AlterTableExpression` |
| DROP TABLE | ✅ | `DropTableExpression` |
| CREATE INDEX | ✅ | `CreateIndexExpression` |
| DROP INDEX | ✅ | `DropIndexExpression` |
| CREATE VIEW | ✅ | `CreateViewExpression` |
| DROP VIEW | ✅ | `DropViewExpression` |
| TRUNCATE | ✅ | `TruncateExpression` |
| CREATE SCHEMA | ✅ | `CreateSchemaExpression` |
| CREATE SEQUENCE | ✅ | `CreateSequenceExpression` |
| CREATE PROCEDURE | ✅ | `SQLServerCreateProcedureExpression` |
| CREATE FUNCTION | ✅ | `SQLServerCreateFunctionExpression` |
| CREATE TRIGGER | ✅ | `SQLServerCreateTriggerExpression` |
| CREATE FULLTEXT CATALOG | ✅ | `SQLServerCreateFullTextCatalogExpression` |
| CREATE FULLTEXT INDEX | ✅ | `SQLServerCreateFullTextIndexExpression` |

## CREATE TABLE

### SQL Server-Specific Table Options

SQL Server supports several table options not available in other backends:

```python
from rhosocial.activerecord.backend.expression.statements.ddl_table import CreateTableExpression

# CREATE TABLE with SQL Server options
# - WITH (MEMORY_OPTIMIZED=ON) for in-memory OLTP
# - ON partition_scheme for partitioned tables
# - TEXTIMAGE_ON for large object storage
```

### IF NOT EXISTS

| Backend | IF NOT EXISTS |
|---------|--------------|
| SQLite | Yes |
| MySQL | Yes |
| PostgreSQL | Yes |
| SQL Server | Yes |

### Temporary Tables

| Backend | Temporary Table Support |
|---------|----------------------|
| SQLite | Yes (but limited) |
| MySQL | Yes |
| PostgreSQL | Yes |
| SQL Server | Yes (#local or ##global) |

## ALTER TABLE

### Adding Columns

| Backend | IF NOT EXISTS on ADD COLUMN |
|---------|--------------------------|
| SQLite | No (before 3.35.0) |
| MySQL | No |
| PostgreSQL | Yes |
| SQL Server | No (use IF EXISTS with DROP and re-add) |

### Dropping Columns

| Backend | IF EXISTS on DROP COLUMN | Minimum Version |
|---------|------------------------|----------------|
| SQLite | Yes | 3.35.0+ |
| MySQL | No | — |
| PostgreSQL | Yes | — |
| SQL Server | Yes | — |

### Renaming Columns

| Backend | RENAME COLUMN |
|---------|--------------|
| SQLite | Yes (3.25.0+) |
| MySQL | No (use `CHANGE COLUMN`) |
| PostgreSQL | Yes |
| SQL Server | Yes (`sp_rename`) |

### Changing Column Types

| Backend | Syntax |
|---------|--------|
| MySQL | `MODIFY COLUMN` or `CHANGE COLUMN` |
| PostgreSQL | `ALTER COLUMN ... TYPE` |
| SQL Server | `ALTER COLUMN ... TYPE` |
| SQLite | Limited |

## DROP TABLE

| Backend | IF EXISTS | CASCADE/RESTRICT |
|---------|----------|-----------------|
| SQLite | Yes | No |
| MySQL | Yes | Parsed but ignored |
| PostgreSQL | Yes | Yes (default: `RESTRICT`) |
| SQL Server | Yes | No (use FK constraints) |

## CREATE INDEX

### Index Types

| Backend | Supported Index Types |
|---------|---------------------|
| SQLite | B-tree only |
| MySQL | BTREE, HASH |
| PostgreSQL | BTREE, HASH, GIN, GiST, SP-GiST, BRIN |
| SQL Server | CLUSTERED, NONCLUSTERED, COLUMNSTORE, FULLTEXT, SPATIAL |

### Partial Indexes

| Backend | Partial Index Support |
|---------|---------------------|
| SQLite | Yes (since 3.8.0) |
| MySQL | No |
| PostgreSQL | Yes |
| SQL Server | No (use filtered indexes with WHERE) |

### Functional Indexes

| Backend | Functional Index Support |
|---------|------------------------|
| SQLite | Yes |
| MySQL | No |
| PostgreSQL | Yes |
| SQL Server | Yes (computed columns) |

### Concurrent Index Creation

| Backend | CONCURRENTLY Support |
|---------|---------------------|
| SQLite | No |
| MySQL | No |
| PostgreSQL | Yes |
| SQL Server | Yes (ONLINE option) |

### Full-Text Indexes

| Backend | Full-Text Index Syntax |
|---------|----------------------|
| SQLite | FTS5 virtual table |
| MySQL | `FULLTEXT INDEX` (InnoDB, MySQL 5.6+) |
| PostgreSQL | GIN index on `tsvector` column |
| SQL Server | `CREATE FULLTEXT INDEX` (separate catalog) |

## CREATE VIEW

| Backend | OR REPLACE | TEMPORARY | Materialized | WITH CHECK OPTION |
|---------|-----------|----------|-------------|------------------|
| SQLite | No | No | No | No |
| MySQL | Yes | Yes | No | Yes |
| PostgreSQL | Yes | Yes | Yes | Yes |
| SQL Server | Yes | No | No | Yes |

## TRUNCATE

| Backend | Supported | RESTART IDENTITY | CASCADE |
|---------|----------|-----------------|---------|
| SQLite | No (use `DELETE FROM`) | N/A | N/A |
| MySQL | Yes | No | No |
| PostgreSQL | Yes | Yes | Yes |
| SQL Server | Yes | No | No |

## Schema Support

| Backend | Schemas | CREATE/DROP SCHEMA |
|---------|---------|-------------------|
| SQLite | No | No |
| MySQL | No (schema = database) | `CREATE DATABASE` (synonym) |
| PostgreSQL | Yes (true namespaces) | Yes |
| SQL Server | Yes (true namespaces) | Yes |

## Sequences

| Backend | Sequences | AUTO_INCREMENT Mechanism |
|---------|----------|------------------------|
| SQLite | No | `AUTOINCREMENT` on `INTEGER PRIMARY KEY` |
| MySQL | No | `AUTO_INCREMENT` column attribute |
| PostgreSQL | Yes (`SERIAL`, `IDENTITY`) | `SERIAL` or `GENERATED ... AS IDENTITY` |
| SQL Server | Yes (`CREATE SEQUENCE`) | `IDENTITY(1,1)` or `SEQUENCE` + `NEXT VALUE FOR` |

## Partitioning

| Backend | Partitioning | Strategies |
|---------|-------------|------------|
| SQLite | **No** | — |
| MySQL | Yes (5.1+) | RANGE, LIST, HASH, KEY, COLUMNS, subpartitioning |
| PostgreSQL | Yes (PG 10+) | RANGE, LIST, HASH |
| SQL Server | Yes (2008+) | RANGE, LIST, HASH (via partition schemes/functions) |

> **Note**: Partition DDL is not integrated into the model declaration layer. You must use backend-specific expression classes directly. See [Partitioning](../backend_specific_features/partition.md) for details.

## SQL Server-Specific Expression Classes

| Expression | Purpose |
|-----------|---------|
| `SQLServerCreateProcedureExpression` | CREATE PROCEDURE with T-SQL syntax |
| `SQLServerCreateFunctionExpression` | CREATE FUNCTION with T-SQL syntax |
| `SQLServerCreateTriggerExpression` | CREATE TRIGGER with INSERTED/DELETED tables |
| `SQLServerCreateFullTextCatalogExpression` | CREATE FULLTEXT CATALOG |
| `SQLServerCreateFullTextIndexExpression` | CREATE FULLTEXT INDEX |
| `SQLServerColumnstoreIndexExpression` | Columnstore index DDL |
| `SQLServerDropRoutineExpression` | DROP PROCEDURE/FUNCTION |
| `SQLServerDropTriggerExpression` | DROP TRIGGER |

## Checking Feature Support

Use the protocol system to check if a feature is available:

```python
from rhosocial.activerecord.backend.dialect.protocols import (
    TableSupport,
    IndexSupport,
    SchemaSupport,
    PartitionSupport,
)

dialect = backend.dialect

if isinstance(dialect, PartitionSupport):
    if dialect.supports_table_partitioning():
        # Use partition DDL expression classes
        ...

if isinstance(dialect, IndexSupport):
    if dialect.supports_partial_index():
        # Create partial indexes (filtered indexes)
        ...
```

---

# Part 2: ActiveRecord DDL Derivation

`ModelSchemaGenerator` derives DDL from your ActiveRecord model declarations. You define fields, table names, indexes, and constraints on the model class — the framework generates the SQL.

## What Can Be Derived from Models

| Feature | Model-Integrated | How to Use |
|---------|-----------------|------------|
| Table creation | Yes | `ModelSchemaGenerator.generate_create_table()` |
| Column definitions | Yes | Declare fields on the model class |
| Indexes | Yes | `indexes()` class method |
| Constraints | Yes | `UseConstraint` annotations |
| Schema | Yes | `schema()` class method |
| Partitioning | **No** | Backend-specific expression classes only |
| Sequences | **No** | Backend-specific expression classes only |
| Triggers | **No** | Backend-specific expression classes only |
| Stored procedures | **No** | Backend-specific expression classes only |

## Creating a Table

```python
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.base import FieldProxy
from typing import ClassVar

class User(ActiveRecord):
    id: int | None = None
    username: str
    email: str
    age: int
    is_active: bool = True
    metadata: dict = {}

    c: ClassVar[FieldProxy] = FieldProxy()

    @classmethod
    def table_name(cls) -> str:
        return 'users'
```

The generated SQL for SQL Server:

```sql
CREATE TABLE IF NOT EXISTS [users] (
    [id] INT NOT NULL IDENTITY(1,1),
    [username] NVARCHAR(255) NOT NULL,
    [email] NVARCHAR(255) NOT NULL,
    [age] INT NOT NULL,
    [is_active] BIT NOT NULL DEFAULT 1,
    [metadata] NVARCHAR(MAX),
    PRIMARY KEY ([id])
)
```

Notice the differences from other backends:
- **SQL Server**: Uses `IDENTITY(1,1)` for auto-increment, `NVARCHAR` for strings, `BIT` for booleans, `NVARCHAR(MAX)` for JSON
- **MySQL**: Uses `AUTO_INCREMENT`, `VARCHAR`, `BOOLEAN`, `JSON`
- **PostgreSQL**: Uses `SERIAL`, `VARCHAR`, `BOOLEAN`, `JSONB`

## Generating DDL SQL

You can generate DDL SQL without executing it:

```python
from rhosocial.activerecord.base.ddl_generator import DDLGenerator

# Generate CREATE TABLE SQL
create_sql = DDLGenerator.generate_create_table(User)
print(create_sql)
```

## Running DDL

To execute DDL, use the backend directly:

```python
# Sync
with User.connection() as conn:
    conn.execute(create_sql)

# Async
async with User.connection() as conn:
    await conn.execute(create_sql)
```

---

## See Also

- [Field Types](../backend_specific_features/field_types.md) — DataType hierarchy and backend-specific types
- [Indexing](../backend_specific_features/indexing.md) — index types and optimization
- [Partitioning](../backend_specific_features/partition.md) — table partitioning strategies
- [Dialect Expressions](../backend_specific_features/dialect.md) — feature detection and protocol system
- [Core: DDL](https://github.com/Rhosocial/python-activerecord/tree/main/docs/en_US/modeling/ddl)

💡 *AI Prompt:* "How does DDL generation differ between SQL Server and PostgreSQL?"
