# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/pivot.py
"""SQL Server PIVOT / UNPIVOT mixin.

PIVOT and UNPIVOT have been available since SQL Server 2005 and work in
every supported version. This mixin provides the capability switches and
the ``format_pivot`` / ``format_unpivot`` formatters used by
``SQLServerPivotExpression`` and ``SQLServerUnpivotExpression``.
"""

from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.pivot import (
        SQLServerPivotExpression,
        SQLServerUnpivotExpression,
    )


_SQL_SERVER_PIVOT_VERSION = (9, 0, 0)


class SQLServerPivotMixin:
    """SQL Server PIVOT / UNPIVOT capability and formatting implementation."""

    def supports_pivot(self) -> bool:
        """PIVOT is supported since SQL Server 2005."""
        return self.version >= _SQL_SERVER_PIVOT_VERSION  # type: ignore[attr-defined]

    def supports_unpivot(self) -> bool:
        """UNPIVOT is supported since SQL Server 2005."""
        return self.version >= _SQL_SERVER_PIVOT_VERSION  # type: ignore[attr-defined]

    def format_pivot(
        self, expr: "SQLServerPivotExpression"
    ) -> Tuple[str, tuple]:
        """Format a PIVOT clause.

        SQL Syntax:
            PIVOT (agg(value_column) FOR pivot_column IN (v1, v2, ...)) [alias]
        """
        value_col = self.format_identifier(expr.value_column)  # type: ignore[attr-defined]
        pivot_col = self.format_identifier(expr.pivot_column)  # type: ignore[attr-defined]
        values_str = ", ".join(str(value) for value in expr.values)

        sql = (
            f"PIVOT ({expr.aggregate_function}({value_col}) "
            f"FOR {pivot_col} IN ({values_str}))"
        )

        if expr.alias:
            sql += f" {self.format_identifier(expr.alias)}"  # type: ignore[attr-defined]

        return sql, ()

    def format_unpivot(
        self, expr: "SQLServerUnpivotExpression"
    ) -> Tuple[str, tuple]:
        """Format an UNPIVOT clause.

        SQL Syntax:
            UNPIVOT (value_column FOR pivot_column IN (col1, col2, ...)) [alias]
        """
        value_col = self.format_identifier(expr.value_column)  # type: ignore[attr-defined]
        pivot_col = self.format_identifier(expr.pivot_column)  # type: ignore[attr-defined]
        columns_str = ", ".join(
            self.format_identifier(col)  # type: ignore[attr-defined]
            for col in expr.columns
        )

        sql = f"UNPIVOT ({value_col} FOR {pivot_col} IN ({columns_str}))"

        if expr.alias:
            sql += f" {self.format_identifier(expr.alias)}"  # type: ignore[attr-defined]

        return sql, ()
