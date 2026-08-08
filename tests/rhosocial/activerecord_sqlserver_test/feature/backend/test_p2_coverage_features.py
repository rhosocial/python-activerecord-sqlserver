# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_p2_coverage_features.py
"""
SQL Server P2 coverage feature tests.

Pure construction tests (no database required) for the P2 items from the
coverage-gap analysis report:

- In-Memory OLTP (memory-optimized) table options (§3.8)
- Indexed views / FULLTEXT CATALOG DDL (§3.10)
- CREATE / DROP PROCEDURE / FUNCTION / TRIGGER DDL (§3.11)

Version boundaries use the real SQL Server releases: 2005=(9,0,0),
2008=(10,0,0), 2012=(11,0,0), 2014=(12,0,0), 2016=(13,0,0), 2022=(16,0,0).
"""
import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression.fulltext import (
    SQLServerCreateFullTextCatalogExpression,
    SQLServerDropFullTextCatalogExpression,
    SQLServerCreateFullTextIndexExpression,
    SQLServerDropFullTextIndexExpression,
)
from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.routine import (
    SQLServerCreateProcedureExpression,
    SQLServerCreateFunctionExpression,
    SQLServerDropRoutineExpression,
)
from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.trigger import (
    SQLServerCreateTriggerExpression,
    SQLServerDropTriggerExpression,
)
from rhosocial.activerecord.backend.impl.sqlserver.mixins import (
    SQLServerMemoryOptimizedMixin,
    SQLServerRoutineMixin,
    SQLServerTriggerDdlMixin,
)
from rhosocial.activerecord.backend.impl.sqlserver.protocols import (
    SQLServerFullTextSearchSupport,
    SQLServerIndexedViewSupport,
)

SQL_SERVER_2005 = (9, 0, 0)
SQL_SERVER_2008 = (10, 0, 0)
SQL_SERVER_2012 = (11, 0, 0)
SQL_SERVER_2014 = (12, 0, 0)
SQL_SERVER_2016 = (13, 0, 0)
SQL_SERVER_2022 = (16, 0, 0)


def _make_query(d, columns=("id", "name"), from_="users", where=None):
    from rhosocial.activerecord.backend.expression import Column, QueryExpression, TableExpression

    return QueryExpression(
        dialect=d,
        select=[Column(d, col) for col in columns],
        from_=TableExpression(d, from_),
        where=where,
    )


