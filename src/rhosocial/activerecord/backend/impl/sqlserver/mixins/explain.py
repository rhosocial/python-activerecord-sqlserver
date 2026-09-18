# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/explain.py
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import ExplainExpression


class SQLServerExplainMixin:
    """SQL Server EXPLAIN (SHOWPLAN/STATISTICS) implementation."""

    def supports_explain_analyze(self) -> bool:
        """SQL Server uses STATISTICS PROFILE for actual execution."""
        return True

    def supports_explain_format(self, format_type: str) -> bool:
        """Check if specific EXPLAIN format is supported."""
        return format_type.upper() in ["XML", "TEXT"]

    def format_explain_statement(self, explain_expr: "ExplainExpression") -> Tuple[str, tuple]:
        """
        Format EXPLAIN for SQL Server.

        SQL Server uses:
        - SET SHOWPLAN_XML ON (estimated plan)
        - SET STATISTICS PROFILE ON (actual plan with statistics)
        - SET STATISTICS XML ON (actual plan in XML)
        """
        statement_sql, statement_params = explain_expr.statement.to_sql()
        options = explain_expr.options

        if options is None:
            return f"SET SHOWPLAN_TEXT ON; {statement_sql}", statement_params

        if options.analyze:
            if options.format and options.format.name == "XML":
                return f"SET STATISTICS XML ON; {statement_sql}; SET STATISTICS XML OFF", statement_params
            return f"SET STATISTICS PROFILE ON; {statement_sql}; SET STATISTICS PROFILE OFF", statement_params

        if options.format and options.format.name == "XML":
            return f"SET SHOWPLAN_XML ON; {statement_sql}", statement_params

        return f"SET SHOWPLAN_TEXT ON; {statement_sql}", statement_params
