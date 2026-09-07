# DDL 特征 Spec

SQL Server 实现了核心 DDL 特征认领协议（`dialect.build_spec`）。本章说明
SQL Server 方言认领哪些 Spec、如何翻译，以及它新增的 SQL Server 特定 Spec。

## 认领机制

`Model.generate_create_table(dialect)` 时，生成器把每个声明的 Spec 交给
`dialect.build_spec(spec)`：

- **接受** → 方言构造并返回表达式层实例，进入 `CreateTableExpression`；
- **不接受** → 返回 `None`，该 Spec 被静默忽略。

接受范围由 SQL Server 方言自行决定。

## 通用 Spec

全部通用 Spec 由核心默认翻译认领：

| Spec | SQL Server 翻译 |
|------|-----------------|
| `CheckSpec` | `TableConstraint(CHECK)`，惰性谓词生成时求值 |
| `UniqueSpec` | `TableConstraint(UNIQUE)` |
| `NotNullSpec` | `ColumnConstraint(NOT NULL)` |
| `PrimaryKeySpec` | 单列→列级 PK / 复合→表级 PK |
| `DefaultSpec` | `ColumnConstraint(DEFAULT)`，参数化 `Literal` |
| `ForeignKeySpec` | `ForeignKeyConstraint`（含参照动作） |
| `IndexSpec` | `IndexDefinition`（SQL Server 无部分索引，部分索引条件被忽略） |
| `JsonColumnSpec` | 列类型补丁 → `JsonType` |

## SQL Server 特定 Spec

定义于 `rhosocial.activerecord.backend.impl.sqlserver.ddl_spec`；以
`isinstance` 认领、由 `SQLServerDDLSpecMixin` 翻译。仅 SQL Server 方言认领。

### RANGE 分区 Spec

```python
from rhosocial.activerecord.backend.impl.sqlserver.ddl_spec import (
    SQLServerRangePartition,
)

class Orders(ActiveRecord):
    __table_partition__ = [
        SQLServerRangePartition(
            column="created_at",
            partition_scheme="ps_orders",
            boundaries=["2026-01-01", "2027-01-01"],  # 供分区函数使用
            right=True,  # RANGE RIGHT（默认）或 RANGE LEFT
        ),
    ]
```

翻译为 `SQLServerPartitionByRangeClause`，渲染 `ON [ps_orders] ([created_at])`。
配套的 `CREATE PARTITION FUNCTION` / `CREATE PARTITION SCHEME` 语句是独立 DDL，
由 `boundaries` 构建——见[分区](partition.md)。
