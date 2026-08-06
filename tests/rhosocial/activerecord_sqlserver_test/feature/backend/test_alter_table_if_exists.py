# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_alter_table_if_exists.py
"""Tests for SQL Server ALTER TABLE IF [NOT] EXISTS handling.

SQL Server supports ``DROP COLUMN IF EXISTS`` and ``DROP CONSTRAINT
IF EXISTS`` since 2016 but **not** ``ADD COLUMN IF NOT EXISTS``. The
``ADD`` form omits the ``COLUMN`` literal (SQL Server syntax).
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.statements import ColumnDefinition
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddColumn,
    DropColumn,
    DropTableConstraint,
)
from rhosocial.activerecord.backend.expression.types import TextType
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


@pytest.fixture
def dialect():
    return SQLServerDialect(version=(15, 0, 0))


class TestSQLServerAlterTableModifierCapabilities:
    def test_supports_switches(self, dialect):
        assert dialect.supports_add_column_if_not_exists() is False
        assert dialect.supports_drop_column_if_exists() is True
        assert dialect.supports_drop_constraint_if_exists() is True


class TestSQLServerAddColumn:
    def test_add_column_omits_column_literal(self, dialect):
        action = AddColumn(dialect, ColumnDefinition("content", TextType()))
        sql, params = action.to_sql()
        assert sql.startswith("ADD [content]")
        assert "ADD COLUMN" not in sql
        assert params == ()

    def test_add_column_if_not_exists_raises(self, dialect):
        action = AddColumn(
            dialect,
            ColumnDefinition("content", TextType()),
            if_not_exists=True,
        )
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()


class TestSQLServerDropColumnIfExists:
    def test_if_exists_renders_qualifier(self, dialect):
        action = DropColumn(dialect, column_name="x", if_exists=True)
        sql, params = action.to_sql()
        assert "DROP COLUMN IF EXISTS [x]" == sql
        assert params == ()

    def test_none_renders_plain_form(self, dialect):
        action = DropColumn(dialect, column_name="x")
        sql, params = action.to_sql()
        assert "DROP COLUMN [x]" == sql
        assert "IF EXISTS" not in sql
        assert params == ()


class TestSQLServerDropConstraintIfExists:
    def test_if_exists_renders_qualifier(self, dialect):
        action = DropTableConstraint(
            dialect, constraint_name="fk", if_exists=True
        )
        sql, params = action.to_sql()
        assert "DROP CONSTRAINT IF EXISTS [fk]" == sql
        assert params == ()

    def test_none_renders_plain_form(self, dialect):
        action = DropTableConstraint(dialect, constraint_name="fk")
        sql, params = action.to_sql()
        assert "DROP CONSTRAINT [fk]" == sql
        assert "IF EXISTS" not in sql
        assert params == ()