# src/rhosocial/activerecord/backend/impl/sqlserver/expression/temporal.py
"""SQL Server temporal table expressions (2016+)."""

from typing import Any, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class SQLServerTemporalPeriodDefinition(BaseExpression):
    """SQL Server PERIOD FOR SYSTEM_TIME definition for temporal tables.

    Defines the period columns used for system-versioned temporal tables.

    Example:
        >>> expr = SQLServerTemporalPeriodDefinition(dialect, "SysStartTime", "SysEndTime")
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        start_column: str = "SysStartTime",
        end_column: str = "SysEndTime",
    ):
        super().__init__(dialect)
        self.start_column = start_column
        self.end_column = end_column

    def to_sql(self) -> SQLQueryAndParams:
        start = self.dialect.format_identifier(self.start_column)
        end = self.dialect.format_identifier(self.end_column)
        return f"PERIOD FOR SYSTEM_TIME ({start}, {end})", ()


class SQLServerSystemVersioningClause(BaseExpression):
    """SQL Server SYSTEM_VERSIONING clause for temporal tables.

    Enables system-versioning on a temporal table.

    Example:
        >>> expr = SQLServerSystemVersioningClause(dialect, "dbo.TestTableHistory")
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        history_table: Optional[str] = None,
        history_schema: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.history_table = history_table
        self.history_schema = history_schema

    def to_sql(self) -> SQLQueryAndParams:
        sql = "WITH (SYSTEM_VERSIONING = ON"
        if self.history_table:
            tbl = self.dialect.format_identifier(self.history_table)
            if self.history_schema:
                schema = self.dialect.format_identifier(self.history_schema)
                tbl = f"{schema}.{tbl}"
            sql += f", HISTORY_TABLE = {tbl}"
        sql += ")"
        return sql, ()