class TestMemoryOptimizedTables:
    """Tests In-Memory OLTP table options and HASH indexes (§3.8)."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def _create_table(self, d, memory_optimized=True, durability="SCHEMA_ONLY",
                      hash_indexes=None):
        from rhosocial.activerecord.backend.expression import CreateTableExpression
        from rhosocial.activerecord.backend.expression.statements import (
            ColumnConstraint,
            ColumnConstraintType,
            ColumnDefinition,
            IndexDefinition,
        )
        from rhosocial.activerecord.backend.expression.types import IntegerType

        col = ColumnDefinition("id", IntegerType())
        col.constraints.append(ColumnConstraint(ColumnConstraintType.PRIMARY_KEY))
        indexes = []
        if hash_indexes:
            for name, (columns, bucket_count) in hash_indexes.items():
                indexes.append(
                    IndexDefinition(
                        name,
                        list(columns),
                        dialect_options={"hash_index": True, "bucket_count": bucket_count},
                    )
                )
        dialect_options = {}
        if memory_optimized:
            dialect_options = {"memory_optimized": True, "durability": durability}
        return CreateTableExpression(
            d, "t", [col], indexes=indexes, dialect_options=dialect_options
        )

    def test_mixin_registered(self, dialect):
        assert isinstance(dialect, SQLServerMemoryOptimizedMixin)

    def test_supports_memory_optimized_tables(self):
        assert SQLServerDialect(SQL_SERVER_2014).supports_memory_optimized_tables() is True
        assert SQLServerDialect(SQL_SERVER_2012).supports_memory_optimized_tables() is False

    def test_format_memory_optimized_option_schema_only(self, dialect):
        assert dialect.format_memory_optimized_option() == (
            "WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_ONLY)"
        )

    def test_format_memory_optimized_option_schema_and_data(self, dialect):
        assert dialect.format_memory_optimized_option("SCHEMA_AND_DATA") == (
            "WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_AND_DATA)"
        )

    def test_format_memory_optimized_option_case_insensitive(self, dialect):
        assert dialect.format_memory_optimized_option("schema_only") == (
            "WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_ONLY)"
        )

    def test_format_memory_optimized_option_invalid_durability(self, dialect):
        with pytest.raises(ValueError):
            dialect.format_memory_optimized_option("DURABLE")

    def test_memory_optimized_option_gate_below_2014(self):
        d = SQLServerDialect(SQL_SERVER_2012)
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            d.format_memory_optimized_option()
        assert exc_info.value.feature_name == "memory-optimized tables"
        assert "2014+" in exc_info.value.suggestion

    def test_hash_index_definition(self, dialect):
        assert dialect.format_hash_index_definition(["id"], 100000) == (
            "NONCLUSTERED HASH ([id]) WITH (BUCKET_COUNT = 100000)"
        )

    def test_hash_index_definition_named(self, dialect):
        assert dialect.format_hash_index_definition(["id"], 100000, name="ix") == (
            "INDEX [ix] NONCLUSTERED HASH ([id]) WITH (BUCKET_COUNT = 100000)"
        )

    def test_hash_index_definition_unique(self, dialect):
        assert dialect.format_hash_index_definition(
            ["id", "name"], 20000, name="ux", unique=True
        ) == (
            "UNIQUE INDEX [ux] NONCLUSTERED HASH ([id], [name]) WITH (BUCKET_COUNT = 20000)"
        )

    def test_hash_index_definition_validation(self, dialect):
        with pytest.raises(ValueError):
            dialect.format_hash_index_definition([], 100000)
        with pytest.raises(ValueError):
            dialect.format_hash_index_definition(["id"], 0)
        with pytest.raises(ValueError):
            dialect.format_hash_index_definition(["id"], None)

    def test_hash_index_gate_below_2014(self):
        d = SQLServerDialect(SQL_SERVER_2012)
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            d.format_hash_index_definition(["id"], 100000)
        assert "NONCLUSTERED HASH index" in exc_info.value.feature_name
        assert "2014+" in exc_info.value.suggestion

    def test_create_table_with_memory_optimized(self, dialect):
        sql, params = self._create_table(dialect).to_sql()
        assert sql == (
            "CREATE TABLE [t] ([id] INT PRIMARY KEY) "
            "WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_ONLY)"
        )
        assert params == ()

    def test_create_table_with_memory_optimized_schema_and_data(self, dialect):
        sql, _ = self._create_table(
            dialect, durability="SCHEMA_AND_DATA"
        ).to_sql()
        assert sql == (
            "CREATE TABLE [t] ([id] INT PRIMARY KEY) "
            "WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_AND_DATA)"
        )

    def test_create_table_with_hash_index(self, dialect):
        sql, params = self._create_table(
            dialect, hash_indexes={"ix": (["id"], 100000)}
        ).to_sql()
        assert sql == (
            "CREATE TABLE [t] ([id] INT PRIMARY KEY, "
            "INDEX [ix] NONCLUSTERED HASH ([id]) WITH (BUCKET_COUNT = 100000)) "
            "WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_ONLY)"
        )
        assert params == ()

    def test_create_table_with_hash_index_missing_bucket_count(self, dialect):
        from rhosocial.activerecord.backend.expression import CreateTableExpression
        from rhosocial.activerecord.backend.expression.statements import (
            ColumnConstraint,
            ColumnConstraintType,
            ColumnDefinition,
            IndexDefinition,
        )
        from rhosocial.activerecord.backend.expression.types import IntegerType

        col = ColumnDefinition("id", IntegerType())
        col.constraints.append(ColumnConstraint(ColumnConstraintType.PRIMARY_KEY))
        ct = CreateTableExpression(
            dialect,
            "t",
            [col],
            indexes=[IndexDefinition("ix", ["id"], dialect_options={"hash_index": True})],
            dialect_options={"memory_optimized": True},
        )
        with pytest.raises(ValueError):
            ct.to_sql()

    def test_create_table_with_memory_optimized_gate_below_2014(self):
        d = SQLServerDialect(SQL_SERVER_2012)
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            self._create_table(d).to_sql()
        assert exc_info.value.feature_name == "memory-optimized tables"
        assert "2014+" in exc_info.value.suggestion

    def test_create_table_with_hash_index_gate_below_2014(self):
        d = SQLServerDialect(SQL_SERVER_2012)
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            self._create_table(d, hash_indexes={"ix": (["id"], 100000)}).to_sql()
        assert "NONCLUSTERED HASH index" in exc_info.value.feature_name

    def test_create_table_without_memory_optimized_unchanged(self, dialect):
        sql, _ = self._create_table(dialect, memory_optimized=False).to_sql()
        assert sql == "CREATE TABLE [t] ([id] INT PRIMARY KEY)"
        assert "MEMORY_OPTIMIZED" not in sql


class TestIndexedView:
    """Tests indexed views (WITH SCHEMABINDING) (§3.10)."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def _view(self, d, view_name="v", columns=("id", "name")):
        from rhosocial.activerecord.backend.expression import CreateViewExpression

        return CreateViewExpression(d, view_name, _make_query(d, columns))

    def test_supports_indexed_view(self):
        assert SQLServerDialect(SQL_SERVER_2005).supports_indexed_view() is True

    def test_protocol_conformance(self, dialect):
        assert isinstance(dialect, SQLServerIndexedViewSupport)

    def test_format_create_indexed_view_statement(self, dialect):
        sql, params = dialect.format_create_indexed_view_statement(self._view(dialect))
        assert sql == (
            "CREATE VIEW [v] WITH SCHEMABINDING AS SELECT [id], [name] FROM [users]"
        )
        assert params == ()

    def test_indexed_view_with_column_aliases(self, dialect):
        view = self._view(dialect, columns=("id",))
        view.column_aliases = ["uid"]
        sql, _ = dialect.format_create_indexed_view_statement(view)
        assert sql == (
            "CREATE VIEW [v] ([uid]) WITH SCHEMABINDING AS SELECT [id] FROM [users]"
        )

    def test_create_view_with_schemabinding_option(self, dialect):
        from rhosocial.activerecord.backend.expression import (
            CreateViewExpression,
            ViewOptions,
        )

        view = CreateViewExpression(
            dialect, "v", _make_query(dialect), options=ViewOptions(schemabinding=True)
        )
        sql, _ = view.to_sql()
        assert sql == "CREATE VIEW [v] WITH SCHEMABINDING AS SELECT [id], [name] FROM [users]"

    def test_create_view_without_schemabinding_unchanged(self, dialect):
        sql, _ = self._view(dialect).to_sql()
        assert sql == "CREATE VIEW [v] AS SELECT [id], [name] FROM [users]"


