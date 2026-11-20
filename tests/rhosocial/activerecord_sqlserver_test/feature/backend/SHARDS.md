# Directory-bound database shards

Every leaf directory under `execute/` owns exactly one database. The mapping is
declared in that directory's `conftest.py`:

```python
from pathlib import Path

from providers.shards import register

register(Path(__file__).parent, "test_db_<n>")
```

`tests/providers/shards.py` resolves the directory a test lives in, so a test
uses its directory's database both serially and under `pytest-xdist`. The
session fixture `_prepare_directory_shards` in `tests/conftest.py` creates and
clears every registered database once at session start (`tests/providers/
pooling.py::prepare_directory_shards`); the databases are kept afterwards.

Directories are the unit of scheduling: `tests/conftest.py` gives every item a
`xdist_group("db:<name>")` marker, so use `--dist=loadgroup` to keep one
directory serial while directories run concurrently. `construct/` holds no
database and no shard.

## Canonical execute directories

| test_db | Directory | Covers |
|---|---|---|
| `test_db_1` | `execute/connection` | backend connection, connection resilience, execution options |
| `test_db_2` | `execute/crud` | CRUD and column/type mapping round trips |
| `test_db_3` | `execute/query` | query/EXPLAIN paths |
| `test_db_4` | `execute/join` | joins (no cases in this backend yet) |
| `test_db_5` | `execute/transaction` | transactions, isolation effects, savepoints, deadlock priority |
| `test_db_6` | `execute/ddl_table` | live table DDL (SELECT INTO, temporary tables) |
| `test_db_7` | `execute/ddl_column` | live column DDL (`DEFAULT` literal readback) |
| `test_db_8` | `execute/ddl_constraint` | constraints (no cases in this backend yet) |
| `test_db_9` | `execute/ddl_index` | indexes (no cases in this backend yet) |
| `test_db_10` | `execute/ddl_view` | views (no cases in this backend yet) |
| `test_db_11` | `execute/dml_insert` | batch inserts (`execute_many`) |
| `test_db_12` | `execute/dml_update_delete` | update/delete (no cases in this backend yet) |
| `test_db_13` | `execute/json` | JSON expressions/functions against a server |
| `test_db_14` | `execute/partition` | live partition DDL and maintenance |
| `test_db_15` | `execute/introspection` | live introspector families and probes |
| `test_db_16` | `execute/errors` | error handling against a server |
| `test_db_17` | `execute/concurrency` | concurrency protocol and concurrent async tasks |
| `test_db_18` | `execute/cli` | CLI against a live server |
| `test_db_19` | `execute/functions` | function execution (`seconds_between`, niladic functions) |
| `test_db_20` | `execute/sequence_identity` | identity capability conformance |
| `test_db_21` | `execute/fulltext_spatial` | spatial types against a server |
| `test_db_22` | `execute/show_admin` | SHOW/admin surfaces |
| `test_db_23` | `execute/routine_domain` | routines and domains (no cases in this backend yet) |

`test_db_24` is unused: backend-unique capabilities are namespaced under
`execute/sqlserver/` (below) instead of a catch-all directory, and their leaves
number from `test_db_25`.

## Backend-unique capabilities (`execute/sqlserver/`)

`execute/sqlserver/` is a namespace, not a shard: its parent directory holds no
test files. Each leaf capability is a shard of its own and takes the next free
number after the canonical range.

| test_db | Directory | Covers |
|---|---|---|
| `test_db_25` | `execute/sqlserver/set_type` | comma-separated `VARCHAR` set emulation (SQL Server has no `SET` type) |
| `test_db_26` | `execute/sqlserver/sql_graph` | SQL Graph: node/edge tables, `MATCH`, `SHORTEST_PATH` |

Backend-unique construction-only capabilities follow the same namespace on the
construct side and need no database, e.g.
`construct/sqlserver/session_settings/` (T-SQL `SET DEADLOCK_PRIORITY`,
`SET LANGUAGE`, `SET DATEFORMAT`, `IDENTITY` parameterized queries).

## Adding a leaf

1. Create `execute/<feature>/` or `execute/sqlserver/<capability>/`.
2. Drop a `conftest.py` in the new leaf that registers the next unused
   `test_db_<n>` (the canonical range is 1–23; backend-unique leaves start at
   25).
3. Add the row to this table.
