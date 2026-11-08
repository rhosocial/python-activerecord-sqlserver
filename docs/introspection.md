# Database Introspection

The SQL Server backend answers three layers of questions: what the database declares (from `sys` catalog views and `INFORMATION_SCHEMA`), what it has been doing (four operational families out of six), and what its rows hold (three data families). `backend.introspector` is the entry point for all three, and every answer on this page is SQL Server's own: what this engine says, not the shape a cross-dialect consumer can expect.

The contract those answers fill is core's, and this page does not restate it: the probe rules live in `backend/introspection/capabilities.md`, the operational shapes in `operations.md`, the profile and coverage types in `data-profiles.md`, all under [python-activerecord/docs](https://github.com/rhosocial/python-activerecord/tree/main/docs). What follows is only where SQL Server stands against that contract, and where its answers come from.

## Overview

- **Database information**: name, product version and collation, asked of the engine rather than read from a catalogue
- **Tables**: name, object type, `MS_Description` as the comment, and data/index bytes from `sys.dm_db_partition_stats`
- **Columns**: declared type, nullability, default, identity, character and numeric parameters, `MS_Description`
- **Indexes**: name, uniqueness, primary-key flag, type and column order, from `sys.indexes` and `sys.index_columns`
- **Foreign keys**: resolved column and table names, update/delete actions
- **Views and triggers**: definitions, updatability, firing events, `INSTEAD OF` flag
- **This backend's own families**: schemas, extended properties, procedures, functions and sequences, plus the primary-key read
- **Operational answers**: unused indexes, per-index counters, instance counters and by-name dependency edges; two families refused
- **Data answers**: per-column profiles, value listings and join coverage, all aggregated over the rows

## What SQL Server Answers

Every question in the introspection contract has a probe on the dialect, and a probe is a question about the server in front of you rather than about the product. This table is SQL Server's answer to all twenty-one. Read the `False` rows first: a probe that answers `False` says the question cannot be asked of this server, never that the answer was empty or zero.

| Probe | SQL Server answers | The question it gates |
|-------|--------------------|-----------------------|
| `supports_introspection()` | `True` | Anything about the schema at all |
| `supports_database_info()` | `True` | The database's name, version and collation |
| `supports_table_introspection()` | `True` | Tables, views and system tables |
| `supports_column_introspection()` | `True` | Columns, identity and descriptions |
| `supports_index_introspection()` | `True` | Indexes, their columns and order |
| `supports_foreign_key_introspection()` | `True` | Foreign keys and their actions |
| `supports_view_introspection()` | `True` | Views and their definitions |
| `supports_trigger_introspection()` | `True` | Triggers, events and timing |
| `supports_table_storage_introspection()` | `True` | Per-table data and index bytes |
| `supports_runtime_stats()` | `True` from 2005 | What the instance says it is counting |
| `supports_table_stats()` | `False` on every version | Per-table usage counters |
| `supports_index_stats()` | `True` from 2005 | Per-index usage counters |
| `supports_unused_indexes_detection()` | `True` from 2005 | Indexes with no recorded read |
| `supports_object_dependencies()` | `True` from 2008 | The dependency graph — by-name references |
| `supports_ddl_extraction()` | `False` on every version | The text that recreates an object |
| `supports_ddl_extraction_native()` | `False` (inherited) | Whether that text is the engine's own |
| `supports_column_data_profile()` | `True` | What each column of a table holds |
| `supports_column_value_sample()` | `True` from 2012 | Which values occur, and how often |
| `supports_join_coverage()` | `True` | How much two columns' domains overlap |
| `supports_partition_info()` | `False` | Core's partition family |
| `supports_extensions()` | `False` | Installed add-on components |

