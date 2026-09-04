# ddl tests

SQL Server DDL coverage: ALTER TABLE IF [NOT] EXISTS handling (DROP COLUMN/CONSTRAINT IF EXISTS, 2016+), auto-increment / defaults regressions, expression-level CreateTableExpression.diff() for the SQL Server dialect (rebuild paths), the absence of CREATE TABLE ... LIKE plus the SELECT INTO alternative and temporary tables.

## Key files

- `test_alter_table_if_exists_backend.py` — IF [NOT] EXISTS modifier capabilities
- `test_auto_increment_ddl.py` — auto-increment regressions
- `test_create_table_expression_diff.py` — CreateTableExpression.diff() with SQL Server rebuild paths
- `test_create_table_like.py` — LIKE unsupported; like_table semantics
- `test_ddl_features.py` — SELECT INTO and temporary tables
