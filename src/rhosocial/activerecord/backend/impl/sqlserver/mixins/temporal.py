# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/temporal.py
"""SQL Server temporal table capability and formatting.

Temporal tables arrived with SQL Server 2016. The two nodes this mixin renders
are the *clauses* of a temporal CREATE TABLE, not statements of their own:

    PERIOD FOR SYSTEM_TIME (SysStartTime, SysEndTime)
    WITH (SYSTEM_VERSIONING = ON [, HISTORY_TABLE = <table>])

Each is a clause, so each formatter answers with the text that goes inside the
surrounding statement and never with a statement of its own.
"""

from typing import Tuple, TYPE_CHECKING

from .version_constants import SQL_SERVER_2016

if TYPE_CHECKING:
    from ..expression.temporal import (
        SQLServerSystemVersioningClause,
        SQLServerTemporalPeriodDefinition,
    )


class SQLServerTemporalMixin:
    """SQL Server temporal table capability declaration and clause formatters."""

    def supports_temporal_tables(self) -> bool:
        """SQL Server 2016+ supports temporal tables."""
        return self.version_at_least(SQL_SERVER_2016)

    def format_sqlserver_temporal_period_definition(
        self, expr: "SQLServerTemporalPeriodDefinition"
    ) -> Tuple[str, tuple]:
        """Format the ``PERIOD FOR SYSTEM_TIME`` clause (2016+).

        SQL Syntax:
            PERIOD FOR SYSTEM_TIME (start_column, end_column)
        """
        start = self.format_identifier(expr.start_column)  # type: ignore[attr-defined]
        end = self.format_identifier(expr.end_column)  # type: ignore[attr-defined]
        return f"PERIOD FOR SYSTEM_TIME ({start}, {end})", ()

    def format_sqlserver_system_versioning_clause(
        self, expr: "SQLServerSystemVersioningClause"
    ) -> Tuple[str, tuple]:
        """Format the ``WITH (SYSTEM_VERSIONING = ON ...)`` clause (2016+).

        SQL Syntax:
            WITH (SYSTEM_VERSIONING = ON [, HISTORY_TABLE = <table>])

        The history table renders through its own formatter, so a schema-
        qualified name keeps the namespace it was built with; a clause with no
        history table renders the bare switch, which is how the engine picks the
        default name.
        """
        sql = "WITH (SYSTEM_VERSIONING = ON"
        if expr.history_table is not None:
            sql += f", HISTORY_TABLE = {expr.history_table.to_sql()[0]}"
        sql += ")"
        return sql, ()
