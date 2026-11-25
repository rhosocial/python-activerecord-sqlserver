# src/rhosocial/activerecord/backend/impl/sqlserver/expression/functions.py
"""SQL Server-specific function expressions."""

from typing import Any, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class SQLServerTryCastExpression(BaseExpression):
    """SQL Server TRY_CAST expression.

    Returns the cast value if successful, NULL otherwise (SQL Server 2012+).

    Example:
        >>> expr = SQLServerTryCastExpression(dialect, "value", "INT")
    """
    KIND_RESERVED = ("SQLServer",)

    def __init__(
        self,
        dialect: "SQLDialectBase",
        expression: Any,
        target_type: str,
    ):
        super().__init__(dialect)
        self.expression = expression
        self.target_type = target_type

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not isinstance(self.target_type, str):
            raise TypeError(f"target_type must be str, got {type(self.target_type)}")

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this TRY_CAST expression."""
        return "format_sqlserver_try_cast_expression"


class SQLServerTryConvertExpression(BaseExpression):
    """SQL Server TRY_CONVERT expression.

    Returns the converted value if successful, NULL otherwise (SQL Server 2012+).

    Example:
        >>> expr = SQLServerTryConvertExpression(dialect, "INT", "value", style=100)
    """
    KIND_RESERVED = ("SQLServer",)

    def __init__(
        self,
        dialect: "SQLDialectBase",
        target_type: str,
        expression: Any,
        style: Optional[int] = None,
    ):
        super().__init__(dialect)
        self.target_type = target_type
        self.expression = expression
        self.style = style

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not isinstance(self.target_type, str):
            raise TypeError(f"target_type must be str, got {type(self.target_type)}")

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this TRY_CONVERT expression."""
        return "format_sqlserver_try_convert_expression"


class SQLServerContainsPredicate(BaseExpression):
    """SQL Server CONTAINS full-text search predicate.

    Example:
        >>> expr = SQLServerContainsPredicate(dialect, "title", "database")
    """
    KIND_RESERVED = ("SQLServer",)

    def __init__(
        self,
        dialect: "SQLDialectBase",
        column: str,
        search_string: str,
        language: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.column = column
        self.search_string = search_string
        self.language = language

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not isinstance(self.column, str):
            raise TypeError(f"column must be str, got {type(self.column)}")
        if not isinstance(self.search_string, str):
            raise TypeError(f"search_string must be str, got {type(self.search_string)}")

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this CONTAINS predicate."""
        return "format_sqlserver_contains_predicate"


class SQLServerFreetextPredicate(BaseExpression):
    """SQL Server FREETEXT full-text search predicate.

    Example:
        >>> expr = SQLServerFreetextPredicate(dialect, "title", "database design")
    """
    KIND_RESERVED = ("SQLServer",)

    def __init__(
        self,
        dialect: "SQLDialectBase",
        column: str,
        search_string: str,
        language: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.column = column
        self.search_string = search_string
        self.language = language

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not isinstance(self.column, str):
            raise TypeError(f"column must be str, got {type(self.column)}")
        if not isinstance(self.search_string, str):
            raise TypeError(f"search_string must be str, got {type(self.search_string)}")

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this FREETEXT predicate."""
        return "format_sqlserver_freetext_predicate"