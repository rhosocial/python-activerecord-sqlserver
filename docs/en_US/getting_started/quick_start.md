# Quick Start

This page shows a complete, SQL Server-backed declarative model. It focuses on
the wiring that is specific to this backend; the meaning of `ActiveRecord`,
field mixins and the query API belongs to the
[core documentation](https://github.com/rhosocial/python-activerecord/tree/main/docs/en_US).

```python
from typing import Annotated, ClassVar

from rhosocial.activerecord.base import FieldProxy, UseSqlType
from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig
from rhosocial.activerecord.backend.expression.types import VarCharType
from rhosocial.activerecord.field import DefaultTimestampMixin, IntegerPKMixin
from rhosocial.activerecord.model import ActiveRecord


class User(
    IntegerPKMixin,         # auto-increment integer primary key `id`
    DefaultTimestampMixin,  # injects `created_at` / `updated_at`
    ActiveRecord,           # persistence, query builder, relations
):
    name: Annotated[str, UseSqlType(VarCharType(length=100))]
    email: Annotated[str, UseSqlType(VarCharType(length=255))]
    age: int = 0

    c: ClassVar[FieldProxy] = FieldProxy()  # enables User.c.<field> expressions

    @classmethod
    def table_name(cls) -> str:
        return "users"


# Bind the model to SQL Server and create the table from the declaration
User.configure(
    SQLServerConnectionConfig(
        host="localhost",
        port=1433,
        database="myapp",
        username="sa",
        password="YourStrong!Passw0rd",
        driver="ODBC Driver 17 for SQL Server",
    ),
    SQLServerBackend,
)
User.create_table()

# Create
alice = User(name="Alice", email="alice@example.com", age=30)
alice.save()
print(alice.id)  # database-assigned integer primary key

# Query with type-safe expressions
adults = User.query().where(User.c.age >= 18).all()
print([user.name for user in adults])

# Preview the generated T-SQL without executing it
sql, params = User.query().where(User.c.age >= 18).to_sql()
print(sql, params)
# SELECT ... FROM [users] WHERE [users].[age] >= ?   (18,)
```

> 💡 *AI prompt: "Why does `configure()` take both a config and a backend class? What does `create_table()` generate for an `IntegerPKMixin` key on SQL Server?"*

## What is SQL Server-specific here

- **`IntegerPKMixin` → `INT IDENTITY`.** A server-assigned integer key is
  rendered as SQL Server `IDENTITY`, and DML that returns it uses the `OUTPUT`
  clause. See [Creating tables](../ddl/create_table.md) and
  [OUTPUT and MERGE](../querying/output_and_merge.md).
- **Unicode text.** For `NVARCHAR` rather than the collation-dependent
  `VARCHAR`, pin the field to a `SQLServerNVarCharType`. See
  [SQL Server field types](../modeling/field_types.md).
- **Bracket quoting.** Identifiers render as `[users]` / `[age]`, and the
  parameter placeholder is `?` (filled by `pyodbc`).
- **Version gates.** Advanced features appear only when the connected server
  supports them; see [Capability gates](../capabilities/README.md).

## Async parity

Use `AsyncActiveRecord` with `AsyncSQLServerBackend`. The method names are the
same; add `await`:

```python
from rhosocial.activerecord.model import AsyncActiveRecord
from rhosocial.activerecord.backend.impl.sqlserver.backend.async_backend import AsyncSQLServerBackend

class AsyncUser(IntegerPKMixin, AsyncActiveRecord):
    c: ClassVar[FieldProxy] = FieldProxy()
    name: str

    @classmethod
    def table_name(cls) -> str:
        return "users"

AsyncUser.configure(config, AsyncSQLServerBackend)
user = AsyncUser(name="Alice")
await user.save()
```

## Runnable scripts

Three complete scripts live under [`docs/examples/`](../../examples/README.md):
connection/configuration, declarative-model CRUD, and
introspection/partitioning. They are syntax-checked but require a reachable SQL
Server to run.
