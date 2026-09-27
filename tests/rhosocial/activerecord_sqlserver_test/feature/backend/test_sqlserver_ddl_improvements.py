# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_sqlserver_ddl_improvements.py
"""Tests for SQL Server DDL improvements: capability gating, UnsupportedFeatureError."""
import pytest
from unittest.mock import patch

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import (
    Column,
    CreateTableExpression,
    CreateViewExpression,
    QueryExpression,
    TableExpression,
)
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    ViewCheckOption,
    ViewOptions,
)
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


class TestSQLServerTableCapabilityGating:
    def test_table_declaration_defaults_are_absent(self):
        dialect = SQLServerDialect(version=(16, 0, 0))
        expression = CreateTableExpression(
            dialect,
            "plain_table_defaults",
            [ColumnDefinition(dialect, "id", IntegerType(dialect))],
        )
        sql, params = expression.to_sql()
        assert expression.inherits == []
        assert expression.tablespace is None
        assert "plain_table_defaults" in sql.lower()
        assert "id" in sql.lower()
        assert params == ()

    def test_table_inherits_declaration_is_propagated_and_fails_fast(self):
        dialect = SQLServerDialect(version=(16, 0, 0))
        expression = CreateTableExpression(
            dialect,
            "inheriting_table",
            [ColumnDefinition(dialect, "id", IntegerType(dialect))],
            inherits=["parent_a", "parent_b"],
        )
        assert expression.inherits == ["parent_a", "parent_b"]
        assert dialect.supports_table_inheritance() is False
        with pytest.raises(UnsupportedFeatureError, match="INHERITS"):
            expression.to_sql()

    def test_table_tablespace_declaration_is_propagated_and_fails_fast(self):
        dialect = SQLServerDialect(version=(16, 0, 0))
        expression = CreateTableExpression(
            dialect,
            "tablespaced_table",
            [ColumnDefinition(dialect, "id", IntegerType(dialect))],
            tablespace="ts_data",
        )
        assert expression.tablespace == "ts_data"
        assert dialect.supports_table_tablespace() is False
        with pytest.raises(UnsupportedFeatureError, match="TABLESPACE"):
            expression.to_sql()


class TestSQLServerViewCapabilityGating:
    """Tests for SQL Server VIEW DDL capability gating."""

    def test_create_view_check_option_gated(self):
        """WITH CHECK OPTION must fail fast when the capability is off."""
        dialect = SQLServerDialect()
        query = QueryExpression(
            dialect, select=[Column(dialect, "id")], from_=TableExpression(dialect, "t")
        )
        expr = CreateViewExpression(
            dialect,
            view_name="v",
            query=query,
            options=ViewOptions(check_option=ViewCheckOption.CASCADED),
        )
        with patch.object(type(dialect), "supports_view_check_option", return_value=False):
            with pytest.raises(UnsupportedFeatureError, match="CHECK OPTION"):
                expr.to_sql()

    def test_create_or_replace_view_not_supported(self):
        """SQL Server does not support CREATE OR REPLACE VIEW."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert dialect.supports_create_or_replace_view() is False

    def test_drop_view_if_exists_supported(self):
        """SQL Server supports DROP VIEW IF EXISTS."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert dialect.supports_if_exists_view() is True

    def test_materialized_view_not_supported(self):
        """SQL Server does not support materialized views (use indexed views)."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert dialect.supports_materialized_view() is False


class TestSQLServerSchemaCapabilityGating:
    """Tests for SQL Server SCHEMA DDL capability gating."""

    def test_create_schema_supported(self):
        """SQL Server supports CREATE SCHEMA."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert dialect.supports_create_schema() is True

    def test_drop_schema_supported(self):
        """SQL Server supports DROP SCHEMA."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert dialect.supports_drop_schema() is True
