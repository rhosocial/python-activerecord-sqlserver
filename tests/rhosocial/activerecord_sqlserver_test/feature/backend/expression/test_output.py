# tests/rhosocial/activerecord_sqlserver_test/feature/backend/expression/test_output.py
"""Offline tests for SQL Server OUTPUT clause expressions.

The OUTPUT clause returns rows affected by INSERT/UPDATE/DELETE statements
through the ``inserted`` and ``deleted`` pseudo-tables. These tests verify
the SQL rendering and validation of both expression classes without a live
database connection.
"""

import pytest

from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression.output import (
    SQLServerOutputDeletedExpression,
    SQLServerOutputInsertedExpression,
)


class TestSQLServerOutputInsertedExpression:
    """Test the OUTPUT INSERTED expression."""

    @pytest.fixture
    def dialect(self):
        """Provide a SQL Server dialect instance."""
        return SQLServerDialect(version=(16, 0, 0))

    def test_init_stores_column(self, dialect):
        """Test that the column name is stored on the instance."""
        expr = SQLServerOutputInsertedExpression(dialect=dialect, column="id")
        assert expr.column == "id", "the column name must be preserved"

    def test_to_sql_renders_inserted(self, dialect):
        """Test that to_sql renders INSERTED.<column>."""
        expr = SQLServerOutputInsertedExpression(dialect=dialect, column="id")
        sql, params = expr.to_sql()
        assert sql == "INSERTED.[id]", "the column must be INSERTED-qualified"
        assert params == (), "the OUTPUT expression must have no params"

    def test_to_sql_escapes_brackets(self, dialect):
        """Test that internal brackets are escaped by format_identifier."""
        expr = SQLServerOutputInsertedExpression(dialect=dialect, column="a]b")
        sql, params = expr.to_sql()
        assert sql == "INSERTED.[a]]b]", "internal brackets must be doubled"

    def test_validate_strict_accepts_str(self, dialect):
        """Test that strict validation accepts a string column."""
        expr = SQLServerOutputInsertedExpression(dialect=dialect, column="id")
        expr.validate(strict=True)

    def test_validate_strict_rejects_non_str(self, dialect):
        """Test that strict validation rejects non-string columns."""
        expr = SQLServerOutputInsertedExpression(dialect=dialect, column=123)
        with pytest.raises(TypeError) as excinfo:
            expr.validate(strict=True)
        assert "column must be str" in str(excinfo.value), (
            "the TypeError message must explain the type contract"
        )

    def test_validate_non_strict_ignores_type(self, dialect):
        """Test that non-strict validation skips the type check."""
        expr = SQLServerOutputInsertedExpression(dialect=dialect, column=123)
        expr.validate(strict=False)


class TestSQLServerOutputDeletedExpression:
    """Test the OUTPUT DELETED expression."""

    @pytest.fixture
    def dialect(self):
        """Provide a SQL Server dialect instance."""
        return SQLServerDialect(version=(16, 0, 0))

    def test_init_stores_column(self, dialect):
        """Test that the column name is stored on the instance."""
        expr = SQLServerOutputDeletedExpression(dialect=dialect, column="id")
        assert expr.column == "id", "the column name must be preserved"

    def test_to_sql_renders_deleted(self, dialect):
        """Test that to_sql renders DELETED.<column>."""
        expr = SQLServerOutputDeletedExpression(dialect=dialect, column="id")
        sql, params = expr.to_sql()
        assert sql == "DELETED.[id]", "the column must be DELETED-qualified"
        assert params == (), "the OUTPUT expression must have no params"

    def test_to_sql_escapes_brackets(self, dialect):
        """Test that internal brackets are escaped by format_identifier."""
        expr = SQLServerOutputDeletedExpression(dialect=dialect, column="a]b")
        sql, params = expr.to_sql()
        assert sql == "DELETED.[a]]b]", "internal brackets must be doubled"

    def test_validate_strict_accepts_str(self, dialect):
        """Test that strict validation accepts a string column."""
        expr = SQLServerOutputDeletedExpression(dialect=dialect, column="id")
        expr.validate(strict=True)

    def test_validate_strict_rejects_non_str(self, dialect):
        """Test that strict validation rejects non-string columns."""
        expr = SQLServerOutputDeletedExpression(dialect=dialect, column=123)
        with pytest.raises(TypeError) as excinfo:
            expr.validate(strict=True)
        assert "column must be str" in str(excinfo.value), (
            "the TypeError message must explain the type contract"
        )

    def test_validate_non_strict_ignores_type(self, dialect):
        """Test that non-strict validation skips the type check."""
        expr = SQLServerOutputDeletedExpression(dialect=dialect, column=123)
        expr.validate(strict=False)