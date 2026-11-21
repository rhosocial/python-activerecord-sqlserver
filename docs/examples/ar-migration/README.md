# Backend-specific AR migration examples — SQL Server

Offline, runnable examples of the `suggest_partition_*` migration API for the
**SQL Server** backend. They render the T-SQL this backend actually emits, but
never open a connection, never call `ctx.apply()`, and never hand-build SQL
strings: every SQL line is read from `expr.to_sql()[0]` on the expression nodes
returned by the dialect.

For the general (core) migration story and the shared recipe behind these
backend-specific examples, see `docs/examples/migration/` and the core repo's
`docs/examples/ar-migration/`.

## What is different about SQL Server

SQL Server has a **three-tier** partition model and only one strategy — `RANGE`
(`LEFT` or `RIGHT`). There is no `ADD PARTITION` and no `DROP PARTITION`:

| Lifecycle point | SQL Server's answer | Data-affecting? |
|-----------------|---------------------|-----------------|
| build | `CREATE PARTITION FUNCTION` → `CREATE PARTITION SCHEME` → `ON [scheme] (col)` | no (DDL scaffolding) |
| add / split | `ALTER PARTITION SCHEME ... NEXT USED`, then `ALTER PARTITION FUNCTION ... SPLIT RANGE` | **yes** — splitting a populated range moves rows |
| drop / merge | `ALTER PARTITION FUNCTION ... MERGE RANGE` | **yes** — removing a boundary folds rows into the neighbour; there is no `DROP PARTITION` |
| retention | one `MERGE RANGE` per boundary at or before the cutoff | **yes** |
| table drop | `DROP PARTITION SCHEME`, then `DROP PARTITION FUNCTION` (dependency order; no `DROP TABLE`) | no |
| table alter | `False` — no in-place mechanism; changing the function moves every row | n/a |

Other consequences:

- **Tri-state result**: `operations` is a tuple of expression nodes when a real
  chain exists, `False` when SQL Server has no such mechanism for the
  strategy/plan, and `None` when nothing needs doing.
- **Version gate**: partitioning requires SQL Server 10.0+. These examples use
  `SQLServerDialect((16, 0, 0))`. A `SQLServerDialect((9, 0, 0))` withdraws every
  mutating chain — `suggest_partition_add/drop/split/merge/retention` (and build)
  all return `operations is False`. Script 02 demonstrates this.
- **Plan contract**: a `SQLServerPartitionPlan` (or a mapping/dict with the same
  fields) describes the function, not the table: `function`, `data_type`,
  `boundaries`, optional `range_direction` (`"RIGHT"` default / `"LEFT"`),
  `scheme`, plus either `all_filegroup` or one `filegroups` entry per partition
  (`N` boundaries ⇒ `N + 1` filegroups). Optional `keys` adds the table's `ON`
  clause; optional `boundary` targets a single add/drop/split/merge; optional
  `cutoff` drives retention.

## Scripts

| Script | Scenarios shown |
|--------|-----------------|
| [`01_partition_build.py`](01_partition_build.py) | (1) RANGE RIGHT `DATE` function + scheme; (2) three-tier build with the table's `ON ... ([created_at])` key; (3) RANGE LEFT `INT` with explicit filegroups; (4) declined requests (LIST strategy / empty plan → `False`). |
| [`02_partition_lifecycle.py`](02_partition_lifecycle.py) | (1) ADD → `NEXT USED` + `SPLIT RANGE`; (2) SPLIT of an existing range (mid-boundary, rows move); (3) DROP → `MERGE RANGE` (no `DROP PARTITION`); (4) MERGE of an explicit boundary; (5) RETENTION → `MERGE RANGE` chain (DATE, numeric-with-text-cutoff, DATETIME2); (6) TABLE DROP → drop scheme then function; (7) TABLE ALTER → `False`; (8) version gate — `(9, 0, 0)` declines every mutating chain. |

## Running

From the repository root, with the worktree's virtual environment and `src` on
the import path (no database required):

```powershell
$env:PYTHONPATH = 'src'
.venv3.14\Scripts\python.exe docs/examples/ar-migration/01_partition_build.py
.venv3.14\Scripts\python.exe docs/examples/ar-migration/02_partition_lifecycle.py
```

Both scripts are syntax-checked and run offline with exit code 0.

### Sample output (script 02, abbreviated)

```text
== 1. ADD a boundary = NEXT USED + SPLIT RANGE (data-affecting) ==
  ALTER PARTITION SCHEME [ps_logs] NEXT USED [PRIMARY]
  ALTER PARTITION FUNCTION [pf_logs] () SPLIT RANGE ('2026-03-01')
== 3. DROP a partition = MERGE RANGE, not DROP PARTITION (data-affecting) ==
  ALTER PARTITION FUNCTION [pf_logs] () MERGE RANGE ('2026-01-01')
== 5. RETENTION = one MERGE RANGE per boundary <= cutoff ==
  ALTER PARTITION FUNCTION [pf_logs] () MERGE RANGE ('2026-01-01')
  ALTER PARTITION FUNCTION [pf_logs] () MERGE RANGE ('2026-02-01')
== 8. version gate: SQLServerDialect((9, 0, 0)) declines ==
  build: operations is False
  add: operations is False
  ...
```