class TestFullTextCatalogAndIndex:
    """Tests FULLTEXT CATALOG / FULLTEXT INDEX DDL (§3.10)."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_supports_fulltext_catalog(self):
        assert SQLServerDialect(SQL_SERVER_2005).supports_fulltext_catalog() is True

    def test_protocol_conformance(self, dialect):
        assert isinstance(dialect, SQLServerFullTextSearchSupport)

    def test_create_fulltext_catalog(self, dialect):
        sql, params = SQLServerCreateFullTextCatalogExpression(dialect, "ftc").to_sql()
        assert sql == "CREATE FULLTEXT CATALOG [ftc]"
        assert params == ()

    def test_create_fulltext_catalog_as_default(self, dialect):
        expr = SQLServerCreateFullTextCatalogExpression(dialect, "ftc", is_default=True)
        sql, _ = expr.to_sql()
        assert sql == "CREATE FULLTEXT CATALOG [ftc] AS DEFAULT"

    def test_drop_fulltext_catalog(self, dialect):
        sql, params = SQLServerDropFullTextCatalogExpression(dialect, "ftc").to_sql()
        assert sql == "DROP FULLTEXT CATALOG [ftc]"
        assert params == ()

    def test_create_fulltext_index(self, dialect):
        expr = SQLServerCreateFullTextIndexExpression(
            dialect, "t", ["body"], key_index="pk", catalog_name="ftc"
        )
        sql, params = expr.to_sql()
        assert sql == (
            "CREATE FULLTEXT INDEX ON [t] ([body]) KEY INDEX [pk] ON [ftc]"
        )
        assert params == ()

    def test_create_fulltext_index_multiple_columns(self, dialect):
        expr = SQLServerCreateFullTextIndexExpression(
            dialect, "t", ["body", "title"], key_index="pk", catalog_name="ftc"
        )
        sql, _ = expr.to_sql()
        assert sql == (
            "CREATE FULLTEXT INDEX ON [t] ([body], [title]) KEY INDEX [pk] ON [ftc]"
        )

    def test_drop_fulltext_index(self, dialect):
        sql, params = SQLServerDropFullTextIndexExpression(dialect, "t").to_sql()
        assert sql == "DROP FULLTEXT INDEX ON [t]"
        assert params == ()

    def test_fulltext_catalog_gate_below_2005(self):
        d = SQLServerDialect(SQL_SERVER_2005)
        assert d.supports_fulltext_catalog() is True
        assert d.format_create_fulltext_catalog_statement("ftc") == (
            "CREATE FULLTEXT CATALOG [ftc]"
        )

    def test_direct_formatter_default_suffix(self, dialect):
        assert dialect.format_create_fulltext_catalog_statement("ftc", as_default=True) == (
            "CREATE FULLTEXT CATALOG [ftc] AS DEFAULT"
        )

    def test_validation_requires_fields(self, dialect):
        with pytest.raises(ValueError):
            SQLServerCreateFullTextIndexExpression(
                dialect, "", [], key_index="pk", catalog_name="ftc"
            ).validate()
        with pytest.raises(ValueError):
            SQLServerCreateFullTextIndexExpression(
                dialect, "t", [], key_index="pk", catalog_name="ftc"
            ).validate()
        with pytest.raises(ValueError):
            SQLServerDropFullTextIndexExpression(dialect, "").validate()


class TestProcedureFunctionDdl:
    """Tests CREATE / DROP PROCEDURE and FUNCTION (§3.11)."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_mixin_registered(self, dialect):
        assert isinstance(dialect, SQLServerRoutineMixin)

    def test_capabilities(self):
        d = SQLServerDialect(SQL_SERVER_2005)
        assert d.supports_create_procedure() is True
        assert d.supports_create_function() is True
        assert d.supports_drop_procedure() is True
        assert d.supports_drop_function() is True

    def test_create_procedure(self, dialect):
        expr = SQLServerCreateProcedureExpression(
            dialect,
            "p",
            ["@x INT"],
            body="SET NOCOUNT ON; SELECT @x + 1;",
            schema="dbo",
        )
        sql, params = expr.to_sql()
        assert sql == (
            "CREATE PROCEDURE [dbo].[p] @x INT "
            "AS BEGIN SET NOCOUNT ON; SELECT @x + 1; END;"
        )
        assert params == ()

    def test_create_procedure_multiple_params(self, dialect):
        expr = SQLServerCreateProcedureExpression(
            dialect, "p", ["@a INT", "@b VARCHAR(50)"], body="SELECT @a;"
        )
        sql, _ = expr.to_sql()
        assert sql == (
            "CREATE PROCEDURE [p] @a INT, @b VARCHAR(50) AS BEGIN SELECT @a; END;"
        )

    def test_create_procedure_or_alter(self, dialect):
        expr = SQLServerCreateProcedureExpression(
            dialect, "p", ["@x INT"], body="SELECT @x;", or_alter=True
        )
        sql, _ = expr.to_sql()
        assert sql == "CREATE OR ALTER PROCEDURE [p] @x INT AS BEGIN SELECT @x; END;"

    def test_create_procedure_no_params(self, dialect):
        expr = SQLServerCreateProcedureExpression(dialect, "p", body="SELECT 1;")
        sql, _ = expr.to_sql()
        assert sql == "CREATE PROCEDURE [p] AS BEGIN SELECT 1; END;"

    def test_create_function(self, dialect):
        expr = SQLServerCreateFunctionExpression(
            dialect,
            "f",
            ["@x INT"],
            returns="INT",
            body="RETURN @x * 2;",
            schema="dbo",
        )
        sql, params = expr.to_sql()
        assert sql == (
            "CREATE FUNCTION [dbo].[f] (@x INT) RETURNS INT AS BEGIN RETURN @x * 2; END;"
        )
        assert params == ()

    def test_create_function_no_params(self, dialect):
        expr = SQLServerCreateFunctionExpression(
            dialect, "f", returns="INT", body="RETURN 42;"
        )
        sql, _ = expr.to_sql()
        assert sql == "CREATE FUNCTION [f] () RETURNS INT AS BEGIN RETURN 42; END;"

    def test_create_function_dict_params(self, dialect):
        expr = SQLServerCreateFunctionExpression(
            dialect,
            "f",
            [{"name": "@x", "type": "INT"}],
            returns="INT",
            body="RETURN @x;",
        )
        sql, _ = expr.to_sql()
        assert sql == "CREATE FUNCTION [f] (@x INT) RETURNS INT AS BEGIN RETURN @x; END;"

    def test_drop_procedure(self, dialect):
        sql, params = SQLServerDropRoutineExpression(dialect, "p", "PROCEDURE").to_sql()
        assert sql == "DROP PROCEDURE [p]"
        assert params == ()

    def test_drop_function(self, dialect):
        sql, _ = SQLServerDropRoutineExpression(dialect, "f", "FUNCTION").to_sql()
        assert sql == "DROP FUNCTION [f]"

    def test_drop_procedure_schema_qualified(self, dialect):
        expr = SQLServerDropRoutineExpression(dialect, "p", "PROCEDURE", schema="dbo")
        sql, _ = expr.to_sql()
        assert sql == "DROP PROCEDURE [dbo].[p]"

    def test_drop_routine_if_exists_supported_on_2016(self):
        d = SQLServerDialect(SQL_SERVER_2016)
        expr = SQLServerDropRoutineExpression(d, "p", "PROCEDURE", if_exists=True)
        sql, _ = expr.to_sql()
        assert sql == "DROP PROCEDURE IF EXISTS [p]"

    def test_drop_routine_if_exists_omitted_below_2016(self):
        d = SQLServerDialect(SQL_SERVER_2012)
        expr = SQLServerDropRoutineExpression(d, "p", "PROCEDURE", if_exists=True)
        sql, _ = expr.to_sql()
        assert sql == "DROP PROCEDURE [p]"

    def test_validation(self, dialect):
        with pytest.raises(ValueError):
            SQLServerCreateProcedureExpression(dialect, "p", body="").validate()
        with pytest.raises(ValueError):
            SQLServerCreateFunctionExpression(dialect, "f", returns="INT", body="").validate()
        with pytest.raises(ValueError):
            SQLServerCreateFunctionExpression(dialect, "f", body="RETURN 1;").validate()
        with pytest.raises(ValueError):
            SQLServerDropRoutineExpression(dialect, "p", "VIEW").validate()

    def test_version_boundary_all_supported_at_2005(self):
        d = SQLServerDialect(SQL_SERVER_2005)
        proc = SQLServerCreateProcedureExpression(d, "p", ["@x INT"], body="SELECT @x;")
        func = SQLServerCreateFunctionExpression(
            d, "f", ["@x INT"], returns="INT", body="RETURN @x;"
        )
        assert proc.to_sql()[0] == "CREATE PROCEDURE [p] @x INT AS BEGIN SELECT @x; END;"
        assert func.to_sql()[0] == "CREATE FUNCTION [f] (@x INT) RETURNS INT AS BEGIN RETURN @x; END;"


