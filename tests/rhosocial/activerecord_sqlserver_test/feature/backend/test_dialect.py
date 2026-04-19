# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_dialect.py
"""
SQL Server backend dialect tests.

This module tests SQL Server dialect formatting methods.
"""
import pytest
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


class TestSQLServerDialect:
    """Test cases for SQL Server dialect formatting methods."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect()

    def test_format_identifier(self, dialect: SQLServerDialect):
        """Test identifier formatting with brackets."""
        result = dialect.format_identifier("test_table")
        assert result == "[test_table]"

        result = dialect.format_identifier("user_name")
        assert result == "[user_name]"

        result = dialect.format_identifier("column with spaces")
        assert result == "[column with spaces]"

    def test_format_limit_offset_clause(self, dialect: SQLServerDialect):
        """Test LIMIT/OFFSET formatting as OFFSET FETCH."""
        from rhosocial.activerecord.backend.expression.query_parts import LimitOffsetClause

        clause = LimitOffsetClause(dialect, limit=10, offset=0)
        sql, params = dialect.format_limit_offset_clause(clause)
        assert "OFFSET 0 ROWS" in sql
        assert "FETCH NEXT 10 ROWS ONLY" in sql

    def test_format_limit_offset_clause_offset_only(self, dialect: SQLServerDialect):
        """Test OFFSET only formatting."""
        from rhosocial.activerecord.backend.expression.query_parts import LimitOffsetClause

        clause = LimitOffsetClause(dialect, offset=5)
        sql, params = dialect.format_limit_offset_clause(clause)
        assert "OFFSET 5 ROWS" in sql
        assert "FETCH" not in sql

    def test_format_limit_offset_clause_limit_only(self, dialect: SQLServerDialect):
        """Test LIMIT only formatting (OFFSET defaults to 0)."""
        from rhosocial.activerecord.backend.expression.query_parts import LimitOffsetClause

        clause = LimitOffsetClause(dialect, limit=10)
        sql, params = dialect.format_limit_offset_clause(clause)
        assert "OFFSET 0 ROWS" in sql
        assert "FETCH NEXT 10 ROWS ONLY" in sql

    def test_get_parameter_placeholder(self, dialect: SQLServerDialect):
        """Test parameter placeholder format."""
        assert dialect.get_parameter_placeholder() == "?"

    def test_supports_limit_offset(self, dialect: SQLServerDialect):
        """Test that SQL Server 2012+ supports OFFSET FETCH."""
        assert dialect.supports_limit_offset() is True
        assert dialect.supports_offset_fetch() is True

    def test_format_limit_offset_none(self, dialect: SQLServerDialect):
        """Test when both limit and offset are None."""
        sql, params = dialect.format_limit_offset()
        assert sql is None
        assert params == []


class TestSQLServerDialectStatements:
    """Test cases for SQL Server statement formatting."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect()

    def test_format_create_index_basic(self, dialect: SQLServerDialect):
        """Test basic CREATE INDEX formatting."""
        from rhosocial.activerecord.backend.expression.statements import CreateIndexExpression

        expr = CreateIndexExpression(
            dialect=dialect,
            index_name="idx_test",
            table_name="test_table",
            columns=["id", "name"],
        )
        sql, params = dialect.format_create_index_statement(expr)
        assert "CREATE INDEX [idx_test]" in sql
        assert "ON [test_table]" in sql
        assert "[id]" in sql
        assert "[name]" in sql

    def test_format_create_unique_index(self, dialect: SQLServerDialect):
        """Test CREATE UNIQUE INDEX formatting."""
        from rhosocial.activerecord.backend.expression.statements import CreateIndexExpression

        expr = CreateIndexExpression(
            dialect=dialect,
            index_name="idx_unique",
            table_name="users",
            columns=["email"],
            unique=True,
        )
        sql, params = dialect.format_create_index_statement(expr)
        assert "CREATE UNIQUE INDEX" in sql
        assert "[idx_unique]" in sql
        assert "ON [users]" in sql


class TestSQLServerDialectProtocols:
    """Test cases for SQL Server dialect protocol support."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect()

    def test_supports_returning(self, dialect: SQLServerDialect):
        """Test that SQL Server supports OUTPUT clause (RETURNING)."""
        assert dialect.supports_returning() is True

    def test_supports_cte(self, dialect: SQLServerDialect):
        """Test that SQL Server supports CTEs."""
        assert dialect.supports_cte() is True

    def test_supports_window_functions(self, dialect: SQLServerDialect):
        """Test that SQL Server supports window functions."""
        assert dialect.supports_window_function() is True

    def test_supports_json(self, dialect: SQLServerDialect):
        """Test that SQL Server 2016+ supports JSON."""
        assert dialect.supports_json() is True

    def test_supports_savepoint(self, dialect: SQLServerDialect):
        """Test that SQL Server supports savepoints."""
        assert dialect.supports_savepoint() is True

    def test_supports_transaction_isolation(self, dialect: SQLServerDialect):
        """Test that SQL Server supports transaction isolation levels."""
        assert dialect.supports_isolation_level() is True
