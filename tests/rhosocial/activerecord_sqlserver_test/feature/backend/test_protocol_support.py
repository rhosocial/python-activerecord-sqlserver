# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_protocol_support.py
"""
SQL Server protocol support tests.

This module verifies that the SQL Server-specific protocol contracts declared
in ``protocols/`` are satisfied by ``SQLServerDialect`` and that their methods
produce valid SQL strings (pure construction, no database required).

Coverage:
- Protocol conformance via isinstance() checks and method presence
- NEXT VALUE FOR expression formatting and version gating
- MERGE with OUTPUT (including $action) and HOLDLOCK
- Delegated formatters: OUTPUT, OFFSET/FETCH, CONTAINS/FREETEXT,
  locking hints, TRY_CAST/TRY_CONVERT, table hints, OPENJSON,
  temporal period, identity insert
"""
import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression.sequence import (
    SQLServerNextValueForExpression,
)
from rhosocial.activerecord.backend.impl.sqlserver.protocols import (
    SQLServerOutputSupport,
    SQLServerPaginationSupport,
    SQLServerFullTextSearchSupport,
    SQLServerLockingSupport,
    SQLServerTryCastSupport,
    SQLServerTableHintSupport,
    SQLServerTableSupport,
    SQLServerJSONSupport,
    SQLServerTemporalTableSupport,
    SQLServerMergeSupport,
    SQLServerSequenceSupport,
    SQLServerIdentitySupport,
    SQLServerIndexedViewSupport,
    SQLServerPartitionSupport,
)

SQL_SERVER_2005 = (9, 0, 0)
SQL_SERVER_2012 = (11, 0, 0)
SQL_SERVER_2014 = (12, 0, 0)
SQL_SERVER_2016 = (13, 0, 0)
SQL_SERVER_2017 = (14, 0, 0)
SQL_SERVER_2019 = (15, 0, 0)
SQL_SERVER_2022 = (16, 0, 0)


def _get_protocol_methods(protocol: type) -> set:
    """Extract public methods declared by a protocol."""
    return {
        name
        for name, value in protocol.__dict__.items()
        if not name.startswith("_") and callable(value)
    }


