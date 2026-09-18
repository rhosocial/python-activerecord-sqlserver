# tests/rhosocial/activerecord_sqlserver_test/feature/backend/dialect/test_sqlserver_sql_graph.py
"""SQL Server SQL Graph tests (node/edge tables, MATCH predicate, SHORTEST_PATH).

SQL Server SQL Graph is independent from SQL/PGQ; see the plan
``.claude/plan/2026-09-16/pgq-expression-layer.md`` §4.3.
"""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    CreateTableExpression,
)
from rhosocial.activerecord.backend.expression.types import IntegerType
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
from rhosocial.activerecord.backend.impl.sqlserver.options import SQLServerExecutionOptions
from rhosocial.activerecord.backend.impl.sqlserver.protocols import SQLServerGraphSupport
from rhosocial.activerecord.testsuite.utils import requires_protocol, skip_test_if_protocol_unsupported
from rhosocial.activerecord.backend.options import StatementType


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

    @pytest.mark.parametrize("major, supported", [(14, False), (15, True), (16, True), (17, True)])
    def test_edge_constraints_since_2019(self, major, supported):
        assert SQLServerDialect(version=(major, 0, 0)).supports_edge_constraints() is supported

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

    @pytest.mark.parametrize("major", [14, 15, 16, 17])
    def test_match_predicate_wraps_pattern(self, major):
        dialect = SQLServerDialect(version=(major, 0, 0))
        assert SQLServerMatchPredicate(dialect, _path(dialect)).to_sql() == (
            "MATCH([Person1]-([friend])->[Person2])", ()
        )

    def test_match_rejected_before_2017(self):
        dialect = SQLServerDialect(version=(13, 0, 0))
        expr = SQLServerMatchPredicate(dialect, _path(dialect))
        with pytest.raises(UnsupportedFeatureError, match="MATCH") as exc:
            expr.to_sql()
        assert "2017" in exc.value.suggestion

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
    @pytest.mark.parametrize(
        "direction, maximum, expected",
        [
            (SQLServerGraphDirection.RIGHT, None, "SHORTEST_PATH([Person1](-([fo])->[Person2])+)"),
            (SQLServerGraphDirection.RIGHT, 3, "SHORTEST_PATH([Person1](-([fo])->[Person2]){1,3})"),
            (SQLServerGraphDirection.LEFT, None, "SHORTEST_PATH([Person1](<-([fo])-[Person2])+)"),
            (SQLServerGraphDirection.LEFT, 3, "SHORTEST_PATH([Person1](<-([fo])-[Person2]){1,3})"),
        ],
    )
    def test_quantifier(self, dialect, direction, maximum, expected):
        expr = SQLServerShortestPathExpression(
            dialect, _path(dialect, edge="fo", direction=direction), maximum=maximum
        )
        assert expr.to_sql() == (expected, ())

    @pytest.mark.parametrize(
        "maximum, expected",
        [
            (None, "SHORTEST_PATH([Person1](-([fo])->[Person2]<-([works])-[Company])+)"),
            (3, "SHORTEST_PATH([Person1](-([fo])->[Person2]<-([works])-[Company]){1,3})"),
        ],
    )
    def test_multi_segment_repeat_group(self, dialect, maximum, expected):
        pattern = _path(dialect, edge="fo")
        pattern.segments.append(
            (
                SQLServerGraphEdgeRef(dialect, "works", SQLServerGraphDirection.LEFT),
                SQLServerGraphNodeRef(dialect, "Company"),
            )
        )
        assert SQLServerShortestPathExpression(dialect, pattern, maximum=maximum).to_sql() == (
            expected, ()
        )

    @pytest.mark.parametrize("maximum, quantifier", [(None, "+"), (3, "{1,3}")])
    @pytest.mark.parametrize("combinator, separator", [("AND", " AND "), (",", ", ")])
    def test_multiple_extra_patterns(self, dialect, maximum, quantifier, combinator, separator):
        second = SQLServerGraphPattern(
            dialect,
            SQLServerGraphNodeRef(dialect, "Person", alias="Person3"),
            [
                (
                    SQLServerGraphEdgeRef(dialect, "works", SQLServerGraphDirection.LEFT),
                    SQLServerGraphNodeRef(dialect, "Company"),
                )
            ],
        )
        third = SQLServerGraphPattern(
            dialect,
            SQLServerGraphNodeRef(dialect, "City"),
            [
                (
                    SQLServerGraphEdgeRef(dialect, "located"),
                    SQLServerGraphNodeRef(dialect, "Country"),
                )
            ],
        )
        expr = SQLServerShortestPathExpression(
            dialect, _path(dialect, edge="fo"), maximum=maximum,
            extra_patterns=[second, third], combinator=combinator,
        )
        assert expr.to_sql() == (
            f"SHORTEST_PATH([Person1](-([fo])->[Person2]){quantifier}"
            f"{separator}[Person3](<-([works])-[Company]){quantifier}"
            f"{separator}[City](-([located])->[Country]){quantifier})",
            (),
        )

    @pytest.mark.parametrize("maximum, quantifier", [(None, "+"), (3, "{1,3}")])
    @pytest.mark.parametrize("combinator, separator", [("AND", " AND "), (",", ", ")])
    def test_params_flattened_once_in_pattern_order(self, dialect, maximum, quantifier, combinator, separator):
        refs = [Mock() for _ in range(10)]
        for index, ref in enumerate(refs):
            ref.to_sql.return_value = (f"marker{index}", (f"param{index}a", f"param{index}b"))
        first = SQLServerGraphPattern(dialect, refs[0], [(refs[1], refs[2]), (refs[3], refs[4])])
        second = SQLServerGraphPattern(dialect, refs[5], [(refs[6], refs[7]), (refs[8], refs[9])])
        expr = SQLServerShortestPathExpression(
            dialect, first, maximum=maximum, extra_patterns=[second], combinator=combinator
        )
        assert expr.to_sql() == (
            f"SHORTEST_PATH(marker0(marker1marker2marker3marker4){quantifier}"
            f"{separator}marker5(marker6marker7marker8marker9){quantifier})",
            (
                "param0a", "param0b", "param1a", "param1b", "param2a", "param2b",
                "param3a", "param3b", "param4a", "param4b", "param5a", "param5b",
                "param6a", "param6b", "param7a", "param7b", "param8a", "param8b",
                "param9a", "param9b",
            ),
        )
        for ref in refs:
            ref.to_sql.assert_called_once_with()

    @pytest.mark.parametrize("empty_extra", [False, True])
    def test_empty_segments_rejected(self, dialect, empty_extra):
        empty = SQLServerGraphPattern(dialect, SQLServerGraphNodeRef(dialect, "Person"), [])
        with pytest.raises(ValueError, match="at least one segment"):
            SQLServerShortestPathExpression(
                dialect, _path(dialect) if empty_extra else empty,
                extra_patterns=[empty] if empty_extra else None,
            ).to_sql()

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
    @pytest.mark.parametrize("major", [14, 15, 16, 17])
    @pytest.mark.parametrize(
        "kind, expected", [(SQLServerGraphTableKind.NODE, "AS NODE"), (SQLServerGraphTableKind.EDGE, "AS EDGE")]
    )
    def test_graph_table_kind(self, major, kind, expected):
        dialect = SQLServerDialect(version=(major, 0, 0))
        assert SQLServerAsGraphTableExpression(dialect, kind).to_sql() == (expected, ())

    @pytest.mark.parametrize("kind", [SQLServerGraphTableKind.NODE, SQLServerGraphTableKind.EDGE])
    @pytest.mark.parametrize("create_table", [False, True])
    def test_graph_table_rejected_before_2017(self, kind, create_table):
        dialect = SQLServerDialect(version=(13, 0, 0))
        expr = SQLServerAsGraphTableExpression(dialect, kind)
        if create_table:
            expr = CreateTableExpression(
                dialect, table="graph_table",
                columns=[ColumnDefinition(dialect, "ID", IntegerType(dialect))],
                dialect_options={"graph_table_kind": kind},
            )
        with pytest.raises(UnsupportedFeatureError, match="AS NODE/EDGE") as exc:
            expr.to_sql()
        assert "2017" in exc.value.suggestion

    @pytest.mark.parametrize("major", [14, 15, 16, 17])
    @pytest.mark.parametrize(
        "name, expected",
        [
            (None, "CONNECTION ([Person] TO [Person])"),
            ("ec_friend", "CONSTRAINT [ec_friend] CONNECTION ([Person] TO [Person])"),
        ],
    )
    def test_edge_constraint(self, major, name, expected):
        dialect = SQLServerDialect(version=(major, 0, 0))
        expr = SQLServerEdgeConstraint(dialect, "Person", "Person", name=name)
        if major == 14:
            with pytest.raises(UnsupportedFeatureError, match="CONNECTION") as exc:
                expr.to_sql()
            assert "2019" in exc.value.suggestion
        else:
            assert expr.to_sql() == (expected, ())

    @pytest.mark.parametrize("major", [14, 15, 16, 17])
    @pytest.mark.parametrize(
        "kind, expected",
        [
            (SQLServerGraphTableKind.NODE, "CREATE TABLE [graph_table] ([ID] INT) AS NODE"),
            (SQLServerGraphTableKind.EDGE, "CREATE TABLE [graph_table] ([ID] INT) AS EDGE"),
        ],
    )
    def test_create_graph_table(self, major, kind, expected):
        dialect = SQLServerDialect(version=(major, 0, 0))
        expr = CreateTableExpression(
            dialect, table="graph_table",
            columns=[ColumnDefinition(dialect, "ID", IntegerType(dialect))],
            dialect_options={"graph_table_kind": kind},
        )
        assert expr.to_sql() == (expected, ())

    @pytest.mark.parametrize("major", [14, 15, 16, 17])
    def test_create_table_edge_with_constraint(self, major):
        dialect = SQLServerDialect(version=(major, 0, 0))
        expr = CreateTableExpression(
            dialect, table="friend",
            columns=[ColumnDefinition(dialect, "ID", IntegerType(dialect))],
            dialect_options={
                "graph_table_kind": SQLServerGraphTableKind.EDGE,
                "edge_constraints": [SQLServerEdgeConstraint(dialect, "Person", "Person", name="ec_friend")],
            },
        )
        if major == 14:
            with pytest.raises(UnsupportedFeatureError, match="CONNECTION") as exc:
                expr.to_sql()
            assert "2019" in exc.value.suggestion
        else:
            assert expr.to_sql() == (
                "CREATE TABLE [friend] ([ID] INT, "
                "CONSTRAINT [ec_friend] CONNECTION ([Person] TO [Person])) AS EDGE",
                (),
            )


