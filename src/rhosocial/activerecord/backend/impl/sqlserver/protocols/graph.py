# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/graph.py
"""SQL Server SQL Graph support protocol (SQL Server 2017+ / 2019+).

SQL Server's SQL Graph is **not** SQL/PGQ: it models graph data as node/edge
**tables** (``CREATE TABLE ... AS NODE | AS EDGE``), queries with a ``MATCH``
**predicate** using ASCII-art patterns, and (2019+) traverses with
``SHORTEST_PATH`` and path aggregates. This protocol is therefore kept separate
from the generic ``GraphSupport`` / ``GraphTableSupport``.
"""

from typing import Any, Protocol, Tuple, runtime_checkable


@runtime_checkable
class SQLServerGraphSupport(Protocol):
    """Contract for SQL Server SQL Graph capability and formatting."""

    # region capability switches

    def supports_sql_graph(self) -> bool:
        """Whether SQL Graph (node/edge tables + MATCH predicate) is supported."""
        ...  # pragma: no cover

    def supports_graph_table_kind(self) -> bool:
        """Whether ``CREATE TABLE ... AS NODE | AS EDGE`` is supported."""
        ...  # pragma: no cover

    def supports_graph_pseudo_columns(self) -> bool:
        """Whether graph pseudo-columns (``$node_id`` etc.) are usable."""
        ...  # pragma: no cover

    def supports_shortest_path(self) -> bool:
        """Whether ``SHORTEST_PATH`` is supported (SQL Server 2019+)."""
        ...  # pragma: no cover

    def supports_graph_path_aggregates(self) -> bool:
        """Whether path aggregates (``... WITHIN GROUP (GRAPH PATH)``) are supported."""
        ...  # pragma: no cover

    def supports_edge_constraints(self) -> bool:
        """Whether ``CONNECTION`` edge constraints are supported."""
        ...  # pragma: no cover

    # endregion

    # region formatting

    def format_sqlserver_graph_table_kind(self, expr: Any) -> Tuple[str, tuple]:
        """Format the ``AS NODE`` / ``AS EDGE`` table kind fragment."""
        ...  # pragma: no cover

    def format_sqlserver_edge_constraint(self, constraint: Any) -> Tuple[str, tuple]:
        """Format a ``CONNECTION (from TO to)`` edge constraint."""
        ...  # pragma: no cover

    def format_sqlserver_graph_node_ref(self, ref: Any) -> Tuple[str, tuple]:
        """Format a node reference in a pattern (optionally ``LAST_NODE(...)``)."""
        ...  # pragma: no cover

    def format_sqlserver_graph_edge_ref(self, ref: Any) -> Tuple[str, tuple]:
        """Format an edge reference in a pattern (``-(edge)->`` / ``<-(edge)-``)."""
        ...  # pragma: no cover

    def format_sqlserver_graph_pattern(self, pattern: Any) -> Tuple[str, tuple]:
        """Format a graph search pattern (ASCII-art node/edge chain)."""
        ...  # pragma: no cover

    def format_sqlserver_match_predicate(self, predicate: Any) -> Tuple[str, tuple]:
        """Format a ``MATCH (<pattern>)`` predicate."""
        ...  # pragma: no cover

    def format_sqlserver_shortest_path(self, expr: Any) -> Tuple[str, tuple]:
        """Format a ``SHORTEST_PATH (<pattern>{1,n})`` expression."""
        ...  # pragma: no cover

    def format_sqlserver_graph_path_aggregate(self, aggregate: Any) -> Tuple[str, tuple]:
        """Format a path aggregate (``<agg>(...) WITHIN GROUP (GRAPH PATH)``)."""
        ...  # pragma: no cover

    def format_sqlserver_for_path_table(self, table: Any) -> Tuple[str, tuple]:
        """Format a ``<table> FOR PATH [AS alias]`` FROM item."""
        ...  # pragma: no cover

    # endregion


__all__ = ["SQLServerGraphSupport"]
