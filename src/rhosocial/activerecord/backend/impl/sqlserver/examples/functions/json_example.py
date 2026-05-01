# examples/functions/json_example.py
"""
SQL Server JSON functions example.

Demonstrates using function factories for JSON operations.
"""
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.functions import (
    json_value,
    json_query,
    is_json,
    json_object,
    json_array,
)
from rhosocial.activerecord.backend.expression import QueryExpression, Column, TableExpression

dialect = SQLServerDialect(version=(16, 0, 0))

print("=" * 60)
print("SQL Server JSON Function Examples")
print("=" * 60)

print("\n1. JSON_VALUE - Extract value from JSON:")
result = json_value(dialect, "data", "$.name")
sql, params = result.to_sql()
print(f"  SQL: {sql}")
print(f"  Params: {params}")

print("\n2. JSON_QUERY - Extract JSON object/array:")
result = json_query(dialect, "data", "$.address")
sql, params = result.to_sql()
print(f"  SQL: {sql}")

print("\n3. ISJSON - Check if valid JSON:")
result = is_json(dialect, "data")
sql, params = result.to_sql()
print(f"  SQL: {sql}")

print("\n4. JSON_OBJECT - Create JSON object (SQL Server 2022+):")
result = json_object(dialect, {"name": "John", "age": 30})
sql, params = result.to_sql()
print(f"  SQL: {sql}")

print("\n5. JSON_ARRAY - Create JSON array (SQL Server 2022+):")
result = json_array(dialect, "a", "b", "c")
sql, params = result.to_sql()
print(f"  SQL: {sql}")

print("\n6. Using functions in a query:")
query = QueryExpression(
    dialect=dialect,
    select=[
        Column(dialect, "id"),
        json_value(dialect, "data", "$.name").as_("name"),
        json_value(dialect, "data", "$.age").as_("age"),
    ],
    from_=TableExpression(dialect, "users"),
)
sql, params = query.to_sql()
print(f"  SQL: {sql}")