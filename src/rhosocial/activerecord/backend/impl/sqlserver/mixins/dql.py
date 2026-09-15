# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/dql.py
from typing import Any, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from .version_constants import SQL_SERVER_2012

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.query_parts import LimitOffsetClause
    from rhosocial.activerecord.backend.expression.statements import QueryExpression


class SQLServerDQLMixin:
    """SQL Server SELECT / LIMIT / OFFSET formatting."""

    def supports_fetch_with_ties(self) -> bool:
        """SQL Server supports FETCH NEXT ... ROWS WITH TIES (2012+)."""
        return True

    def supports_nulls_first_last(self) -> bool:
        """SQL Server does not support explicit NULLS FIRST/LAST ordering."""
        return False

    def format_limit_offset(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> Tuple[str, tuple]:
        """
        Format LIMIT/OFFSET as OFFSET FETCH for SQL Server 2012+.

        SQL Server 2012+ uses OFFSET FETCH syntax for pagination.
        Note: ORDER BY is required when using OFFSET FETCH.
        """
        if limit is None and offset is None:
            return "", ()

        if self.version < SQL_SERVER_2012:
            raise UnsupportedFeatureError(
                self.name,
                "OFFSET FETCH pagination",
                "SQL Server 2012+ required for OFFSET FETCH. Use ROW_NUMBER() for older versions."
            )

        sql_parts = []

        offset_val = offset or 0
        sql_parts.append(f"OFFSET {offset_val} ROWS")

        if limit is not None:
            sql_parts.append(f"FETCH NEXT {limit} ROWS ONLY")

        return " ".join(sql_parts), ()

    def format_limit_offset_clause(self, clause: "LimitOffsetClause") -> Tuple[str, tuple]:
        """Format LIMIT/OFFSET clause for SQL Server using OFFSET FETCH syntax."""
        if clause.limit is None and clause.offset is None:
            return "", ()

        if self.version < SQL_SERVER_2012:
            raise UnsupportedFeatureError(
                self.name,
                "OFFSET FETCH pagination",
                "SQL Server 2012+ required for OFFSET FETCH. Use ROW_NUMBER() for older versions."
            )

        parts = []

        offset_val = clause.offset if clause.offset is not None else 0
        parts.append(f"OFFSET {offset_val} ROWS")

        if clause.limit is not None:
            if getattr(clause, "with_ties", False):
                if not self.supports_fetch_with_ties():
                    raise UnsupportedFeatureError(
                        self.name, "FETCH NEXT ... ROWS WITH TIES",
                        "This SQL Server dialect does not support WITH TIES."
                    )
                parts.append(f"FETCH NEXT {clause.limit} ROWS WITH TIES")
            else:
                parts.append(f"FETCH NEXT {clause.limit} ROWS ONLY")

        return " ".join(parts), ()

    def format_query_statement(self, expr: "QueryExpression") -> Tuple[str, tuple]:
        sql, params = super().format_query_statement(expr)
        if expr.limit_offset is not None and expr.order_by is None:
            lo_sql = expr.limit_offset.to_sql()[0]
            if lo_sql and lo_sql in sql:
                sql = sql.replace(lo_sql, f"ORDER BY (SELECT NULL) {lo_sql}")
            else:
                sql += " ORDER BY (SELECT NULL)"
        return sql, tuple(params)