Five families beyond core's shared set are this backend's own, and each is declared in the mixin that owns it: `supports_extended_property_introspection()` for the `extended-properties` family over `sys.extended_properties`, plus `supports_schema_introspection()`, `supports_procedure_introspection()`, `supports_function_introspection()` and `supports_sequence_introspection()`. `get_primary_key()` is core's method, answered from `list_indexes()`'s `is_primary` flag; the primary-key statement is also what `list_columns()` runs first, so each column's `is_primary_key` is filled. `get_supported_introspection_scopes()` returns database, table, column, index, foreign key, view, trigger and sequence — core's `SCHEMA` scope is not among them, and extended properties and routines have no scope of their own.

A `True` promises only that the query renders and the server accepts it; it says nothing about the shape of the answer or its price, and the price of every family is stated where the family is described.

`supports_table_stats()` is `False` on every release, and the reason is the shape of the engine's counters rather than a missing catalogue. `sys.dm_db_index_usage_stats` is keyed by object **and index**: one row per index, never one row per table. Summing its rows per table would be an aggregate wearing the shape of a measured counter — a caller asking "how many scans did this table take" would receive a number no engine ever counted. Two of the slots the family names are not tracked at all: sequential scans are not distinguishable from indexed ones at the table level, and inserts and deletes are recorded nowhere — `user_updates` is the only write shape the DMV carries, and it counts writes of every kind. The row estimate is a different source again, and the table listing does not answer it either: `row_count` stays `None`, because an exact count would be a scan of the table and the listing reads no estimate.

`supports_ddl_extraction()` is `False` on every release. The engine has no per-object retrieval call of the kind `SHOW CREATE TABLE` is: `OBJECT_DEFINITION` and `sys.sql_modules` hold the *body* of a routine, a view or a trigger — text the engine stores because it executes it — while a table's columns, constraints, indexes and storage are recorded as rows across `sys.columns`, `sys.indexes`, `sys.default_constraints` and more. Reassembling a `CREATE TABLE` from them is a reconstruction, and this family's rule is that a reconstruction is not an answer: `DDLStatement.native` exists to say which of the two a caller is looking at, and an assembly that used it would be claiming the engine said something it did not. `supports_ddl_extraction_native()` is `False` by inheritance for the same reason.

`supports_unused_indexes_detection()`, `supports_index_stats()` and `supports_runtime_stats()` are the 2005 (9.0) floor: the three dynamic management views arrived there. `supports_object_dependencies()` is the 2008 (10.0) floor, where `sys.sql_expression_dependencies` arrived. `supports_column_value_sample()` is the 2012 (11.0) floor, because its cap rides `OFFSET 0 ROWS FETCH NEXT n ROWS ONLY`, which the engine parses only from that release — asking the version accessor is a truer answer than a statement that fails to parse.

`supports_partition_info()` and `supports_extensions()` stay `False` by inheritance. Core's partition family has no method on this backend to oblige, and no catalogue is mapped for installable add-on components, so there is no answer behind a `True`.

## Basic Usage

```python
from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend

backend = SQLServerBackend(
    host="localhost",
    port=1433,
    database="mydb",
    username="sa",
    password="YourStrong!Passw0rd",
    driver="{ODBC Driver 18 for SQL Server}",
)
backend.connect()
backend.introspect_and_adapt()

introspector = backend.introspector

info = introspector.get_database_info()
print(info.name, info.version, info.collation)

for table in introspector.list_tables():
    print(table.name, table.table_type.value,
          table.data_size_bytes, table.index_size_bytes, table.comment)

for column in introspector.list_columns("orders"):
    print(column.name, column.data_type_full, column.nullable.value)
```

`backend.introspect_and_adapt()` is the step that makes a version-gated probe answer for the server the handshake reached, rather than for the version the backend was constructed with. The CLI calls it at the entrance; a caller gating on a probe should do the same.

Schema is a real level here. Every statement that takes one falls back to `dbo` when the caller names none, and the CLI's `schemas` type lists the database's schemas with their owners (`sys.schemas` left-joined to `sys.database_principals` on `principal_id`, because a schema and its owner need not share a name). The backend's own families sit beside the core API:

