# src/rhosocial/activerecord/backend/impl/sqlserver/expression/functions.py
"""SQL Server-specific function expressions."""

from typing import Any, List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class SQLServerTryCastExpression(BaseExpression):
    """SQL Server TRY_CAST expression.

    Returns the cast value if successful, NULL otherwise (SQL Server 2012+).

    Example:
        >>> expr = SQLServerTryCastExpression(dialect, "value", "INT")
    """

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

    def to_sql(self) -> SQLQueryAndParams:
        if isinstance(self.expression, BaseExpression):
            expr_sql, expr_params = self.expression.to_sql()
        else:
            expr_sql, expr_params = str(self.expression), ()
        return f"TRY_CAST({expr_sql} AS {self.target_type})", expr_params


class SQLServerTryConvertExpression(BaseExpression):
    """SQL Server TRY_CONVERT expression.

    Returns the converted value if successful, NULL otherwise (SQL Server 2012+).

    Example:
        >>> expr = SQLServerTryConvertExpression(dialect, "INT", "value", style=100)
    """

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

    def to_sql(self) -> SQLQueryAndParams:
        if isinstance(self.expression, BaseExpression):
            expr_sql, expr_params = self.expression.to_sql()
        else:
            expr_sql, expr_params = str(self.expression), ()
        sql = f"TRY_CONVERT({self.target_type}, {expr_sql}"
        if self.style is not None:
            sql += f", {self.style}"
        sql += ")"
        return sql, expr_params


class SQLServerContainsPredicate(BaseExpression):
    """SQL Server CONTAINS full-text search predicate.

    Example:
        >>> expr = SQLServerContainsPredicate(dialect, "title", "database")
    """

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

    def to_sql(self) -> SQLQueryAndParams:
        col = self.dialect.format_identifier(self.column)
        sql = f"CONTAINS({col}, '{self.search_string.replace(chr(39), chr(39)+chr(39))}'"
        if self.language:
            sql += f", LANGUAGE '{self.language}'"
        sql += ")"
        return sql, ()


class SQLServerFreetextPredicate(BaseExpression):
    """SQL Server FREETEXT full-text search predicate.

    Example:
        >>> expr = SQLServerFreetextPredicate(dialect, "title", "database design")
    """

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

    def to_sql(self) -> SQLQueryAndParams:
        col = self.dialect.format_identifier(self.column)
        sql = f"FREETEXT({col}, '{self.search_string.replace(chr(39), chr(39)+chr(39))}'"
        if self.language:
            sql += f", LANGUAGE '{self.language}'"
        sql += ")"
        return sql, ()