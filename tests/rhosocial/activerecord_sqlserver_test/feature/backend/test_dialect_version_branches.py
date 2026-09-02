# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_dialect_version_branches.py
"""Version-gated dialect branch coverage, fully offline.

The SQL Server dialect is instantiated at explicit versions
(2008=10.0 / 2012=11.0 / 2016=13.0 / 2019=15.0 / 2022=16.0) so no server
probe ever happens. Rendering snapshots pin OFFSET-FETCH pagination,
STRING_SPLIT/JSON capability bits, temporary tables, table hints,
MERGE OUTPUT and EXPLAIN/OPTION/TOP clause rendering per version.
"""
from types import SimpleNamespace

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.sqlserver.dialect import (
    SQL_SERVER_2012,
    SQL_SERVER_2016,
    SQL_SERVER_2019,
    SQL_SERVER_2022,
    SQLServerDialect,
)

VERSIONS = {
    "2008": (10, 0, 0),
    "2012": SQL_SERVER_2012,
    "2016": SQL_SERVER_2016,
    "2019": SQL_SERVER_2019,
    "2022": SQL_SERVER_2022,
}


@pytest.fixture(params=VERSIONS.values(), ids=VERSIONS.keys())
def dialect(request):
    return SQLServerDialect(request.param)


class TestPaginationOffsetFetch:
    """OFFSET-FETCH exists only on 2012+, rendered identically above."""

    @pytest.mark.parametrize("version", [(11, 0, 0), (13, 0, 0), (15, 0, 0), (16, 0, 0)])
    def test_offset_fetch_snapshot(self, version):
        sql, params = SQLServerDialect(version).format_limit_offset(10, 5)
        assert sql == "OFFSET 5 ROWS FETCH NEXT 10 ROWS ONLY"
        assert params == []

    @pytest.mark.parametrize("version", [(11, 0, 0), (13, 0, 0), (15, 0, 0), (16, 0, 0)])
    def test_limit_only_defaults_offset_to_zero(self, version):
        sql, _ = SQLServerDialect(version).format_limit_offset(limit=7)
        assert sql == "OFFSET 0 ROWS FETCH NEXT 7 ROWS ONLY"

    @pytest.mark.parametrize("version", [(11, 0, 0), (13, 0, 0), (15, 0, 0), (16, 0, 0)])
    def test_offset_only_has_no_fetch(self, version):
        sql, _ = SQLServerDialect(version).format_limit_offset(offset=9)
        assert sql == "OFFSET 9 ROWS"
        assert "FETCH" not in sql

    @pytest.mark.parametrize("version", [(11, 0, 0), (13, 0, 0), (15, 0, 0), (16, 0, 0)])
    def test_both_none_renders_nothing(self, version):
        assert SQLServerDialect(version).format_limit_offset() == (None, [])

    def test_pre_2012_raises_with_row_number_suggestion(self):
        with pytest.raises(UnsupportedFeatureError) as exc:
            SQLServerDialect((10, 0, 0)).format_limit_offset(10, 5)
        assert "ROW_NUMBER()" in str(exc.value.suggestion)

    def test_clause_variant_pre_2012_raises(self):
        from rhosocial.activerecord.backend.expression.query_parts import LimitOffsetClause

        d = SQLServerDialect((10, 0, 0))
        clause = LimitOffsetClause(d, limit=10, offset=0)
        with pytest.raises(UnsupportedFeatureError):
            d.format_limit_offset_clause(clause)

    def test_clause_variant_snapshot(self):
        from rhosocial.activerecord.backend.expression.query_parts import LimitOffsetClause

        d = SQLServerDialect((16, 0, 0))
        clause = LimitOffsetClause(d, limit=10, offset=20)
        sql, params = d.format_limit_offset_clause(clause)
        assert sql == "OFFSET 20 ROWS FETCH NEXT 10 ROWS ONLY"
        assert params == ()

    @pytest.mark.parametrize(
        ("version", "expected"),
        [((10, 0, 0), False), ((11, 0, 0), True), ((13, 0, 0), True)],
    )
    def test_supports_offset_fetch_protocol_bit(self, version, expected):
        assert SQLServerDialect(version).supports_offset_fetch() is expected