class TestProtocolConformance:
    """Tests SQLServerDialect satisfies the SQL Server-specific protocols."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_isinstance_output_support(self, dialect):
        assert isinstance(dialect, SQLServerOutputSupport)

    def test_isinstance_pagination_support(self, dialect):
        assert isinstance(dialect, SQLServerPaginationSupport)

    def test_isinstance_fulltext_support(self, dialect):
        assert isinstance(dialect, SQLServerFullTextSearchSupport)

    def test_isinstance_locking_support(self, dialect):
        assert isinstance(dialect, SQLServerLockingSupport)

    def test_isinstance_try_cast_support(self, dialect):
        assert isinstance(dialect, SQLServerTryCastSupport)

    def test_isinstance_table_hint_support(self, dialect):
        assert isinstance(dialect, SQLServerTableHintSupport)

    def test_isinstance_table_support(self, dialect):
        assert isinstance(dialect, SQLServerTableSupport)

    def test_isinstance_json_support(self, dialect):
        assert isinstance(dialect, SQLServerJSONSupport)

    def test_isinstance_temporal_support(self, dialect):
        assert isinstance(dialect, SQLServerTemporalTableSupport)

    def test_isinstance_merge_support(self, dialect):
        assert isinstance(dialect, SQLServerMergeSupport)

    def test_isinstance_sequence_support(self, dialect):
        assert isinstance(dialect, SQLServerSequenceSupport)

    def test_isinstance_identity_support(self, dialect):
        assert isinstance(dialect, SQLServerIdentitySupport)

    def test_isinstance_indexed_view_support(self, dialect):
        assert isinstance(dialect, SQLServerIndexedViewSupport)

    def test_isinstance_partition_support(self, dialect):
        assert isinstance(dialect, SQLServerPartitionSupport)

    def test_protocol_methods_are_implemented(self):
        """Every declared SQL Server protocol method should exist on the dialect."""
        protocols = [
            SQLServerOutputSupport,
            SQLServerPaginationSupport,
            SQLServerFullTextSearchSupport,
            SQLServerLockingSupport,
            SQLServerTryCastSupport,
            SQLServerTableHintSupport,
            SQLServerTableSupport,
            SQLServerJSONSupport,
            SQLServerTemporalTableSupport,
            SQLServerMergeSupport,
            SQLServerSequenceSupport,
            SQLServerIdentitySupport,
            SQLServerIndexedViewSupport,
        ]
        expected = set()
        for protocol in protocols:
            expected |= _get_protocol_methods(protocol)
        dialect_methods = {
            name for name in dir(SQLServerDialect) if not name.startswith("_")
        }
        missing = expected - dialect_methods
        assert missing == set(), f"Missing methods: {missing}"


class TestNextValueFor:
    """Tests SQLServerNextValueForExpression and its version gating."""

    def test_next_value_for_basic(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        expr = SQLServerNextValueForExpression(d, "my_seq")
        sql, params = expr.to_sql()
        assert sql == "NEXT VALUE FOR [my_seq]"
        assert params == ()

    def test_next_value_for_schema_qualified(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        expr = SQLServerNextValueForExpression(d, "dbo.my_seq")
        sql, params = expr.to_sql()
        assert sql == "NEXT VALUE FOR [dbo].[my_seq]"
        assert params == ()

    def test_format_next_value_for_plain_string(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        assert d.format_next_value_for("my_seq") == "NEXT VALUE FOR [my_seq]"

    def test_next_value_for_supported_at_gate(self):
        d = SQLServerDialect(SQL_SERVER_2014)
        sql = d.format_next_value_for("my_seq")
        assert sql == "NEXT VALUE FOR [my_seq]"

    def test_next_value_for_gate_below_2012(self):
        d = SQLServerDialect(SQL_SERVER_2005)
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            d.format_next_value_for("my_seq")
        assert "NEXT VALUE FOR" in str(exc_info.value)
        assert "requires SQL Server 2012+" in str(exc_info.value)

    def test_next_value_for_gate_on_2012(self):
        d = SQLServerDialect(SQL_SERVER_2012)
        assert d.format_next_value_for("my_seq") == "NEXT VALUE FOR [my_seq]"

    def test_next_value_for_in_select(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        expr = SQLServerNextValueForExpression(d, "my_seq")
        from rhosocial.activerecord.backend.expression import QueryExpression

        query = QueryExpression(dialect=d, select=[expr])
        sql, params = query.to_sql()
        assert "SELECT NEXT VALUE FOR [my_seq]" in sql

    def test_next_value_for_in_insert_values(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        from rhosocial.activerecord.backend.expression import InsertExpression, TableExpression
        from rhosocial.activerecord.backend.expression.statements import ValuesSource

        seq = SQLServerNextValueForExpression(d, "my_seq")
        insert = InsertExpression(
            dialect=d,
            into=TableExpression(d, "t"),
            columns=["id"],
            source=ValuesSource(d, [[seq]]),
        )
        sql, params = insert.to_sql()
        assert "VALUES (NEXT VALUE FOR [my_seq])" in sql


class TestMergeOutputAndHoldlock:
    """Tests MERGE statement OUTPUT clause and HOLDLOCK table hint."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def _build_merge(self, d):
        from rhosocial.activerecord.backend.expression import Column, TableExpression
        from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate
        from rhosocial.activerecord.backend.expression.statements import (
            MergeAction,
            MergeActionType,
            MergeExpression,
        )

        return MergeExpression(
            dialect=d,
            target_table="tgt",
            source=TableExpression(d, "src"),
            on_condition=ComparisonPredicate(
                d, "=", Column(d, "id", "tgt"), Column(d, "id", "src")
            ),
            when_matched=[
                MergeAction(
                    MergeActionType.UPDATE, {"name": Column(d, "name", "src")}
                )
            ],
            when_not_matched=[
                MergeAction(
                    MergeActionType.INSERT,
                    {"id": Column(d, "id", "src"), "name": Column(d, "name", "src")},
                )
            ],
        )

    def test_merge_output_clause(self, dialect):
        sql, params = dialect.format_merge_output_clause(
            ["inserted.*", "deleted.*"]
        )
        assert sql == "OUTPUT inserted.*, deleted.*"
        assert params == ()

    def test_merge_output_clause_with_action(self, dialect):
        sql, params = dialect.format_merge_output_clause(
            ["inserted.*", "deleted.*"], action_type="$action"
        )
        assert sql == "OUTPUT $action, inserted.*, deleted.*"
        assert params == ()

    def test_merge_statement_with_output(self, dialect):
        merge = self._build_merge(dialect)
        merge.dialect_options = {
            "output": ["inserted.*", "deleted.*"],
            "output_action": True,
        }
        sql, params = merge.to_sql()
        assert sql.startswith("MERGE INTO [tgt]")
        assert "OUTPUT $action, inserted.*, deleted.*" in sql

    def test_merge_statement_with_holdlock(self, dialect):
        merge = self._build_merge(dialect)
        merge.dialect_options = {"holdlock": True}
        sql, params = merge.to_sql()
        assert sql.startswith("MERGE INTO [tgt] WITH (HOLDLOCK)")
        assert "USING [src]" in sql

    def test_merge_statement_with_output_and_holdlock(self, dialect):
        merge = self._build_merge(dialect)
        merge.dialect_options = {
            "output": ["inserted.*", "deleted.*"],
            "output_action": True,
            "holdlock": True,
        }
        sql, params = merge.to_sql()
        assert sql.startswith("MERGE INTO [tgt] WITH (HOLDLOCK)")
        assert "OUTPUT $action, inserted.*, deleted.*" in sql

    def test_merge_without_options_unchanged(self, dialect):
        merge = self._build_merge(dialect)
        sql, params = merge.to_sql()
        assert sql.startswith("MERGE INTO [tgt]")
        assert "HOLDLOCK" not in sql
        assert "OUTPUT" not in sql

    def test_supports_merge_output(self, dialect):
        assert dialect.supports_merge_output() is True

    def test_supports_merge_holdlock(self, dialect):
        assert dialect.supports_merge_holdlock() is True


