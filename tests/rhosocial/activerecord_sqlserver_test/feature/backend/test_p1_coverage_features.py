# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_p1_coverage_features.py
"""
SQL Server P1 coverage feature tests.

Pure construction tests (no database required) for the P1 items from the
coverage-gap analysis report:

- OPTION query hints (§3.4)
- PIVOT / UNPIVOT (§3.5)
- TABLESAMPLE / SELECT INTO (§3.6)
- Columnstore indexes (§3.7)
- ALTER TABLE ... ALTER COLUMN type / SPARSE / MASKED (§3.9)

Version boundaries use the real SQL Server releases: 2005=(9,0,0),
2008=(10,0,0), 2012=(11,0,0), 2014=(12,0,0), 2016=(13,0,0), 2022=(16,0,0).
"""
import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression.option_hint import (
    SQLServerOptionHintClause,
    recompile_hint,
    maxdop_hint,
    optimize_for_hint,
    hash_join_hint,
    loop_join_hint,
    merge_join_hint,
)
from rhosocial.activerecord.backend.impl.sqlserver.expression.pivot import (
    SQLServerPivotExpression,
    SQLServerUnpivotExpression,
)
from rhosocial.activerecord.backend.impl.sqlserver.expression.columnstore import (
    SQLServerColumnstoreIndexExpression,
)
from rhosocial.activerecord.backend.impl.sqlserver.mixins import (
    SQLServerPivotMixin,
    SQLServerColumnstoreIndexMixin,
)

SQL_SERVER_2005 = (9, 0, 0)
SQL_SERVER_2008 = (10, 0, 0)
SQL_SERVER_2012 = (11, 0, 0)
SQL_SERVER_2014 = (12, 0, 0)
SQL_SERVER_2016 = (13, 0, 0)
SQL_SERVER_2022 = (16, 0, 0)


def _make_query(d, columns=("a", "b"), where=None, **dialect_options):
    from rhosocial.activerecord.backend.expression import Column, QueryExpression, TableExpression

    return QueryExpression(
        dialect=d,
        select=[Column(d, col) for col in columns],
        from_=TableExpression(d, "t"),
        where=where,
        dialect_options=dialect_options,
    )


class TestOptionQueryHints:
    """Tests SQLServerOptionHintClause and the OPTION formatter."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_option_clause_basic(self, dialect):
        clause = SQLServerOptionHintClause(
            dialect, [maxdop_hint(4), recompile_hint()]
        )
        sql, params = clause.to_sql()
        assert sql == "OPTION (MAXDOP 4, RECOMPILE)"
        assert params == ()

    def test_option_clause_full_example(self, dialect):
        clause = SQLServerOptionHintClause(
            dialect,
            [maxdop_hint(4), recompile_hint(), optimize_for_hint([("@p", 10)])],
        )
        sql, _ = clause.to_sql()
        assert sql == "OPTION (MAXDOP 4, RECOMPILE, OPTIMIZE FOR (@p = 10))"

    def test_optimize_for_unknown(self, dialect):
        sql = optimize_for_hint([("@p", 10), ("@q", None)])
        assert sql == "OPTIMIZE FOR (@p = 10, @q = UNKNOWN)"

    def test_hint_factories(self, dialect):
        assert recompile_hint() == "RECOMPILE"
        assert maxdop_hint(8) == "MAXDOP 8"
        assert hash_join_hint() == "HASH JOIN"
        assert loop_join_hint() == "LOOP JOIN"
        assert merge_join_hint() == "MERGE JOIN"

    def test_option_clause_empty_raises(self, dialect):
        clause = SQLServerOptionHintClause(dialect, [])
        with pytest.raises(ValueError):
            clause.validate(strict=True)

    def test_option_clause_no_version_gate(self):
        d = SQLServerDialect(SQL_SERVER_2005)
        clause = SQLServerOptionHintClause(d, [recompile_hint()])
        assert clause.to_sql()[0] == "OPTION (RECOMPILE)"

    def test_appended_to_query_sql(self, dialect):
        clause = SQLServerOptionHintClause(dialect, [recompile_hint()])
        query_sql = _make_query(dialect).to_sql()[0]
        combined = f"{query_sql} {clause.to_sql()[0]}"
        assert combined == "SELECT [a], [b] FROM [t] OPTION (RECOMPILE)"


class TestPivotUnpivot:
    """Tests SQLServerPivotExpression / SQLServerUnpivotExpression."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_supports_pivot(self):
        assert SQLServerDialect(SQL_SERVER_2005).supports_pivot() is True
        assert SQLServerDialect(SQL_SERVER_2005).supports_unpivot() is True

    def test_mixin_registered(self, dialect):
        assert isinstance(dialect, SQLServerPivotMixin)

    def test_pivot_basic(self, dialect):
        expr = SQLServerPivotExpression(
            dialect, "SUM", "sales", "quarter", ["Q1", "Q2", "Q3", "Q4"], alias="p"
        )
        sql, params = expr.to_sql()
        assert sql == (
            "PIVOT (SUM([sales]) FOR [quarter] IN (Q1, Q2, Q3, Q4)) [p]"
        )
        assert params == ()

    def test_pivot_without_alias(self, dialect):
        expr = SQLServerPivotExpression(dialect, "COUNT", "id", "status", ["A", "B"])
        sql, _ = expr.to_sql()
        assert sql == "PIVOT (COUNT([id]) FOR [status] IN (A, B))"

    def test_pivot_string_values_verbatim(self, dialect):
        expr = SQLServerPivotExpression(
            dialect, "SUM", "sales", "month", ["'Jan'", "'Feb'"]
        )
        sql, _ = expr.to_sql()
        assert sql == "PIVOT (SUM([sales]) FOR [month] IN ('Jan', 'Feb'))"

    def test_unpivot_basic(self, dialect):
        expr = SQLServerUnpivotExpression(dialect, "val", "col", ["a", "b"], alias="u")
        sql, params = expr.to_sql()
        assert sql == "UNPIVOT ([val] FOR [col] IN ([a], [b])) [u]"
        assert params == ()

    def test_unpivot_without_alias(self, dialect):
        expr = SQLServerUnpivotExpression(dialect, "amount", "month", ["jan", "feb", "mar"])
        sql, _ = expr.to_sql()
        assert sql == "UNPIVOT ([amount] FOR [month] IN ([jan], [feb], [mar]))"

    def test_pivot_validation(self, dialect):
        with pytest.raises(ValueError):
            SQLServerPivotExpression(dialect, "SUM", "sales", "quarter", []).validate()
        with pytest.raises(ValueError):
            SQLServerUnpivotExpression(dialect, "val", "col", []).validate()

    def test_appended_to_query_sql(self, dialect):
        pivot = SQLServerPivotExpression(
            dialect, "SUM", "sales", "quarter", ["Q1", "Q2"], alias="p"
        )
        query_sql = _make_query(dialect).to_sql()[0]
        combined = f"{query_sql} {pivot.to_sql()[0]}"
        assert combined == (
            "SELECT [a], [b] FROM [t] PIVOT (SUM([sales]) FOR [quarter] IN (Q1, Q2)) [p]"
        )


