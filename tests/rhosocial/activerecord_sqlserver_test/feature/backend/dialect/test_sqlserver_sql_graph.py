# tests/rhosocial/activerecord_sqlserver_test/feature/backend/dialect/test_sqlserver_sql_graph.py
"""SQL Server SQL Graph tests (node/edge tables, MATCH predicate, SHORTEST_PATH).

SQL Server SQL Graph is independent from SQL/PGQ; see the plan
``.claude/plan/2026-09-16/pgq-expression-layer.md`` §4.3.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    CreateTableExpression,
)
from rhosocial.activerecord.backend.expression.types import IntegerType, VarCharType
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression import (
    SQLServerForPathTable,
    SQLServerGraphDirection,
    SQLServerGraphEdgeRef,
    SQLServerGraphNodeRef,
    SQLServerGraphPathAggregate,
    SQLServerGraphPattern,
    SQLServerGraphPseudoColumn,
    SQLServerMatchPredicate,
    SQLServerShortestPathExpression,
)
from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl import (
    SQLServerAsGraphTableExpression,
    SQLServerEdgeConstraint,
    SQLServerGraphTableKind,
)


@pytest.fixture
def dialect():
    return SQLServerDialect(version=(17, 0, 0))


@pytest.fixture
def dialect_2017():
    return SQLServerDialect(version=(14, 0, 0))


def _path(dialect, edge="friend", direction=SQLServerGraphDirection.RIGHT):
    return SQLServerGraphPattern(
        dialect,
        SQLServerGraphNodeRef(dialect, "Person", alias="Person1"),
        [(SQLServerGraphEdgeRef(dialect, edge, direction), SQLServerGraphNodeRef(dialect, "Person", alias="Person2"))],
    )


class TestCapabilitySwitches:
    def test_sql_graph_since_2017(self, dialect_2017):
        assert dialect_2017.supports_sql_graph() is True
        assert dialect_2017.supports_graph_table_kind() is True
        assert dialect_2017.supports_graph_pseudo_columns() is True
        assert dialect_2017.supports_edge_constraints() is True

    def test_shortest_path_since_2019(self, dialect_2017, dialect):
        assert dialect_2017.supports_shortest_path() is False
        assert dialect_2017.supports_graph_path_aggregates() is False
        assert dialect.supports_shortest_path() is True
        assert dialect.supports_graph_path_aggregates() is True

    def test_protocol_isinstance(self, dialect):
        from rhosocial.activerecord.backend.impl.sqlserver.protocols import SQLServerGraphSupport

        assert isinstance(dialect, SQLServerGraphSupport)


class TestPatternRendering:
    def test_right_direction(self, dialect):
        sql, _ = _path(dialect).to_sql()
        assert sql == "[Person1]-([friend])->[Person2]"

    def test_left_direction(self, dialect):
        sql, _ = _path(dialect, direction=SQLServerGraphDirection.LEFT).to_sql()
        assert sql == "[Person1]<-([friend])-[Person2]"

    def test_match_predicate_wraps_pattern(self, dialect):
        sql, _ = SQLServerMatchPredicate(dialect, _path(dialect)).to_sql()
        assert sql == "MATCH([Person1]-([friend])->[Person2])"

    def test_match_combines_with_and(self, dialect):
        sql, _ = SQLServerMatchPredicate(dialect, [_path(dialect), _path(dialect)]).to_sql()
        assert " AND " in sql
        assert sql.startswith("MATCH(") and sql.endswith(")")

    def test_match_combines_with_comma(self, dialect):
        sql, _ = SQLServerMatchPredicate(dialect, [_path(dialect), _path(dialect)], combinator=",").to_sql()
        assert ", " in sql

    def test_match_rejects_other_combinator(self, dialect):
        with pytest.raises(ValueError):
            SQLServerMatchPredicate(dialect, [_path(dialect)], combinator="OR")

    def test_match_requires_pattern(self, dialect):
        with pytest.raises(ValueError):
            SQLServerMatchPredicate(dialect, [])


class TestShortestPath:
    def test_plus_quantifier(self, dialect):
        expr = SQLServerShortestPathExpression(dialect, _path(dialect, edge="fo"))
        sql, _ = expr.to_sql()
        assert sql.endswith(")" + "+")
        assert sql.startswith("SHORTEST_PATH(")

    def test_bounded_quantifier(self, dialect):
        expr = SQLServerShortestPathExpression(dialect, _path(dialect, edge="fo"), maximum=3)
        sql, _ = expr.to_sql()
        assert sql.endswith("{1,3}")

    def test_minimum_must_be_one(self, dialect):
        with pytest.raises(ValueError):
            SQLServerShortestPathExpression(dialect, _path(dialect), minimum=2)

    def test_raises_before_2019(self, dialect_2017):
        expr = SQLServerShortestPathExpression(dialect_2017, _path(dialect_2017))
        with pytest.raises(UnsupportedFeatureError, match="SHORTEST_PATH"):
            expr.to_sql()

    def test_for_path_raises_before_2019(self, dialect_2017):
        with pytest.raises(UnsupportedFeatureError, match="FOR PATH"):
            SQLServerForPathTable(dialect_2017, "friendOf", alias="fo").to_sql()

    def test_for_path_renders(self, dialect):
        sql, _ = SQLServerForPathTable(dialect, "friendOf", alias="fo").to_sql()
        assert sql == "[friendOf] FOR PATH AS [fo]"


class TestPathAggregate:
    def test_renders(self, dialect):
        agg = SQLServerGraphPathAggregate(
            dialect, "STRING_AGG", SQLServerGraphNodeRef(dialect, "Person", alias="Person2"),
            separator="->", alias="Friends",
        )
        sql, params = agg.to_sql()
        assert sql == "STRING_AGG([Person2], '->') WITHIN GROUP (GRAPH PATH) AS [Friends]"
        assert params == ()

    def test_raises_before_2019(self, dialect_2017):
        agg = SQLServerGraphPathAggregate(
            dialect_2017, "STRING_AGG", SQLServerGraphNodeRef(dialect_2017, "Person", alias="P"),
            separator="->",
        )
        with pytest.raises(UnsupportedFeatureError, match="path aggregate"):
            agg.to_sql()


class TestPseudoColumn:
    def test_renders_unquoted(self, dialect):
        sql, _ = SQLServerGraphPseudoColumn(dialect, "$node_id").to_sql()
        assert sql == "$node_id"

    @pytest.mark.parametrize("name", ["$edge_id", "$from_id", "$to_id"])
    def test_allowed_names(self, dialect, name):
        sql, _ = SQLServerGraphPseudoColumn(dialect, name).to_sql()
        assert sql == name

    def test_rejects_unknown_name(self, dialect):
        with pytest.raises(ValueError, match="pseudo-column"):
            SQLServerGraphPseudoColumn(dialect, "id")


class TestDdl:
    def test_as_node(self, dialect):
        sql, _ = SQLServerAsGraphTableExpression(dialect, SQLServerGraphTableKind.NODE).to_sql()
        assert sql == "AS NODE"

    def test_as_edge(self, dialect):
        sql, _ = SQLServerAsGraphTableExpression(dialect, SQLServerGraphTableKind.EDGE).to_sql()
        assert sql == "AS EDGE"

    def test_edge_constraint(self, dialect):
        sql, _ = SQLServerEdgeConstraint(dialect, "Person", "Person", name="ec_friend").to_sql()
        assert sql == "CONSTRAINT [ec_friend] CONNECTION ([Person] TO [Person])"

    def test_create_table_as_node(self, dialect):
        expr = CreateTableExpression(
            dialect, table="Person",
            columns=[ColumnDefinition(dialect, "ID", IntegerType(dialect))],
            dialect_options={"graph_table_kind": SQLServerGraphTableKind.NODE},
        )
        sql, _ = expr.to_sql()
        assert sql.endswith(") AS NODE")

    def test_create_table_edge_with_constraint(self, dialect):
        expr = CreateTableExpression(
            dialect, table="friend",
            columns=[ColumnDefinition(dialect, "start_date", VarCharType(dialect))],
            dialect_options={
                "graph_table_kind": SQLServerGraphTableKind.EDGE,
                "edge_constraints": [SQLServerEdgeConstraint(dialect, "Person", "Person", name="ec_friend")],
            },
        )
        sql, _ = expr.to_sql()
        assert "CONNECTION ([Person] TO [Person])" in sql
        assert sql.endswith(") AS EDGE") or sql.endswith(" AS EDGE")


class TestCorePgqStillRejected:
    """Core SQL/PGQ ``MatchClause`` must remain rejected (independent families)."""

    def test_core_match_clause_rejected(self, dialect):
        from rhosocial.activerecord.backend.expression.graph import GraphVertex, MatchClause

        clause = MatchClause(dialect, GraphVertex(dialect, "p", "Person"))
        with pytest.raises(UnsupportedFeatureError, match="graph MATCH clause"):
            dialect.format_match_clause(clause)

    def test_supports_graph_match_false(self, dialect):
        assert dialect.supports_graph_match() is False