class TestDelegatedFormatters:
    """Tests protocol methods that delegate to existing dialect formatters."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_format_output_clause(self, dialect):
        sql, params = dialect.format_output_clause(["id", "name"])
        assert sql == "OUTPUT INSERTED.[id], INSERTED.[name]"
        assert params == ()

    def test_format_output_clause_deleted(self, dialect):
        sql, _ = dialect.format_output_clause(["id"], clause_type="deleted")
        assert sql == "OUTPUT DELETED.[id]"

    def test_supports_output_clause(self, dialect):
        assert dialect.supports_output_clause() is True

    def test_supports_offset_fetch(self, dialect):
        assert dialect.supports_offset_fetch() is True

    def test_supports_offset_fetch_below_2012(self):
        d = SQLServerDialect(SQL_SERVER_2005)
        assert d.supports_offset_fetch() is False

    def test_supports_order_by_in_subquery(self, dialect):
        assert dialect.supports_order_by_in_subquery() is True

    def test_format_contains_predicate(self, dialect):
        sql, params = dialect.format_contains_predicate("title", "database")
        assert sql == "CONTAINS([title], 'database')"
        assert params == ()

    def test_format_contains_predicate_escapes(self, dialect):
        sql, _ = dialect.format_contains_predicate("title", "it's")
        assert sql == "CONTAINS([title], 'it''s')"

    def test_format_freetext_predicate(self, dialect):
        sql, params = dialect.format_freetext_predicate("title", "database design")
        assert sql == "FREETEXT([title], 'database design')"
        assert params == ()

    def test_format_containstable_function(self, dialect):
        sql, params = dialect.format_containstable_function("docs", "body", "term")
        assert sql == "CONTAINSTABLE([docs], [body], 'term')"
        assert params == ()

    def test_format_containstable_function_top_n(self, dialect):
        sql, _ = dialect.format_containstable_function("docs", "body", "term", top_n=10)
        assert sql == "CONTAINSTABLE([docs], [body], 'term', 10)"

    def test_supports_fulltext_catalog(self, dialect):
        assert dialect.supports_fulltext_catalog() is True

    def test_format_create_fulltext_catalog_statement(self, dialect):
        assert dialect.format_create_fulltext_catalog_statement("ftc") == (
            "CREATE FULLTEXT CATALOG [ftc]"
        )

    def test_supports_readpast_on_2019(self):
        assert SQLServerDialect(SQL_SERVER_2019).supports_readpast() is True

    def test_supports_readpast_below_2019(self):
        assert SQLServerDialect(SQL_SERVER_2017).supports_readpast() is False

    def test_format_table_hint_locking(self, dialect):
        assert dialect.format_table_hint_locking("UPDLOCK") == (
            "WITH (UPDLOCK, ROWLOCK)"
        )

    def test_format_table_hint_locking_readpast(self, dialect):
        assert dialect.format_table_hint_locking("READPAST") == (
            "WITH (UPDLOCK, ROWLOCK, READPAST)"
        )

    def test_supports_try_cast(self, dialect):
        assert dialect.supports_try_cast() is True

    def test_supports_try_cast_below_2012(self):
        assert SQLServerDialect(SQL_SERVER_2005).supports_try_cast() is False

    def test_supports_try_convert(self, dialect):
        assert dialect.supports_try_convert() is True

    def test_format_try_cast_expression(self, dialect):
        sql, params = dialect.format_try_cast_expression("value", "INT")
        assert sql == "TRY_CAST(value AS INT)"
        assert params == ()

    def test_format_try_convert_expression(self, dialect):
        sql, params = dialect.format_try_convert_expression("value", "INT", style=100)
        assert sql == "TRY_CONVERT(INT, value, 100)"
        assert params == ()

    def test_supports_table_hints(self, dialect):
        assert dialect.supports_table_hints() is True

    def test_format_table_hint(self, dialect):
        assert dialect.format_table_hint(["NOLOCK", "ROWLOCK"]) == (
            "WITH (NOLOCK, ROWLOCK)"
        )

    def test_supports_select_into(self, dialect):
        assert dialect.supports_select_into() is True

    def test_supports_tablesample(self, dialect):
        assert dialect.supports_tablesample() is True

    def test_format_select_into_not_implemented(self, dialect):
        from rhosocial.activerecord.backend.expression import Column, QueryExpression

        query = QueryExpression(dialect=dialect, select=[Column(dialect, "id")])
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_select_into_statement(query)

    def test_format_openjson_expression(self, dialect):
        sql, params = dialect.format_openjson_expression(
            "@json", path="$.orders", schema={"order_id": "INT"}, alias="o"
        )
        assert sql == "OPENJSON(@json, '$.orders') WITH ([order_id] INT) AS [o]"
        assert params == ()

    def test_supports_system_versioning(self, dialect):
        assert dialect.supports_system_versioning() is True

    def test_supports_system_versioning_below_2016(self):
        assert SQLServerDialect(SQL_SERVER_2014).supports_system_versioning() is False

    def test_format_temporal_period_definition(self, dialect):
        assert dialect.format_temporal_period_definition("SysStart", "SysEnd") == (
            "PERIOD FOR SYSTEM_TIME ([SysStart], [SysEnd])"
        )

    def test_supports_sequence_as_data_type(self, dialect):
        assert dialect.supports_sequence_as_data_type() is False

    def test_supports_identity_insert(self, dialect):
        assert dialect.supports_identity_insert() is True

    def test_format_set_identity_insert_on(self, dialect):
        assert dialect.format_set_identity_insert("orders", True) == (
            "SET IDENTITY_INSERT [orders] ON"
        )

    def test_format_set_identity_insert_off(self, dialect):
        assert dialect.format_set_identity_insert("orders", False) == (
            "SET IDENTITY_INSERT [orders] OFF"
        )

    def test_supports_indexed_view(self, dialect):
        assert dialect.supports_indexed_view() is True

    def test_format_create_indexed_view_not_implemented(self, dialect):
        from rhosocial.activerecord.backend.expression import Column, QueryExpression

        query = QueryExpression(dialect=dialect, select=[Column(dialect, "id")])
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_create_indexed_view_statement(query)

    def test_format_create_temporal_table_not_implemented(self, dialect):
        from rhosocial.activerecord.backend.expression import Column, QueryExpression

        query = QueryExpression(dialect=dialect, select=[Column(dialect, "id")])
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_create_temporal_table_statement(query)