class TestTriggerDdl:
    """Tests CREATE / DROP TRIGGER (§3.11)."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_mixin_registered(self, dialect):
        assert isinstance(dialect, SQLServerTriggerDdlMixin)

    def test_capabilities(self):
        d = SQLServerDialect(SQL_SERVER_2005)
        assert d.supports_trigger() is True
        assert d.supports_create_trigger() is True
        assert d.supports_drop_trigger() is True

    def test_create_trigger_after_insert(self, dialect):
        expr = SQLServerCreateTriggerExpression(
            dialect, "trg", "t", timing="AFTER", events=["INSERT"], body="SELECT 1;"
        )
        sql, params = expr.to_sql()
        assert sql == (
            "CREATE TRIGGER [trg] ON [t] AFTER INSERT AS BEGIN SELECT 1; END;"
        )
        assert params == ()

    def test_create_trigger_instead_of(self, dialect):
        expr = SQLServerCreateTriggerExpression(
            dialect,
            "trg",
            "t",
            timing="INSTEAD OF",
            events=["DELETE"],
            body="RAISERROR('blocked', 16, 1);",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            "CREATE TRIGGER [trg] ON [t] INSTEAD OF DELETE "
            "AS BEGIN RAISERROR('blocked', 16, 1); END;"
        )

    def test_create_trigger_multiple_events(self, dialect):
        expr = SQLServerCreateTriggerExpression(
            dialect,
            "trg",
            "t",
            timing="AFTER",
            events=["INSERT", "UPDATE", "DELETE"],
            body="SELECT 1;",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            "CREATE TRIGGER [trg] ON [t] AFTER INSERT, UPDATE, DELETE AS BEGIN SELECT 1; END;"
        )

    def test_create_trigger_or_alter(self, dialect):
        expr = SQLServerCreateTriggerExpression(
            dialect, "trg", "t", events=["INSERT"], body="SELECT 1;", or_alter=True
        )
        sql, _ = expr.to_sql()
        assert sql == (
            "CREATE OR ALTER TRIGGER [trg] ON [t] AFTER INSERT AS BEGIN SELECT 1; END;"
        )

    def test_drop_trigger(self, dialect):
        sql, params = SQLServerDropTriggerExpression(dialect, "trg").to_sql()
        assert sql == "DROP TRIGGER [trg]"
        assert params == ()

    def test_drop_trigger_if_exists_supported_on_2016(self):
        d = SQLServerDialect(SQL_SERVER_2016)
        expr = SQLServerDropTriggerExpression(d, "trg", if_exists=True)
        sql, _ = expr.to_sql()
        assert sql == "DROP TRIGGER IF EXISTS [trg]"

    def test_drop_trigger_if_exists_omitted_below_2016(self):
        d = SQLServerDialect(SQL_SERVER_2012)
        expr = SQLServerDropTriggerExpression(d, "trg", if_exists=True)
        sql, _ = expr.to_sql()
        assert sql == "DROP TRIGGER [trg]"

    def test_validation(self, dialect):
        with pytest.raises(ValueError):
            SQLServerCreateTriggerExpression(dialect, "trg", "t", events=[], body="SELECT 1;").validate()
        with pytest.raises(ValueError):
            SQLServerCreateTriggerExpression(dialect, "trg", "t", events=["INSERT"], body="").validate()
        with pytest.raises(ValueError):
            SQLServerCreateTriggerExpression(
                dialect, "trg", "t", timing="BEFORE", events=["INSERT"], body="SELECT 1;"
            ).validate()
        with pytest.raises(ValueError):
            SQLServerDropTriggerExpression(dialect, "").validate()

    def test_version_boundary_supported_at_2005(self):
        d = SQLServerDialect(SQL_SERVER_2005)
        expr = SQLServerCreateTriggerExpression(
            d, "trg", "t", events=["INSERT"], body="SELECT 1;"
        )
        assert expr.to_sql()[0] == (
            "CREATE TRIGGER [trg] ON [t] AFTER INSERT AS BEGIN SELECT 1; END;"
        )
