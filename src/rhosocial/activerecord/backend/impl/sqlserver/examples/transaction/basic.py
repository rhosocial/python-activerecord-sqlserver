"""
Basic transaction with context manager for automatic commit/rollback.
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
    password=os.environ.get('SQLSERVER_PASSWORD', 'Password123!'),
    driver=os.environ.get('SQLSERVER_DRIVER', 'SQL Server'),
    encrypt=os.environ.get('SQLSERVER_ENCRYPT', 'false').lower() == 'true',
    trust_server_certificate=(
        os.environ.get('SQLSERVER_TRUST_SERVER_CERTIFICATE', 'true').lower() == 'true'
    ),
    autocommit=False,
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

create_table = CreateTableExpression(
    dialect=dialect,
    table_name='txn_users',
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
sql, params = create_table.to_sql()
backend.execute(sql, params, options=ddl_options)

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
from rhosocial.activerecord.backend.expression import InsertExpression, ValuesSource
from rhosocial.activerecord.backend.expression.core import Literal

# Use transaction context manager for automatic commit/rollback
# If an exception occurs, the transaction is automatically rolled back
with backend.transaction():
    insert_expr = InsertExpression(
        dialect=dialect,
        into='txn_users',
        columns=['name'],
        source=ValuesSource(dialect, [[Literal(dialect, 'Alice')]]),
    )
    sql, params = insert_expr.to_sql()
    backend.execute(sql, params)
    
    insert_expr2 = InsertExpression(
        dialect=dialect,
        into='txn_users',
        columns=['name'],
        source=ValuesSource(dialect, [[Literal(dialect, 'Bob')]]),
    )
    sql, params = insert_expr2.to_sql()
    backend.execute(sql, params)
    
    print("Both inserts executed within transaction")

# Transaction is automatically committed when exiting the context
print("Transaction committed")

# ============================================================
# SECTION: Execution (verify results)
# ============================================================
from rhosocial.activerecord.backend.expression import QueryExpression, TableExpression, Column

query = QueryExpression(
    dialect=dialect,
    select=[Column(dialect, 'id'), Column(dialect, 'name')],
    from_=TableExpression(dialect, 'txn_users'),
)
sql, params = query.to_sql()
dql_options = ExecutionOptions(stmt_type=StatementType.DQL)
result = backend.execute(sql, params, options=dql_options)
print(f"Rows after transaction: {len(result.data) if result.data else 0}")
for row in result.data or []:
    print(f" {row}")

# ============================================================
# SECTION: Teardown (necessary for execution, reference only)
# ============================================================
from rhosocial.activerecord.backend.expression import DropTableExpression

drop_expr = DropTableExpression(dialect=dialect, table_name='txn_users', if_exists=True)
sql, params = drop_expr.to_sql()
backend.execute(sql, params, options=ddl_options)

backend.disconnect()
