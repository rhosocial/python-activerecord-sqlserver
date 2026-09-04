# tests/rhosocial/activerecord_sqlserver_test/feature/backend/introspection/test_introspection_sql_builders.py
"""Offline tests for the parameterized SQL builder methods in the introspector.

Covers the SQL injection hardening changes: every ``_build_*_sql`` method
now returns parameterized SQL (``?`` placeholders) with separate params,
instead of string-interpolated values.
"""
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig
from rhosocial.activerecord.backend.impl.sqlserver.introspection import (
    SyncSQLServerIntrospector,
)


def make_introspector() -> SyncSQLServerIntrospector:
    config = SQLServerConnectionConfig(
        host="localhost", port=1433, database="master", username="sa", password="",
    )
    backend = SQLServerBackend(connection_config=config)
    backend._version = (16, 0, 0)
    introspector = SyncSQLServerIntrospector(backend, executor=object())
    return introspector


class TestBuildTableListSql:
    def test_default_schema_parameterized(self):
        introspector = make_introspector()
        sql, params = introspector._build_table_list_sql(None, False)
        assert "TABLE_SCHEMA = ?" in sql
        assert params == ("dbo",)

    def test_with_table_type_parameterized(self):
        introspector = make_introspector()
        sql, params = introspector._build_table_list_sql("sys", False, table_type="BASE TABLE")
        assert "TABLE_TYPE = ?" in sql
        assert params == ("sys", "BASE TABLE")

    def test_without_views_no_table_type(self):
        introspector = make_introspector()
        sql, params = introspector._build_table_list_sql("dbo", False, include_views=False)
        assert "BASE TABLE" in sql
        assert params == ("dbo",)


class TestBuildColumnInfoSql:
    def test_parameterized(self):
        introspector = make_introspector()
        sql, params = introspector._build_column_info_sql("users", "dbo")
        assert "c.TABLE_SCHEMA = ?" in sql
        assert params == ("dbo", "users")


class TestBuildPrimaryKeySql:
    def test_parameterized(self):
        introspector = make_introspector()
        sql, params = introspector._build_primary_key_sql("users", "dbo")
        assert "tc.TABLE_SCHEMA = ?" in sql
        assert params == ("dbo", "users")


class TestBuildIndexInfoSql:
    def test_parameterized(self):
        introspector = make_introspector()
        sql, params = introspector._build_index_info_sql("users", "dbo")
        assert "s.name = ?" in sql
        assert params == ("dbo", "users")


class TestBuildForeignKeySql:
    def test_parameterized(self):
        introspector = make_introspector()
        sql, params = introspector._build_foreign_key_sql("users", "dbo")
        assert "s.name = ?" in sql
        assert params == ("dbo", "users")


class TestBuildViewListSql:
    def test_parameterized(self):
        introspector = make_introspector()
        sql, params = introspector._build_view_list_sql("dbo", False)
        assert "TABLE_SCHEMA = ?" in sql
        assert params == ("dbo",)


class TestBuildViewInfoSql:
    def test_parameterized(self):
        introspector = make_introspector()
        sql, params = introspector._build_view_info_sql("active_users", "dbo")
        assert "TABLE_SCHEMA = ?" in sql
        assert params == ("dbo", "active_users")


class TestBuildTriggerListSql:
    def test_with_table_name_parameterized(self):
        introspector = make_introspector()
        sql, params = introspector._build_trigger_list_sql("orders", "dbo")
        assert "AND t.name = ?" in sql
        assert params == ("dbo", "orders")

    def test_without_table_name(self):
        introspector = make_introspector()
        sql, params = introspector._build_trigger_list_sql(None, "dbo")
        assert "AND t.name = ?" not in sql
        assert params == ("dbo",)


class TestBuildDatabaseInfoSql:
    def test_returns_sql(self):
        introspector = make_introspector()
        sql, params = introspector._build_database_info_sql()
        assert "DB_NAME()" in sql
        assert params == ()