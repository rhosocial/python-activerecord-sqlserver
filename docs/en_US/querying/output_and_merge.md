# OUTPUT, MERGE and Query Dialect

This chapter covers the parts of DML and SELECT where SQL Server's dialect
differs from portable SQL. Core's query builder is unchanged; what differs is
the T-SQL the dialect renders and a handful of capability answers.

## OUTPUT / RETURNING

SQL Server returns affected rows with the `OUTPUT` clause. The backend declares
`supports_output_clause() == True` and renders DML through the OUTPUT path, so a
`RETURNING`-style call maps onto native T-SQL rather than a second SELECT.

Expressions live in `expression/output.py` and `expression/dml.py`, with the
mixin in `mixins/output.py` / `mixins/returning.py`. A typical statement returns
the inserted identity value:

```sql
INSERT INTO [users] ([name]) OUTPUT INSERTED.[id] VALUES (?);
```

```python
sql, params = insert_expr.to_sql()   # preview before running
result = backend.execute(sql, params, options=dml_options)
print(result.data)                   # rows projected by OUTPUT
```

> 💡 *AI prompt: "Why does the backend use OUTPUT to return generated keys, and how does that differ from running a second SELECT?"*

## MERGE

`supports_merge_statement()` is `True` — SQL Server has had `MERGE` since 2008.
The `merge` mixin and `expression/` support `MERGE ... WHEN MATCHED / WHEN NOT
MATCHED`, with backend-local extras `supports_merge_output()` and
`supports_merge_holdlock()` controlling whether `OUTPUT` and the `HOLDLOCK`
hint can be attached. `MERGE` is the backend's native upsert route.

## Locking

SQL Server has no `FOR UPDATE` syntax, but the backend still answers
`supports_for_update() == True`: it renders row locks as table hints.

```sql
SELECT ... FROM [users] WITH (UPDLOCK, ROWLOCK);
```

`skip_locked` adds `READPAST` and is gated to SQL Server 2019+ via
`supports_for_update_skip_locked()`. A lock strength other than `UPDATE` raises
`UnsupportedFeatureError` at render time; the refusal names the SQL phrase it
cannot express.

## Pagination

`format_limit_offset()` renders `OFFSET ... FETCH NEXT ... ROWS ONLY` (with the
required `ORDER BY`), gated to SQL Server 2012+. Two portability flags are
explicitly `False`:

- `supports_fetch_with_ties()` — `WITH TIES` exists only with `TOP`, not with
  `OFFSET FETCH`.
- `supports_nulls_first_last()` — SQL Server has no `NULLS FIRST` / `NULLS LAST`
  syntax.

`TOP`, `TABLESAMPLE`, `PIVOT` / `UNPIVOT`, window functions, CTEs (including
recursive), grouping sets, lateral constructs and set operations are all part
of the dialect; the corresponding `supports_*` answers live in the mixins.

## JSON, XML and functions

- **JSON is stored as text** (`NVARCHAR(MAX)`); there is no native JSON column
  type. `supports_json_type()` answers from the 2016 floor because that is when
  the JSON *functions* arrive.
- There is no `->` operator: JSON extraction renders as `JSON_VALUE(col, 'path')`.
- `supports_json_table()` is **`False`** even on recent servers. The formatter
  refuses unconditionally and points at `OPENJSON`, which is fully implemented
  as `SQLServerOpenJsonExpression`. Advertising `JSON_TABLE` would promise a
  statement the backend cannot render.
- `XML`, `HIERARCHYID`, spatial and math/string/date functions are supplied as
  native expressions under `expression/` and `functions/`.

## Query hints and diagnostics

`WITH (...)` table hints, `OPTION (...)` query hints and `INDEX` / `FORCESEEK`
style hints are available through `mixins/table_hint.py` and
`expression/option_hint.py`. `EXPLAIN` maps to execution-plan output, with
`supports_explain_analyze()` plus one switch per plan format
(`supports_explain_format_text()` / `supports_explain_format_xml()`) answering
for the supported forms; the other format switches and the option switches
(`verbose` / `costs` / `buffers` / `timing` / `settings` / `wal`) are `False`.
