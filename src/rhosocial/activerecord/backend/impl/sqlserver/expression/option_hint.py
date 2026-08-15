# src/rhosocial/activerecord/backend/impl/sqlserver/expression/option_hint.py
"""SQL Server OPTION query hint clause.

SQL Server exposes optimizer hints through the query-level ``OPTION`` clause
rather than comment-style hints:

    SELECT ... OPTION (MAXDOP 4, RECOMPILE, OPTIMIZE FOR (@p = 10));

This module defines ``SQLServerOptionHintClause`` together with factory
helpers that produce the individual hint expressions. SQL generation is
delegated to the dialect's ``format_query_option_clause`` formatter. The
OPTION clause is available in every supported SQL Server version (2005+).
"""

from typing import Any, Sequence, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams

if TYPE_CHECKING:
    from ..dialect import SQLServerDialect


def recompile_hint() -> str:
    """Return a RECOMPILE hint forcing a new plan for each execution."""
    return "RECOMPILE"


def maxdop_hint(degree: int) -> str:
    """Return a MAXDOP hint limiting the degree of parallelism."""
    return f"MAXDOP {degree}"


def optimize_for_hint(pairs: Sequence[Tuple[str, Any]]) -> str:
    """Return an OPTIMIZE FOR hint.

    Args:
        pairs: Sequence of ``(variable, value)`` tuples. A ``None`` value
            renders the ``UNKNOWN`` literal, e.g.
            ``[("@p", 10), ("@q", None)]`` renders
            ``OPTIMIZE FOR (@p = 10, @q = UNKNOWN)``.
    """
    parts = []
    for variable, value in pairs:
        if value is None:
            parts.append(f"{variable} = UNKNOWN")
        else:
            parts.append(f"{variable} = {value}")
    return f"OPTIMIZE FOR ({', '.join(parts)})"


def hash_join_hint() -> str:
    """Return a HASH JOIN hint for the whole query."""
    return "HASH JOIN"


def loop_join_hint() -> str:
    """Return a LOOP JOIN hint for the whole query."""
    return "LOOP JOIN"


def merge_join_hint() -> str:
    """Return a MERGE JOIN hint for the whole query."""
    return "MERGE JOIN"


class SQLServerOptionHintClause(BaseExpression):
    """SQL Server OPTION query hint clause.

    Holds the individual hint expressions and delegates rendering to the
    dialect's ``format_query_option_clause``.

    Attributes:
        hints: List of hint strings (see the module-level factories).

    Example:
        >>> clause = SQLServerOptionHintClause(
        ...     dialect, [maxdop_hint(4), recompile_hint(), optimize_for_hint([("@p", 10)])]
        ... )
        >>> sql, params = clause.to_sql()
        >>> assert sql == "OPTION (MAXDOP 4, RECOMPILE, OPTIMIZE FOR (@p = 10))"
    """

    def __init__(self, dialect: "SQLServerDialect", hints: Sequence[str]):
        super().__init__(dialect)
        self.hints = list(hints)

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not self.hints:
            raise ValueError("at least one query hint is required")

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_query_option_clause(self)
