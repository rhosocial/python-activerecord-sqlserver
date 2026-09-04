# tests/rhosocial/activerecord_sqlserver_test/feature/backend/dialect/test_dialect_comprehensive.py
"""Comprehensive SQL Server dialect formatting tests."""

import pytest
from rhosocial.activerecord.backend.impl.sqlserver.dialect import (
    SQLServerDialect,
    SQL_SERVER_2012, SQL_SERVER_2016, SQL_SERVER_2019, SQL_SERVER_2022,
)


class TestSQLServerDialectCore:
    """Core dialect behavior tests."""

    @pytest.fixture(params=[
        (16, 0, 0),
        (15, 0, 0),
        (13, 0, 0),
        (11, 0, 0),
    ])
    def dialect(self, request):
        return SQLServerDialect(version=request.param)

    def test_parameter_placeholder(self, dialect):
        assert dialect.get_parameter_placeholder() == "?"

    def test_identifier_quoting(self, dialect):
        assert dialect.format_identifier("table") == "[table]"
        assert dialect.format_identifier("col with spaces") == "[col with spaces]"
        assert dialect.format_identifier("]weird") == "[]]weird]"

    def test_name(self, dialect):
        assert dialect.name == "SQL Server"

    def test_get_server_version(self, dialect):
        assert dialect.get_server_version() == dialect.version


class TestSQLServerDialectPagination:
    """OFFSET FETCH pagination tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_limit_offset_basic(self, dialect):
        from rhosocial.activerecord.backend.expression.query_parts import LimitOffsetClause

        clause = LimitOffsetClause(dialect, limit=10)
        sql, params = dialect.format_limit_offset_clause(clause)
        assert "OFFSET 0 ROWS" in sql
        assert "FETCH NEXT 10 ROWS ONLY" in sql

    def test_limit_offset_with_offset(self, dialect):
        from rhosocial.activerecord.backend.expression.query_parts import LimitOffsetClause

        clause = LimitOffsetClause(dialect, limit=20, offset=10)
        sql, params = dialect.format_limit_offset_clause(clause)
        assert "OFFSET 10 ROWS" in sql
        assert "FETCH NEXT 20 ROWS ONLY" in sql

    def test_limit_offset_no_limit(self, dialect):
        sql, params = dialect.format_limit_offset(limit=None, offset=5)
        assert "OFFSET 5 ROWS" in sql
        assert "FETCH" not in sql

    def test_limit_offset_none(self, dialect):
        sql, params = dialect.format_limit_offset()
        assert sql is None

    def test_old_version_raises(self, dialect):
        old = SQLServerDialect((10, 0, 0))
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
        with pytest.raises(UnsupportedFeatureError):
            old.format_limit_offset(limit=10, offset=0)


class TestSQLServerDialectDML:
    """DML statement formatting tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_insert_with_output(self, dialect):
        from rhosocial.activerecord.backend.expression import (
            InsertExpression, ValuesSource, ReturningClause, Column,
        )
        from rhosocial.activerecord.backend.expression.core import Literal, TableExpression

        insert = InsertExpression(
            dialect=dialect,
            into=TableExpression(dialect, "users"),
            columns=["name"],
            source=ValuesSource(dialect, [[Literal(dialect, "Alice")]]),
            returning=ReturningClause(dialect, [Column(dialect, "id")]),
        )

        sql, params = insert.to_sql()
        assert "INSERT INTO" in sql
        assert "OUTPUT INSERTED.[id]" in sql
        assert "VALUES" in sql

    def test_insert_default_values(self, dialect):
        from rhosocial.activerecord.backend.expression import (
            InsertExpression, DefaultValuesSource,
        )
        from rhosocial.activerecord.backend.expression.core import TableExpression

        insert = InsertExpression(
            dialect=dialect,
            into=TableExpression(dialect, "log"),
            source=DefaultValuesSource(dialect),
        )

        sql, params = insert.to_sql()
        assert "INSERT INTO" in sql
        assert "DEFAULT VALUES" in sql

    def test_update_with_output(self, dialect):
        from rhosocial.activerecord.backend.expression import (
            UpdateExpression, ReturningClause, Column,
        )
        from rhosocial.activerecord.backend.expression.core import Literal, TableExpression

        update = UpdateExpression(
            dialect=dialect,
            table=TableExpression(dialect, "users"),
            assignments={"name": Literal(dialect, "Bob")},
            returning=ReturningClause(dialect, [Column(dialect, "id")]),
        )

        sql, params = update.to_sql()
        assert "UPDATE" in sql
        assert "SET" in sql
        assert "OUTPUT INSERTED.[id]" in sql

    def test_delete_with_output(self, dialect):
        from rhosocial.activerecord.backend.expression import (
            DeleteExpression, ReturningClause, Column, TableExpression,
        )

        delete = DeleteExpression(
            dialect=dialect,
            tables=[TableExpression(dialect, "users")],
            returning=ReturningClause(dialect, [Column(dialect, "id")]),
        )

        sql, params = delete.to_sql()
        assert "DELETE" in sql
        assert "OUTPUT DELETED.[id]" in sql

    def test_insert_top(self, dialect):
        from rhosocial.activerecord.backend.expression import (
            InsertExpression, ValuesSource, Column, TableExpression,
        )
        from rhosocial.activerecord.backend.expression.core import Literal

        insert = InsertExpression(
            dialect=dialect,
            into=TableExpression(dialect, "users"),
            columns=["name"],
            source=ValuesSource(dialect, [
                [Literal(dialect, "A")],
                [Literal(dialect, "B")],
            ]),
        )

        sql, params = insert.to_sql()
        assert "INSERT INTO" in sql
        assert "VALUES" in sql


