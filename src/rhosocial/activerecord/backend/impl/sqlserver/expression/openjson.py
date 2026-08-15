# src/rhosocial/activerecord/backend/impl/sqlserver/expression/openjson.py
"""SQL Server OPENJSON expression."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams

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

    def to_sql(self) -> SQLQueryAndParams:
        params: list = []

        parts = [f"OPENJSON({self.json_doc}"]
        if self.path:
            parts[0] += f", '{self.path}'"
        parts[0] += ")"

        if self.schema:
            col_defs = []
            for col in self.schema:
                col_sql = f"{self.dialect.format_identifier(col.name)} {col.type}"
                if col.path:
                    col_sql += f" '{col.path}'"
                if col.as_json:
                    col_sql += " AS JSON"
                col_defs.append(col_sql)
            parts.append(f"WITH ({', '.join(col_defs)})")

        sql = " ".join(parts)

        if self.alias:
            sql = f"{sql} AS {self.dialect.format_identifier(self.alias)}"

        return sql, tuple(params)