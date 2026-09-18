# src/rhosocial/activerecord/backend/impl/sqlserver/expression/graph.py
"""SQL Server SQL Graph query expressions (SQL Server 2017+ / 2019+).

These are **independent** from the core SQL/PGQ family: SQL Server models graph
data as node/edge tables and queries with a ``MATCH`` predicate using
ASCII-art patterns, ``SHORTEST_PATH`` and path aggregates. SQL generation is
delegated to the SQL Server dialect's ``format_sqlserver_*`` formatters.
"""

from enum import Enum
from typing import List, Optional, Sequence, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLPredicate
from rhosocial.activerecord.backend.expression.core import Column

if TYPE_CHECKING:  # pragma: no cover
    from ..dialect import SQLServerDialect


class SQLServerGraphDirection(Enum):
    """Direction of an edge in a MATCH pattern."""

    RIGHT = "->"  # -(edge)->
    LEFT = "<-"  # <-(edge)-


class SQLServerGraphPseudoColumn(Column):
    """A SQL Graph pseudo-column: ``$node_id`` / ``$edge_id`` / ``$from_id`` / ``$to_id``.

    Pseudo-columns must never be quoted; the name is validated at construction.
    """

    _ALLOWED = frozenset({"$node_id", "$edge_id", "$from_id", "$to_id"})

    def __init__(self, dialect: "SQLServerDialect", name: str, table: Optional[str] = None,
                 alias: Optional[str] = None):
        if name not in self._ALLOWED:
            raise ValueError(
                f"Invalid graph pseudo-column {name!r}; allowed: {sorted(self._ALLOWED)}"
            )
        super().__init__(dialect, name, table=table, alias=alias, name_need_quote=False)


class SQLServerGraphNodeRef(BaseExpression):
    """A node reference inside a MATCH pattern.

    Attributes:
        table: Node table name or alias.
        alias: Optional alias used in the ASCII-art pattern.
        last_node: Render as ``LAST_NODE(<node>)``.
    """

    def __init__(self, dialect: "SQLServerDialect", table: str, alias: Optional[str] = None,
                 last_node: bool = False):
        super().__init__(dialect)
        self.table = table
        self.alias = alias
        self.last_node = bool(last_node)

    @property
    def format_method(self) -> str:
        return "format_sqlserver_graph_node_ref"


class SQLServerGraphEdgeRef(BaseExpression):
    """An edge reference inside a MATCH pattern (``-(edge)->`` / ``<-(edge)-``)."""

    def __init__(self, dialect: "SQLServerDialect", edge: str,
                 direction: SQLServerGraphDirection = SQLServerGraphDirection.RIGHT):
        super().__init__(dialect)
        self.edge = edge
        self.direction = direction

    @property
    def format_method(self) -> str:
        return "format_sqlserver_graph_edge_ref"


class SQLServerGraphPattern(BaseExpression):
    """A single path pattern: ``<start> (<edge> <node>)*``.

    Example:
        ``Person1-(friend)->Person2``
    """

    def __init__(
        self,
        dialect: "SQLServerDialect",
        start: SQLServerGraphNodeRef,
        segments: Optional[Sequence[Tuple[SQLServerGraphEdgeRef, SQLServerGraphNodeRef]]] = None,
    ):
        super().__init__(dialect)
        self.start = start
        self.segments = list(segments) if segments else []

    @property
    def format_method(self) -> str:
        return "format_sqlserver_graph_pattern"


class SQLServerMatchPredicate(SQLPredicate):
    """A ``MATCH (<pattern>[, <pattern>...])`` predicate.

    Multiple patterns are combined with ``AND`` or ``,`` (the two forms SQL
    Server accepts). ``OR`` / ``NOT`` are rejected at construction.
    """

    _COMBINATORS = ("AND", ",")

    def __init__(self, dialect: "SQLServerDialect", patterns, combinator: str = "AND"):
        super().__init__(dialect)
        if isinstance(patterns, BaseExpression):
            patterns = [patterns]
        if not patterns:
            raise ValueError("MATCH requires at least one pattern.")
        comb = combinator.upper() if isinstance(combinator, str) else combinator
        if comb not in self._COMBINATORS:
            raise ValueError(
                f"Invalid MATCH combinator {combinator!r}; SQL Server accepts 'AND' or ','."
            )
        self.patterns = list(patterns)
        self.combinator = comb

    @property
    def format_method(self) -> str:
        return "format_sqlserver_match_predicate"


class SQLServerShortestPathExpression(BaseExpression):
    """A ``SHORTEST_PATH(<start>(<segments>)<quantifier>)`` traversal (SQL Server 2019+).

    SQL Server restricts the quantifier to ``+`` or ``{1,n}``; ``minimum`` must
    therefore be ``1``.
    """

    def __init__(
        self,
        dialect: "SQLServerDialect",
        pattern,
        minimum: int = 1,
        maximum: Optional[int] = None,
        extra_patterns: Optional[List] = None,
        combinator: str = "AND",
    ):
        super().__init__(dialect)
        if minimum != 1:
            raise ValueError(
                "SQL Server SHORTEST_PATH quantifier must be '+' or '{1,n}'; "
                "minimum must be 1."
            )
        if maximum is not None and maximum < 1:
            raise ValueError("maximum must be >= 1.")
        comb = combinator.upper() if isinstance(combinator, str) else combinator
        if comb not in ("AND", ","):
            raise ValueError(
                f"Invalid SHORTEST_PATH combinator {combinator!r}; use 'AND' or ','."
            )
        # Attribute names mirror the constructor parameters so that the
        # introspection-based get_params() / serialization round-trip works.
        self.pattern = pattern
        self.extra_patterns = list(extra_patterns or [])
        self.combinator = comb
        self.minimum = minimum
        self.maximum = maximum

    @property
    def patterns(self) -> List:
        """All patterns: the primary ``pattern`` followed by ``extra_patterns``."""
        return [self.pattern] + list(self.extra_patterns)

    @property
    def format_method(self) -> str:
        return "format_sqlserver_shortest_path"


class SQLServerGraphPathAggregate(BaseExpression):
    """A path aggregate: ``<agg>(<expr>[, <sep>]) WITHIN GROUP (GRAPH PATH)``.

    Example:
        ``STRING_AGG(Person2.name, '->') WITHIN GROUP (GRAPH PATH) AS Friends``
    """

    def __init__(self, dialect: "SQLServerDialect", function: str, expression: BaseExpression,
                 separator: Optional[str] = None, alias: Optional[str] = None):
        super().__init__(dialect)
        self.function = function
        self.expression = expression
        self.separator = separator
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_sqlserver_graph_path_aggregate"


class SQLServerForPathTable(BaseExpression):
    """A ``<table> FOR PATH [AS <alias>]`` FROM item.

    Used with ``SHORTEST_PATH`` so intermediate nodes/edges can be projected by
    path aggregates.
    """

    def __init__(self, dialect: "SQLServerDialect", table: str, alias: Optional[str] = None):
        super().__init__(dialect)
        self.table = table
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_sqlserver_for_path_table"


__all__ = [
    "SQLServerGraphDirection",
    "SQLServerGraphPseudoColumn",
    "SQLServerGraphNodeRef",
    "SQLServerGraphEdgeRef",
    "SQLServerGraphPattern",
    "SQLServerMatchPredicate",
    "SQLServerShortestPathExpression",
    "SQLServerGraphPathAggregate",
    "SQLServerForPathTable",
]
