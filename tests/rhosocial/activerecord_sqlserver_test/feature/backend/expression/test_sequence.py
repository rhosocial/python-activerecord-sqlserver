# tests/rhosocial/activerecord_sqlserver_test/feature/backend/expression/test_sequence.py
"""Offline tests for SQL Server NEXT VALUE FOR expressions.

Covers the SQLServerNextValueForExpression validation and SQL rendering
through the dialect's format_next_value_for formatter, including
schema-qualified sequence names and the 2012+ version gate. No database
connection is required.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression.sequence import (
    SQLServerNextValueForExpression,
)


class TestSQLServerNextValueForExpression:
    """Test the NEXT VALUE FOR expression."""

    @pytest.fixture
    def dialect(self):
        """Provide a SQL Server 2016 dialect instance."""
        return SQLServerDialect(version=(13, 0, 0))

    def test_init_stores_sequence_name(self, dialect):
        """Test that the sequence name is stored on the instance."""
        expr = SQLServerNextValueForExpression(
            dialect=dialect, sequence_name="order_seq"
        )
        assert expr.sequence_name == "order_seq", (
            "the sequence name must be preserved"
        )

    def test_to_sql_renders_next_value_for(self, dialect):
        """Test that to_sql renders NEXT VALUE FOR <sequence>."""
        expr = SQLServerNextValueForExpression(
            dialect=dialect, sequence_name="order_seq"
        )
        sql, params = expr.to_sql()
        assert sql == "NEXT VALUE FOR [order_seq]", (
            "the sequence must be rendered as NEXT VALUE FOR"
        )
        assert params == (), "no parameters are expected for NEXT VALUE FOR"

    def test_to_sql_schema_qualified(self, dialect):
        """Test that schema-qualified names quote each part separately."""
        expr = SQLServerNextValueForExpression(
            dialect=dialect, sequence_name="dbo.order_seq"
        )
        sql, params = expr.to_sql()
        assert sql == "NEXT VALUE FOR [dbo].[order_seq]", (
            "schema-qualified names must quote each part"
        )

    def test_validate_strict_accepts_str(self, dialect):
        """Test that strict validation accepts a string sequence name."""
        expr = SQLServerNextValueForExpression(
            dialect=dialect, sequence_name="order_seq"
        )
        expr.validate(strict=True)

    def test_validate_strict_rejects_non_str(self, dialect):
        """Test that strict validation rejects non-string names."""
        expr = SQLServerNextValueForExpression(dialect=dialect, sequence_name=123)
        with pytest.raises(TypeError) as excinfo:
            expr.validate(strict=True)
        assert "sequence_name must be str" in str(excinfo.value), (
            "the TypeError message must explain the type contract"
        )

    def test_validate_non_strict_ignores_type(self, dialect):
        """Test that non-strict validation skips the type check."""
        expr = SQLServerNextValueForExpression(dialect=dialect, sequence_name=123)
        expr.validate(strict=False)

    def test_to_sql_delegates_to_formatter(self, dialect):
        """Test that the expression delegates SQL generation to the dialect."""
        expr = SQLServerNextValueForExpression(
            dialect=dialect, sequence_name="order_seq"
        )
        sql, params = expr.to_sql()
        expected = dialect.format_next_value_for(expr)
        assert sql == expected, "to_sql must delegate to the dialect formatter"


class TestSQLServerSequenceDialect:
    """Test the dialect's NEXT VALUE FOR formatter and sequence support."""

    def test_format_next_value_for_plain_string(self):
        """Test that a plain sequence name string is accepted by the formatter."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        sql = dialect.format_next_value_for("my_seq")
        assert sql == "NEXT VALUE FOR [my_seq]", (
            "a plain string must render as a quoted sequence name"
        )

    def test_format_next_value_for_rejected_before_2012(self):
        """Test that NEXT VALUE FOR raises before SQL Server 2012."""
        dialect = SQLServerDialect(version=(10, 0, 0))
        expr = SQLServerNextValueForExpression(
            dialect=dialect, sequence_name="my_seq"
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_sequence_not_supported_as_data_type(self):
        """Test that sequences cannot be used as column data types."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert dialect.supports_sequence_as_data_type() is False, (
            "SQL Server sequences must not be usable as data types"
        )