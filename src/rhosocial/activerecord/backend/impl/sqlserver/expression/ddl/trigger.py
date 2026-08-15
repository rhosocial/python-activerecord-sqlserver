# src/rhosocial/activerecord/backend/impl/sqlserver/expression/ddl/trigger.py
"""SQL Server trigger DDL expressions.

T-SQL triggers are attached to a table and run a ``BEGIN ... END`` batch:

    CREATE TRIGGER trg ON t AFTER INSERT AS BEGIN <body> END;
    DROP TRIGGER trg;

SQL generation and version gating are delegated to the dialect's
``format_create_trigger_statement`` / ``format_drop_trigger_statement``
formatters. Bodies are passed through verbatim as raw T-SQL strings.
"""

from typing import List, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams

if TYPE_CHECKING:
    from ...dialect import SQLServerDialect


class SQLServerCreateTriggerExpression(BaseExpression):
    """SQL Server CREATE TRIGGER statement (2005+).

    Attributes:
        name: Trigger name.
        table: Table the trigger is attached to.
        timing: Either ``AFTER`` or ``INSTEAD OF``.
        events: List of ``INSERT`` / ``UPDATE`` / ``DELETE``.
        body: Raw T-SQL body passed through verbatim.
        or_alter: Whether to render ``CREATE OR ALTER TRIGGER``.

    Example:
        >>> expr = SQLServerCreateTriggerExpression(
        ...     dialect, "trg", "t", timing="AFTER", events=["INSERT"],
        ...     body="SET NOCOUNT ON;",
        ... )
        >>> sql, params = expr.to_sql()
        >>> assert sql == "CREATE TRIGGER [trg] ON [t] AFTER INSERT AS BEGIN SET NOCOUNT ON; END;"
    """

    def __init__(
        self,
        dialect: "SQLServerDialect",
        name: str,
        table: str,
        timing: str = "AFTER",
        events: Optional[List[str]] = None,
        body: str = "",
        *,
        or_alter: bool = False,
    ):
        super().__init__(dialect)
        self.name = name
        self.table = table
        self.timing = timing
        self.events = list(events or [])
        self.body = body
        self.or_alter = or_alter

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not self.name:
            raise ValueError("trigger name is required")
        if not self.table:
            raise ValueError("trigger table is required")
        if self.timing.upper() not in ("AFTER", "INSTEAD OF"):
            raise ValueError("timing must be either AFTER or INSTEAD OF")
        if not self.events:
            raise ValueError("at least one trigger event is required")
        if not self.body:
            raise ValueError("trigger body is required")

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_create_trigger_statement(self)


class SQLServerDropTriggerExpression(BaseExpression):
    """SQL Server DROP TRIGGER statement (2005+).

    Attributes:
        name: Trigger name.
        if_exists: Render ``IF EXISTS`` (SQL Server 2016+ only).

    Example:
        >>> expr = SQLServerDropTriggerExpression(dialect, "trg")
        >>> sql, params = expr.to_sql()
        >>> assert sql == "DROP TRIGGER [trg]"
    """

    def __init__(
        self,
        dialect: "SQLServerDialect",
        name: str,
        *,
        if_exists: bool = False,
    ):
        super().__init__(dialect)
        self.name = name
        self.if_exists = if_exists

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not self.name:
            raise ValueError("trigger name is required")

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_drop_trigger_statement(self)
