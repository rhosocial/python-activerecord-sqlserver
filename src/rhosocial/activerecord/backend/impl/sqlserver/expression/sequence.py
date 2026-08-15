# src/rhosocial/activerecord/backend/impl/sqlserver/expression/sequence.py
"""SQL Server SEQUENCE value expression.

SQL Server sequences are objects that generate a sequence of numeric values.
Values are obtained with the ``NEXT VALUE FOR`` expression (SQL Server 2012+):

    SELECT NEXT VALUE FOR my_seq;
    INSERT INTO t (id) VALUES (NEXT VALUE FOR my_seq);

This module defines the expression used to request the next value from a
sequence. SQL generation is delegated to the dialect's
``format_next_value_for`` formatter.
"""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams

if TYPE_CHECKING:
    from ..dialect import SQLServerDialect


class SQLServerNextValueForExpression(BaseExpression):
    """SQL Server NEXT VALUE FOR expression (2012+).

    Requests the next value from a sequence object.

    Attributes:
        sequence_name: Name of the sequence (may be schema-qualified).

    Example:
        >>> expr = SQLServerNextValueForExpression(dialect, "my_seq")
        >>> sql, params = expr.to_sql()
        >>> assert sql == "NEXT VALUE FOR [my_seq]"
    """

    def __init__(self, dialect: "SQLServerDialect", sequence_name: str):
        super().__init__(dialect)
        self.sequence_name = sequence_name

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not isinstance(self.sequence_name, str):
            raise TypeError(f"sequence_name must be str, got {type(self.sequence_name)}")

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_next_value_for(self), ()
