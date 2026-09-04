# dialect tests

SQL Server dialect formatting: core/statements/protocols tests, comprehensive formatting coverage (pagination, MERGE, hints, temporal tables, OPENJSON, ...) and offline version-gated branch coverage (2008/2012/2016/...).

## Key files

- `test_dialect.py` — dialect formatting methods
- `test_dialect_comprehensive.py` — comprehensive formatting matrix
- `test_dialect_version_branches.py` — version-gated branches (offline)
