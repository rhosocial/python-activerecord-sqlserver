# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_sqlserver_ddl_improvements.py
"""Tests for SQL Server DDL improvements: capability gating, UnsupportedFeatureError."""
import pytest
from unittest.mock import patch, PropertyMock

from rhosocial.activerecord.backend.expression import (
    Column,
    TableExpression,
    QueryExpression,
    CreateViewExpression,
    DropViewExpression,
)
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class TestSQLServerViewCapabilityGating:
    """Tests for SQL Server VIEW DDL capability gating."""

    def test_create_or_replace_view_not_supported(self):
        """SQL Server does not support CREATE OR REPLACE VIEW."""
        dialect = SQLServerDialect()
        assert dialect.supports_create_or_replace_view() is False

    def test_drop_view_if_exists_supported(self):
        """SQL Server supports DROP VIEW IF EXISTS."""
        dialect = SQLServerDialect()
        assert dialect.supports_if_exists_view() is True

    def test_materialized_view_not_supported(self):
        """SQL Server does not support materialized views (use indexed views)."""
        dialect = SQLServerDialect()
        assert dialect.supports_materialized_view() is False


class TestSQLServerSchemaCapabilityGating:
    """Tests for SQL Server SCHEMA DDL capability gating."""

    def test_create_schema_supported(self):
        """SQL Server supports CREATE SCHEMA."""
        dialect = SQLServerDialect()
        assert dialect.supports_create_schema() is True

    def test_drop_schema_supported(self):
        """SQL Server supports DROP SCHEMA."""
        dialect = SQLServerDialect()
        assert dialect.supports_drop_schema() is True
