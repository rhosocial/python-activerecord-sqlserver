# src/rhosocial/activerecord/backend/impl/sqlserver/expression/openjson.py
"""SQL Server OPENJSON expression."""

from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


@dataclass
class OpenJsonColumn:
    """Column definition for OPENJSON WITH schema.

    Attributes:
        name: Column name
        type: SQL data type (e.g., 'NVARCHAR(255)', 'INT')
        path: Optional JSON path expression
        as_json: If True, column value is a JSON fragment
    """
    name: str
    type: str
    path: Optional[str] = None
    as_json: bool = False


class SQLServerOpenJsonExpression(BaseExpression):
    """SQL Server OPENJSON table-valued function expression.

    Parses JSON text and returns rows and columns.

    Example:
        >>> expr = SQLServerOpenJsonExpression(
        ...     dialect, json_doc='@json_var',
        ...     path='$.orders',
        ...     schema=[OpenJsonColumn(name='order_id', type='INT')],
        ...     alias='orders'
        ... )
    """
    KIND_RESERVED = ("SQLServer",)

    def __init__(
        self,
        dialect: "SQLDialectBase",
        json_doc: str,
        path: Optional[str] = None,
        schema: Optional[List[OpenJsonColumn]] = None,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.json_doc = json_doc
        self.path = path
        self.schema = schema or []
        self.alias = alias

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not isinstance(self.json_doc, str):
            raise TypeError(f"json_doc must be str, got {type(self.json_doc)}")
        for col in self.schema:
            if not isinstance(col, OpenJsonColumn):
                raise TypeError(f"schema must contain OpenJsonColumn, got {type(col)}")

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this OPENJSON expression."""
        return "format_sqlserver_open_json_expression"