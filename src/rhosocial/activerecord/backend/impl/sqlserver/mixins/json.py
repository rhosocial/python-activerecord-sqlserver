# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/json.py
from typing import Optional, Tuple, TYPE_CHECKING

from .version_constants import SQL_SERVER_2016

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.bases import BaseExpression
    from ..expression.openjson import SQLServerOpenJsonExpression


class SQLServerJSONMixin:
    """SQL Server JSON function implementations."""

    def supports_json_type(self) -> bool:
        """JSON functions are supported since SQL Server 2016."""
        return self.version_at_least(SQL_SERVER_2016)

    def get_json_access_operator(self) -> Optional[str]:
        """SQL Server doesn't have -> operator, uses JSON_VALUE/JSON_QUERY."""
        return None

    def format_json_function_expression(self, expr: "BaseExpression") -> Tuple[str, tuple]:
        """Format JSON extraction using SQL Server's JSON_VALUE built-in.

        The base implementation renders ``JSON_UNQUOTE(JSON_EXTRACT(...))``
        which is MySQL syntax. SQL Server uses ``JSON_VALUE(column, 'path')``,
        which already returns a scalar value without surrounding quotes.

        Args:
            expr: The JSON path node to format -- a
                JSONDocumentValue for ``->``, a
                JSONTextValue for ``->>``.

        Returns:
            (SQL string, params tuple).
        """
        col_sql, col_params = expr.column.to_sql()

        escaped_path = self.escape_sql_string(expr.path)
        sql = f"JSON_VALUE({col_sql}, '{escaped_path}')"
        params = col_params

        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"

        return sql, params

    def format_sqlserver_open_json_expression(
        self, expr: "SQLServerOpenJsonExpression"
    ) -> Tuple[str, tuple]:
        """Format an OPENJSON table-valued function call (2016+).

        SQL Syntax:
            OPENJSON(json_doc [, path]) [WITH (column type [path] [AS JSON], ...)]
            [AS alias]

        The column list is a *schema declaration inside the statement*, not a
        bind value: each column names its own type, so the types are spelled
        here rather than read from a data-type node.

        Returns:
            Tuple of (SQL string, params tuple).
        """
        parts = [f"OPENJSON({expr.json_doc}"]
        if expr.path:
            parts[0] += f", '{expr.path}'"
        parts[0] += ")"

        if expr.schema:
            col_defs = []
            for col in expr.schema:
                col_sql = f"{self.format_identifier(col.name)} {col.type}"
                if col.path:
                    col_sql += f" '{col.path}'"
                if col.as_json:
                    col_sql += " AS JSON"
                col_defs.append(col_sql)
            parts.append(f"WITH ({', '.join(col_defs)})")

        sql = " ".join(parts)

        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"

        return sql, ()

    def supports_json_table(self) -> bool:
        """Always False: this backend has no JSON_TABLE path.

        The probe used to answer True on 2016+, which contradicted
        ``format_json_table_expression`` — that formatter raises
        unconditionally and points at OPENJSON. A caller that trusted the
        probe would be told a table expression was available and then get an
        exception at render time.

        OPENJSON is the supported route and it is fully implemented, through
        ``SQLServerOpenJsonExpression``; it just is not JSON_TABLE.
        """
        return False