```python
for schema in introspector.list_schemas():
    print(schema.name, schema.owner)

for property_ in introspector.list_extended_properties(
    class_name="OBJECT_OR_COLUMN", table_name="orders"
):
    print(property_.name, property_.value)

for routine in introspector.list_functions():
    print(routine.name, routine.type_code)
```

`list_extended_properties()` takes either a `major_id` it already has or a `table_name` to resolve — the named form joins `sys.tables` and `sys.schemas`, so a caller needs no first round trip to turn a name into an id. Its `class_name` is checked against the `class_desc` values the engine documents (`OBJECT_OR_COLUMN`, `INDEX`, `DATABASE`, `PARAMETER` and so on), and a schema filter is refused for a class whose `major_id` lives in another id space, because "no rows" there would be a silent contradiction rather than an answer. `value` is `sql_variant` and the driver cannot fetch it, so it is cast to `NVARCHAR(4000)` in the statement.

## Structure answers worth knowing

- **Database information is asked, not read.** The statement has no `FROM`: `DB_NAME()` and the `SERVERPROPERTY` values `ProductVersion`, `Collation` and `Edition`, each property cast to `NVARCHAR(128)`. The record carries the name, the version and the collation; `Edition` is projected but has no slot in the record, and `encoding` stays `None` — this engine reports a collation, not an encoding.
- **Tables come from `sys.objects`, not `INFORMATION_SCHEMA.TABLES`.** The information-schema view folds object kinds into two-word spellings and omits every `is_ms_shipped` row, so the one row that says "this is a system table" never reaches the parser. `sys.objects.type` (`U` user table, `V` view, `S` system table) and `is_ms_shipped` are the two facts the question is about, and `--include-system` changes the answer rather than being ignored.
- **No row count on the listing.** `IntrospectionTableInfo.row_count` stays `None`: an exact count would be a scan, and the listing reads no estimate. The storage slots beside it are measured, not estimated, and are `None` for a view rather than `0`.
- **Comments.** SQL Server has no `COMMENT` clause; `MS_Description` in `sys.extended_properties` is the only place a table's or column's comment lives. The table listing joins it with a `LEFT JOIN` on the object-level property alone (`minor_id = 0`), so a table without a comment keeps its row and a column description cannot be mistaken for the table's. The column listing reaches it through `sys.columns`, because the property is keyed by the object id and the column id, neither of which `INFORMATION_SCHEMA.COLUMNS` carries.
- **Storage bytes.** `sys.dm_db_partition_stats` counts one row per partition of one index: the partitions of `index_id` 0 (a heap) or 1 (a clustered index) are the table's own storage, everything above 1 is a nonclustered index's, and all partitions together are the total. The listing carries three scalar subqueries rather than a join, because a `GROUP BY` over that view would fold the object kinds and a view — which has no partition rows — would vanish from the listing instead of answering `None` for its storage. Page size is 8 KiB with no configuration switch, so the multiplication by 8192 is a fact of the engine.
- **Identity.** `INFORMATION_SCHEMA.COLUMNS` reports no identity flag; the column listing joins `sys.columns` and asks `COLUMNPROPERTY(..., 'IsIdentity')`. `DATETIME_PRECISION` is projected because it is the only place the fractional-seconds precision of `time`/`datetime2`/`datetimeoffset` lives.
- **Indexes.** `sys.indexes` joined to `sys.index_columns` and `sys.columns`; a heap has no named index row and is excluded, so `index_id` 0 never appears as an index.
- **Triggers.** Firing events are not a column of `sys.triggers`; they live one table over, in `sys.trigger_events`, one row per event. The join is a `LEFT JOIN`, one row per event, and the parser folds contiguous rows back into one trigger — so a trigger with no event row is still a trigger, and its definition comes from `OBJECT_DEFINITION`.
- **Views.** `INFORMATION_SCHEMA.VIEWS` carries `VIEW_DEFINITION`, which is `NULL` for a view whose text the caller may not read — unlike `OBJECT_DEFINITION()`, which returns the text to a caller holding `VIEW DEFINITION`. Both the list and the single-view question read that one view, so they cannot disagree, and `include_system` is not consulted because the view holds no server-owned row.