class TestSQLServerDialectSequence:
    """SEQUENCE DDL tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_create_sequence(self, dialect):
        from rhosocial.activerecord.backend.expression.statements import CreateSequenceExpression

        expr = CreateSequenceExpression(
            dialect=dialect,
            sequence_name="test_seq",
            start=1,
            increment=1,
        )
        sql, params = dialect.format_create_sequence_statement(expr)
        assert "CREATE SEQUENCE [test_seq]" in sql
        assert "START WITH 1" in sql
        assert "INCREMENT BY 1" in sql

    def test_create_sequence_full(self, dialect):
        from rhosocial.activerecord.backend.expression.statements import CreateSequenceExpression

        expr = CreateSequenceExpression(
            dialect=dialect,
            sequence_name="order_seq",
            start=1000,
            increment=10,
            minvalue=1,
            maxvalue=999999,
            cycle=True,
            cache=20,
        )
        sql, params = dialect.format_create_sequence_statement(expr)
        assert "START WITH 1000" in sql
        assert "INCREMENT BY 10" in sql
        assert "MINVALUE 1" in sql
        assert "MAXVALUE 999999" in sql
        assert "CYCLE" in sql
        assert "CACHE 20" in sql

    def test_drop_sequence_if_exists(self, dialect):
        from rhosocial.activerecord.backend.expression.statements import DropSequenceExpression

        expr = DropSequenceExpression(
            dialect=dialect,
            sequence_name="test_seq",
            if_exists=True,
        )
        sql, params = dialect.format_drop_sequence_statement(expr)
        assert "DROP SEQUENCE IF EXISTS [test_seq]" in sql


class TestSQLServerDialectSchema:
    """SCHEMA DDL tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_create_schema(self, dialect):
        from rhosocial.activerecord.backend.expression.statements import CreateSchemaExpression

        expr = CreateSchemaExpression(
            dialect=dialect,
            schema_name="sales",
        )
        sql, params = dialect.format_create_schema_statement(expr)
        assert "CREATE SCHEMA [sales]" in sql

    def test_create_schema_with_authorization(self, dialect):
        from rhosocial.activerecord.backend.expression.statements import CreateSchemaExpression

        expr = CreateSchemaExpression(
            dialect=dialect,
            schema_name="sales",
            authorization="dbo",
        )
        sql, params = dialect.format_create_schema_statement(expr)
        assert "CREATE SCHEMA [sales]" in sql
        assert "AUTHORIZATION [dbo]" in sql

    def test_drop_schema(self, dialect):
        from rhosocial.activerecord.backend.expression.statements import DropSchemaExpression

        expr = DropSchemaExpression(
            dialect=dialect,
            schema_name="sales",
        )
        sql, params = dialect.format_drop_schema_statement(expr)
        assert "DROP SCHEMA [sales]" in sql


