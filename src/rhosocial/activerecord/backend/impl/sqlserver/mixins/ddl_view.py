# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/ddl_view.py
from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from .version_constants import SQL_SERVER_2005, SQL_SERVER_2016

_SUGGESTION_MATERIALIZED_VIEW = "SQL Server does not support materialized views. Consider using indexed views."

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import (
        CreateViewExpression,
        DropViewExpression,
        CreateMaterializedViewExpression,
    )


class SQLServerViewMixin:
    """SQL Server VIEW capability declarations and formatting."""

    def supports_indexed_view(self) -> bool:
        """SQL Server supports indexed views (similar to materialized views)."""
        return self.version >= SQL_SERVER_2005

    def supports_create_or_replace_view(self) -> bool:
        """SQL Server does not support CREATE OR REPLACE VIEW (uses CREATE OR ALTER)."""
        return False

    def supports_if_not_exists_view(self) -> bool:
        """SQL Server does not support IF NOT EXISTS for views."""
        return False

    def supports_if_exists_view(self) -> bool:
        """SQL Server supports DROP VIEW IF EXISTS (2016+)."""
        return self.version >= SQL_SERVER_2016

    def supports_view_check_option(self) -> bool:
        """SQL Server supports WITH CHECK OPTION."""
        return True

    def format_create_view_statement(
        self, expr: "CreateViewExpression"
    ) -> Tuple[str, tuple]:
        """Format CREATE VIEW statement for SQL Server."""
        parts = ["CREATE VIEW"]

        if expr.replace:
            parts = ["CREATE OR ALTER VIEW"]

        parts.append(self.format_identifier(expr.view_name))

        if expr.column_aliases:
            cols = ", ".join(self.format_identifier(c) for c in expr.column_aliases)
            parts.append(f"({cols})")

        query_sql, query_params = expr.query.to_sql()
        as_sql = f"AS {query_sql}"
        if expr.options and getattr(expr.options, "schemabinding", False):
            as_sql = f"WITH SCHEMABINDING {as_sql}"
        parts.append(as_sql)

        if expr.options and hasattr(expr.options, 'check_option') and expr.options.check_option:
            if not self.supports_view_check_option():
                from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
                raise UnsupportedFeatureError(
                    self.name, "WITH CHECK OPTION",
                    f"{self.name} does not support WITH CHECK OPTION.",
                )
            parts.append(f"WITH {expr.options.check_option.value} CHECK OPTION")

        return " ".join(parts), query_params

    def format_drop_view_statement(
        self, expr: "DropViewExpression"
    ) -> Tuple[str, tuple]:
        """Format DROP VIEW statement for SQL Server."""
        parts = ["DROP VIEW"]

        if expr.if_exists and self.supports_if_exists_view():
            parts.append("IF EXISTS")

        parts.append(self.format_identifier(expr.view_name))

        return " ".join(parts), ()

    def format_create_materialized_view_statement(
        self, expr: "CreateMaterializedViewExpression"
    ) -> Tuple[str, tuple]:
        """Format CREATE MATERIALIZED VIEW - not supported."""
        raise UnsupportedFeatureError(self.name, "CREATE MATERIALIZED VIEW", _SUGGESTION_MATERIALIZED_VIEW)