## Operational Families

SQL Server implements four of the six.

| Family | Method | SQL Server source | Price |
|--------|--------|-------------------|-------|
| Unused indexes | `list_unused_indexes()` | `sys.dm_db_index_usage_stats` through `sys.objects`/`sys.schemas`/`sys.indexes` | One DMV read |
| Table counters | `list_table_usage_stats()` | none — refused by the probe | no query is run |
| Runtime metrics | `list_runtime_metrics()` | `sys.dm_os_performance_counters` | One instance-wide read |
| Index counters | `list_index_usage_stats()` | the same index usage DMV | One DMV read |
| Dependencies | `list_object_dependencies()` | `sys.sql_expression_dependencies` | One catalogue read |
| DDL | `get_ddl_statement()` | none — refused by the probe | no query is run |

Every counter here is since the view was last flushed, which is the engine's own window and not a resettable epoch: the index usage view flushes on its own schedule after a restart, and the performance counters start again when the instance does. Nothing in the answer dates the window, so a zero is "none in the stretch the engine remembers", never "never". That is also why a cached answer ages faster here than in the declaration layer: a schema cached yesterday is probably still the schema, while the window a counter described has kept running.

### Unused Indexes

One row per index of the schema, addressed by three names the DMV does not itself carry: `sys.dm_db_index_usage_stats` addresses everything by `database_id`, `object_id` and `index_id`, so it is joined through `sys.objects` and `sys.schemas` for the table and schema names, and through `sys.indexes` for the index name. Two predicates are the answer to "unused" as this engine means it: `index_id > 0` excludes a heap's row, which is not an index, and the sum of the three read counters — `user_seeks`, `user_scans`, `user_lookups` — being zero says no query the engine counted has read it.

The answer is "worth reviewing", never "safe to drop". An index absent from the listing is absence of evidence, not evidence of use, and the DMV only reports the indexes it knows about. `DBCC SQLPERF('sys.dm_os_wait_stats', CLEAR)` clears some counters, but this view keeps its own schedule. Reading it needs `VIEW DATABASE STATE` (or `VIEW SERVER STATE`); without that grant the view returns only the objects the caller owns, so a caller with less privilege gets a shorter list rather than an error, and the probe cannot say so because it can ask a version, not a grant.

### Index Usage Counters

The same DMV, one slot further. `scans` is the sum of the same three read shapes — that is not a derived measurement but the same counter spelled in three parts — and `user_updates` rides the row into `extra` under the name `writes`, because an update is not a scan and the two are not interchangeable. `rows_read` and `rows_fetched` stay `None`: the view keeps no per-index row counter, and an operation is not a row. `size_bytes` stays `None` too; the DMV does not carry it. Unlike the unused listing, a zero here is a measurement, and the difference between one scan and a million is what the family exists to show.

### Runtime Metrics

`sys.dm_os_performance_counters` names what is actually being maintained on this instance, one row per counter grouped by the object that owns it. `counter_name` is projected as `name`, `cntr_value` as `value`, `cntr_type` as `kind` — the engine's own classification, so a caller can group without learning the DMV's vocabulary — and `object_name` as `source`, which is the counter group that owns it (`SQLServer:Buffer Manager` and friends). `instance_name`, the per-node or per-LRU split that makes two rows of the same counter distinguishable, travels in `extra`.

There is no schema filter, and that is deliberate: the counters describe a running instance and carry no schema column, so a filter here would refuse a correct query for a nonsensical reason. `unit` and `description` stay `None`. Reading the view needs `VIEW SERVER STATE`; without that grant it answers nothing, and a listing that silently loses every row there is a privilege statement rather than a measurement.

### Object Dependencies

