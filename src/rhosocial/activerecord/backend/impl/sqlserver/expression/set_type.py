# src/rhosocial/activerecord/backend/impl/sqlserver/expression/set_type.py
"""SQL Server SET type expression classes for format_* signature compliance."""

from typing import List, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import SQLValueExpression
from rhosocial.activerecord.backend.expression.mixins import (
    AliasableMixin,
    ComparisonMixin,
)

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class SQLServerSetLiteralExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server SET literal expression (comma-separated values in VARCHAR).

    SQL Server stores comma-separated values in VARCHAR columns.

    Example:
        >>> expr = SQLServerSetLiteralExpression(dialect, ["a", "b", "c"])
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        values: List[str],
        column_values: Optional[List[str]] = None,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.values = values
        self.column_values = column_values
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_set_literal"


class SQLServerFindInSetExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server FIND_IN_SET equivalent using LIKE predicate.

    SQL Server has no FIND_IN_SET; membership is checked with a LIKE predicate.

    Example:
        >>> expr = SQLServerFindInSetExpression(dialect, "value", "set_column")
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        value: str,
        set_column: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.value = value
        self.set_column = set_column
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_find_in_set"


class SQLServerSetContainsExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server SET containment predicate as AND-ed membership checks.

    Example:
        >>> expr = SQLServerSetContainsExpression(dialect, "col", ["a", "b"])
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        column: str,
        values: List[str],
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.column = column
        self.values = values
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_set_contains"
