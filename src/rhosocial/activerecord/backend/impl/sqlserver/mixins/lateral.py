# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/lateral.py
from typing import Tuple


class SQLServerLateralMixin:
    """SQL Server CROSS APPLY / OUTER APPLY (LATERAL) support."""

    def supports_lateral_join(self) -> bool:
        """SQL Server uses CROSS APPLY/OUTER APPLY instead of LATERAL."""
        return True

    def format_lateral_expression(
        self,
        expr_sql: str,
        expr_params: tuple,
        alias: str,
        join_type: str = "CROSS APPLY",
    ) -> Tuple[str, tuple]:
        """Format LATERAL as CROSS APPLY / OUTER APPLY for SQL Server.

        SQL Server uses CROSS APPLY (equivalent to INNER LATERAL) and
        OUTER APPLY (equivalent to LEFT LATERAL) instead of LATERAL.
        """
        if join_type.upper() in ("LEFT", "LEFT JOIN", "LEFT OUTER JOIN"):
            apply_type = "OUTER APPLY"
        else:
            apply_type = "CROSS APPLY"

        sql = f"{apply_type} ({expr_sql})"
        if alias:
            sql += f" AS {self.format_identifier(alias)}"
        return sql, expr_params
