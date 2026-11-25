# src/rhosocial/activerecord/backend/impl/sqlserver/expression/output.py
"""SQL Server OUTPUT clause expressions."""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class SQLServerOutputInsertedExpression(BaseExpression):
    """SQL Server OUTPUT INSERTED expression.

    Represents OUTPUT inserted.column for INSERT and UPDATE statements.

    Example:
        >>> expr = SQLServerOutputInsertedExpression(dialect, "id")
    """
    KIND_RESERVED = ("SQLServer",)

    def __init__(self, dialect: "SQLDialectBase", column: str):
        super().__init__(dialect)
        self.column = column

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not isinstance(self.column, str):
            raise TypeError(f"column must be str, got {type(self.column)}")

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this OUTPUT INSERTED reference."""
        return "format_sqlserver_output_inserted_expression"


class SQLServerOutputDeletedExpression(BaseExpression):
    """SQL Server OUTPUT DELETED expression.

    Represents OUTPUT deleted.column for DELETE and UPDATE statements.
    """
    KIND_RESERVED = ("SQLServer",)

    def __init__(self, dialect: "SQLDialectBase", column: str):
        super().__init__(dialect)
        self.column = column

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not isinstance(self.column, str):
            raise TypeError(f"column must be str, got {type(self.column)}")

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this OUTPUT DELETED reference."""
        return "format_sqlserver_output_deleted_expression"