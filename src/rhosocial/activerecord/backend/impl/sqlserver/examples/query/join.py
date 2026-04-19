"""
JOIN multiple tables.
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
    port=int(os.environ.get('SQLSERVER_PORT', '11434')),
    database=os.environ.get('SQLSERVER_DATABASE', 'test_db'),
    username=os.environ.get('SQLSERVER_USERNAME', 'sa'),
    password=os.environ.get('SQLSERVER_PASSWORD', 'Password123!'),
    driver=os.environ.get('SQLSERVER_DRIVER', 'SQL Server'),
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
)

ddl_options = ExecutionOptions(stmt_type=StatementType.DDL)

users_table = CreateTableExpression(
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
sql, params = users_table.to_sql()
backend.execute(sql, params, options=ddl_options)

orders_table = CreateTableExpression(
    dialect=dialect,
    table_name='join_orders',
    columns=[
        ColumnDefinition('id', 'INT', constraints=[
            ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
            ColumnConstraint(ColumnConstraintType.NOT_NULL, is_auto_increment=True),
        ]),
        ColumnDefinition('user_id', 'INT'),
        ColumnDefinition('amount', 'DECIMAL(10,2)'),
    ],
    table_constraints=[
        TableConstraint(
            constraint_type=TableConstraintType.FOREIGN_KEY,
            columns=['user_id'],
            foreign_key_table='join_users',
            foreign_key_columns=['id'],
        ),
    ],
    if_not_exists=True,
)
sql, params = orders_table.to_sql()
backend.execute(sql, params, options=ddl_options)

users = [('Alice',), ('Bob',)]
for user in users:
    insert_expr = InsertExpression(
        dialect=dialect,
        into='join_users',
        columns=['name'],
        source=ValuesSource(dialect, [[Literal(dialect, v) for v in user]]),
    )
    sql, params = insert_expr.to_sql()
    backend.execute(sql, params)

orders = [
    (1, 100.0),
    (1, 200.0),
    (2, 150.0),
]
for row in orders:
    insert_expr = InsertExpression(
        dialect=dialect,
        into='join_orders',
        columns=['user_id', 'amount'],
        source=ValuesSource(dialect, [[Literal(dialect, v) for v in row]]),
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
    JoinExpression,
)
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate

join_expr = JoinExpression(
    dialect=dialect,
    left_table=TableExpression(dialect, 'join_users', alias='u'),
    right_table=TableExpression(dialect, 'join_orders', alias='o'),
    join_type='LEFT JOIN',
    condition=ComparisonPredicate(
        dialect,
        '=',
        Column(dialect, 'id', 'u'),
        Column(dialect, 'user_id', 'o'),
    ),
)

query = QueryExpression(
    dialect=dialect,
    select=[
        Column(dialect, 'name', 'u'),
        Column(dialect, 'amount', 'o'),
    ],
    from_=join_expr,
)

sql, params = query.to_sql()
print(f"SQL: {sql}")
print(f"Params: {params}")

# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
dql_options = ExecutionOptions(stmt_type=StatementType.DQL)
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
