"""
JSON operations using SQL Server 2016+ JSON functions.

SQL Server doesn't have a native JSON type but provides functions
for working with JSON data stored in NVARCHAR columns.
"""

import os

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
from rhosocial.activerecord.backend.impl.sqlserver import (
    SQLServerBackend,
    SQLServerConnectionConfig,
)

config = SQLServerConnectionConfig(
    host=os.environ.get('SQLSERVER_HOST', 'localhost'),
    port=int(os.environ.get('SQLSERVER_PORT', '11434')),
    database=os.environ.get('SQLSERVER_DATABASE', 'test_db'),
    username=os.environ.get('SQLSERVER_USERNAME', 'sa'),
    password=os.environ.get('SQLSERVER_PASSWORD', ''),
    driver=os.environ.get('SQLSERVER_DRIVER', 'SQL Server'),
    encrypt=os.environ.get('SQLSERVER_ENCRYPT', 'false').lower() == 'true',
    trust_server_certificate=(
        os.environ.get('SQLSERVER_TRUST_SERVER_CERTIFICATE', 'true').lower() == 'true'
    ),
)
backend = SQLServerBackend(connection_config=config)
backend.connect()
dialect = backend.dialect

from rhosocial.activerecord.backend.expression import CreateTableExpression
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

ddl_options = ExecutionOptions(stmt_type=StatementType.DDL)
dql_options = ExecutionOptions(stmt_type=StatementType.DQL)

create_table = CreateTableExpression(
    dialect=dialect,
    table='json_data',
    columns=[
        ColumnDefinition('id', 'INT', constraints=[
            ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
            ColumnConstraint(ColumnConstraintType.NOT_NULL, is_auto_increment=True),
        ]),
        ColumnDefinition('data', 'NVARCHAR(MAX)'),
    ],
    if_not_exists=True,
)
sql, params = create_table.to_sql()
backend.execute(sql, params, options=ddl_options)

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
from rhosocial.activerecord.backend.expression import InsertExpression, ValuesSource
from rhosocial.activerecord.backend.expression.core import Literal

# Insert JSON data as string literal
# Note: SQL Server 2022+ supports JSON_OBJECT function
json_literal = '{"name": "John", "age": 30, "hobbies": ["reading", "coding"]}'

insert_expr = InsertExpression(
    dialect=dialect,
    into='json_data',
    columns=['data'],
    source=ValuesSource(dialect, [[Literal(dialect, json_literal)]]),
)
sql, params = insert_expr.to_sql()
backend.execute(sql, params)
print("JSON data inserted")

# ============================================================
# SECTION: Execution (query JSON data)
# ============================================================
# For JSON queries, we use raw SQL since JSON_VALUE/JSON_QUERY
# are SQL Server specific functions not yet available as expressions
from rhosocial.activerecord.backend.expression import QueryExpression, TableExpression, Column

# Basic query to get the JSON data
query = QueryExpression(
    dialect=dialect,
    select=[Column(dialect, 'id'), Column(dialect, 'data')],
    from_=TableExpression(dialect, 'json_data'),
)
sql, params = query.to_sql()
result = backend.execute(sql, params, options=dql_options)
print(f"Stored JSON data:")
for row in result.data or []:
    print(f" ID={row['id']}: {row['data']}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
from rhosocial.activerecord.backend.expression import DropTableExpression

drop_expr = DropTableExpression(dialect=dialect, table='json_data', if_exists=True)
sql, params = drop_expr.to_sql()
backend.execute(sql, params, options=ddl_options)

backend.disconnect()