`sys.sql_expression_dependencies` records, per reference, which object depends on which *named* entity. The dependent side is the referencing object — the statement joins that view to `sys.objects` on `referencing_id` and to `sys.schemas` for the schema — and the referenced side is a *name*, `referenced_entity_name`, never an id, which is why the join is on the referencing object and a second join would have to resolve the name. `type_desc` of the referencing object arrives as `dependent_type`, and `referenced_class_desc` arrives as `kind` — `OBJECT`, `COLUMN`, `TYPE` and so on.

`action` and `referenced_type` stay `None`: this view records no referential action, and no type for the referenced entity beyond the class descriptor. It is a real graph and a partial one — a foreign key is not a row here, and an object bound through dynamic SQL is invisible to it. A reference that leaves the database is not filtered out: the row still names the entity, and its server or database qualifier is not in the projection. Naming an object narrows the answer to its dependants; omitting the name returns the whole graph for the schema.

### The two refusals

`table-stats` and `ddl` are refused by their probes on every release, and the CLI exits **2** with "not supported by this server" without sending a statement. That is a different answer from an empty list: "this server cannot be asked" is not "the table was never read", and an assembled `CREATE TABLE` would be a statement the engine never made. The roundtrip matrix in this repository keeps an explicit pin for `DDLStatementQueryStatement` with this reason.

Every family — answered or refused — is reached through the same introspector, sync and async alike:

```python
backend.introspect_and_adapt()

if backend.dialect.supports_unused_indexes_detection():
    for index in backend.introspector.list_unused_indexes():
        print(f"{index.table_name}.{index.index_name}")

for edge in backend.introspector.list_object_dependencies("orders"):
    print(f"{edge.dependent} -> {edge.referenced} ({edge.kind})")
```

## Data Families

The three data families measure the rows rather than read a catalogue. SQL Server publishes statistics, and they are the reason `column-profiles` is worth a paragraph rather than a sentence: `sys.stats` names a *statistics object*, `sys.stats_columns` maps that object to one or more columns, and `sys.dm_db_stats_properties` reports what the last update of that object measured — `rows`, `rows_sampled`, `steps`, `modification_counter`, `last_updated`, `persisted_sample_percent`. The key is the object, never the column. A single-column statistics object is a fair proxy for its column, but a two-column one describes the pair's leading prefix, and the same column can appear in several objects with different samples, so summing or picking one would invent a per-column fact the catalogue does not hold.

What is missing is sharper than what is keyed oddly. There is no per-column null count anywhere in the catalogue — nullability is a *declaration* in `sys.columns`, never a measurement — and no per-column distinct count either. `sys.dm_db_stats_histogram` (2016+) reports `range_high_key`, `equal_rows` and `distinct_range_rows` per step of one object, which is a bucket summary for that object's leading column, not a count of the values in a column. The one figure the catalogue could contribute, `last_updated`, would be the vintage of a statistics object, not of the profile, and this family's rule is that a figure travels with the source and vintage that produced it. A profile that mixed a sampled estimate with exact counts would have to be labelled with one source it does not deserve.

So all five figures come from one place, and it is the rows: exact, and paid for in time.

| Family | Method | Price |
|--------|--------|-------|
| Column profiles | `list_column_data_profiles(table)` | One pass over the table per column |
| Value samples | `sample_column_values(table, column, limit=100)` | One grouped pass over the column, plus a sort |
| Join coverage | `estimate_join_coverage(left_table, left_column, right_table, right_column)` | Two sides read for their distinct domains, plus the intersection |

The `aggregate` label is projected *into* each row rather than stamped onto the result afterwards, so a consumer comparing a SQL Server profile with another engine's estimate can tell them apart without knowing which engine it asked.

### Column Profiles

One `UNION ALL` arm per column of the table, and each arm reads the table once: the null count is a `SUM` over a `CASE`, the distinct count `COUNT(DISTINCT ...)`, the endpoints the engine's `MIN`/`MAX`, and the row count rides the same scan as the divisor. A table of ten columns is therefore read ten times — one round trip, ten scans. `null_fraction` is derived in the parser (`null_count / row_count`), so a row count that may be zero never has to be guarded in SQL, and `SUM` over no rows is NULL: an empty table answers "not measured" for the fraction rather than `0.0`, while `distinct_count` and `row_count` are `0`, which are measurements.

