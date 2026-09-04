# introspection tests

SQL Server introspection coverage: the parameterized SQL builder methods of the introspector (pinning the SQL-injection hardening of every _build_*_sql method) and the SHOW compatibility parsing layer.

## Key files

- `test_introspection_sql_builders.py` — injection-hardened SQL builders
- `test_show_functionality.py` — SHOW compatibility parsing