class TestSQLServerDialectTruncate:
    """TRUNCATE formatting tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_truncate_table(self, dialect):
        from rhosocial.activerecord.backend.expression.statements import TruncateExpression

        expr = TruncateExpression(
            dialect=dialect,
            table="users",
        )
        sql, params = dialect.format_truncate_statement(expr)
        assert sql == "TRUNCATE TABLE [users]"


class TestSQLServerDialectLateral:
    """LATERAL (CROSS/OUTER APPLY) formatting tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_cross_apply(self, dialect):
        sql, params = dialect.format_lateral_expression(
            "SELECT * FROM [items]", (), "i", "CROSS APPLY"
        )
        assert "CROSS APPLY" in sql
        assert "AS [i]" in sql

    def test_outer_apply(self, dialect):
        sql, params = dialect.format_lateral_expression(
            "SELECT * FROM [items]", (), "i", "LEFT JOIN"
        )
        assert "OUTER APPLY" in sql
        assert "AS [i]" in sql


class TestSQLServerDialectSetOperation:
    """Set operation (UNION/INTERSECT/EXCEPT) formatting tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_union_all(self, dialect):
        from rhosocial.activerecord.backend.expression import QueryExpression, Column, TableExpression

        left = QueryExpression(
            dialect=dialect,
            select=[Column(dialect, "id")],
            from_=TableExpression(dialect, "users"),
        )
        right = QueryExpression(
            dialect=dialect,
            select=[Column(dialect, "id")],
            from_=TableExpression(dialect, "admins"),
        )

        sql, params = dialect.format_set_operation_expression(
            left, right, "UNION", alias=None, all_=True
        )
        assert "UNION ALL" in sql
        assert "[users]" in sql
        assert "[admins]" in sql

    def test_intersect(self, dialect):
        from rhosocial.activerecord.backend.expression import QueryExpression, Column, TableExpression

        left = QueryExpression(
            dialect=dialect,
            select=[Column(dialect, "id")],
            from_=TableExpression(dialect, "orders"),
        )
        right = QueryExpression(
            dialect=dialect,
            select=[Column(dialect, "id")],
            from_=TableExpression(dialect, "shipments"),
        )

        sql, params = dialect.format_set_operation_expression(
            left, right, "INTERSECT", alias=None, all_=False
        )
        assert "INTERSECT" in sql

    def test_except(self, dialect):
        from rhosocial.activerecord.backend.expression import QueryExpression, Column, TableExpression

        left = QueryExpression(
            dialect=dialect,
            select=[Column(dialect, "id")],
            from_=TableExpression(dialect, "employees"),
        )
        right = QueryExpression(
            dialect=dialect,
            select=[Column(dialect, "id")],
            from_=TableExpression(dialect, "managers"),
        )

        sql, params = dialect.format_set_operation_expression(
            left, right, "EXCEPT", alias=None, all_=False
        )
        assert "EXCEPT" in sql


class TestSQLServerDialectForUpdate:
    """FOR UPDATE (table hints) formatting tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_for_update(self, dialect):
        from rhosocial.activerecord.backend.expression.query_parts import ForUpdateClause

        clause = ForUpdateClause(dialect)
        sql, params = dialect.format_for_update_clause(clause)
        assert "WITH (UPDLOCK, ROWLOCK)" in sql

    def test_for_update_skip_locked(self, dialect):
        from rhosocial.activerecord.backend.expression.query_parts import ForUpdateClause

        clause = ForUpdateClause(dialect, skip_locked=True)
        sql, params = dialect.format_for_update_clause(clause)
        assert "READPAST" in sql


class TestSQLServerDialectMerge:
    """MERGE statement formatting tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_merge_basic(self, dialect):
        from rhosocial.activerecord.backend.expression.statements import (
            MergeExpression, MergeActionType, MergeAction,
        )
        from rhosocial.activerecord.backend.expression import (
            QueryExpression, Column, TableExpression,
        )
        from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate
        from rhosocial.activerecord.backend.expression.core import Literal

        merge = MergeExpression(
            dialect=dialect,
            target=TableExpression(dialect, "target"),
            source=QueryExpression(
                dialect=dialect,
                select=[Column(dialect, "id"), Column(dialect, "name")],
                from_=TableExpression(dialect, "source"),
            ),
            on_condition=ComparisonPredicate(
                dialect, "=",
                Column(dialect, "id", "target"),
                Column(dialect, "id", "source"),
            ),
            when_matched=[
                MergeAction(
                    action_type=MergeActionType.UPDATE,
                    assignments={"name": Column(dialect, "name", "source")},
                ),
            ],
            when_not_matched=[
                MergeAction(
                    action_type=MergeActionType.INSERT,
                    assignments={"id": Column(dialect, "id", "source"), "name": Column(dialect, "name", "source")},
                ),
            ],
        )

        sql, params = merge.to_sql()
        assert "MERGE INTO" in sql
        assert "USING" in sql
        assert "ON" in sql
        assert "WHEN MATCHED THEN UPDATE SET" in sql
        assert "WHEN NOT MATCHED BY TARGET THEN INSERT" in sql


class TestSQLServerDialectFullText:
    """Full-text search formatting tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_contains(self, dialect):
        sql, params = dialect.format_fulltext_match(["title", "content"], "database")
        assert "CONTAINS([title], [content]" in sql or "CONTAINS(" in sql
        assert "database" in sql

    def test_contains_with_language(self, dialect):
        sql, params = dialect.format_fulltext_match(["title"], "search term", language="English")
        assert "LANGUAGE" in sql


