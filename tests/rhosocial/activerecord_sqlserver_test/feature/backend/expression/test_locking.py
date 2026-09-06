# tests/rhosocial/activerecord_sqlserver_test/feature/backend/expression/test_locking.py
"""Offline tests for SQL Server table hint and locking expressions.

These tests exercise the SQLServerTableHint hierarchy and the
SQLServerTableHintClause expression, including hint addition, validation,
and SQL rendering. No live database connection is required.
"""

import pytest

from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression.locking import (
    SQLServerReadPastHint,
    SQLServerTableHint,
    SQLServerTableHintClause,
)


class TestSQLServerTableHint:
    """Test the SQLServerTableHint definition."""

    def test_hint_stores_name(self):
        """Test that the hint name is stored on the instance."""
        hint = SQLServerTableHint("NOLOCK")
        assert hint.name == "NOLOCK", "the hint name must be preserved"

    def test_hint_to_sql_returns_name(self):
        """Test that to_sql returns the raw hint name."""
        hint = SQLServerTableHint("UPDLOCK")
        assert hint.to_sql() == "UPDLOCK", "to_sql must render the hint verbatim"


class TestSQLServerReadPastHint:
    """Test the READPAST hint subclass."""

    def test_read_past_hint_name(self):
        """Test that SQLServerReadPastHint uses the READPAST name."""
        hint = SQLServerReadPastHint()
        assert hint.name == "READPAST", "the READPAST hint name is fixed"

    def test_read_past_hint_is_table_hint(self):
        """Test that SQLServerReadPastHint is a SQLServerTableHint subclass."""
        hint = SQLServerReadPastHint()
        assert isinstance(hint, SQLServerTableHint), (
            "SQLServerReadPastHint must be a SQLServerTableHint"
        )


class TestSQLServerTableHintClause:
    """Test the SQLServerTableHintClause expression."""

    @pytest.fixture
    def dialect(self):
        """Provide a SQL Server dialect instance."""
        return SQLServerDialect(version=(16, 0, 0))

    def test_default_hints_empty(self, dialect):
        """Test that an omitted hints argument defaults to an empty list."""
        clause = SQLServerTableHintClause(dialect=dialect)
        assert clause.hints == [], "the hints list must default to empty"

    def test_to_sql_empty_hints(self, dialect):
        """Test that an empty hint list renders an empty clause."""
        clause = SQLServerTableHintClause(dialect=dialect)
        sql, params = clause.to_sql()
        assert sql == "", "an empty hint list must render an empty clause"
        assert params == (), "an empty hint list must have no params"

    def test_to_sql_single_hint(self, dialect):
        """Test that a single hint renders WITH (hint)."""
        clause = SQLServerTableHintClause(
            dialect=dialect, hints=[SQLServerTableHint("NOLOCK")]
        )
        sql, params = clause.to_sql()
        assert sql == "WITH (NOLOCK)", "a single hint must render as WITH (NOLOCK)"
        assert params == (), "hints must not produce bound parameters"

    def test_to_sql_multiple_hints(self, dialect):
        """Test that multiple hints are comma-separated."""
        clause = SQLServerTableHintClause(
            dialect=dialect,
            hints=[
                SQLServerTableHint("UPDLOCK"),
                SQLServerReadPastHint(),
                SQLServerTableHint("HOLDLOCK"),
            ],
        )
        sql, params = clause.to_sql()
        assert sql == "WITH (UPDLOCK, READPAST, HOLDLOCK)", (
            "multiple hints must be joined with ', '"
        )
        assert params == (), "hints must not produce bound parameters"

    def test_add_hint_returns_self(self, dialect):
        """Test that add_hint returns the clause for chaining."""
        clause = SQLServerTableHintClause(dialect=dialect)
        result = clause.add_hint(SQLServerTableHint("ROWLOCK"))
        assert result is clause, "add_hint must return the same clause instance"
        assert len(clause.hints) == 1, "the hint must have been appended"

    def test_add_hint_appends(self, dialect):
        """Test that add_hint appends a hint to the existing list."""
        clause = SQLServerTableHintClause(
            dialect=dialect, hints=[SQLServerTableHint("NOLOCK")]
        )
        clause.add_hint(SQLServerReadPastHint())
        sql, params = clause.to_sql()
        assert sql == "WITH (NOLOCK, READPAST)", (
            "the added hint must appear after the original hints"
        )

    def test_validate_strict_accepts_hints(self, dialect):
        """Test that strict validation accepts SQLServerTableHint instances."""
        clause = SQLServerTableHintClause(
            dialect=dialect, hints=[SQLServerTableHint("NOLOCK")]
        )
        clause.validate(strict=True)

    def test_validate_strict_rejects_non_hints(self, dialect):
        """Test that strict validation rejects non-hint entries."""
        clause = SQLServerTableHintClause(dialect=dialect, hints=["NOLOCK"])
        with pytest.raises(TypeError) as excinfo:
            clause.validate(strict=True)
        assert "hints must contain SQLServerTableHint" in str(excinfo.value), (
            "the TypeError message must explain the type contract"
        )

    def test_validate_non_strict_ignores_type(self, dialect):
        """Test that non-strict validation skips type checking."""
        clause = SQLServerTableHintClause(dialect=dialect, hints=["NOLOCK"])
        clause.validate(strict=False)