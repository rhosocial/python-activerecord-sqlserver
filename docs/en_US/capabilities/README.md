# Capability Gates

The dialect exposes a large family of `supports_*` switches. They are the
backend's answer to "can this be asked of / rendered for the server in front of
us?". This page explains how they behave; the feature chapters list which ones
matter for each area.

## How gates work

1. **Capability questions are about the server, not the product.** A probe may
   consult the detected server version (`version_at_least(...)` against the
   constants in `mixins/version_constants.py`), or it may be a fixed statement
   about what this backend implements. `backend.introspect_and_adapt()` refreshes
   the detected version so version-gated probes answer for the server actually
   reached. The CLI calls it on entry; code that gates on a probe should too.
2. **A `False` answer means "this question cannot be asked here"**, not "the
   answer was empty or zero". It is distinct from an empty list, which is the
   answer to a question that *was* asked and had nothing to report. Callers can
   take a fallback knowingly.
3. **Gates do not test grants.** Two introspection DMVs need `VIEW DATABASE
   STATE` / `VIEW SERVER STATE`; without them the engine answers a short list
   or nothing at all, not an error. The probe answers `True` because the server
   can answer — not because this login may ask.

A gate that opens only means a statement renders and the server accepts it; it
says nothing about the shape or cost of the answer. The introspection page
states the price of each family it describes.

## Two kinds of `False`

- **Version floors** — the feature exists in SQL Server only from a certain
  release. E.g. `supports_object_dependencies()` is `True` from 2008;
  `supports_column_value_sample()` from 2012 because its `OFFSET ... FETCH`
  cap needs that parser.
- **Permanent statements about the engine** — e.g. `supports_table_stats()`
  and `supports_ddl_extraction()` are `False` on every release: the counters
  are keyed per index (not per table), and the engine has no per-object DDL
  retrieval call. `supports_json_table()` is `False` even on recent releases
  because this backend's route is `OPENJSON`, not `JSON_TABLE`.
- **Syntax decisions** — `supports_nulls_first_last()` and
  `supports_fetch_with_ties()` are `False` because SQL Server has no such
  syntax in those positions; `supports_subpartitioning()`,
  `supports_add_partition()` and `supports_drop_partition()` are `False`
  because partitioning here uses `SPLIT` / `MERGE` / `SWITCH`
  (see [Partitioning](../ddl/partition.md)).

## Version floor reference

| Feature / gate | Floor | What happens below it |
|----------------|-------|-----------------------|
| DMV-based gates (`runtime`, `index-stats`, `unused-indexes`) | 2005 (9.0) | probe `False`; CLI exits 2 without sending a statement |
| `supports_object_dependencies()` | 2008 (10.0) | probe `False`; CLI exits 2 |
| `supports_column_value_sample()` | 2012 (11.0) | probe `False`; CLI exits 2 |
| JSON functions (`supports_json_type()`) | 2016 (13.x) | probe `False` |
| Temporal tables (`supports_system_versioning()`) | 2016 (13.x) | gate closed |
| SQL Graph (node/edge, pseudo-columns) | 2017 (14.x) | gate closed |
| Graph shortest path / path aggregates; `READPAST` skip-locked | 2019 (15.x) | gate closed |
| Columnstore `ORDER (...)` | 2022 (16.x) | gate closed |
| `table-stats`, `ddl`, `extensions`, `json_table` | never | probe `False` on every release |

All tested releases (2017–2025) are past the 2005/2008/2012/2016 floors; the
2017, 2019 and 2022 floors narrow what the earlier tested releases can render.

## Probing from code

```python
backend.introspect_and_adapt()

if backend.dialect.supports_unused_indexes_detection():
    for index in backend.introspector.list_unused_indexes():
        print(f"{index.table_name}.{index.index_name}")
else:
    ...  # take the fallback knowingly
```

The full introspection probe table, including which answers are backend-local
or newly added, is in [Database introspection](../introspection/README.md).
