# Partitioning on SQL Server

SQL Server does not spell partitioning the way PostgreSQL or MySQL do. There
is no `PARTITION BY` clause and no `PARTITION OF`. A partitioned table is
three catalogue objects working together:

```
CREATE PARTITION FUNCTION pf_logs (DATE)
    AS RANGE RIGHT FOR VALUES ('2026-01-01', '2026-02-01');

CREATE PARTITION SCHEME ps_logs
    AS PARTITION pf_logs ALL TO ([PRIMARY]);

CREATE TABLE dbo.logs (
    id INT NOT NULL,
    created_at DATE NOT NULL,
    CONSTRAINT pk_logs PRIMARY KEY (id, created_at)
) ON [ps_logs] ([created_at]);
```

- The **function** fixes the boundary values. `N` boundaries describe
  `N + 1` partitions, and `RANGE RIGHT` (the default) puts the boundary value
  in the partition to its right.
- The **scheme** maps each partition to a filegroup. `ALL TO` uses one
  filegroup; an explicit list needs one name per partition.
- The table is built `ON <scheme> (<column>)`. The partitioning column must
  be part of every unique index on the table, which is why the primary key
  above includes `created_at`.

## No subpartitions

SQL Server has no subpartitioning at any version. `supports_subpartitioning()`
returns `False`, and `SQLServerPartitionPlan` refuses a plan that asks for
another strategy or a `subpartition_by` at construction:

```python
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

SQLServerPartitionPlan(
    function="pf_logs",
    data_type="DATE",
    boundaries=(date(2026, 1, 1),),
    subpartition_by="HASH",
)  # raises UnsupportedFeatureError
```

There is also no `ADD PARTITION` / `DROP PARTITION`: adding a partition means
`SPLIT RANGE`, and removing one means `MERGE RANGE`. `supports_add_partition()`
and `supports_drop_partition()` stay `False`; the SQL Server-specific
capability flags are `supports_split_partition()`, `supports_merge_partition()`
and `supports_switch_partition()`.

## DDL expressions

Each statement is an expression node; the dialect renders the text.

```python
from datetime import date

from rhosocial.activerecord.backend.impl.sqlserver.expression.partition import (
    SQLServerDropPartitionFunctionExpression,
    SQLServerDropPartitionSchemeExpression,
    SQLServerPartitionFunctionExpression,
    SQLServerPartitionFunctionMergeExpression,
    SQLServerPartitionFunctionSplitExpression,
    SQLServerPartitionSchemeExpression,
    SQLServerPartitionSchemeNextUsedExpression,
    SQLServerSwitchPartitionExpression,
)

SQLServerPartitionFunctionExpression(
    dialect, "pf_logs", "DATE", [date(2026, 1, 1), date(2026, 2, 1)]
).to_sql()
# CREATE PARTITION FUNCTION [pf_logs] (DATE)
#   AS RANGE RIGHT FOR VALUES ('2026-01-01', '2026-02-01')

SQLServerPartitionSchemeExpression(
    dialect, "ps_logs", "pf_logs", [], all_filegroup="PRIMARY"
).to_sql()
# CREATE PARTITION SCHEME [ps_logs] AS PARTITION [pf_logs] ALL TO ([PRIMARY])

SQLServerPartitionFunctionSplitExpression(
    dialect, "pf_logs", date(2026, 1, 15)
).to_sql()
# ALTER PARTITION FUNCTION [pf_logs] () SPLIT RANGE ('2026-01-15')

SQLServerPartitionFunctionMergeExpression(
    dialect, "pf_logs", date(2026, 1, 15)
).to_sql()
# ALTER PARTITION FUNCTION [pf_logs] () MERGE RANGE ('2026-01-15')

SQLServerPartitionSchemeNextUsedExpression(
    dialect, "ps_logs", "PRIMARY"
).to_sql()
# ALTER PARTITION SCHEME [ps_logs] NEXT USED [PRIMARY]

SQLServerSwitchPartitionExpression(
    dialect, "logs", "logs_archive", source_partition=1
).to_sql()
# ALTER TABLE [logs] SWITCH PARTITION 1 TO [logs_archive]

SQLServerDropPartitionSchemeExpression(dialect, "ps_logs").to_sql()
# DROP PARTITION SCHEME [ps_logs]

SQLServerDropPartitionFunctionExpression(dialect, "pf_logs").to_sql()
# DROP PARTITION FUNCTION [pf_logs]
```

`SPLIT RANGE` consumes a destination from the scheme. If the scheme has no
filegroup marked `NEXT USED`, the server refuses the split, so the suggested
`add` / `split` chains emit `NEXT USED` before each `SPLIT RANGE`.

## Suggestions and introspection

SQL Server does not ship a partition-maintenance executor. Partition DDL is
offered through the dialect's eight **partition-suggestion** methods, and the
catalogue side through the engine's own **partition introspection** family.
Together they are the single source for how this backend handles partitions.

`SQLServerPartitionPlan` remains the owner-agnostic layout description: a
function, its boundaries and direction, and an optional scheme with its
filegroups. It carries no table name and no retention rule. A caller passes
that plan (or a mapping with the same field names) to the dialect:

