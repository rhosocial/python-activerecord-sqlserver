# tests/rhosocial/activerecord_sqlserver_test/feature/backend/schema/test_schema_support.py
"""Tests for the SchemaSupport capability declared on the SQL Server dialect.

SQL Server models named schema namespaces natively (e.g. dbo), so the dialect
must report ``supports_schema()`` as True. IF NOT EXISTS / IF EXISTS variants
are not supported by the server and must stay False.
"""
from rhosocial.activerecord.backend.dialect.protocols import SchemaSupport
from rhosocial.activerecord.backend.expression.statements.ddl_schema import (
    CreateSchemaExpression,
    DropSchemaExpression,
)
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


class TestSchemaCapability:
    """Umbrella flag and granular schema DDL capability bits."""

    def _dialect(self) -> SQLServerDialect:
        # Pin the version so the constructor never probes a live server.
        return SQLServerDialect((16, 0, 0))

    def test_supports_schema_is_true(self):
        assert self._dialect().supports_schema() is True

    def test_implements_schema_support_protocol(self):
        assert isinstance(self._dialect(), SchemaSupport)

    def test_granular_schema_ddl_capabilities(self):
        d = self._dialect()
        assert d.supports_create_schema() is True
        assert d.supports_drop_schema() is True
        assert d.supports_schema_if_not_exists() is False
        assert d.supports_schema_if_exists() is False
        assert d.supports_schema_cascade() is False

    def test_schema_authorization_capability(self):
        assert self._dialect().supports_schema_authorization() is True


class TestSchemaDDLFormatting:
    """CREATE/DROP SCHEMA rendering through the standard core formatters."""

    def _dialect(self) -> SQLServerDialect:
        # Pin the version so the constructor never probes a live server.
        return SQLServerDialect((16, 0, 0))

    def test_create_schema(self):
        sql, params = CreateSchemaExpression(self._dialect(), "app").to_sql()
        assert sql == "[app]" or sql == "CREATE SCHEMA [app]"
        assert "IF NOT EXISTS" not in sql
        assert params == ()

    def test_drop_schema(self):
        sql, _ = DropSchemaExpression(self._dialect(), "app").to_sql()
        assert sql == "DROP SCHEMA [app]" or sql == "DROP SCHEMA app"
        assert "IF EXISTS" not in sql

    def test_drop_schema_rejects_unsupported_if_exists(self):
        """The formatter must never emit IF EXISTS even if requested."""
        sql, _ = DropSchemaExpression(self._dialect(), "app", if_exists=True).to_sql()
        assert "IF EXISTS" not in sql
