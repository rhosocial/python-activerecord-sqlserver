# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/dml.py
from typing import Any, List, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.objects import Table

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import (
        InsertExpression,
        UpdateExpression,
        DeleteExpression,
    )


class SQLServerDMLMixin:
    """SQL Server INSERT / UPDATE / DELETE statement formatting."""

    def format_insert_statement(self, expr: "InsertExpression") -> Tuple[str, tuple]:
        """
        Format INSERT statement with SQL Server-specific options.

        SQL Server supports:
        - OUTPUT clause for returning inserted rows
        - INSERT TOP (n) for limiting rows
        - DEFAULT VALUES

        Raises:
            TypeError: ``expr.into`` is not a Table. A view or a sequence handed
                here would render as a well-formed ``INSERT INTO`` over that
                object's name.
        """
        if not isinstance(expr.into, Table):
            raise TypeError(
                f"InsertExpression.into must be a Table, "
                f"got {type(expr.into).__name__}"
            )
        if self.strict_validation:
            expr.validate(strict=True)

        all_params: List[Any] = []

        table_sql, table_params = expr.into.to_sql()
        all_params.extend(table_params)

        parts = ["INSERT INTO", table_sql]

        if expr.columns:
            columns_sql = "(" + ", ".join([self.format_identifier(c) for c in expr.columns]) + ")"
            parts.append(columns_sql)

        # Add OUTPUT clause before VALUES/SELECT (SQL Server requirement)
        if expr.returning:
            returning_sql, returning_params = self.format_returning_clause(expr.returning)
            parts.append(returning_sql)
            all_params.extend(returning_params)

        from rhosocial.activerecord.backend.expression.statements import (
            DefaultValuesSource,
            ValuesSource,
            SelectSource,
        )

        if isinstance(expr.source, DefaultValuesSource):
            parts.append("DEFAULT VALUES")
        elif isinstance(expr.source, ValuesSource):
            all_rows_sql = []
            for row in expr.source.values_list:
                row_sql = []
                row_params = []
                for val in row:
                    s, p = val.to_sql()
                    row_sql.append(s)
                    row_params.extend(p)
                all_rows_sql.append(f"({', '.join(row_sql)})")
                all_params.extend(row_params)
            parts.append("VALUES " + ", ".join(all_rows_sql))
        elif isinstance(expr.source, SelectSource):
            s_sql, s_params = expr.source.select_query.to_sql()
            parts.append(s_sql)
            all_params.extend(s_params)

        sql = " ".join(parts)

        return sql, tuple(all_params)

    def format_update_statement(self, expr: "UpdateExpression") -> Tuple[str, tuple]:
        """Format UPDATE statement with OUTPUT clause support.

        Raises:
            TypeError: ``expr.table`` is not a Table. A view handed here would
                render as a well-formed ``UPDATE`` over that view's name.
        """
        if not isinstance(expr.table, Table):
            raise TypeError(
                f"UpdateExpression.table must be a Table, "
                f"got {type(expr.table).__name__}"
            )
        if self.strict_validation:
            expr.validate(strict=True)

        all_params: List[Any] = []

        table_sql, table_params = expr.table.to_sql()
        all_params.extend(table_params)

        parts = ["UPDATE", table_sql]

        set_parts = []
        for col, val in expr.assignments.items():
            col_sql = self.format_identifier(col)
            val_sql, val_params = val.to_sql()
            set_parts.append(f"{col_sql} = {val_sql}")
            all_params.extend(val_params)
        parts.append("SET " + ", ".join(set_parts))

        if expr.returning:
            returning_sql, returning_params = self.format_returning_clause(expr.returning)
            parts.append(returning_sql)
            all_params.extend(returning_params)

        if expr.where:
            where_sql, where_params = expr.where.to_sql()
            parts.append(where_sql)
            all_params.extend(where_params)

        return " ".join(parts), tuple(all_params)

    def format_delete_statement(self, expr: "DeleteExpression") -> Tuple[str, tuple]:
        """Format DELETE statement with OUTPUT clause support.

        Raises:
            TypeError: An entry of ``expr.tables`` is not a Table. Any other
                object kind would have its own name rendered as a delete
                target.
        """
        for _table in expr.tables or ():
            if not isinstance(_table, Table):
                raise TypeError(
                    f"DeleteExpression.tables must hold Table instances, "
                    f"got {type(_table).__name__}"
                )
        if self.strict_validation:
            expr.validate(strict=True)

        all_params: List[Any] = []

        # DeleteExpression has .tables (list), not .table
        if expr.tables:
            table_refs = []
            for tbl in expr.tables:
                tbl_sql, tbl_params = tbl.to_sql()
                table_refs.append(tbl_sql)
                all_params.extend(tbl_params)
            table_sql = ", ".join(table_refs)
        else:
            table_sql = ""

        parts = ["DELETE FROM", table_sql]

        if expr.returning:
            returning_sql, returning_params = self.format_returning_clause(expr.returning, default_table="DELETED")
            parts.append(returning_sql)
            all_params.extend(returning_params)

        if expr.where:
            where_sql, where_params = expr.where.to_sql()
            parts.append(where_sql)
            all_params.extend(where_params)

        return " ".join(parts), tuple(all_params)