class TestFunctionCapabilityMatrix:
    """STRING_SPLIT/JSON style capability bits across the version grid."""

    @pytest.mark.parametrize(
        ("function", "expected"),
        [
            # Exact gate per (2012, 2016, 2019):
            ("string_split", (False, True, True)),  # 2016+
            ("string_agg", (False, False, True)),  # 2017+
            ("json_value", (False, True, True)),  # 2016+
            ("json_object", (False, False, False)),  # 2022+ only
            ("approx_count_distinct", (False, False, True)),  # 2019+
            ("iif", (True, True, True)),  # 2012+
        ],
    )
    def test_function_gate_at_2012_2016_2019(self, function, expected):
        results = tuple(
            SQLServerDialect(v)._is_sqlserver_function_supported(function)
            for v in ((11, 0, 0), (13, 0, 0), (15, 0, 0))
        )
        assert results == expected

    @pytest.mark.parametrize(
        ("version", "string_split_ok"),
        [((11, 0, 0), False), ((13, 0, 0), True), ((15, 0, 0), True), ((16, 0, 0), True)],
    )
    def test_string_split_gate_exact(self, version, string_split_ok):
        assert SQLServerDialect(version)._is_sqlserver_function_supported("string_split") is string_split_ok

    @pytest.mark.parametrize(
        ("function", "version", "expected"),
        [
            ("JSON_VALUE", (13, 0, 0), True),
            ("JSON_VALUE", (11, 0, 0), False),
            ("JSON_OBJECT", (13, 0, 0), False),
            ("JSON_OBJECT", (16, 0, 0), True),
            ("JSON_PATH_EXISTS", (15, 0, 0), False),
            ("JSON_PATH_EXISTS", (16, 0, 0), True),
            ("JSON_TABLE", (16, 0, 0), False),  # OPENJSON instead, never supported
        ],
    )
    def test_json_function_gates(self, function, version, expected):
        assert SQLServerDialect(version).supports_json_function(function) is expected

    @pytest.mark.parametrize(
        ("version", "json_bits"),
        [
            ((11, 0, 0), {"supports_json_type": False, "supports_json_table": False}),
            ((13, 0, 0), {"supports_json_type": True, "supports_json_table": True}),
            ((15, 0, 0), {"supports_json_type": True, "supports_json_table": True}),
            ((16, 0, 0), {"supports_json_type": True, "supports_json_table": True}),
        ],
    )
    def test_json_capability_bits_per_version(self, version, json_bits):
        d = SQLServerDialect(version)
        for method, expected in json_bits.items():
            assert getattr(d, method)() is expected