```python
from rhosocial.activerecord.backend.expression import Column
from rhosocial.activerecord.backend.expression.statements import PartitionByRangeClause
from rhosocial.activerecord.backend.impl.sqlserver.partition import SQLServerPartitionPlan

plan = SQLServerPartitionPlan(
    function="pf_logs",
    data_type="DATE",
    boundaries=(date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)),
    scheme="ps_logs",
    all_filegroup="PRIMARY",
)

# The strategy is an expression clause carrying the RANGE word and its keys.
strategy = PartitionByRangeClause(dialect, [Column(dialect, "created_at")])

build = dialect.suggest_partition_build(strategy, plan)
add = dialect.suggest_partition_add(
    strategy, {**plan.__dict__, "boundary": date(2026, 3, 15)}
)
drop = dialect.suggest_partition_drop(
    strategy, {**plan.__dict__, "boundary": date(2026, 1, 1)}
)
retention = dialect.suggest_partition_retention(
    strategy, {**plan.__dict__, "cutoff": date(2026, 2, 1)}
)
```

Each suggestion is a frozen value whose `operations` is one of three things:
a tuple of real SQL Server expression nodes the dialect can render and the
caller can execute in order, `False` when SQL Server has no such mechanism for
the strategy/plan, or `None` when nothing needs doing. The eight methods cover
`build`, `table_drop`, `table_alter`, `add`, `drop`, `split`, `merge` and
`retention`.

What the answers mean in SQL Server terms:

- **`build`** returns the three-tier chain: `CREATE PARTITION FUNCTION`, then
  `CREATE PARTITION SCHEME` when the plan names one, then a `PARTITION BY`
  clause `ON <scheme> (<keys>)` when the plan supplies `keys`.
- **`table_drop`** returns `DROP PARTITION SCHEME` followed by
  `DROP PARTITION FUNCTION`, in dependency order. Dropping the function while
  a scheme maps it is refused by the server.
- **`table_alter`** is always `False`: there is no in-place way to change a
  partitioned table's scheme. Doing so moves every row and is the caller's
  decision.
- **`add`** and **`split`** return `NEXT USED` (when a scheme is present)
  followed by `ALTER PARTITION FUNCTION ... SPLIT RANGE`. Splitting moves rows.
- **`drop`** and **`merge`** return `ALTER PARTITION FUNCTION ... MERGE RANGE`:
  SQL Server has **no** `DROP PARTITION`. Merging removes one boundary and
  folds its rows into the partition on the left, so it is data-affecting.
- **`retention`** returns one `MERGE RANGE` per boundary at or before the
  plan's `cutoff`. SQL Server's boundary is the upper bound of the partition to
  its left in both RANGE directions, so `<= cutoff` means the partition ends on
  or before the cutoff. No candidate means `None`; a non-RANGE strategy or a
  missing cutoff means `False`.

The capability probes on the dialect gate every mutating chain, so a dialect
that withdraws a feature answers `False` rather than emitting SQL the server
would reject.

The catalogue side is answered by introspection:

```python
if dialect.supports_partition_metadata_introspection():
    state = backend.introspector.get_partition_state("orders", include_stats=True)
    if state is not None:
        for bound in state.bounds:
            print(bound.name, bound.upper, bound.row_count)
```

`supports_partition_metadata_introspection()` asks only whether the catalogue
can be read, so it answers on Standard and Express too; the mutating chains
above are `supports_table_partitioning()`'s question and still need the
Enterprise feature set. A `False` from that DDL probe never means a table is
unpartitioned.

`PartitionState` is core's neutral record: `scheme` is `None` for an
unpartitioned table, `key_expression`/`key_columns` name the partitioning
column, `bounds` carries one `PartitionBound` per partition, and `raw` keeps
this engine's own spelling -- the scheme name, the partition function and the
boundary direction. See [Database Introspection](../introspection/README.md)
for the full probe table. The
caller decides which partitions are old, which table to act on, and whether to
execute a suggested chain -- no retention policy is embedded in the backend.

## Boundaries and ranges

SQL Server requires boundary values in ascending order and supports one
direction per function:

- `RANGE RIGHT` (default): the boundary value belongs to the partition on the
  right. With boundaries `2026-01-01`, `2026-02-01`, `2026-03-01`, the rows
  are `(-inf, 2026-01-01)`, `[2026-01-01, 2026-02-01)`,
  `[2026-02-01, 2026-03-01)`, `[2026-03-01, +inf)`.
- `RANGE LEFT`: the boundary value belongs to the partition on the left.

A plan sorts its boundaries and refuses duplicates. Removing a boundary with
`MERGE RANGE` does not change the other boundaries; it only widens one
partition to absorb its neighbour.

## Test coverage

The offline suites in
`tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/ddl/`
cover every family without a server: `test_partition_expressions.py` asserts the
rendered statement text, `test_partition_syntax_matrix.py` checks the plan and
DDL matrix, and `test_partition_suggestions.py` checks the eight suggestion
protocols and their tri-state values. The plan and introspection records are
covered alongside them; no live partition-maintenance suite remains.
