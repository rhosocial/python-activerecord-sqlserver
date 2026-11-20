# Advanced Objects

SQL Server presents several object families that have no portable equivalent.
This backend exposes them as expressions and gates each one on the connected
server's version. The contract for how gates work is in
[Capability gates](../capabilities/README.md); this page is the catalogue of
what is gated.

## Version-gated feature map

| Feature | Gate | Floor |
|---------|------|-------|
| System-versioned temporal tables | `supports_system_versioning()` | SQL Server 2016 (13.x) |
| SQL Graph (node/edge tables) | `supports_sql_graph()` | 2017 (14.x) |
| Shortest path / graph path aggregates | `supports_shortest_path()`, `supports_graph_path_aggregates()` | 2019 (15.x) |
| Nonclustered columnstore index | `supports_nonclustered_columnstore()` | 2012 (11.x) |
| Clustered columnstore index | `supports_clustered_columnstore()` | 2014 (12.x) |
| `ORDER (...)` in a columnstore index | `supports_columnstore_order()` | 2022 (16.x) |
| Sequences | `supports_sequence()` and friends | 2012 (11.x) |
| User-defined types (incl. CLR, memory-optimized table types) | `supports_type_objects()` family | varies |

Every release this repository tests against — 2017, 2019, 2022 and 2025 — is
past the 2012/2014/2016 floors, so those gates are open there; the 2017, 2019
and 2022 floors narrow what the earlier tested releases can render.

## Temporal tables

A system-versioned table keeps a history table and is queried with
`FOR SYSTEM_TIME`. Expressions live in `expression/temporal.py`; the dialect's
`supports_system_versioning()` answers from the 2016 floor. Queries are built
through the mixin in `mixins/temporal.py` rather than raw text.

```python
# The capability is asked of the connected server, not hard-coded
if backend.dialect.supports_system_versioning():
    ...  # render a SYSTEM_VERSIONING / FOR SYSTEM_TIME expression
```

## SQL Graph

Node and edge tables, `$node_id` / `$edge_id` pseudo-columns, `MATCH` pattern
matching and `SHORTEST_PATH` are available from SQL Server 2017 (2019 for the
path functions). The protocol surface is in `protocols/graph.py` and
`mixins/graph.py`, with expressions in `expression/graph.py`:

- `supports_sql_graph()`, `supports_graph_table_kind()`,
  `supports_graph_pseudo_columns()`
- `supports_shortest_path()`, `supports_graph_path_aggregates()`,
  `supports_edge_constraints()`

## Columnstore and memory-optimized tables

The columnstore expressions (`expression/columnstore.py`) render clustered and
nonclustered columnstore indexes, with the `ORDER` clause gated to 2022.
Memory-optimized tables are gated by `supports_memory_optimized_tables()` and
belong to the `WITH (MEMORY_OPTIMIZED = ON, ...)` family. These are storage
choices — the model declaration stays the same; the DDL expression changes.

## Sequences and user-defined types

`CREATE/ALTER/DROP SEQUENCE` support is in `mixins/sequence.py`, gated to 2012,
with a few sequence-as-data-type and validation clauses gated to 2016.
User-defined types (alias, table, CLR and memory-optimized table types) are
covered by `mixins/ddl_type.py` and the `protocols/type.py` capability surface
(`supports_create_type`, `supports_clr_user_defined_type`,
`supports_memory_optimized_table_types`, and so on). Introspection for these
objects is described in [Database introspection](../introspection/README.md).

## Other SQL Server DDL surfaces

- **Views** — indexed views, `WITH CHECK OPTION`, `CREATE OR ALTER`, and
  `SELECT INTO`; see the `supports_*` answers in `mixins/ddl_view.py`.
- **Fulltext** — fulltext catalogs and indexes (`protocols/fulltext.py`,
  `mixins/index.py`).
- **Generated columns** — stored and virtual computed columns
  (`mixins/generated_column.py`).
- **Triggers and routines** — DDL and introspection under `expression/ddl/`
  and `mixins/trigger.py` / `mixins/routine.py`.

> 💡 *AI prompt: "How does the backend decide whether a feature can be rendered, and why is that decision made at connect time rather than import time?"*
