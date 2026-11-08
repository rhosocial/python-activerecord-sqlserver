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
filegroup marked `NEXT USED`, the server refuses the split, so the maintenance
helper emits `NEXT USED` before each split.

## Maintenance

`rhosocial.activerecord.backend.impl.sqlserver.partition` provides the plan and
one executor with six operations. The executor is owner-agnostic: no table
name, partition column or retention policy is embedded in it; `drop_before`
takes the cutoff from the caller and reads the boundaries from the catalogue.

```python
from rhosocial.activerecord.backend.impl.sqlserver.partition import (
    SQLServerPartitionMaintenance,
    SQLServerPartitionPlan,
)

plan = SQLServerPartitionPlan(
    function="pf_logs",
    data_type="DATE",
    boundaries=(date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)),
    scheme="ps_logs",
    all_filegroup="PRIMARY",
)

maintenance = SQLServerPartitionMaintenance(backend)

# Idempotent: creates the function and scheme when absent, splits only the
# boundaries the server does not already hold.
report = maintenance.ensure(plan)

# Catalogue report: functions, schemes, tables, per-partition ranges.
report = maintenance.list(plan, table="logs", schema="dbo")

# Checks only; never repairs. The issues tuple says what is wrong.
report = maintenance.validate(plan, table="logs", schema="dbo")

# SQL Server has no DROP PARTITION: merge the boundaries away.
report = maintenance.drop_or_merge(plan, [date(2026, 1, 1)], dry_run=True)

# Retention: compute the boundaries at or before a cutoff, then merge them.
boundaries = maintenance.retention_boundaries(plan, date(2026, 2, 1))
report = maintenance.drop_before(plan, date(2026, 2, 1), dry_run=True)
```

### `ensure(plan, dry_run=False)`

- Function absent: creates it with the plan's full boundary list, then the
  scheme when one was named.
- Function present: splits only missing boundaries, in ascending order. The
  server decides whether a boundary exists (the value is cast to the
  function's type), so date/time and decimal spellings cannot produce a false
  "missing".
- Scheme absent: creates it. With explicit `filegroups`, the function must
  already have the plan's partition count; otherwise use `all_filegroup`.
- Direction or data-type mismatch: raises `ValueError`. Repairing that in
  place means dropping the function, and dropping a function used by a table
  is not something a maintenance call should do silently.

`dry_run=True` returns the statements without executing them.

### `list(plan=None, *, table=None, schema=None)`

Reads `sys.partition_functions`, `sys.partition_schemes`,
`sys.destination_data_spaces`, `sys.tables`, `sys.indexes`,
`sys.index_columns` and `sys.partitions`. The report carries:

- `functions` / `schemes` / `tables` with filegroups, type, direction and
  partition count;
- `ranges` for the requested table: partition number, low/high boundary
  text, row count and data bytes;
- `partitions`: the same rows as the core `PartitionInfo` contract (`name`
  is `<table>_<number>`, `parent` is the table, `level` is 1, `bound` joins
  low/high and `extras` carries the scheme, function and partition number);
- `missing_boundaries` and `existing_boundaries`, when a plan was given;
- `issues`, which only report; nothing is repaired.

A real `ensure` / `drop_or_merge` run re-reads the catalogue before returning;
a dry run keeps the pre-execution snapshot. SQL Server's DDL auto-commits, so
the executor stops at the first `DatabaseError`, records it in `errors`, and
leaves the statements that did run in `operations`.

`sql_variant` boundary values are cast to text for display, with date/time
values in ISO style so the report does not depend on the login language.

### `drop_or_merge(plan, boundaries=None, *, dry_run=True, drop_scaffolding=False)`

SQL Server cannot drop a partition. `MERGE RANGE` removes the boundary and
folds the partition's rows into the partition on the left. `boundaries`
names exactly which boundaries to merge -- there is no "before date" or
retention rule here; that decision belongs to the application.

`dry_run` defaults to `True` because merging moves rows. With
`drop_scaffolding=True`, the scheme and function are dropped afterwards, but
only when the catalogue shows no table built on the scheme. When a table uses
it, the report says why the drop was refused.

### `retention_boundaries(plan, cutoff, *, table=None, schema=None)`

Reads the function's boundary values (or a table's range upper bounds when
`table` is passed) and returns the ones at or before `cutoff`. Nothing is
executed. SQL Server's boundary is the upper bound of the partition to its
left in both RANGE directions, so `<= cutoff` means "the partition is wholly
before or ends on the cutoff".

### `drop_before(plan, cutoff, *, dry_run=True, drop_scaffolding=False)`

Computes `retention_boundaries(plan, cutoff)` and calls `drop_or_merge` with
them. It implements the core `PartitionRetention` protocol. A dry run only
renders `MERGE RANGE` statements; a real run re-reads the catalogue afterwards
and reports what is left.

### `validate(plan, *, table=None, schema=None)`

Reports, without changing anything:

- a missing function or scheme;
- a direction, data type or boundary-count mismatch;
- a scheme mapped to another function;
- a scheme whose destination count does not match the partition count;
- a table on another scheme/function, or with missing partition numbers.

The report's `issues` tuple is the whole result; there is no automatic fix.

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

## Live coverage

`tests/.../feature/backend/test_sqlserver_partition_live.py` exercises
`CREATE PARTITION FUNCTION` / `SCHEME`, `SPLIT RANGE`, `MERGE RANGE`, `SWITCH`
and catalogue reads against the SQL Server 2022 image in `docker-compose.yml`.
It skips -- rather than passes -- when no scenario is configured or the server
cannot be reached. The offline suites cover the same decisions with canned
catalogue rows and assert every rendered statement.