class TestOtherVersionGates:
    @pytest.mark.parametrize(
        ("version", "window_frame"),
        [((10, 0, 0), False), ((11, 0, 0), True), ((16, 0, 0), True)],
    )
    def test_window_frame_clause_2012_gate(self, version, window_frame):
        assert SQLServerDialect(version).supports_window_frame_clause() is window_frame

    @pytest.mark.parametrize(
        ("version", "temporal"),
        [((11, 0, 0), False), ((13, 0, 0), True), ((15, 0, 0), True), ((16, 0, 0), True)],
    )
    def test_temporal_tables_2016_gate(self, version, temporal):
        assert SQLServerDialect(version).supports_temporal_tables() is temporal

    @pytest.mark.parametrize(
        ("version", "readpast"),
        [((13, 0, 0), False), ((15, 0, 0), True), ((16, 0, 0), True)],
    )
    def test_skip_locked_readpast_2019_gate(self, version, readpast):
        d = SQLServerDialect(version)
        assert d.supports_for_update_skip_locked() is readpast
        assert d.supports_readpast() is readpast

    def test_if_exists_rendering_turns_on_in_2016(self):
        from rhosocial.activerecord.backend.expression.statements.ddl_view import DropViewExpression

        pre = DropViewExpression(SQLServerDialect((11, 0, 0)), "v", if_exists=True).to_sql()
        post = DropViewExpression(SQLServerDialect((13, 0, 0)), "v", if_exists=True).to_sql()
        assert pre[0] == "DROP VIEW [v]"
        assert post[0] == "DROP VIEW IF EXISTS [v]"

    @pytest.mark.parametrize(
        ("version", "if_exists_bit"),
        [((11, 0, 0), False), ((13, 0, 0), True), ((15, 0, 0), True), ((16, 0, 0), True)],
    )
    def test_drop_table_if_exists_capability(self, version, if_exists_bit):
        d = SQLServerDialect(version)
        assert d.supports_if_exists_table() is if_exists_bit
        assert d.supports_if_exists_view() is if_exists_bit
        assert d.supports_index_if_exists() is if_exists_bit

    @pytest.mark.parametrize(
        ("version", "sequence"),
        [((10, 0, 0), False), ((11, 0, 0), True), ((16, 0, 0), True)],
    )
    def test_sequence_objects_2012_gate(self, version, sequence):
        assert SQLServerDialect(version).supports_create_sequence() is sequence


