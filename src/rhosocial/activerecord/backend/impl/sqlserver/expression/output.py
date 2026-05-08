# src/rhosocial/activerecord/backend/impl/sqlserver/expression/output.py
"""SQL Server OUTPUT clause expressions."""

from typing import Any, List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class SQLServerOutputInsertedExpression(BaseExpression):
    """SQL Server OUTPUT INSERTED expression.

    Represents OUTPUT inserted.column for INSERT and UPDATE statements.

    Example:
        >>> expr = SQLServerOutputInsertedExpression(dialect, "id")
    """

    def __init__(self, dialect: "SQLDialectBase", column: str):
        super().__init__(dialect)
        self.column = column

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not isinstance(self.column, str):
            raise TypeError(f"column must be str, got {type(self.column)}")

    def to_sql(self) -> SQLQueryAndParams:
        return f"INSERTED.{self.dialect.format_identifier(self.column)}", ()


class SQLServerOutputDeletedExpression(BaseExpression):
    """SQL Server OUTPUT DELETED expression.

    Represents OUTPUT deleted.column for DELETE and UPDATE statements.
    """

    def __init__(self, dialect: "SQLDialectBase", column: str):
        super().__init__(dialect)
        self.column = column

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not isinstance(self.column, str):
            raise TypeError(f"column must be str, got {type(self.column)}")

    def to_sql(self) -> SQLQueryAndParams:
        return f"DELETED.{self.dialect.format_identifier(self.column)}", ()