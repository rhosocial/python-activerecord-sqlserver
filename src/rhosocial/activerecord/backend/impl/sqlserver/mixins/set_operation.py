# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/set_operation.py
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression import bases


class SQLServerSetOperationMixin:
    """SQL Server set operation capability declarations and formatting."""

    def supports_union(self) -> bool:
        """UNION is supported."""
        return True

    def supports_union_all(self) -> bool:
        """UNION ALL is supported."""
        return True

    def supports_intersect(self) -> bool:
        """INTERSECT is supported."""
        return True

    def supports_except(self) -> bool:
        """EXCEPT is supported."""
        return True

    def supports_set_operation_order_by(self) -> bool:
        """Set operations support ORDER BY."""
        return True

    def supports_set_operation_limit_offset(self) -> bool:
        """Set operations support OFFSET FETCH."""
        return True

    def format_set_operation_expression(self, expr: "bases.BaseExpression") -> Tuple[str, tuple]:
        """Format set operation for SQL Server.

        SQL Server supports UNION, UNION ALL, INTERSECT, EXCEPT.
        ORDER BY and OFFSET FETCH apply to the entire set operation result.
        """
        left, right = expr.left, expr.right
        operation = expr.operation
        all_ = expr.all_
        alias = expr.alias
        order_by_clause = expr.order_by_clause
        limit_offset_clause = expr.limit_offset_clause

        left_sql, left_params = left.to_sql()
        right_sql, right_params = right.to_sql()
        all_str = " ALL" if all_ else ""

        base_sql = f"{left_sql} {operation}{all_str} {right_sql}"

        all_params = list(left_params + right_params)

        sql_parts = [base_sql]

        if alias:
            sql_parts.append(f"AS {self.format_identifier(alias)}")

        if order_by_clause:
            order_by_sql, order_by_params = order_by_clause.to_sql()
            sql_parts.append(order_by_sql)
            all_params.extend(order_by_params)

        if limit_offset_clause:
            limit_offset_sql, limit_offset_params = limit_offset_clause.to_sql()
            sql_parts.append(limit_offset_sql)
            all_params.extend(limit_offset_params)

        return " ".join(sql_parts), tuple(all_params)
