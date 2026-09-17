# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/graph.py
"""SQL Server SQL Graph mixin (SQL Server 2017+ / 2019+).

Implements the ``SQLServerGraphSupport`` contract: node/edge graph tables,
the ``MATCH`` predicate (ASCII-art patterns), ``SHORTEST_PATH`` (2019+),
path aggregates, graph pseudo-columns and ``FOR PATH``.

Kept **independent** of the core SQL/PGQ family; ``supports_graph_match``
stays ``False`` and the core ``MatchClause`` remains rejected.
"""

from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

from .version_constants import SQL_SERVER_2017, SQL_SERVER_2019

if TYPE_CHECKING:  # pragma: no cover
    from ..expression.graph import (
        SQLServerGraphEdgeRef,
        SQLServerGraphNodeRef,
        SQLServerGraphPathAggregate,
        SQLServerGraphPattern,
        SQLServerMatchPredicate,
        SQLServerShortestPathExpression,
        SQLServerForPathTable,
    )
    from ..expression.ddl.graph import (
        SQLServerAsGraphTableExpression,
        SQLServerEdgeConstraint,
    )


class SQLServerGraphMixin:
    """SQL Server SQL Graph capability and formatting implementation."""

    # region capability switches

    def supports_sql_graph(self) -> bool:
        """SQL Graph (node/edge tables + MATCH predicate) requires 2017+."""
        return self.version >= SQL_SERVER_2017

    def supports_graph_table_kind(self) -> bool:
        """``CREATE TABLE ... AS NODE | AS EDGE`` requires SQL Server 2017+."""
        return self.version >= SQL_SERVER_2017

    def supports_graph_pseudo_columns(self) -> bool:
        """Graph pseudo-columns (``$node_id`` etc.) require SQL Server 2017+."""
        return self.version >= SQL_SERVER_2017

    def supports_shortest_path(self) -> bool:
        """``SHORTEST_PATH`` requires SQL Server 2019+."""
        return self.version >= SQL_SERVER_2019

    def supports_graph_path_aggregates(self) -> bool:
        """Path aggregates require SQL Server 2019+."""
        return self.version >= SQL_SERVER_2019

    def supports_edge_constraints(self) -> bool:
        """``CONNECTION`` edge constraints require SQL Server 2019+."""
        return self.version >= SQL_SERVER_2019

    # endregion

    # region DDL formatting

    def format_sqlserver_graph_table_kind(
        self, expr: "SQLServerAsGraphTableExpression"
    ) -> Tuple[str, tuple]:
        """Format the ``AS NODE`` / ``AS EDGE`` table-kind fragment."""
        if not self.supports_graph_table_kind():
            raise UnsupportedFeatureError(
                self.name,
                "CREATE TABLE ... AS NODE/EDGE",
                "SQL Graph tables require SQL Server 2017 or later.",
            )
        return f"AS {expr.kind.value}", ()

    def format_sqlserver_edge_constraint(
        self, constraint: "SQLServerEdgeConstraint"
    ) -> Tuple[str, tuple]:
        """Format a ``[CONSTRAINT name] CONNECTION (<from> TO <to>)`` edge constraint."""
        if not self.supports_edge_constraints():
            raise UnsupportedFeatureError(
                self.name,
                "CONNECTION edge constraint",
                "Edge constraints require SQL Server 2019 or later.",
            )
        parts = []
        if constraint.name:
            parts.append(f"CONSTRAINT {self.format_identifier(constraint.name)}")
        from_table = self.format_identifier(constraint.from_table)
        to_table = self.format_identifier(constraint.to_table)
        parts.append(f"CONNECTION ({from_table} TO {to_table})")
        return " ".join(parts), ()

    # endregion

    # region query formatting

    def format_sqlserver_graph_node_ref(
        self, ref: "SQLServerGraphNodeRef"
    ) -> Tuple[str, tuple]:
        """Format a node reference (optionally ``LAST_NODE(...)``)."""
        if not self.supports_sql_graph():
            raise UnsupportedFeatureError(
                self.name, "SQL Graph MATCH pattern",
                "SQL Graph requires SQL Server 2017 or later.",
            )
        name = self.format_identifier(ref.alias or ref.table)
        if ref.last_node:
            if not self.supports_shortest_path():
                raise UnsupportedFeatureError(
                    self.name, "LAST_NODE",
                    "LAST_NODE requires SQL Server 2019 or later.",
                )
            return f"LAST_NODE({name})", ()
        return name, ()

    def format_sqlserver_graph_edge_ref(
        self, ref: "SQLServerGraphEdgeRef"
    ) -> Tuple[str, tuple]:
        """Format an edge reference (``-(edge)->`` / ``<-(edge)-``)."""
        if not self.supports_sql_graph():
            raise UnsupportedFeatureError(
                self.name, "SQL Graph MATCH pattern",
                "SQL Graph requires SQL Server 2017 or later.",
            )
        from ..expression.graph import SQLServerGraphDirection

        edge = self.format_identifier(ref.edge)
        if ref.direction == SQLServerGraphDirection.LEFT:
            return f"<-({edge})-", ()
        return f"-({edge})->", ()

    def format_sqlserver_graph_pattern(
        self, pattern: "SQLServerGraphPattern"
    ) -> Tuple[str, tuple]:
        """Format a single path pattern (ASCII-art node/edge chain)."""
        if not self.supports_sql_graph():
            raise UnsupportedFeatureError(
                self.name, "SQL Graph MATCH pattern",
                "SQL Graph requires SQL Server 2017 or later.",
            )
        parts, params = [], []
        start_sql, start_params = pattern.start.to_sql()
        parts.append(start_sql)
        params.extend(start_params)
        for edge_ref, node_ref in pattern.segments:
            edge_sql, edge_params = edge_ref.to_sql()
            node_sql, node_params = node_ref.to_sql()
            parts.append(edge_sql)
            parts.append(node_sql)
            params.extend(edge_params)
            params.extend(node_params)
        return "".join(parts), tuple(params)

    def format_sqlserver_match_predicate(
        self, predicate: "SQLServerMatchPredicate"
    ) -> Tuple[str, tuple]:
        """Format a ``MATCH (<pattern>...)`` predicate."""
        if not self.supports_sql_graph():
            raise UnsupportedFeatureError(
                self.name, "SQL Graph MATCH predicate",
                "SQL Graph requires SQL Server 2017 or later.",
            )
        separator = " AND " if predicate.combinator == "AND" else ", "
        parts, params = [], []
        for pattern in predicate.patterns:
            sql, pattern_params = pattern.to_sql()
            parts.append(sql)
            params.extend(pattern_params)
        return f"MATCH({separator.join(parts)})", tuple(params)

    def format_sqlserver_shortest_path(
        self, expr: "SQLServerShortestPathExpression"
    ) -> Tuple[str, tuple]:
        """Format ``SHORTEST_PATH(<start>(<edge/node segments>)<quantifier>)``."""
        if not self.supports_shortest_path():
            raise UnsupportedFeatureError(
                self.name, "SHORTEST_PATH",
                "SHORTEST_PATH requires SQL Server 2019 or later.",
            )
        separator = " AND " if expr.combinator == "AND" else ", "
        quantifier = "+" if expr.maximum is None else "{{1,{0}}}".format(expr.maximum)
        parts, params = [], []
        for pattern in expr.patterns:
            if not pattern.segments:
                raise ValueError("SHORTEST_PATH requires at least one segment per pattern.")
            start_sql, start_params = pattern.start.to_sql()
            params.extend(start_params)
            segments = []
            for edge_ref, node_ref in pattern.segments:
                edge_sql, edge_params = edge_ref.to_sql()
                node_sql, node_params = node_ref.to_sql()
                segments.extend((edge_sql, node_sql))
                params.extend(edge_params)
                params.extend(node_params)
            parts.append(f"{start_sql}({''.join(segments)}){quantifier}")
        return f"SHORTEST_PATH({separator.join(parts)})", tuple(params)

    def format_sqlserver_graph_path_aggregate(
        self, aggregate: "SQLServerGraphPathAggregate"
    ) -> Tuple[str, tuple]:
        """Format a ``<agg>(<expr>[, <sep>]) WITHIN GROUP (GRAPH PATH)`` aggregate."""
        if not self.supports_graph_path_aggregates():
            raise UnsupportedFeatureError(
                self.name, "path aggregate",
                "Path aggregates require SQL Server 2019 or later.",
            )
        expr_sql, params = aggregate.expression.to_sql()
        args = [expr_sql]
        if aggregate.separator is not None:
            args.append(self.format_literal(aggregate.separator))
        sql = f"{aggregate.function.upper()}({', '.join(args)}) WITHIN GROUP (GRAPH PATH)"
        if aggregate.alias:
            sql += f" AS {self.format_identifier(aggregate.alias)}"
        return sql, tuple(params)

    def format_sqlserver_for_path_table(
        self, table: "SQLServerForPathTable"
    ) -> Tuple[str, tuple]:
        """Format a ``<table> FOR PATH [AS <alias>]`` FROM item."""
        if not self.supports_shortest_path():
            raise UnsupportedFeatureError(
                self.name, "FOR PATH",
                "FOR PATH requires SQL Server 2019 or later.",
            )
        sql = f"{self.format_identifier(table.table)} FOR PATH"
        if table.alias:
            sql += f" AS {self.format_identifier(table.alias)}"
        return sql, ()

    # endregion


__all__ = ["SQLServerGraphMixin"]
