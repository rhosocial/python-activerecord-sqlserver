# expression tests

SQL Server expression formatting: serialization round trips over all expression classes, OFFSET FETCH / OUTPUT clause / CREATE INDEX / JOIN formatting and JSON expression rendering (JSON_VALUE, JSON_QUERY, ISJSON, ...).

## Key files

- `test_expression_roundtrip_all.py` — serialization round trips
- `test_expressions.py` — OFFSET FETCH, OUTPUT, index, join formatting
- `test_json_expressions.py` — JSON function expressions
