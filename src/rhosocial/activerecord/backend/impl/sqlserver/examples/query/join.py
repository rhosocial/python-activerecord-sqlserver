"""
JOIN multiple tables including CROSS APPLY (SQL Server specific).
"""

import os

# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
from rhosocial.activerecord.backend.impl.sqlserver import (
    SQLServerBackend,
    SQLServerConnectionConfig,
)
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

config = SQLServerConnectionConfig(
    host=os.environ.get('SQLSERVER_HOST', 'localhost'),
    port=int(os.environ.get('SQLSERVER_PORT', '1433')),
    database=os.environ.get('SQLSERVER_DATABASE', 'test_db'),
    username=os.environ.get('SQLSERVER_USERNAME', 'sa'),
    password=os.environ.get('SQLSERVER_PASSWORD', 'Password123!'),
    driver=os.environ.get('SQLSERVER_DRIVER', 'ODBC Driver 17 for SQL Server'),
    encrypt=os.environ.get('SQLSERVER_ENCRYPT', 'false').lower() == 'true',
    trust_server_certificate=(
        os.environ.get('SQLSERVER_TRUST_SERVER_CERTIFICATE', 'true').lower() == 'true'
    ),
)
backend = SQLServerBackend(connection_config=config)
backend.connect()
dialect = backend.dialect

from rhosocial.activerecord.backend.expression import (
    CreateTableExpression,
    InsertExpression,
    ValuesSource,
)
from rhosocial.activerecord.backend.expression.core import Literal
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
    TableConstraint,
    TableConstraintType,
    ForeignKeyConstraint,
)

ddl_options = ExecutionOptions(stmt_type=StatementType.DDL)
dql_options = ExecutionOptions(stmt_type=StatementType.DQL)

# Create orders table
create_orders = CreateTableExpression(
    dialect=dialect,
    table_name='join_orders',
    columns=[
        ColumnDefinition('id', 'INT', constraints=[
            ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
            ColumnConstraint(ColumnConstraintType.NOT_NULL, is_auto_increment=True),
        ]),
        ColumnDefinition('user_id', 'INT', constraints=[
            ColumnConstraint(ColumnConstraintType.NOT_NULL),
        ]),
        ColumnDefinition('amount', 'DECIMAL(10,2)'),
    ],
    if_not_exists=True,
)
sql, params = create_orders.to_sql()
backend.execute(sql, params, options=ddl_options)

# Create users table
create_users = CreateTableExpression(
    dialect=dialect,
    table_name='join_users',
    columns=[
        ColumnDefinition('id', 'INT', constraints=[
            ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
            ColumnConstraint(ColumnConstraintType.NOT_NULL, is_auto_increment=True),
        ]),
        ColumnDefinition('name', 'NVARCHAR(100)', constraints=[
            ColumnConstraint(ColumnConstraintType.NOT_NULL),
        ]),
    ],
    if_not_exists=True,
)
sql, params = create_users.to_sql()
backend.execute(sql, params, options=ddl_options)

# Insert users
for name in ['Alice', 'Bob']:
    insert_expr = InsertExpression(
        dialect=dialect,
        into='join_users',
        columns=['name'],
        source=ValuesSource(dialect, [[Literal(dialect, name)]]),
    )
    sql, params = insert_expr.to_sql()
    backend.execute(sql, params)

# Insert orders
for user_id, amount in [(1, 100.00), (1, 200.00), (2, 150.00)]:
    insert_expr = InsertExpression(
        dialect=dialect,
        into='join_orders',
        columns=['user_id', 'amount'],
        source=ValuesSource(dialect, [[Literal(dialect, user_id), Literal(dialect, amount)]]),
    )
    sql, params = insert_expr.to_sql()
    backend.execute(sql, params)

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
from rhosocial.activerecord.backend.expression import (
    QueryExpression,
    TableExpression,
    Column,
    JoinClause,
    JoinType,
)
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate

# INNER JOIN example
join_query = QueryExpression(
    dialect=dialect,
    select=[
        Column(dialect, 'u.id', alias='user_id'),
        Column(dialect, 'u.name', alias='user_name'),
        Column(dialect, 'o.id', alias='order_id'),
        Column(dialect, 'o.amount'),
    ],
    from_=TableExpression(dialect, 'join_users', alias='u'),
    joins=[
        JoinClause(
            dialect,
            join_type=JoinType.INNER,
            table=TableExpression(dialect, 'join_orders', alias='o'),
            on_condition=ComparisonPredicate(
                dialect,
                '=',
                Column(dialect, 'u.id'),
                Column(dialect, 'o.user_id'),
            ),
        ),
    ],
)

sql, params = join_query.to_sql()
print(f"SQL: {sql}")
print(f"Params: {params}")

# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
result = backend.execute(sql, params, options=dql_options)
print(f"Rows returned: {len(result.data) if result.data else 0}")
for row in result.data or []:
    print(f" {row}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
from rhosocial.activerecord.backend.expression import DropTableExpression

drop_orders = DropTableExpression(dialect=dialect, table_name='join_orders', if_exists=True)
sql, params = drop_orders.to_sql()
backend.execute(sql, params, options=ddl_options)

drop_users = DropTableExpression(dialect=dialect, table_name='join_users', if_exists=True)
sql, params = drop_users.to_sql()
backend.execute(sql, params, options=ddl_options)

backend.disconnect()
