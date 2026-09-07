# DDL Feature Specs

SQL Server implements the core DDL feature-spec claiming protocol
(`dialect.build_spec`). This chapter documents which Specs the SQL Server
dialect claims, how it translates them, and the SQL Server-specific Spec it
adds.

## How claiming works

At `Model.generate_create_table(dialect)` time the generator hands each
declared Spec to `dialect.build_spec(spec)`:

- **Accepted** → the dialect builds and returns an expression-layer instance,
  which lands in the `CreateTableExpression`;
- **Not accepted** → returns `None`, and the Spec is silently ignored.

Acceptance scope is the SQL Server dialect's own decision.

## Generic Specs

All generic Specs are claimed and translated by the core default:

| Spec | SQL Server translation |
|------|------------------------|
| `CheckSpec` | `TableConstraint(CHECK)`, lazy predicates evaluated at build time |
| `UniqueSpec` | `TableConstraint(UNIQUE)` |
| `NotNullSpec` | `ColumnConstraint(NOT NULL)` |
| `PrimaryKeySpec` | column-level PK (single) / table-level composite PK |
| `DefaultSpec` | `ColumnConstraint(DEFAULT)` with a parameterized `Literal` |
| `ForeignKeySpec` | `ForeignKeyConstraint` with referential actions |
| `IndexSpec` | `IndexDefinition` (SQL Server has no partial indexes; partial conditions are ignored) |
| `JsonColumnSpec` | column type patch → `JsonType` |

## SQL Server-specific Spec

Defined in `rhosocial.activerecord.backend.impl.sqlserver.ddl_spec`; claimed
via `isinstance` and translated by `SQLServerDDLSpecMixin`. Only the SQL
Server dialect claims it.

### Range Partition Spec

```python
from rhosocial.activerecord.backend.impl.sqlserver.ddl_spec import (
    SQLServerRangePartition,
)

class Orders(ActiveRecord):
    __table_partition__ = [
        SQLServerRangePartition(
            column="created_at",
            partition_scheme="ps_orders",
            boundaries=["2026-01-01", "2027-01-01"],  # for the partition function
            right=True,  # RANGE RIGHT (default) or RANGE LEFT
        ),
    ]
```

Translated to `SQLServerPartitionByRangeClause` and rendered as
`ON [ps_orders] ([created_at])`. The companion
`CREATE PARTITION FUNCTION` / `CREATE PARTITION SCHEME` statements are
separate DDL built from `boundaries` — see [Partitioning](partition.md).
