# Creating Tables

There are two ways to create schema on this backend:

1. **From a declarative model** — `Model.create_table()` renders DDL from the
   model's field declarations (see [Quick start](../getting_started/quick_start.md)).
2. **From expression nodes** — build `CreateTableStatement` directly when you
   need precise control over types, identity and constraints. This is the style
   used by the backend's own DDL examples.

Both end in the dialect rendering T-SQL; call `.to_sql()` first to preview it.

## Expression-based DDL

```python
from rhosocial.activerecord.backend.expression import (
    ColumnConstraint,
    ColumnDefinition,
    CreateTableStatement,
    DropTableStatement,
)
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import auto_increment_parts
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnNotNullConstraint,
    ColumnPrimaryKeyConstraint,
    ColumnUniqueConstraint,
    IndexDefinition,
)
from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

config = SQLServerConnectionConfig(
    host="localhost", database="myapp", username="sa", password="secret",
    driver="ODBC Driver 18 for SQL Server",
)
backend = SQLServerBackend(connection_config=config)
backend.connect()
dialect = backend.dialect

id_type, id_attrs = auto_increment_parts(dialect, "INT")

columns = [
    ColumnDefinition(
        name="id",
        data_type=id_type,                       # INT
        attributes=id_attrs,                     # IDENTITY(1,1)
        constraints=[ColumnConstraint(dialect, branch=ColumnPrimaryKeyConstraint(dialect))],
    ),
    ColumnDefinition(
        name="name",
        data_type="NVARCHAR(100)",
        constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))],
    ),
    ColumnDefinition(
        name="email",
        data_type="NVARCHAR(200)",
        constraints=[ColumnConstraint(dialect, branch=ColumnUniqueConstraint(dialect))],
    ),
    ColumnDefinition(name="created_at", data_type="DATETIME2"),
]

indexes = [IndexDefinition(name="idx_users_email", columns=["email"])]

create = CreateTableStatement(
    dialect=dialect,
    table=Table(dialect, "users"),
    columns=columns,
    indexes=indexes,
    if_not_exists=True,
)
sql, params = create.to_sql()
backend.execute(sql, params, options=ExecutionOptions(stmt_type=StatementType.DDL))
```

Rendered shape:

```sql
CREATE TABLE [users] (
    [id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [name] NVARCHAR(100) NOT NULL,
    [email] NVARCHAR(200) UNIQUE,
    [created_at] DATETIME2
);
CREATE INDEX [idx_users_email] ON [users] ([email]);
```

## IDENTITY and generated keys

`auto_increment_parts(dialect, "INT")` returns the pair `(type, attributes)`:
the base integer type and the `IDENTITY(1,1)` column attribute. This split
mirrors how SQL Server models identity — it is a column property, not a type.
A model using `IntegerPKMixin` goes through the same path automatically.

See [SQL Server field types](../modeling/field_types.md) for server-maintained
columns (`ROWVERSION`) that must instead be excluded from writes.

## Constraints and indexes

- Primary key, `NOT NULL` and `UNIQUE` column constraints render as inline or
  table constraints.
- Indexes are declared with `IndexDefinition`. SQL Server-specific index kinds
  are also available as expressions (filtered, fulltext, columnstore, XML,
  spatial); see [Advanced objects](advanced_objects.md).
- Which DDL clauses are legal is expressed by `supports_*` switches — for
  example `supports_drop_table_cascade()` is `False` because SQL Server has no
  `DROP TABLE ... CASCADE`, and `supports_table_partitioning()` is `True`.

## Dropping / altering

```python
drop = DropTableStatement(dialect=dialect, table=Table(dialect, "users"), if_exists=True)
sql, params = drop.to_sql()
backend.execute(sql, params, options=ExecutionOptions(stmt_type=StatementType.DDL))
```

`ALTER TABLE` support is implemented by a modifier with explicit feature
answers: adding and dropping columns are supported; `ADD COLUMN IF NOT EXISTS`,
`DROP COLUMN IF EXISTS` and `DROP CONSTRAINT IF EXISTS` are **not** (SQL Server
has no such clause) and answer `False`.

## Next steps

- [Partitioning](partition.md) — functions, schemes, suggestions and introspection
- [Advanced objects](advanced_objects.md) — temporal tables, graph, columnstore, sequences
- [OUTPUT and MERGE](../querying/output_and_merge.md) — returning rows from DML