The arms are rendered individually and joined by the set operator's word — the one place in this module where a set operator is written as text — because a column list known only at run time has no operand to represent it, and each arm remains a real statement with its own parameters, concatenated in arm order. An empty column list answers with no rows.

Three type decisions are written into the projection rather than left to the reader:

- **`COUNT_BIG` and `BIGINT`.** SQL Server's `SUM` and `COUNT` return `INT`, so a table with more than 2,147,483,647 rows — exactly the table worth profiling — would overflow the very counts the profile exists to report. The null flag is cast to `BIGINT` before it is summed, and the row count is `COUNT_BIG(*)`.
- **Endpoints cast to `NVARCHAR(MAX)`.** A `UNION ALL` resolves *one* result type per column position by data-type precedence and implicitly converts the other arms to it, so the `min_value` slot would have to hold an `int` from one arm and a `varchar` from another: `int` wins, and the text value is converted to a number, which fails. A `decimal` beside a `datetime` fails the same way in the other direction. Nothing in the formatter knows a column's declared type, so there is no per-type cast to choose; text is the one target every scalar column converts to. The figures are exact; the Python types are the union's, and a `datetime` endpoint renders without its sub-minute part because that is what SQL Server's style-free conversion produces.
- **The label is `NVARCHAR(128)`.** SQL Server's `CHAR` and `NVARCHAR` default to length 1 in a `CAST`, which would truncate the word `aggregate` to its first character.

The column name is also bound rather than written into the statement, because a non-prefixed literal would be typed with the database's code page and an identifier outside that page would arrive as question marks; a parameter is typed Unicode by the driver.

A table holding an `xml`, `text`/`ntext`/`image` or CLR-typed column cannot be profiled this way at all: SQL Server refuses `MIN` and `MAX` on those types, and the statement fails rather than answering a partial profile. That is the honest limit of an aggregate, and it is a limit of the *statement*, not of the capability probe.

### Value Samples

A `GROUP BY` over the column plus a sort of the groups — the same order of cost as the profile, which is why the two are separate calls. `ORDER BY COUNT_BIG(*) DESC` is what makes the answer "the most frequent values" rather than "the first values", and ties break by the value so two runs of the same query agree. `COUNT_BIG` rather than `COUNT` for the same overflow reason as the profile; `frequency` stays `None` because the engine reports a count and the denominator is the row count the profile carries.

The cap rides `OFFSET 0 ROWS FETCH NEXT n ROWS ONLY`, which is why the probe has a 2012 floor. `n` is an integer the statement carries, so no caller text is spliced into the statement. Only `value` and `count` are projected. `GROUP BY` groups NULLs, so a column that contains NULL has an entry whose `value` is `None`, and it is usually the most frequent one — NULL is a member of the domain in this listing.

### Join Coverage

Both fractions come from one statement. For each side, the numerator counts the distinct values that also occur on the other side — a `COUNT_BIG(*)` over a derived `DISTINCT` — and the denominator counts that side's distinct non-NULL values. Distinct on both sides is what makes the figure a coverage of values rather than of rows: a key repeated a thousand times that matches once would otherwise read as well covered. NULLs are excluded from both halves explicitly; a `DISTINCT` would count NULL as one value and credit a match that can never join. `NULLIF(..., 0)` makes a column with nothing to match answer NULL rather than `0.0`, so "nothing matched" and "nothing to match" stay distinct.

