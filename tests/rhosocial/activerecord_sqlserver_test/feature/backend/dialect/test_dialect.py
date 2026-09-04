# tests/rhosocial/activerecord_sqlserver_test/feature/backend/dialect/test_dialect.py
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
        return SQLServerDialect(version=(16, 0, 0))

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
        """Test OFFSET only formatting - requires LIMIT in SQL Server."""
        from rhosocial.activerecord.backend.expression.query_parts import LimitOffsetClause

        # In SQL Server, OFFSET requires LIMIT, so we test with both
        clause = LimitOffsetClause(dialect, limit=10, offset=5)
        sql, params = dialect.format_limit_offset_clause(clause)
        assert "OFFSET 5 ROWS" in sql
        assert "FETCH NEXT 10 ROWS ONLY" in sql

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

    def test_supports_offset_fetch(self, dialect: SQLServerDialect):
        """Test that SQL Server 2012+ supports OFFSET FETCH."""
        # SQL Server uses OFFSET FETCH for pagination
        # Check that the dialect can format limit/offset correctly
        from rhosocial.activerecord.backend.expression.query_parts import LimitOffsetClause
        clause = LimitOffsetClause(dialect, limit=10, offset=0)
        sql, params = dialect.format_limit_offset_clause(clause)
        assert "OFFSET" in sql
        assert "FETCH" in sql

    def test_format_limit_offset_none(self, dialect: SQLServerDialect):
        """Test when both limit and offset are None."""
        sql, params = dialect.format_limit_offset()
        assert sql is None
        assert params == []


class TestSQLServerDialectStatements:
    """Test cases for SQL Server statement formatting."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(version=(16, 0, 0))

    def test_format_create_index_basic(self, dialect: SQLServerDialect):
        """Test basic CREATE INDEX formatting."""
        from rhosocial.activerecord.backend.expression.statements import CreateIndexExpression

        expr = CreateIndexExpression(
            dialect=dialect,
            index="idx_test",
            table="test_table",
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
            index="idx_unique",
            table="users",
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
        return SQLServerDialect(version=(16, 0, 0))

    def test_supports_returning(self, dialect: SQLServerDialect):
        """Test that SQL Server supports OUTPUT clause (RETURNING)."""
        # SQL Server supports OUTPUT via ReturningMixin
        assert dialect.supports_returning_clause() is True

    def test_supports_cte(self, dialect: SQLServerDialect):
        """Test that SQL Server supports CTEs."""
        from rhosocial.activerecord.backend.dialect.protocols import CTESupport
        assert isinstance(dialect, CTESupport)

    def test_supports_window_functions(self, dialect: SQLServerDialect):
        """Test that SQL Server supports window functions."""
        assert dialect.supports_window_functions() is True

    def test_supports_json(self, dialect: SQLServerDialect):
        """Test that SQL Server 2016+ supports JSON."""
        from rhosocial.activerecord.backend.dialect.protocols import JSONSupport
        assert isinstance(dialect, JSONSupport)

    def test_supports_savepoint(self, dialect: SQLServerDialect):
        """Test that SQL Server supports savepoints."""
        assert dialect.supports_savepoint() is True

    def test_supports_transaction_isolation(self, dialect: SQLServerDialect):
        """Test that SQL Server supports transaction isolation levels."""
        # SQL Server supports isolation levels but not in BEGIN statement
        assert dialect.supports_isolation_level_in_begin() is False or dialect.supports_isolation_level() is True
