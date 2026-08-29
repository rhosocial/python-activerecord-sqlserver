# src/rhosocial/activerecord/backend/impl/sqlserver/examples/named_expressions/order_expressions.py
"""
Order-related named query examples.

This file demonstrates how to define named queries (Named Query) for encapsulating
reusable SQL query logic. Named queries are backend features, independent of
ActiveRecord models.

SQL Server notes
----------------
Unlike the SQLite examples, this module does NOT create any tables or data at
import time. Importing this module must stay side-effect free (the CLI imports
it for --list/--describe without a live database). Use ``prepare_orders_demo``
to create the schema and seed data, then the CLI named-expression /
named-procedure commands to execute the queries.
"""

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
from rhosocial.activerecord.backend.expression import (  # noqa: E402
    Column,
    Literal,
    QueryExpression,
    TableExpression,
)


def get_order(dialect, order_id: int):
    """Get order details by ID."""
    return QueryExpression(
        dialect,
        select=[Column(dialect, "id"), Column(dialect, "status"), Column(dialect, "user_id")],
        from_=TableExpression(dialect, "orders"),
        where=Column(dialect, "id") == Literal(dialect, order_id),
    )


def check_inventory(dialect, order_id: int):
    """Check available inventory for an order."""
    return QueryExpression(
        dialect,
        select=[Column(dialect, "available")],
        from_=TableExpression(dialect, "inventory"),
        where=Column(dialect, "order_id") == Literal(dialect, order_id),
    )


def reserve_inventory(dialect, order_id: int):
    """Reserve inventory for an order."""
    return QueryExpression(
        dialect,
        select=[Column(dialect, "id"), Column(dialect, "available")],
        from_=TableExpression(dialect, "inventory"),
        where=Column(dialect, "order_id") == Literal(dialect, order_id),
    )


def send_notification(dialect, user_id: int, type: str):
    """Send notification to a user."""
    return QueryExpression(
        dialect,
        select=[Column(dialect, "id")],
        from_=TableExpression(dialect, "notifications"),
        where=Column(dialect, "user_id") == Literal(dialect, user_id),
    )


def process_payment(dialect, order_id: int, amount: float):
    """Process payment for an order."""
    return QueryExpression(
        dialect,
        select=[Column(dialect, "status"), Column(dialect, "transaction_id")],
        from_=TableExpression(dialect, "payments"),
        where=Column(dialect, "order_id") == Literal(dialect, order_id),
    )


def release_inventory(dialect, order_id: int):
    """Release reserved inventory."""
    return QueryExpression(
        dialect,
        select=[Column(dialect, "id")],
        from_=TableExpression(dialect, "inventory"),
        where=Column(dialect, "order_id") == Literal(dialect, order_id),
    )


def create_order_record(dialect, order_id: int, user_id: int, amount: float):
    """Create an order record."""
    return QueryExpression(
        dialect,
        select=[Column(dialect, "id"), Column(dialect, "created_at")],
        from_=TableExpression(dialect, "order_records"),
        where=Column(dialect, "order_id") == Literal(dialect, order_id),
    )


def confirm_inventory(dialect, order_id: int):
    """Confirm inventory (final confirmation)."""
    return QueryExpression(
        dialect,
        select=[Column(dialect, "id")],
        from_=TableExpression(dialect, "inventory"),
        where=Column(dialect, "order_id") == Literal(dialect, order_id),
    )


# ============================================================
# SECTION: Setup (necessary for execution, reference only)
# ============================================================
# The setup below is import-safe: it only prepares the schema when this module
# is run directly, so importing it for --list/--describe never touches a database.

_PREPARE_SCRIPT = """
IF OBJECT_ID(N'dbo.order_records', N'U') IS NOT NULL DROP TABLE dbo.order_records;
IF OBJECT_ID(N'dbo.payments', N'U') IS NOT NULL DROP TABLE dbo.payments;
IF OBJECT_ID(N'dbo.notifications', N'U') IS NOT NULL DROP TABLE dbo.notifications;
IF OBJECT_ID(N'dbo.inventory', N'U') IS NOT NULL DROP TABLE dbo.inventory;
IF OBJECT_ID(N'dbo.orders', N'U') IS NOT NULL DROP TABLE dbo.orders;
CREATE TABLE dbo.orders (
    id INT PRIMARY KEY,
    status NVARCHAR(20) DEFAULT 'pending',
    user_id INT NOT NULL
);
CREATE TABLE dbo.inventory (
    id INT PRIMARY KEY,
    order_id INT NOT NULL,
    available INT DEFAULT 0
);
CREATE TABLE dbo.notifications (
    id INT PRIMARY KEY,
    user_id INT NOT NULL,
    type NVARCHAR(20)
);
CREATE TABLE dbo.payments (
    id INT PRIMARY KEY,
    order_id INT NOT NULL,
    status NVARCHAR(20),
    transaction_id NVARCHAR(40)
);
CREATE TABLE dbo.order_records (
    id INT PRIMARY KEY,
    order_id INT NOT NULL,
    created_at NVARCHAR(30)
);
INSERT INTO dbo.orders (id, status, user_id) VALUES (1, 'pending', 100);
INSERT INTO dbo.inventory (id, order_id, available) VALUES (1, 1, 10);
"""


def prepare_orders_demo(backend) -> None:
    """Create the demo schema and seed data.

    Drops any existing demo tables first so the demo is idempotent.

    Args:
        backend: Connected SQLServerBackend instance.
    """
    backend.executescript(_PREPARE_SCRIPT)


# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
if __name__ == "__main__":
    import os

    from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend, SQLServerConnectionConfig
    from rhosocial.activerecord.backend.options import ExecutionOptions
    from rhosocial.activerecord.backend.schema import StatementType

    config = SQLServerConnectionConfig(
        host=os.getenv("SQLSERVER_HOST", "127.0.0.1"),
        port=int(os.getenv("SQLSERVER_PORT", "1433")),
        username=os.getenv("SQLSERVER_USERNAME", "sa"),
        password=os.getenv("SQLSERVER_PASSWORD", "Password123!"),
        database=os.getenv("SQLSERVER_DATABASE", "master"),
        driver=os.getenv("SQLSERVER_DRIVER", "ODBC Driver 17 for SQL Server"),
        encrypt=False,
        trust_server_certificate=True,
    )
    backend = SQLServerBackend(connection_config=config)
    backend.connect()
    dialect = backend.dialect

    prepare_orders_demo(backend)

    print("=== Named Query Examples ===\n")
    query = get_order(dialect, order_id=1)
    sql, params = query.to_sql()
    print(f"get_order SQL: {sql}")
    print(f"Params: {params}\n")

    options = ExecutionOptions(stmt_type=StatementType.DQL)
    result = backend.execute(sql, params, options=options)
    print(f"Execution result: {result.data}\n")

    backend.disconnect()