class TestTablesampleAndSelectInto:
    """Tests TABLESAMPLE clause and SELECT INTO statement formatting."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_supports_tablesample(self):
        assert SQLServerDialect(SQL_SERVER_2005).supports_tablesample() is True
        assert SQLServerDialect(SQL_SERVER_2012).supports_tablesample() is True

    def test_supports_select_into(self, dialect):
        assert dialect.supports_select_into() is True

    def test_tablesample_rows(self, dialect):
        assert dialect.format_tablesample_clause(10) == "TABLESAMPLE (10 ROWS)"

    def test_tablesample_rows_repeatable(self, dialect):
        assert dialect.format_tablesample_clause(10, repeatable=42) == (
            "TABLESAMPLE (10 ROWS) REPEATABLE (42)"
        )

    def test_tablesample_percent(self, dialect):
        assert dialect.format_tablesample_clause(25, percentage=True) == (
            "TABLESAMPLE (25 PERCENT)"
        )

    def test_tablesample_percent_repeatable(self, dialect):
        assert dialect.format_tablesample_clause(25, percentage=True, repeatable=7) == (
            "TABLESAMPLE (25 PERCENT) REPEATABLE (7)"
        )

    def test_tablesample_appended_to_query_sql(self, dialect):
        query_sql = _make_query(dialect).to_sql()[0]
        combined = f"{query_sql} {dialect.format_tablesample_clause(10, repeatable=42)}"
        assert combined == "SELECT [a], [b] FROM [t] TABLESAMPLE (10 ROWS) REPEATABLE (42)"

    def test_select_into_statement(self, dialect):
        query = _make_query(dialect, select_into_table="new_table")
        sql, params = dialect.format_select_into_statement(query)
        assert sql == "SELECT [a], [b] INTO [new_table] FROM [t]"
        assert params == ()

    def test_select_into_with_where(self, dialect):
        from rhosocial.activerecord.backend.expression import Column, Literal
        from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate

        where = ComparisonPredicate(dialect, ">", Column(dialect, "id"), Literal(dialect, 5))
        query = _make_query(dialect, where=where, select_into_table="new_table")
        sql, params = dialect.format_select_into_statement(query)
        assert sql == "SELECT [a], [b] INTO [new_table] FROM [t] WHERE [id] > ?"
        assert params == (5,)

    def test_select_into_requires_target_table(self, dialect):
        query = _make_query(dialect)
        with pytest.raises(ValueError):
            dialect.format_select_into_statement(query)


class TestColumnstoreIndex:
    """Tests SQLServerColumnstoreIndexExpression and version gating."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_mixin_registered(self, dialect):
        assert isinstance(dialect, SQLServerColumnstoreIndexMixin)

    def test_clustered_columnstore(self, dialect):
        expr = SQLServerColumnstoreIndexExpression(dialect, "cci", "t", clustered=True)
        sql, params = expr.to_sql()
        assert sql == "CREATE CLUSTERED COLUMNSTORE INDEX [cci] ON [t]"
        assert params == ()

    def test_default_columnstore_omits_keyword(self, dialect):
        expr = SQLServerColumnstoreIndexExpression(dialect, "cci", "t")
        sql, _ = expr.to_sql()
        assert sql == "CREATE COLUMNSTORE INDEX [cci] ON [t]"

    def test_nonclustered_columnstore(self, dialect):
        expr = SQLServerColumnstoreIndexExpression(
            dialect, "ncci", "t", columns=["c"], clustered=False
        )
        sql, params = expr.to_sql()
        assert sql == "CREATE NONCLUSTERED COLUMNSTORE INDEX [ncci] ON [t] ([c])"
        assert params == ()

    def test_ordered_clustered_columnstore(self, dialect):
        expr = SQLServerColumnstoreIndexExpression(
            dialect, "cci", "t", clustered=True, order_columns=["c1", "c2"]
        )
        sql, _ = expr.to_sql()
        assert sql == (
            "CREATE CLUSTERED COLUMNSTORE INDEX [cci] ON [t] ORDER ([c1], [c2])"
        )

    def test_ncci_validation(self, dialect):
        with pytest.raises(ValueError):
            SQLServerColumnstoreIndexExpression(
                dialect, "ncci", "t", clustered=False
            ).validate()

    def test_cci_forbids_columns(self, dialect):
        with pytest.raises(ValueError):
            SQLServerColumnstoreIndexExpression(
                dialect, "cci", "t", columns=["c"], clustered=True
            ).validate()

    def test_ncci_gate_below_2012(self):
        d = SQLServerDialect(SQL_SERVER_2008)
        expr = SQLServerColumnstoreIndexExpression(d, "ncci", "t", columns=["c"], clustered=False)
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            expr.to_sql()
        assert exc_info.value.feature_name == "NONCLUSTERED COLUMNSTORE INDEX"
        assert "2012+" in exc_info.value.suggestion

    def test_ncci_supported_on_2012(self):
        d = SQLServerDialect(SQL_SERVER_2012)
        expr = SQLServerColumnstoreIndexExpression(d, "ncci", "t", columns=["c"], clustered=False)
        assert expr.to_sql()[0] == (
            "CREATE NONCLUSTERED COLUMNSTORE INDEX [ncci] ON [t] ([c])"
        )

    def test_cci_gate_below_2014(self):
        d = SQLServerDialect(SQL_SERVER_2012)
        expr = SQLServerColumnstoreIndexExpression(d, "cci", "t", clustered=True)
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            expr.to_sql()
        assert exc_info.value.feature_name == "CLUSTERED COLUMNSTORE INDEX"
        assert "2014+" in exc_info.value.suggestion

    def test_cci_supported_on_2014(self):
        d = SQLServerDialect(SQL_SERVER_2014)
        expr = SQLServerColumnstoreIndexExpression(d, "cci", "t", clustered=True)
        assert expr.to_sql()[0] == "CREATE CLUSTERED COLUMNSTORE INDEX [cci] ON [t]"

    def test_order_gate_below_2022(self):
        d = SQLServerDialect(SQL_SERVER_2014)
        expr = SQLServerColumnstoreIndexExpression(
            d, "cci", "t", clustered=True, order_columns=["c1"]
        )
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            expr.to_sql()
        assert exc_info.value.feature_name == "ORDER (...) ordered columnstore index"
        assert "2022+" in exc_info.value.suggestion

    def test_order_supported_on_2022(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        expr = SQLServerColumnstoreIndexExpression(
            d, "cci", "t", clustered=True, order_columns=["c1", "c2"]
        )
        assert expr.to_sql()[0] == (
            "CREATE CLUSTERED COLUMNSTORE INDEX [cci] ON [t] ORDER ([c1], [c2])"
        )


class TestAlterColumn:
    """Tests ALTER TABLE ... ALTER COLUMN type / SPARSE / MASKED."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def _alter(self, d, action):
        from rhosocial.activerecord.backend.expression.statements import AlterTableExpression

        return AlterTableExpression(d, "t", actions=[action]).to_sql()[0]

    def _alter_column(self, d, column_name="c", operation="SET DATA TYPE", new_value=None, **dialect_options):
        from rhosocial.activerecord.backend.expression.statements import AlterColumn

        return AlterColumn(
            d, column_name, operation=operation, new_value=new_value,
            dialect_options=dialect_options,
        )

    def test_alter_column_type(self, dialect):
        action = self._alter_column(dialect, new_value="VARCHAR(100)", not_null=True)
        assert self._alter(dialect, action) == (
            "ALTER TABLE [t] ALTER COLUMN [c] VARCHAR(100) NOT NULL"
        )

    def test_alter_column_type_nullable(self, dialect):
        action = self._alter_column(dialect, new_value="INT", not_null=False)
        assert self._alter(dialect, action) == "ALTER TABLE [t] ALTER COLUMN [c] INT NULL"

    def test_alter_column_type_collate(self, dialect):
        action = self._alter_column(dialect, new_value="VARCHAR(100)", collate="Latin1_General_CS_AS")
        assert self._alter(dialect, action) == (
            "ALTER TABLE [t] ALTER COLUMN [c] VARCHAR(100) COLLATE Latin1_General_CS_AS"
        )

    def test_alter_column_type_sparse(self, dialect):
        action = self._alter_column(dialect, new_value="INT", sparse=True)
        assert self._alter(dialect, action) == "ALTER TABLE [t] ALTER COLUMN [c] INT SPARSE"

    def test_alter_column_type_data_type_option(self, dialect):
        action = self._alter_column(dialect, operation="SET DATA TYPE", data_type="DECIMAL(10, 2)")
        assert self._alter(dialect, action) == (
            "ALTER TABLE [t] ALTER COLUMN [c] DECIMAL(10, 2)"
        )

    def test_alter_column_sparse_gate_below_2008(self):
        d = SQLServerDialect(SQL_SERVER_2005)
        action = self._alter_column(d, new_value="INT", sparse=True)
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            self._alter(d, action)
        assert exc_info.value.feature_name == "SPARSE column"
        assert "2008+" in exc_info.value.suggestion

    def test_alter_column_sparse_supported_on_2008(self):
        d = SQLServerDialect(SQL_SERVER_2008)
        action = self._alter_column(d, new_value="INT", sparse=True)
        assert self._alter(d, action) == "ALTER TABLE [t] ALTER COLUMN [c] INT SPARSE"

    def test_alter_column_add_masked(self, dialect):
        action = self._alter_column(
            dialect, operation="ADD MASKED", masked_function='partial(2,"xxxx",0)'
        )
        assert self._alter(dialect, action) == (
            "ALTER TABLE [t] ALTER COLUMN [c] ADD MASKED "
            "WITH (FUNCTION = 'partial(2,\"xxxx\",0)')"
        )

    def test_alter_column_add_masked_escapes_quotes(self, dialect):
        action = self._alter_column(
            dialect, operation="ADD MASKED", masked_function="default()"
        )
        assert self._alter(dialect, action) == (
            "ALTER TABLE [t] ALTER COLUMN [c] ADD MASKED WITH (FUNCTION = 'default()')"
        )

    def test_alter_column_drop_masked(self, dialect):
        action = self._alter_column(dialect, operation="DROP MASKED")
        assert self._alter(dialect, action) == (
            "ALTER TABLE [t] ALTER COLUMN [c] DROP MASKED"
        )

    def test_alter_column_masked_gate_below_2016(self):
        d = SQLServerDialect(SQL_SERVER_2014)
        action = self._alter_column(d, operation="ADD MASKED", masked_function="default()")
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            self._alter(d, action)
        assert "dynamic data masking" in exc_info.value.feature_name
        assert "2016+" in exc_info.value.suggestion

    def test_alter_column_drop_masked_gate_below_2016(self):
        d = SQLServerDialect(SQL_SERVER_2014)
        action = self._alter_column(d, operation="DROP MASKED")
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            self._alter(d, action)
        assert "2016+" in exc_info.value.suggestion

    def test_alter_column_masked_supported_on_2016(self):
        d = SQLServerDialect(SQL_SERVER_2016)
        action = self._alter_column(d, operation="ADD MASKED", masked_function="default()")
        assert self._alter(d, action) == (
            "ALTER TABLE [t] ALTER COLUMN [c] ADD MASKED WITH (FUNCTION = 'default()')"
        )

    def test_alter_column_unsupported_operation(self, dialect):
        action = self._alter_column(dialect, operation="SET DEFAULT", new_value="0")
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            self._alter(dialect, action)
        assert "SET DEFAULT" in exc_info.value.feature_name
