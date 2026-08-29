# src/rhosocial/activerecord/backend/impl/sqlserver/examples/named_procedures/order_workflow.py
"""
Order processing workflow example - demonstrates Named Procedure flowchart capabilities.

This procedure includes:
- Conditional branching (inventory check)
- Parallel execution (inventory reservation + notification)
- Conditional rollback (payment failure)

Named Procedure is a backend feature, independent of ActiveRecord models.

SQL Server notes
----------------
This module is import-safe: no database connection is made at import time.
Prepare the schema and seed data with
``rhosocial.activerecord.backend.impl.sqlserver.examples.named_expressions.order_expressions.prepare_orders_demo``
before running the procedure.
"""

# ============================================================
# SECTION: Business Logic (the pattern to learn)
# ============================================================
from rhosocial.activerecord.backend.named_expression import (  # noqa: E402
    Procedure,
    ProcedureContext,
    ParallelStep,
)


class OrderProcessingProcedure(Procedure):
    """Complete order processing workflow.

    Flow:
    1. Query order details
    2. Check inventory (abort if insufficient)
    3. Parallel: reserve inventory + send notification
    4. Process payment (rollback inventory on failure)
    5. Create order record
    6. Final inventory confirmation
    """

    order_id: int
    user_id: int
    amount: float = 0.0

    def run(self, ctx: ProcedureContext) -> None:
        ctx.log(f"Starting order processing: {self.order_id}", "INFO")

        ctx.execute(
            "rhosocial.activerecord.backend.impl.sqlserver.examples.named_expressions.order_expressions.get_order",
            params={"order_id": self.order_id},
            bind="order",
        )

        order = ctx.scalar("order", "status")
        if order is None:
            ctx.log(f"Order {self.order_id} not found", "ERROR")
            ctx.abort("OrderProcessingProcedure", f"Order {self.order_id} not found")

        ctx.log(f"Order status: {order}", "DEBUG")

        ctx.execute(
            "rhosocial.activerecord.backend.impl.sqlserver.examples.named_expressions.order_expressions.check_inventory",
            params={"order_id": self.order_id},
            bind="inventory",
        )

        available = ctx.scalar("inventory", "available")
        if not available or available < 1:
            ctx.log("Insufficient inventory, aborting", "WARNING")
            ctx.abort("OrderProcessingProcedure", "Insufficient inventory")

        ctx.parallel(
            ParallelStep(
                "rhosocial.activerecord.backend.impl.sqlserver.examples.named_expressions.order_expressions.reserve_inventory",
                params={"order_id": self.order_id},
                bind="reserved",
            ),
            ParallelStep(
                "rhosocial.activerecord.backend.impl.sqlserver.examples.named_expressions.order_expressions.send_notification",
                params={"user_id": self.user_id, "type": "order_started"},
            ),
            max_concurrency=1,
        )

        ctx.execute(
            "rhosocial.activerecord.backend.impl.sqlserver.examples.named_expressions.order_expressions.process_payment",
            params={"order_id": self.order_id, "amount": self.amount},
            bind="payment",
        )

        payment_status = ctx.scalar("payment", "status")
        if payment_status != "success":
            ctx.log(f"Payment failed: {payment_status}, rolling back inventory", "ERROR")
            ctx.execute(
                "rhosocial.activerecord.backend.impl.sqlserver.examples.named_expressions.order_expressions.release_inventory",
                params={"order_id": self.order_id},
                output=True,
            )
            ctx.abort("OrderProcessingProcedure", f"Payment failed: {payment_status}")

        ctx.execute(
            "rhosocial.activerecord.backend.impl.sqlserver.examples.named_expressions.order_expressions.create_order_record",
            params={
                "order_id": self.order_id,
                "user_id": self.user_id,
                "amount": self.amount,
            },
            bind="order_record",
            output=True,
        )

        ctx.execute(
            "rhosocial.activerecord.backend.impl.sqlserver.examples.named_expressions.order_expressions.confirm_inventory",
            params={"order_id": self.order_id},
            output=True,
        )

        ctx.log(f"Order {self.order_id} processing complete", "INFO")


# Demo: Generate static diagram
if __name__ == "__main__":
    print("=== Order Processing Procedure ===\n")
    print("Static Diagram (Flowchart):")
    print(OrderProcessingProcedure.static_diagram("flowchart"))
    print("\nStatic Diagram (Sequence):")
    print(OrderProcessingProcedure.static_diagram("sequence"))

# ============================================================
# SECTION: Execution (run the expression)
# ============================================================
from rhosocial.activerecord.backend.named_expression import ProcedureRunner, TransactionMode  # noqa: E402

if __name__ == "__main__":
    import os

    from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend, SQLServerConnectionConfig
    from rhosocial.activerecord.backend.impl.sqlserver.examples.named_expressions.order_expressions import (
        prepare_orders_demo,
    )

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

    prepare_orders_demo(backend)

    runner = ProcedureRunner(
        "rhosocial.activerecord.backend.impl.sqlserver.examples.named_procedures.order_workflow.OrderProcessingProcedure"
    ).load()

    result = runner.run(
        backend,
        user_params={"order_id": 1, "user_id": 100, "amount": 99.99},
        transaction_mode=TransactionMode.AUTO,
    )

    print(f"Procedure completed. Aborted: {result.aborted}")
    if result.aborted:
        print(f"Abort reason: {result.abort_reason}")
    for log in result.logs:
        print(f"[{log.level}] {log.message}")

    # ============================================================
    # SECTION: Teardown (necessary for execution, reference only)
    # ============================================================
    backend.disconnect()