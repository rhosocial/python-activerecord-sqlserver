# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/lateral.py
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.query_sources import LateralExpression


class SQLServerLateralMixin:
    """SQL Server CROSS APPLY / OUTER APPLY (LATERAL) support."""

    def supports_lateral_join(self) -> bool:
        """SQL Server uses CROSS APPLY/OUTER APPLY instead of LATERAL."""
        return True

    def format_lateral_expression(
        self,
        expr: "LateralExpression",
    ) -> Tuple[str, tuple]:
        """Format LATERAL as CROSS APPLY / OUTER APPLY for SQL Server.

        SQL Server uses CROSS APPLY (equivalent to INNER LATERAL) and
        OUTER APPLY (equivalent to LEFT LATERAL) instead of LATERAL.

        The parameter is the ``LateralExpression`` node, which is what core's
        ``LateralExpression.to_sql()`` passes and what every other dialect's
        override of this method takes. It used to take the four pieces the node
        is made of -- ``expr_sql, expr_params, alias, join_type`` -- which no
        caller has ever done: the node calls the formatter with itself, so every
        ``LateralExpression`` on SQL Server raised ``TypeError`` for a missing
        argument, and nothing reported it because the round-trip matrix
        swallowed every render failure. The pieces are read off the node here.

        Args:
            expr: The LateralExpression node, carrying the joined expression,
                the join type, and an optional alias.

        Returns:
            Tuple of (SQL string, parameters tuple).
        """
        if not self.supports_lateral_join():
            from rhosocial.activerecord.backend.dialect.exceptions import (
                UnsupportedFeatureError,
            )

            raise UnsupportedFeatureError(
                self.name,
                "LATERAL join",
                "Restructure the query with a plain subquery or a CTE instead.",
            )
        expr_sql, expr_params = expr.expression.to_sql()
        join_type = (expr.join_type or "INNER").upper()
        if join_type in ("LEFT", "LEFT JOIN", "LEFT OUTER JOIN"):
            apply_type = "OUTER APPLY"
        else:
            apply_type = "CROSS APPLY"

        sql = f"{apply_type} ({expr_sql})"
        if expr.alias is not None:
            sql += f" AS {self.format_identifier(expr.alias)}"
        return sql, expr_params