class TestRenderingSnapshots:
    def test_temporary_table_gets_hash_prefix(self):
        from rhosocial.activerecord.backend.expression.core import TableExpression
        from rhosocial.activerecord.backend.expression.statements import (
            ColumnDefinition,
            CreateTableExpression,
        )
        from rhosocial.activerecord.backend.expression.types import IntegerType

        d = SQLServerDialect((16, 0, 0))
        expr = CreateTableExpression(
            dialect=d,
            table=TableExpression(d, "stage_users"),
            columns=[ColumnDefinition(name="id", data_type=IntegerType())],
            temporary=True,
        )
        sql, params = expr.to_sql()
        assert sql == "CREATE TABLE [#stage_users] ([id] INT)"
        assert params == ()

    def test_temporary_table_keeps_schema_prefix_order(self):
        from rhosocial.activerecord.backend.expression.core import TableExpression
        from rhosocial.activerecord.backend.expression.statements import (
            ColumnDefinition,
            CreateTableExpression,
        )
        from rhosocial.activerecord.backend.expression.types import IntegerType

        d = SQLServerDialect((16, 0, 0))
        expr = CreateTableExpression(
            dialect=d,
            table=TableExpression(d, "t", "dbo"),
            columns=[ColumnDefinition(name="id", data_type=IntegerType())],
            temporary=True,
        )
        assert expr.to_sql()[0] == "CREATE TABLE [dbo].[#t] ([id] INT)"

    def test_create_table_like_is_unsupported(self):
        from rhosocial.activerecord.backend.expression.core import TableExpression
        from rhosocial.activerecord.backend.expression.statements import (
            ColumnDefinition,
            CreateTableExpression,
        )
        from rhosocial.activerecord.backend.expression.types import IntegerType

        d = SQLServerDialect((16, 0, 0))
        expr = CreateTableExpression(
            dialect=d,
            table=TableExpression(d, "copy"),
            columns=[ColumnDefinition(name="id", data_type=IntegerType())],
        )
        expr.dialect_options["like_table"] = "original"
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_table_hint_single_and_multiple(self):
        d = SQLServerDialect((16, 0, 0))
        assert d.format_table_hint(["NOLOCK"]) == "WITH (NOLOCK)"
        assert d.format_table_hint(["NOLOCK", "READCOMMITTED"]) == "WITH (NOLOCK, READCOMMITTED)"

    def test_locking_hints_gain_readpast_only_on_2019_plus(self):
        base = SQLServerDialect((13, 0, 0)).format_table_hint_locking("UPDLOCK, READPAST")
        newer = SQLServerDialect((15, 0, 0)).format_table_hint_locking("UPDLOCK, READPAST")
        assert base == "WITH (UPDLOCK, ROWLOCK)"  # READPAST silently dropped pre-2019
        assert newer == "WITH (UPDLOCK, ROWLOCK, READPAST)"

    def test_for_update_clause_hint_rendering(self):
        from rhosocial.activerecord.backend.expression.query_parts import ForUpdateClause

        d16 = SQLServerDialect((16, 0, 0))
        sql, params = d16.format_for_update_clause(ForUpdateClause(d16))
        assert (sql, params) == ("WITH (UPDLOCK, ROWLOCK)", ())
        sql, params = d16.format_for_update_clause(ForUpdateClause(d16, skip_locked=True))
        assert sql == "WITH (UPDLOCK, ROWLOCK, READPAST)"

    def test_merge_output_action_snapshot(self):
        from rhosocial.activerecord.backend.expression import Column, QueryExpression, TableExpression
        from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate
        from rhosocial.activerecord.backend.expression.statements import (
            MergeAction,
            MergeActionType,
            MergeExpression,
        )

        d = SQLServerDialect((16, 0, 0))
        merge = MergeExpression(
            dialect=d,
            target=TableExpression(d, "target"),
            source=QueryExpression(
                dialect=d,
                select=[Column(d, "id"), Column(d, "name")],
                from_=TableExpression(d, "source"),
            ),
            on_condition=ComparisonPredicate(
                d, "=", Column(d, "id", "target"), Column(d, "id", "source")
            ),
            when_matched=[
                MergeAction(
                    action_type=MergeActionType.UPDATE,
                    assignments={"name": Column(d, "name", "source")},
                )
            ],
            when_not_matched=[
                MergeAction(action_type=MergeActionType.INSERT, assignments={"id": Column(d, "id", "source")})
            ],
        )
        # MergeExpression carries no dialect_options of its own; the dialect
        # reads them via getattr, so the test injects the mapping directly.
        merge.dialect_options = {"output": ["inserted.id"], "output_action": True, "holdlock": True}
        sql, params = merge.to_sql()
        assert sql.endswith("OUTPUT $action, inserted.id;")
        assert sql.startswith("MERGE INTO [target] WITH (HOLDLOCK)")
        assert params == ()

    def test_merge_without_options_has_no_output(self):
        from rhosocial.activerecord.backend.expression import Column, QueryExpression, TableExpression
        from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate
        from rhosocial.activerecord.backend.expression.statements import (
            MergeAction,
            MergeActionType,
            MergeExpression,
        )

        d = SQLServerDialect((16, 0, 0))
        merge = MergeExpression(
            dialect=d,
            target=TableExpression(d, "t"),
            source=QueryExpression(dialect=d, select=[Column(d, "id")], from_=TableExpression(d, "s")),
            on_condition=ComparisonPredicate(d, "=", Column(d, "id", "t"), Column(d, "id", "s")),
            when_matched=[MergeAction(action_type=MergeActionType.DELETE)],
        )
        sql, _ = merge.to_sql()
        assert sql.startswith("MERGE INTO [t]")
        assert "OUTPUT" not in sql
        assert sql.endswith(";")  # T-SQL requires the trailing semicolon

    def test_explain_statement_variants(self):
        stmt = SimpleNamespace(to_sql=lambda: ("SELECT 1", ()))
        d = SQLServerDialect((16, 0, 0))

        none_opts = d.format_explain_statement(SimpleNamespace(statement=stmt, options=None))[0]
        xml_opts = d.format_explain_statement(
            SimpleNamespace(statement=stmt, options=SimpleNamespace(analyze=False, format=SimpleNamespace(name="XML")))
        )[0]
        analyze_profile = d.format_explain_statement(
            SimpleNamespace(statement=stmt, options=SimpleNamespace(analyze=True, format=None))
        )[0]
        analyze_xml = d.format_explain_statement(
            SimpleNamespace(statement=stmt, options=SimpleNamespace(analyze=True, format=SimpleNamespace(name="XML")))
        )[0]
        assert none_opts == "SET SHOWPLAN_TEXT ON; SELECT 1"
        assert xml_opts == "SET SHOWPLAN_XML ON; SELECT 1"
        assert analyze_profile == "SET STATISTICS PROFILE ON; SELECT 1; SET STATISTICS PROFILE OFF"
        assert analyze_xml == "SET STATISTICS XML ON; SELECT 1; SET STATISTICS XML OFF"

    def test_explain_format_support_matrix(self):
        d = SQLServerDialect((16, 0, 0))
        assert d.supports_explain_format("TEXT") is True
        assert d.supports_explain_format("XML") is True
        assert d.supports_explain_format("JSON") is False

    def test_option_query_hint_clause(self):
        clause = SimpleNamespace(hints=["RECOMPILE", "MAXDOP 4"])
        sql, params = SQLServerDialect((16, 0, 0)).format_query_option_clause(clause)
        assert (sql, params) == ("OPTION (RECOMPILE, MAXDOP 4)", ())

    def test_top_n_clause_variants(self):
        d = SQLServerDialect((16, 0, 0))
        assert d.format_top_n_clause(10) == "TOP 10"
        assert d.format_top_n_clause(5, percentage=True) == "TOP 5 PERCENT"

    def test_lateral_renders_as_apply(self):
        d = SQLServerDialect((16, 0, 0))
        cross = d.format_lateral_expression("SELECT 1", (), "x")
        outer = d.format_lateral_expression("SELECT 1", (), "x", join_type="LEFT")
        assert cross == ("CROSS APPLY (SELECT 1) AS [x]", ())
        assert outer == ("OUTER APPLY (SELECT 1) AS [x]", ())


