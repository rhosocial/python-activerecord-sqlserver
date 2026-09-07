# SQL Server Specific Features

This section covers SQL Server-specific features that differ from other backends. rhosocial-activerecord uses a two-layer architecture for many features: a **core layer** provides common interfaces and default implementations, while each backend's **dialect layer** overrides formatting and adds backend-specific capabilities.

When you encounter a feature in this section, check whether it is a backend-specific extension or a core feature with backend-specific formatting — the documentation will indicate which layer applies.

## Contents

- [Dialect Expressions](dialect.md): Two-layer expression system — common core and T-SQL-specific overrides
- [Field Types](field_types.md): Core DataType hierarchy and SQL Server-specific type extensions
- [Indexing](indexing.md): SQL Server-specific index types and optimization strategies
- [EXPLAIN](explain.md): Query execution plan analysis (SET STATISTICS IO/TIME)
- [Introspection](introspection.md): Database metadata queries and schema inspection
- [Partitioning](partition.md): Table partitioning with partition schemes and functions
- [DDL Feature Specs](ddl_spec.md): declarative DDL Specs claimed by the SQL Server dialect

## Feature Highlights

| Feature | Common Layer | SQL Server-Specific Layer |
|---------|-------------|---------------------------|
| Expressions | Core expression classes (Column, Literal, FunctionCall, etc.) | T-SQL overrides and SQL Server-specific expression classes (OUTPUT, OPENJSON, PIVOT) |
| Type System | Core DataType hierarchy (IntegerType, VarCharType, etc.) | SQL Server-specific DataType subclasses (NVarCharType, DateTime2Type, HierarchyIdType) |
| EXPLAIN | ExplainExpression interface | SET STATISTICS IO/TIME syntax |
| Introspection | Introspector interface | SQL Server metadata queries (INFORMATION_SCHEMA, sys.) |

## SQL Server-Specific Expression Classes

| Expression | Purpose |
|-----------|---------|
| `SQLServerOutputInsertedExpression` | OUTPUT INSERTED for returning inserted rows |
| `SQLServerOutputDeletedExpression` | OUTPUT DELETED for returning deleted rows |
| `SQLServerTableHintClause` | WITH (NOLOCK, ROWLOCK, etc.) table hints |
| `SQLServerTemporalPeriodDefinition` | FOR SYSTEM_TIME temporal queries |
| `SQLServerSystemVersioningClause` | System versioning DDL |
| `SQLServerOpenJsonExpression` | OPENJSON for JSON shredding |
| `SQLServerNextValueForExpression` | NEXT VALUE FOR sequence access |
| `SQLServerTryCastExpression` | TRY_CAST with error handling |
| `SQLServerTryConvertExpression` | TRY_CONVERT with error handling |
| `SQLServerContainsPredicate` | CONTAINS full-text predicate |
| `SQLServerFreetextPredicate` | FREETEXT full-text predicate |
| `SQLServerPivotExpression` | PIVOT row-to-column transform |
| `SQLServerUnpivotExpression` | UNPIVOT column-to-row transform |
| `SQLServerColumnstoreIndexExpression` | Columnstore index DDL |

## Related Topics

- [Type Adapters](../type_adapters/README.md) — type mapping and custom adapters
- [DDL Operations](../ddl/README.md) — schema management
- [Core: Expression System](https://github.com/Rhosocial/python-activerecord/tree/main/docs/en_US/backend/expression)
- [Core: Backend System](https://github.com/Rhosocial/python-activerecord/tree/main/docs/en_US/backend)
