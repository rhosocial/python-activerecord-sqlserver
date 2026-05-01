# examples/functions/string_example.py
"""
SQL Server string functions example.

Demonstrates using function factories for string operations.
"""
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.functions import (
    string_agg,
    concat_ws,
    trim,
    string_split,
    format,
)
from rhosocial.activerecord.backend.expression import QueryExpression, Column, TableExpression

dialect = SQLServerDialect(version=(16, 0, 0))

print("=" * 60)
print("SQL Server String Function Examples")
print("=" * 60)

print("\n1. STRING_AGG - Aggregate strings:")
result = string_agg(dialect, "name", ",")
sql, params = result.to_sql()
print(f"  SQL: {sql}")

print("\n2. CONCAT_WS - Concatenate with separator:")
result = concat_ws(dialect, "-", "first", "second", "third")
sql, params = result.to_sql()
print(f"  SQL: {sql}")

print("\n3. TRIM - Trim whitespace:")
result = trim(dialect, "  text  ")
sql, params = result.to_sql()
print(f"  SQL: {sql}")

print("\n4. STRING_SPLIT - Split string into rows:")
result = string_split(dialect, "a,b,c", ",")
sql, params = result.to_sql()
print(f"  SQL: {sql}")

print("\n5. FORMAT - Format value with culture:")
result = format(dialect, "value", "C", "en-US")
sql, params = result.to_sql()
print(f"  SQL: {sql}")

print("\n6. Using functions in a query:")
query = QueryExpression(
    dialect=dialect,
    select=[
        Column(dialect, "id"),
        concat_ws(dialect, "-", "first_name", "last_name").as_("full_name"),
    ],
    from_=TableExpression(dialect, "users"),
)
sql, params = query.to_sql()
print(f"  SQL: {sql}")

print("\n7. Using STRING_SPLIT in WHERE clause:")
query = QueryExpression(
    dialect=dialect,
    select=[Column(dialect, "id")],
    from_=TableExpression(dialect, "users"),
    where=string_split(dialect, Column(dialect, "tags"), ","),
)
sql, params = query.to_sql()
print(f"  SQL: {sql}")