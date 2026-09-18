# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/json.py
from typing import Optional, Tuple, TYPE_CHECKING

from .version_constants import SQL_SERVER_2016

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.bases import BaseExpression


class SQLServerJSONMixin:
    """SQL Server JSON function implementations."""

    def supports_json_type(self) -> bool:
        """JSON functions are supported since SQL Server 2016."""
        return self.version >= SQL_SERVER_2016

    def get_json_access_operator(self) -> Optional[str]:
        """SQL Server doesn't have -> operator, uses JSON_VALUE/JSON_QUERY."""
        return None

    def format_json_function_expression(self, expr: "BaseExpression") -> Tuple[str, tuple]:
        """Format JSON extraction using SQL Server's JSON_VALUE built-in.

        The base implementation renders ``JSON_UNQUOTE(JSON_EXTRACT(...))``
        which is MySQL syntax. SQL Server uses ``JSON_VALUE(column, 'path')``,
        which already returns a scalar value without surrounding quotes.

        Args:
            expr: The JSONExpression to format.

        Returns:
            (SQL string, params tuple).
        """
        col_sql, col_params = expr.column.to_sql()

        escaped_path = self._escape_sql_string(expr.path)
        sql = f"JSON_VALUE({col_sql}, '{escaped_path}')"
        params = col_params

        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"

        return sql, params

    def supports_json_table(self) -> bool:
        """OPENJSON provides JSON table functionality since SQL Server 2016."""
        return self.version >= SQL_SERVER_2016