The numerator is multiplied by `1.0` before it is divided, and that is not decoration: SQL Server divides two integers with integer division, so `COUNT(*) / COUNT(DISTINCT ...)` would answer 0 or 1 and lose every fraction between them. The multiplier makes the division decimal, which is exact for these counts rather than approximate. Collations are not reconciled — the engine compares the two columns under whichever collation applies to the comparison, so values the database would treat as equal may be counted as distinct, and across mismatched collations the fractions are a *lower* bound, never an upper one. The price is the two sides read for their distinct domains plus the intersection, which is why this is a call of its own and never part of a profile.

```python
profiles = backend.introspector.list_column_data_profiles("orders")
for profile in profiles:
    print(profile.column_name, profile.null_fraction, profile.distinct_count,
          profile.row_count, profile.source)

samples = backend.introspector.sample_column_values("orders", "status", limit=20)
for sample in samples:
    print(sample.value, sample.count)    # value is None when NULL is a group

coverage = backend.introspector.estimate_join_coverage(
    "orders", "customer_id",
    "customers", "id",
)
print(coverage.left_coverage, coverage.right_coverage)
```

## Version and Availability Floors

Two limits decide whether an operational or data family can answer at all, and neither is a property of the query text.

| Family | Floor | What a missing floor looks like |
|--------|-------|---------------------------------|
| `unused-indexes`, `index-stats`, `runtime` | SQL Server 2005 (version 9.0), where the DMVs arrive | probe `False`; the CLI exits 2 without running the query |
| `dependencies` | SQL Server 2008 (version 10.0), where `sys.sql_expression_dependencies` arrives | probe `False`; the CLI exits 2 |
| `value-samples` | SQL Server 2012 (version 11.0), where `OFFSET ... FETCH` parses | probe `False`; the CLI exits 2 |
| `table-stats`, `ddl` | none — no release answers them | probe `False` on every version; the CLI exits 2 |
| every other family | none established here | — |

The floors are asked of the version accessor, not left to a runtime syntax error: a server below one of them is refused at the capability question with "cannot answer", which is a different and truer answer than a query that fails to parse. Every release this repository tests against — 2017, 2019, 2022 and 2025 — is well past all three, so the gates change nothing there and keep an older server from an execution error.

A probe answering `False` is "the question cannot be asked here", not "nothing was used". It does not say that no index was read or that the database has no indexes: it says the server cannot be asked. `False` lets a caller take its fallback knowingly; the empty list is reserved for a question that was asked and had nothing to report.

The probes do not test grants. No privilege floor is established here: a probe answers about the server and its settings, not about the account's privileges. Two of the DMVs need one — `VIEW DATABASE STATE` for the index usage view, `VIEW SERVER STATE` for the performance counters — and without it the engine answers a short list or nothing at all, not an error. That is an answer about what the caller may see, and the probe said `True` because the server can answer, not because this account may ask.

## Command Line Introspection

```bash
# Schemas and their owners, then the tables of the connected database
python -m rhosocial.activerecord.backend.impl.sqlserver introspect schemas --database mydb
python -m rhosocial.activerecord.backend.impl.sqlserver introspect tables --database mydb

# One table's columns, and its MS_Description properties
python -m rhosocial.activerecord.backend.impl.sqlserver introspect columns orders --database mydb
python -m rhosocial.activerecord.backend.impl.sqlserver introspect extended-properties orders --database mydb

# Operational readings
python -m rhosocial.activerecord.backend.impl.sqlserver introspect unused-indexes --database mydb
python -m rhosocial.activerecord.backend.impl.sqlserver introspect index-stats --database mydb
python -m rhosocial.activerecord.backend.impl.sqlserver introspect runtime --database mydb
python -m rhosocial.activerecord.backend.impl.sqlserver introspect dependencies orders --database mydb

# Exact profiles over the rows
python -m rhosocial.activerecord.backend.impl.sqlserver introspect column-profiles orders --database mydb
python -m rhosocial.activerecord.backend.impl.sqlserver introspect value-samples orders \
  --column status --limit 20 --database mydb

# The two families this engine does not answer are refused after connecting, exit 2
python -m rhosocial.activerecord.backend.impl.sqlserver introspect table-stats --database mydb
```

