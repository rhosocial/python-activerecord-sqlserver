# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/returning.py
from typing import Tuple, TYPE_CHECKING

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

    def format_returning_clause(self, clause: "ReturningClause", default_table: str = "INSERTED") -> Tuple[str, tuple]:
        """
        Format RETURNING as OUTPUT clause for SQL Server.

        SQL Server OUTPUT syntax:
        - INSERT: OUTPUT inserted.column, inserted.column2
        - UPDATE: OUTPUT deleted.old_column, inserted.new_column
        - DELETE: OUTPUT deleted.column

        Args:
            clause: The ReturningClause with expressions to output.
            default_table: The default virtual table prefix ("INSERTED" for
                INSERT/UPDATE, "DELETED" for DELETE).
        """
        all_params = []
        expr_parts = []

        for expr in clause.expressions:
            if hasattr(expr, 'table') and expr.table:
                expr_sql, expr_params = expr.to_sql()
                expr_parts.append(f"{default_table}.{expr_sql}")
            else:
                expr_sql, expr_params = expr.to_sql()
                expr_parts.append(f"{default_table}.{expr_sql}")
            all_params.extend(expr_params)

        output_sql = f"OUTPUT {', '.join(expr_parts)}"

        return output_sql, tuple(all_params)