class TestSQLServerDialectTop:
    """TOP n clause formatting tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_top_n(self, dialect):
        result = dialect.format_top_n_clause(10)
        assert result == "TOP 10"

    def test_top_n_percent(self, dialect):
        result = dialect.format_top_n_clause(50, percentage=True)
        assert result == "TOP 50 PERCENT"


class TestSQLServerDialectCTE:
    """CTE formatting tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_supports_cte(self, dialect):
        assert dialect.supports_basic_cte() is True
        assert dialect.supports_recursive_cte() is True
        assert dialect.supports_materialized_cte() is False


class TestSQLServerDialectWindow:
    """Window function support tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_window_support(self, dialect):
        assert dialect.supports_window_functions() is True

    def test_window_frame_2012(self, dialect):
        d2012 = SQLServerDialect(SQL_SERVER_2012)
        assert d2012.supports_window_frame_clause() is True

    def test_window_frame_2008(self, dialect):
        d2008 = SQLServerDialect((10, 0, 0))
        assert d2008.supports_window_frame_clause() is False


class TestSQLServerDialectJSON:
    """JSON support tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_json_support_2022(self, dialect):
        assert dialect.supports_json_type() is True
        assert dialect.supports_json_table() is True

    def test_json_access_operator(self, dialect):
        assert dialect.get_json_access_operator() is None

    def test_json_support_pre_2016(self, dialect):
        d2012 = SQLServerDialect(SQL_SERVER_2012)
        assert d2012.supports_json_type() is False


class TestSQLServerDialectOutputExpression:
    """SQL Server-specific OUTPUT expression tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_output_inserted(self, dialect):
        from rhosocial.activerecord.backend.impl.sqlserver.expression import (
            SQLServerOutputInsertedExpression,
        )
        expr = SQLServerOutputInsertedExpression(dialect, "id")
        sql, params = expr.to_sql()
        assert sql == "INSERTED.[id]"

    def test_output_deleted(self, dialect):
        from rhosocial.activerecord.backend.impl.sqlserver.expression import (
            SQLServerOutputDeletedExpression,
        )
        expr = SQLServerOutputDeletedExpression(dialect, "old_value")
        sql, params = expr.to_sql()
        assert sql == "DELETED.[old_value]"


class TestSQLServerDialectTableHint:
    """Table hint expression tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_table_hint_basic(self, dialect):
        from rhosocial.activerecord.backend.impl.sqlserver.expression import (
            SQLServerTableHintClause, SQLServerTableHint,
        )
        hint = SQLServerTableHintClause(dialect, [SQLServerTableHint("NOLOCK")])
        sql, params = hint.to_sql()
        assert sql == "WITH (NOLOCK)"

    def test_table_hint_multiple(self, dialect):
        from rhosocial.activerecord.backend.impl.sqlserver.expression import (
            SQLServerTableHintClause, SQLServerTableHint,
        )
        hint = SQLServerTableHintClause(dialect, [
            SQLServerTableHint("NOLOCK"),
            SQLServerTableHint("READPAST"),
        ])
        sql, params = hint.to_sql()
        assert "NOLOCK" in sql
        assert "READPAST" in sql

    def test_readpast_hint(self, dialect):
        from rhosocial.activerecord.backend.impl.sqlserver.expression import (
            SQLServerTableHintClause, SQLServerReadPastHint,
        )
        hint = SQLServerTableHintClause(dialect, [SQLServerReadPastHint()])
        sql, params = hint.to_sql()
        assert "READPAST" in sql