### Introspection Types

| Type | Description | Name |
|------|-------------|------|
| `tables` | User tables and views, plus system tables with `--include-system` | not accepted |
| `views` | List all views, or describe one | optional (view) |
| `columns` | Column information of one table | required (table) |
| `indexes` | Index information of one table | required (table) |
| `foreign-keys` | Foreign keys of one table | required (table) |
| `extended-properties` | `MS_Description` and friends on one table | required (table) |
| `triggers` | All triggers, or one table's | optional (table) |
| `database` | Name, product version and collation | not accepted |
| `procedures` | Stored procedures in `dbo` | not accepted |
| `functions` | User-defined functions in `dbo` | not accepted |
| `sequences` | Sequences in `dbo` | not accepted |
| `schemas` | Schemas and their owners | not accepted |
| `unused-indexes` | Indexes with no recorded read, from 2005 | not accepted |
| `table-stats` | Per-table usage counters — refused on every version | not accepted |
| `runtime` | Instance performance counters | not accepted |
| `index-stats` | Per-index usage counters, from 2005 | not accepted |
| `dependencies` | By-name dependency edges, from 2008 | optional (table) |
| `ddl` | The DDL that recreates one object — refused on every version | required (table) |
| `column-profiles` | What each column of a table holds | required (table) |
| `value-samples` | Most frequent values of one column | required (table), plus `--column` |
| `join-coverage` | Overlap of two columns' value domains | not accepted; four flags required |

The nine operational and data families are the set the other CLIs ask for too, and each one names the probe that answers for it here — which is not automatically the same answer it gives elsewhere. `views NAME` is a *view* name and `triggers NAME` is a *table* name: the two are not the same kind of argument, which is why the rule table names both. A name the type cannot use is refused (exit 2) rather than ignored; a missing required name or flag is an incomplete invocation (exit 1); a flag the type does not read is refused (exit 2). A `views` name or an `extended-properties` name that answers nothing is reported as "not found" (exit 1), and for extended properties the table is first checked against the catalogue, because a table with no `MS_Description` and a table that is not there both answer with no rows. `ddl` and `join-coverage` answering `None` — "the engine will not produce a text", "the overlap could not be measured" — also leave with 1 rather than printing a row of nulls a reader would take for a measurement.

`--limit` is forwarded to `sample_column_values()` only when it is given; without it the introspector's own default answers (`VALUE_SAMPLE_LIMIT`, 100), so the number is not written in two places. `--include-system` changes the table listing; the view listing reads `INFORMATION_SCHEMA.VIEWS`, which holds no server-owned row, so the flag has nothing to add there. `column-profiles` writes one note to stderr saying the profiles are aggregated from the rows themselves and paid for with a full scan per column, so a caller piping JSON to a consumer still sees where the numbers came from.

### Output and connection

`-o table` (default, rich), `json`, `csv` and `tsv` are available for every type; `--rich-ascii` switches the table borders. Connection parameters can be given as flags or as environment variables:

| Flag | Environment variable | Default |
|------|----------------------|---------|
| `--host` | `SQLSERVER_HOST` | `localhost` |
| `--port` | `SQLSERVER_PORT` | `1433` |
| `--database` | `SQLSERVER_DATABASE` | required for introspection |
| `--user` / `--username` | `SQLSERVER_USERNAME` | `sa` |
| `--password` | `SQLSERVER_PASSWORD` | empty |
| `--driver` | `SQLSERVER_DRIVER` | `ODBC Driver 18 for SQL Server` |

`--trusted-connection` switches to Windows authentication. `--ssl` selects one of `auto`, `require`, `verify-ca`, `verify-full` and `disabled`, and `--encrypt`/`--no-encrypt` plus `--trust-server-certificate`/`--no-trust-server-certificate` take precedence over it.

A named connection profile (`--named-connection`) may stand in for `--database` when one is configured. `--async` runs the same command through `AsyncSQLServerBackend`; every family is asked the same way and the answers are the same.
