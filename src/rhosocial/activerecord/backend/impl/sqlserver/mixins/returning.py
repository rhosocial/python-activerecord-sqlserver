# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/returning.py
from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import ReturningClause


class SQLServerReturningMixin:
    """SQL Server OUTPUT clause support for RETURNING."""

    def supports_returning_insert(self) -> bool:
        """SQL Server supports OUTPUT clause for INSERT."""
        return True

    def supports_returning_update(self) -> bool:
        """SQL Server supports OUTPUT clause for UPDATE."""
        return True

    def supports_returning_delete(self) -> bool:
        """SQL Server supports OUTPUT clause for DELETE."""
        return True

    def supports_returning_alias(self) -> bool:
        """SQL Server OUTPUT does not support a clause-level ``AS`` alias."""
        return False

    def supports_returning_wildcard(self) -> bool:
        """SQL Server OUTPUT requires explicit column references."""
        return False

    def supports_returning_into(self) -> bool:
        """SQL Server supports ``OUTPUT ... INTO``."""
        return True

    def format_returning_clause(self, clause: "ReturningClause", default_table: str = "INSERTED") -> Tuple[str, tuple]:
        """
        Format RETURNING as OUTPUT clause for SQL Server.

        SQL Server OUTPUT syntax:
        - INSERT: OUTPUT INSERTED.column, INSERTED.column2
        - UPDATE: OUTPUT DELETED.old_column, INSERTED.new_column
        - DELETE: OUTPUT DELETED.column

        Only INSERTED/DELETED virtual-table column references (and raw SQL
        escape hatches) are legal in an OUTPUT list. The prefix for each item
        comes from the expression's own ``table`` attribute when set
        (e.g. ``Column(dialect, "name", table="DELETED")``), otherwise the
        ``default_table`` is used.

        Args:
            clause: The ReturningClause with expressions to output.
            default_table: The default virtual table prefix ("INSERTED" for
                INSERT/UPDATE, "DELETED" for DELETE).

        Raises:
            UnsupportedFeatureError: If the clause requests an alias, a
                wildcard, or contains a non-column expression.
        """
        from rhosocial.activerecord.backend.expression.core import Column, WildcardExpression
        from rhosocial.activerecord.backend.expression.operators import RawSQLExpression

        if clause.alias:
            raise UnsupportedFeatureError(
                self.name,
                "alias in OUTPUT",
                "SQL Server OUTPUT does not support a clause-level alias.",
            )

        all_params = []
        expr_parts = []

        for expr in clause.expressions:
            if isinstance(expr, WildcardExpression):
                raise UnsupportedFeatureError(
                    self.name,
                    "wildcard in OUTPUT",
                    "SQL Server OUTPUT requires explicit column references; '*' "
                    "is not supported.",
                )
            if isinstance(expr, Column):
                prefix = expr.table.upper() if expr.table else default_table
                col_sql = self.format_identifier(expr.name, expr.name_need_quote)
                expr_parts.append(f"{prefix}.{col_sql}")
            elif isinstance(expr, RawSQLExpression):
                expr_sql, expr_params = expr.to_sql()
                expr_parts.append(f"{default_table}.{expr_sql}")
                all_params.extend(expr_params)
            else:
                raise UnsupportedFeatureError(
                    self.name,
                    "expressions in OUTPUT",
                    "SQL Server OUTPUT only supports INSERTED/DELETED column "
                    "references.",
                )

        output_sql = f"OUTPUT {', '.join(expr_parts)}"

        if clause.output_into:
            output_sql += f" INTO {clause.output_into}"

        return output_sql, tuple(all_params)
