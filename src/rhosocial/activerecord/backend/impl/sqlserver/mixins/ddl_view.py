# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/ddl_view.py
from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import View
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
        """Format CREATE VIEW statement for SQL Server.

        SQL Server spells the replacement form ``CREATE OR ALTER VIEW``, and
        ``WITH SCHEMABINDING`` is an indexed view's requirement rather than an
        option -- see ``format_create_indexed_view_statement``.

        Raises:
            TypeError: ``expr.view`` is not a View. A table or a materialized
                view handed here would render as a well-formed ``CREATE VIEW``
                over that object's name.
        """
        if not isinstance(expr.view, View):
            raise TypeError(
                f"CreateViewExpression.view must be a View, "
                f"got {type(expr.view).__name__}"
            )
        parts = ["CREATE OR ALTER VIEW" if expr.replace else "CREATE VIEW"]

        parts.append(expr.view.to_sql()[0])

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
        """Format DROP VIEW statement for SQL Server.

        ``IF EXISTS`` is rendered only on SQL Server 2016+; a request for it on
        an older version is a no-op rather than a syntax error, which is the
        spelling this dialect has always produced.

        SQL Server has neither ``CASCADE`` nor ``RESTRICT`` on ``DROP VIEW``
        (measured refused on 2019 / 2022 / 2025). This override replaces core's
        gated formatter, so an explicitly requested behavior is refused by name
        rather than silently dropped.

        Raises:
            TypeError: ``expr.view`` is not a View. A table handed here would
                render as a well-formed ``DROP VIEW`` over that table's name.
            UnsupportedFeatureError: If CASCADE or RESTRICT was requested.
        """
        if not isinstance(expr.view, View):
            raise TypeError(
                f"DropViewExpression.view must be a View, "
                f"got {type(expr.view).__name__}"
            )
        if expr.cascade and not self.supports_cascade_view():
            raise UnsupportedFeatureError(
                self.name, "DROP VIEW CASCADE",
                f"{self.name} does not support DROP VIEW CASCADE."
            )
        if expr.restrict and not self.supports_restrict_view():
            raise UnsupportedFeatureError(
                self.name, "DROP VIEW RESTRICT",
                f"{self.name} does not support DROP VIEW RESTRICT."
            )
        parts = ["DROP VIEW"]

        if expr.if_exists and self.supports_if_exists_view():
            parts.append("IF EXISTS")

        parts.append(expr.view.to_sql()[0])

        return " ".join(parts), ()

    def format_create_materialized_view_statement(
        self, expr: "CreateMaterializedViewExpression"
    ) -> Tuple[str, tuple]:
        """Format CREATE MATERIALIZED VIEW - not supported."""
        raise UnsupportedFeatureError(self.name, "CREATE MATERIALIZED VIEW", _SUGGESTION_MATERIALIZED_VIEW)