class TestSQLServerDialectOpenJson:
    """OPENJSON expression tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_openjson_basic(self, dialect):
        from rhosocial.activerecord.backend.impl.sqlserver.expression import (
            SQLServerOpenJsonExpression,
        )
        expr = SQLServerOpenJsonExpression(dialect, "@json_var")
        sql, params = expr.to_sql()
        assert "OPENJSON(@json_var)" in sql

    def test_openjson_with_path(self, dialect):
        from rhosocial.activerecord.backend.impl.sqlserver.expression import (
            SQLServerOpenJsonExpression,
        )
        expr = SQLServerOpenJsonExpression(dialect, "@json_var", path="$.orders")
        sql, params = expr.to_sql()
        assert "OPENJSON(@json_var, '$.orders')" in sql

    def test_openjson_with_schema(self, dialect):
        from rhosocial.activerecord.backend.impl.sqlserver.expression import (
            SQLServerOpenJsonExpression, OpenJsonColumn,
        )
        expr = SQLServerOpenJsonExpression(
            dialect, "@json_var", path="$.orders",
            schema=[
                OpenJsonColumn(name="order_id", type="INT", path="$.id"),
                OpenJsonColumn(name="amount", type="DECIMAL(10,2)"),
            ],
            alias="orders",
        )
        sql, params = expr.to_sql()
        assert "OPENJSON(@json_var, '$.orders')" in sql
        assert "WITH" in sql
        assert "[order_id] INT '$.id'" in sql
        assert "[amount] DECIMAL(10,2)" in sql
        assert "AS [orders]" in sql


class TestSQLServerDialectTemporal:
    """Temporal table expression tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_temporal_period(self, dialect):
        from rhosocial.activerecord.backend.impl.sqlserver.expression import (
            SQLServerTemporalPeriodDefinition,
        )
        expr = SQLServerTemporalPeriodDefinition(dialect, "StartTime", "EndTime")
        sql, params = expr.to_sql()
        assert "PERIOD FOR SYSTEM_TIME ([StartTime], [EndTime])" in sql

    def test_system_versioning(self, dialect):
        from rhosocial.activerecord.backend.impl.sqlserver.expression import (
            SQLServerSystemVersioningClause,
        )
        expr = SQLServerSystemVersioningClause(dialect, "TestTableHistory", "dbo")
        sql, params = expr.to_sql()
        assert "SYSTEM_VERSIONING = ON" in sql
        assert "[dbo].[TestTableHistory]" in sql


class TestSQLServerDialectTryCast:
    """TRY_CAST / TRY_CONVERT expression tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_try_cast_expression(self, dialect):
        from rhosocial.activerecord.backend.impl.sqlserver.expression import (
            SQLServerTryCastExpression,
        )
        from rhosocial.activerecord.backend.expression.core import Column

        expr = SQLServerTryCastExpression(dialect, Column(dialect, "value"), "INT")
        sql, params = expr.to_sql()
        assert "TRY_CAST([value] AS INT)" in sql

    def test_try_convert_expression(self, dialect):
        from rhosocial.activerecord.backend.impl.sqlserver.expression import (
            SQLServerTryConvertExpression,
        )
        from rhosocial.activerecord.backend.expression.core import Column

        expr = SQLServerTryConvertExpression(dialect, "NVARCHAR(50)", Column(dialect, "value"))
        sql, params = expr.to_sql()
        assert "TRY_CONVERT(NVARCHAR(50), [value])" in sql

    def test_try_convert_with_style(self, dialect):
        from rhosocial.activerecord.backend.impl.sqlserver.expression import (
            SQLServerTryConvertExpression,
        )
        from rhosocial.activerecord.backend.expression.core import Column

        expr = SQLServerTryConvertExpression(dialect, "DATE", Column(dialect, "date_str"), style=100)
        sql, params = expr.to_sql()
        assert "TRY_CONVERT(DATE, [date_str], 100)" in sql


class TestSQLServerDialectFullTextExpressions:
    """Full-text search expression tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_contains_predicate(self, dialect):
        from rhosocial.activerecord.backend.impl.sqlserver.expression import (
            SQLServerContainsPredicate,
        )
        expr = SQLServerContainsPredicate(dialect, "title", "database")
        sql, params = expr.to_sql()
        assert "CONTAINS([title], 'database')" in sql

    def test_freetext_predicate(self, dialect):
        from rhosocial.activerecord.backend.impl.sqlserver.expression import (
            SQLServerFreetextPredicate,
        )
        expr = SQLServerFreetextPredicate(dialect, "content", "database design")
        sql, params = expr.to_sql()
        assert "FREETEXT([content], 'database design')" in sql