@pytest.fixture
def check_graph_protocol_requirements(request, sqlserver_backend):
    subject = SimpleNamespace(__backend__=sqlserver_backend)
    for marker in request.node.iter_markers("requires_protocol"):
        protocol_class, method_name = marker.args[0]
        skip_test_if_protocol_unsupported(subject, protocol_class, method_name)


@pytest.mark.requires_sqlserver
@pytest.mark.usefixtures("check_graph_protocol_requirements")
@requires_protocol(SQLServerGraphSupport, "supports_sql_graph")
@requires_protocol(SQLServerGraphSupport, "supports_graph_table_kind")
@requires_protocol(SQLServerGraphSupport, "supports_graph_pseudo_columns")
@requires_protocol(SQLServerGraphSupport, "supports_shortest_path")
@requires_protocol(SQLServerGraphSupport, "supports_graph_path_aggregates")
@requires_protocol(SQLServerGraphSupport, "supports_edge_constraints")
class TestGraphExecution:
    @pytest.mark.parametrize("maximum", [None, 3])
    @pytest.mark.parametrize("direction", [SQLServerGraphDirection.RIGHT, SQLServerGraphDirection.LEFT])
    @pytest.mark.parametrize("segment_count", [1, 2])
    def test_shortest_path_and_edge_constraint(self, sqlserver_backend, maximum, direction, segment_count):
        backend = sqlserver_backend
        dialect = backend.dialect
        transaction = backend.transaction_manager
        transaction.begin()
        try:
            suffix = uuid4().hex
            node_name, edge_name = f"graph_node_{suffix}", f"graph_edge_{suffix}"
            node = dialect.format_identifier(node_name)
            edge = dialect.format_identifier(edge_name)
            node_kind = SQLServerAsGraphTableExpression(dialect, SQLServerGraphTableKind.NODE).to_sql()[0]
            edge_kind = SQLServerAsGraphTableExpression(dialect, SQLServerGraphTableKind.EDGE).to_sql()[0]
            constraint_sql, params = SQLServerEdgeConstraint(dialect, node_name, node_name).to_sql()
            assert params == ()
            backend.execute(f"CREATE TABLE {node} (ID INT NOT NULL) {node_kind}")
            backend.execute(f"CREATE TABLE {edge} ({constraint_sql}) {edge_kind}")
            backend.execute(f"INSERT INTO {node} (ID) VALUES (1), (2), (3), (4), (5)")
            backend.execute(
                f"INSERT INTO {edge} ($from_id, $to_id) "
                f"SELECT a.$node_id, b.$node_id FROM {node} a, {node} b WHERE b.ID = a.ID + 1"
            )
            segments, tables = [], [f"{node} AS [Person1]"]
            for index in range(segment_count):
                edge_alias, node_alias = f"fo{index}", f"Person{index + 2}"
                segments.append((
                    SQLServerGraphEdgeRef(dialect, edge_alias, direction),
                    SQLServerGraphNodeRef(dialect, node_name, alias=node_alias),
                ))
                tables.extend([
                    SQLServerForPathTable(dialect, edge_name, alias=edge_alias).to_sql()[0],
                    SQLServerForPathTable(dialect, node_name, alias=node_alias).to_sql()[0],
                ])
            pattern = SQLServerGraphPattern(
                dialect, SQLServerGraphNodeRef(dialect, node_name, alias="Person1"), segments
            )
            predicate = SQLServerMatchPredicate(
                dialect, SQLServerShortestPathExpression(dialect, pattern, maximum=maximum)
            )
            match_sql, params = predicate.to_sql()
            start_id = 1 if direction == SQLServerGraphDirection.RIGHT else 5
            result = backend.execute(
                f"SELECT LAST_VALUE([Person{segment_count + 1}].ID) WITHIN GROUP (GRAPH PATH) AS [endpoint_id] "
                f"FROM {', '.join(tables)} WHERE {match_sql} AND [Person1].ID = {dialect.p()}",
                params + (start_id,),
                options=SQLServerExecutionOptions(stmt_type=StatementType.DQL, noscan=True),
            )
            assert result.data is not None
            actual = {row["endpoint_id"] for row in result.data}
            hops = min(4 // segment_count, maximum or 4)
            step = segment_count if start_id == 1 else -segment_count
            assert actual == {start_id + step * iteration for iteration in range(1, hops + 1)}
        finally:
            if transaction.is_active:
                transaction.rollback()


class TestCorePgqStillRejected:
    """Core SQL/PGQ ``MatchClause`` must remain rejected (independent families)."""

    def test_core_match_clause_rejected(self, dialect):
        from rhosocial.activerecord.backend.expression.graph import GraphVertex, MatchClause

        clause = MatchClause(dialect, GraphVertex(dialect, "p", "Person"))
        with pytest.raises(UnsupportedFeatureError, match="graph MATCH clause"):
            dialect.format_match_clause(clause)

    def test_supports_graph_match_false(self, dialect):
        assert dialect.supports_graph_match() is False