class TestGroupingAndUpsertBasics:
    def test_grouping_operations_use_tsql_syntax(self):
        d = SQLServerDialect((16, 0, 0))
        assert d.format_grouping_expression("ROLLUP", []) == ("WITH ROLLUP", ())
        assert d.format_grouping_expression("CUBE", []) == ("WITH CUBE", ())
        assert d.format_grouping_expression("GROUPING SETS", []) == ("GROUPING SETS", ())
        with pytest.raises(UnsupportedFeatureError):
            d.format_grouping_expression("PIVOT", [])

    def test_upsert_targets_merge_syntax(self):
        for version in VERSIONS.values():
            d = SQLServerDialect(version)
            assert d.get_upsert_syntax_type() == "MERGE"

    def test_sequence_ddl_snapshots(self):
        from rhosocial.activerecord.backend.expression.statements import (
            CreateSequenceExpression,
            DropSequenceExpression,
        )

        d16 = SQLServerDialect((16, 0, 0))
        create_sql, create_params = CreateSequenceExpression(
            d16, "seq", start=1, increment=2, minvalue=1, maxvalue=100, cycle=False, cache=10
        ).to_sql()
        assert create_sql == (
            "CREATE SEQUENCE [seq] START WITH 1 INCREMENT BY 2 "
            "MINVALUE 1 MAXVALUE 100 NO CYCLE CACHE 10"
        )
        assert create_params == ()
        # IF EXISTS only appears from 2012 onwards.
        assert DropSequenceExpression(SQLServerDialect((10, 0, 0)), "seq", if_exists=True).to_sql()[0] == (
            "DROP SEQUENCE [seq]"
        )
        assert DropSequenceExpression(d16, "seq", if_exists=True).to_sql()[0] == "DROP SEQUENCE IF EXISTS [seq]"
