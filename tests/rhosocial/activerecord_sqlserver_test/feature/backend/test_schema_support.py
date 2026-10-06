# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_schema_support.py
"""Tests for the SQL Server schema and namespace capabilities.

SQL Server models named schema namespaces natively (e.g. dbo), so the dialect
must report ``supports_schema()`` as True, and it renders every namespace level
a name can carry -- catalog, schema and name. IF NOT EXISTS / IF EXISTS variants
are not supported by the server and must stay False.
"""
from rhosocial.activerecord.backend.dialect.protocols import NamespaceSupport
from rhosocial.activerecord.backend.expression.objects import Schema, Table
from rhosocial.activerecord.backend.expression.statements.ddl_schema import (
    CreateSchemaExpression,
    DropSchemaExpression,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnDefinition,
    CreateTableExpression,
)
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


class TestSchemaCapability:
    """Umbrella flag and granular schema DDL capability bits."""

    def _dialect(self) -> SQLServerDialect:
        # Pin the version so the constructor never probes a live server.
        return SQLServerDialect((16, 0, 0))

    def test_supports_schema_is_true(self):
        assert self._dialect().supports_schema() is True

    def test_implements_namespace_support_protocol(self):
        assert isinstance(self._dialect(), NamespaceSupport)

    def test_renders_every_namespace_level(self):
        """SQL Server qualifies a name with both its catalog and its schema."""
        d = self._dialect()
        assert d.supports_catalog() is True
        assert d.supports_catalog_qualification() is True
        assert d.supports_schema_qualification() is True
        assert Table(d, "t", catalog_name="app", schema_name="dbo").to_sql() == (
            "[app].[dbo].[t]",
            (),
        )

    def test_identifier_cap_is_enforced(self):
        """A namespace part longer than 128 characters is rejected."""
        d = self._dialect()
        try:
            Table(d, "t", schema_name="s" * 129).to_sql()
        except ValueError as error:
            assert "128 characters" in str(error)
        else:
            raise AssertionError("a 129-character schema name was rendered")

    def test_object_id_name_is_the_bare_name_not_the_bracketed_one(self):
        """``OBJECT_ID`` takes bare text, and the bracketed form breaks it.

        This is the failure mode the whole ``OBJECT_ID`` shape exists to prevent.
        Every other name SQL Server renders is bracketed, because ``format_identifier``
        brackets it. ``OBJECT_ID`` is handed a *string literal* instead, and SQL
        Server parses that literal's text into namespace parts -- brackets included.
        So ``OBJECT_ID(N'[app].[dbo].[users]')`` resolves to nothing and returns
        NULL for a table that plainly exists, and the ``CREATE TABLE IF NOT EXISTS``
        guard built on it runs the CREATE anyway.

        The two spellings are asserted side by side, so a change that routed the
        ``OBJECT_ID`` name through ``format_qualified_name`` fails here even though
        both methods would still render without error.
        """
        d = self._dialect()
        table = Table(d, "users", catalog_name="app", schema_name="dbo")

        bracketed = d.format_qualified_name(table)[0]
        bare = d.format_object_id_name(table)

        assert bracketed == "[app].[dbo].[users]"
        assert bare == "app.dbo.users"
        assert "[" not in bare and "]" not in bare, (
            f"the OBJECT_ID name carries brackets: {bare!r}. SQL Server parses the "
            f"string literal's text, so brackets make it resolve to nothing."
        )

    def test_object_id_guard_in_create_table_is_unbracketed(self):
        """The one call site: the ``IF NOT EXISTS`` guard on CREATE TABLE.

        Asserted on the rendered statement rather than on the formatter, because the
        call site is where a future change would reintroduce the brackets -- the
        formatter would still be correct on its own.
        """
        d = self._dialect()
        table = Table(d, "users", catalog_name="app", schema_name="dbo")
        column = ColumnDefinition(d, "id", IntegerType(d))
        expr = CreateTableExpression(d, table, [column], if_not_exists=True)

        sql, _ = expr.to_sql()
        guard = sql.splitlines()[0]

        assert guard == "IF OBJECT_ID(N'app.dbo.users', N'U') IS NULL"
        assert "[" not in guard, (
            f"the OBJECT_ID guard carries brackets: {guard!r}; it would resolve to "
            f"NULL and the CREATE would run unconditionally."
        )
        # The CREATE itself is still bracketed: only the OBJECT_ID argument is not.
        assert "CREATE TABLE [app].[dbo].[users]" in sql

    def test_object_id_name_still_validates_the_namespace(self):
        """The bare spelling must not bypass the namespace checks.

        ``format_object_id_name`` used to join the object's slots itself, which meant
        it skipped ``validate_namespace`` entirely: a name SQL Server could not store
        produced a bare string instead of an error. The check now runs first, so the
        third operation is a different spelling of the same name rather than a
        different policy.
        """
        d = self._dialect()
        over_long = Table(d, "users", schema_name="s" * 129)
        try:
            d.format_object_id_name(over_long)
        except ValueError as error:
            assert "128 characters" in str(error)
        else:
            raise AssertionError(
                "a 129-character schema name reached OBJECT_ID unchecked"
            )

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
        d = self._dialect()
        sql, params = CreateSchemaExpression(d, Schema(d, "app")).to_sql()
        assert sql == "CREATE SCHEMA [app]"
        assert "IF NOT EXISTS" not in sql
        assert params == ()

    def test_drop_schema(self):
        d = self._dialect()
        sql, _ = DropSchemaExpression(d, Schema(d, "app")).to_sql()
        assert sql == "DROP SCHEMA [app]"

    def test_drop_schema_rejects_unsupported_if_exists(self):
        """The formatter must never emit IF EXISTS even if requested."""
        d = self._dialect()
        sql, _ = DropSchemaExpression(d, Schema(d, "app"), if_exists=True).to_sql()
        assert "IF EXISTS" not in sql