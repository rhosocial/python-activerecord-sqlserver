# src/rhosocial/activerecord/backend/impl/sqlserver/expression/pivot.py
"""SQL Server PIVOT and UNPIVOT expressions.

PIVOT rotates rows to columns, creating a cross-tabulation query; UNPIVOT
rotates columns to rows, the inverse of PIVOT. Both are available since
SQL Server 2005:

    SELECT ... FROM t PIVOT (SUM(sales) FOR quarter IN (Q1, Q2, Q3, Q4)) p;
    SELECT ... FROM t UNPIVOT (val FOR col IN (a, b)) u;

SQL generation is delegated to the dialect's ``format_pivot`` and
``format_unpivot`` formatters.
"""

from typing import Optional, Sequence, Union, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams

if TYPE_CHECKING:
    from ..dialect import SQLServerDialect


class SQLServerPivotExpression(BaseExpression):
    """SQL Server PIVOT clause for row-to-column transformation.

    Attributes:
        aggregate_function: Aggregate function (SUM, COUNT, AVG, MAX, MIN).
        value_column: Column to aggregate.
        pivot_column: Column whose values become the new column names.
        values: List of pivot values to rotate into columns. Values are
            rendered verbatim; quote string literals yourself when needed.
        alias: Optional alias for the pivoted result.

    Example:
        >>> expr = SQLServerPivotExpression(
        ...     dialect, "SUM", "sales", "quarter", ["Q1", "Q2"], alias="p"
        ... )
        >>> sql, params = expr.to_sql()
        >>> assert sql == "PIVOT (SUM([sales]) FOR [quarter] IN (Q1, Q2)) [p]"
    """

    def __init__(
        self,
        dialect: "SQLServerDialect",
        aggregate_function: str,
        value_column: str,
        pivot_column: str,
        values: Sequence[Union[str, int, float]] = (),
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.aggregate_function = aggregate_function
        self.value_column = value_column
        self.pivot_column = pivot_column
        self.values = list(values)
        self.alias = alias

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not self.aggregate_function:
            raise ValueError("aggregate_function is required")
        if not self.value_column:
            raise ValueError("value_column is required")
        if not self.pivot_column:
            raise ValueError("pivot_column is required")
        if not self.values:
            raise ValueError("at least one pivot value is required")

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_pivot(self)


class SQLServerUnpivotExpression(BaseExpression):
    """SQL Server UNPIVOT clause for column-to-row transformation.

    SQL Server UNPIVOT always excludes NULL values and does not support an
    INCLUDE NULLS option.

    Attributes:
        value_column: Name for the value column in the output.
        pivot_column: Name for the pivot column in the output.
        columns: List of columns to unpivot.
        alias: Optional alias for the unpivoted result.

    Example:
        >>> expr = SQLServerUnpivotExpression(
        ...     dialect, "val", "col", ["a", "b"], alias="u"
        ... )
        >>> sql, params = expr.to_sql()
        >>> assert sql == "UNPIVOT ([val] FOR [col] IN ([a], [b])) [u]"
    """

    def __init__(
        self,
        dialect: "SQLServerDialect",
        value_column: str,
        pivot_column: str,
        columns: Sequence[str] = (),
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.value_column = value_column
        self.pivot_column = pivot_column
        self.columns = list(columns)
        self.alias = alias

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not self.value_column:
            raise ValueError("value_column is required")
        if not self.pivot_column:
            raise ValueError("pivot_column is required")
        if not self.columns:
            raise ValueError("at least one column is required")

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_unpivot(self)