class TestSQLServerDialectVersionSpecific:
    """Version-dependent feature support tests."""

    def test_2012_features(self):
        d = SQLServerDialect(SQL_SERVER_2012)
        assert d.supports_create_sequence() is True
        assert d.supports_json_type() is False
        assert d.supports_temporal_tables() is False
        assert d.supports_for_update_skip_locked() is False

    def test_2016_features(self):
        d = SQLServerDialect(SQL_SERVER_2016)
        assert d.supports_json_type() is True
        assert d.supports_temporal_tables() is True
        assert d.supports_index_if_exists() is True
        assert d.supports_if_exists_view() is True
        assert d.supports_if_exists_table() is True

    def test_2019_features(self):
        d = SQLServerDialect(SQL_SERVER_2019)
        assert d.supports_for_update_skip_locked() is True

    def test_2022_features(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        assert d.supports_json_type() is True
        assert d.supports_temporal_tables() is True
        assert d.supports_for_update_skip_locked() is True


class TestSQLServerDialectDDL:
    """DDL statement formatting tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_create_table_basic(self, dialect):
        from rhosocial.activerecord.backend.expression.statements import (
            CreateTableExpression, ColumnDefinition, ColumnConstraint,
            ColumnConstraintType,
        )
        from rhosocial.activerecord.backend.expression.core import TableExpression
        from rhosocial.activerecord.backend.expression.types import (
            IntegerType, VarCharType,
        )

        expr = CreateTableExpression(
            dialect=dialect,
            table=TableExpression(dialect, "users"),
            columns=[
                ColumnDefinition(
                    name="id",
                    data_type=IntegerType(),
                    constraints=[ColumnConstraint(constraint_type=ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)],
                ),
                ColumnDefinition(
                    name="name",
                    data_type=VarCharType(length=255),
                    constraints=[ColumnConstraint(constraint_type=ColumnConstraintType.NOT_NULL)],
                ),
            ],
        )

        sql, params = dialect.format_create_table_statement(expr)
        assert "CREATE TABLE [users]" in sql
        assert "[id]" in sql
        assert "PRIMARY KEY" in sql
        assert "[name]" in sql
        assert "NOT NULL" in sql

    def test_drop_table_if_exists(self, dialect):
        from rhosocial.activerecord.backend.expression.statements import (
            DropTableExpression,
        )
        from rhosocial.activerecord.backend.expression.core import TableExpression

        expr = DropTableExpression(
            dialect=dialect,
            table=TableExpression(dialect, "users"),
            if_exists=True,
        )
        sql, params = dialect.format_drop_table_statement(expr)
        assert "DROP TABLE IF EXISTS [users]" in sql

    def test_create_index_with_includes(self, dialect):
        from rhosocial.activerecord.backend.expression.statements import CreateIndexExpression

        expr = CreateIndexExpression(
            dialect=dialect,
            index="idx_users_email_include",
            table="users",
            columns=["email"],
            include=["id", "name"],
        )
        sql, params = dialect.format_create_index_statement(expr)
        assert "CREATE INDEX [idx_users_email_include]" in sql
        assert "INCLUDE ([id], [name])" in sql


class TestSQLServerDialectTransaction:
    """Transaction formatting tests."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_begin_transaction(self, dialect):
        from rhosocial.activerecord.backend.expression.transaction import BeginTransactionExpression

        expr = BeginTransactionExpression(dialect)
        sql, params = dialect.format_begin_transaction(expr)
        assert sql == "BEGIN TRANSACTION"

    def test_set_transaction_isolation(self, dialect):
        from rhosocial.activerecord.backend.expression.transaction import SetTransactionExpression
        from rhosocial.activerecord.backend.transaction import IsolationLevel

        expr = SetTransactionExpression(dialect).isolation_level(IsolationLevel.READ_COMMITTED)
        sql, params = dialect.format_set_transaction(expr)
        assert "SET TRANSACTION ISOLATION LEVEL" in sql
        assert "READ COMMITTED" in sql

    def test_supports_savepoint(self, dialect):
        assert dialect.supports_savepoint() is True

    def test_supports_isolation_level_in_begin(self, dialect):
        assert dialect.supports_isolation_level_in_begin() is False