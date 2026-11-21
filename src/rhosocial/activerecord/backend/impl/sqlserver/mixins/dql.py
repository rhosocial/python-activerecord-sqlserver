# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/dql.py
from typing import Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from .version_constants import SQL_SERVER_2012

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.query_parts import LimitOffsetClause

from rhosocial.activerecord.backend.expression import (
    Literal,
    OrderByClause,
    Subquery,
)
from rhosocial.activerecord.backend.expression.statements import QueryStatement


class SQLServerDQLMixin:
    """SQL Server SELECT / LIMIT / OFFSET formatting."""

    def supports_fetch_with_ties(self) -> bool:
        """SQL Server supports WITH TIES only with TOP, not OFFSET FETCH."""
        return False

    def supports_nulls_first_last(self) -> bool:
        """SQL Server does not support explicit NULLS FIRST/LAST ordering."""
        return False

    def render_limit_offset(
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

    def format_limit_offset_clause(self, expr: "LimitOffsetClause") -> Tuple[str, tuple]:
        """Format LIMIT/OFFSET clause for SQL Server using OFFSET FETCH syntax."""
        if expr.with_ties:
            raise UnsupportedFeatureError(
                self.name, "FETCH NEXT ... ROWS WITH TIES",
                "SQL Server supports WITH TIES only with TOP, not OFFSET FETCH."
            )

        if expr.limit is None and expr.offset is None:
            return "", ()

        if self.version < SQL_SERVER_2012:
            raise UnsupportedFeatureError(
                self.name,
                "OFFSET FETCH pagination",
                "SQL Server 2012+ required for OFFSET FETCH. Use ROW_NUMBER() for older versions."
            )

        parts = []

        offset_val = expr.offset if expr.offset is not None else 0
        parts.append(f"OFFSET {offset_val} ROWS")

        if expr.limit is not None:
            parts.append(f"FETCH NEXT {expr.limit} ROWS ONLY")

        return " ".join(parts), ()

    def format_query_statement(self, expr: "QueryStatement") -> Tuple[str, tuple]:
        """Format a complete SELECT query.

        SQL Server refuses OFFSET/FETCH on a query without an ORDER BY. The
        preamble is synthesized as an ``ORDER BY`` *expression* and rendered by
        the generic formatter -- the produced SQL is never patched afterwards,
        because a formatter only concatenates what the clause objects return.
        """
        if expr.limit_offset is None or expr.order_by is not None:
            return super().format_query_statement(expr)
        preamble = OrderByClause(
            self,
            expressions=[
                (
                    Subquery(
                        self, QueryStatement(self, select=[Literal(self, None)])
                    ),
                    "ASC",
                )
            ],
        )
        ordered = QueryStatement(
            self,
            select=expr.select,
            from_=expr.from_,
            where=expr.where,
            group_by_having=expr.group_by_having,
            order_by=preamble,
            qualify=expr.qualify,
            limit_offset=expr.limit_offset,
            for_update=expr.for_update,
            select_modifier=expr.select_modifier,
        )
        return super().format_query_statement(ordered)
