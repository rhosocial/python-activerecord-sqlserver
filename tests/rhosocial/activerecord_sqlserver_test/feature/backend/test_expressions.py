# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_expressions.py
"""
Tests for SQL Server expression formatting.

This module tests SQL Server-specific expression formatting including
OFFSET FETCH, OUTPUT clause, and other SQL Server features.
"""
import pytest
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


class TestOffsetFetchExpression:
    """Test cases for OFFSET FETCH expression formatting."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect()

    def test_offset_fetch_basic(self, dialect):
        """Test basic OFFSET FETCH formatting."""
        from rhosocial.activerecord.backend.expression import QueryExpression, Column, TableExpression
        from rhosocial.activerecord.backend.expression.query_parts import LimitOffsetClause

        query = QueryExpression(
            dialect=dialect,
            select=[Column(dialect, "id"), Column(dialect, "name")],
            from_=TableExpression(dialect, "users"),
            limit_offset=LimitOffsetClause(dialect, limit=10, offset=0),
        )

        sql, params = query.to_sql()
        assert "OFFSET 0 ROWS" in sql
        assert "FETCH NEXT 10 ROWS ONLY" in sql

    def test_offset_fetch_with_offset(self, dialect):
        """Test OFFSET FETCH with non-zero offset."""
        from rhosocial.activerecord.backend.expression import QueryExpression, Column, TableExpression
        from rhosocial.activerecord.backend.expression.query_parts import LimitOffsetClause

        query = QueryExpression(
            dialect=dialect,
            select=[Column(dialect, "id")],
            from_=TableExpression(dialect, "products"),
            limit_offset=LimitOffsetClause(dialect, limit=20, offset=10),
        )

        sql, params = query.to_sql()
        assert "OFFSET 10 ROWS" in sql
        assert "FETCH NEXT 20 ROWS ONLY" in sql

    def test_offset_only_no_fetch(self, dialect):
        """Test OFFSET without FETCH (no limit)."""
        from rhosocial.activerecord.backend.expression.query_parts import LimitOffsetClause

        clause = LimitOffsetClause(dialect, offset=5)
        sql, params = dialect.format_limit_offset_clause(clause)
        assert "OFFSET 5 ROWS" in sql
        assert "FETCH" not in sql


class TestOutputClauseExpression:
    """Test cases for OUTPUT clause expression formatting."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect()

    def test_output_clause_insert(self, dialect):
        """Test OUTPUT clause in INSERT statement."""
        from rhosocial.activerecord.backend.expression import (
            InsertExpression,
            ValuesSource,
            ReturningClause,
            Column,
            TableExpression,
        )
        from rhosocial.activerecord.backend.expression.core import Literal

        insert = InsertExpression(
            dialect=dialect,
            into=TableExpression(dialect, "users"),
            columns=["name"],
            source=ValuesSource(dialect, [[Literal(dialect, "Alice")]]),
            returning=ReturningClause(dialect, [Column(dialect, "id")]),
        )

        sql, params = insert.to_sql()
        assert "INSERT INTO" in sql
        assert "OUTPUT INSERTED.[id]" in sql
        assert "VALUES" in sql

    def test_output_clause_multiple_columns(self, dialect):
        """Test OUTPUT clause with multiple columns."""
        from rhosocial.activerecord.backend.expression import (
            InsertExpression,
            ValuesSource,
            ReturningClause,
            Column,
            TableExpression,
        )
        from rhosocial.activerecord.backend.expression.core import Literal

        insert = InsertExpression(
            dialect=dialect,
            into=TableExpression(dialect, "products"),
            columns=["name", "price"],
            source=ValuesSource(dialect, [[Literal(dialect, "Widget"), Literal(dialect, 9.99)]]),
            returning=ReturningClause(dialect, [Column(dialect, "id"), Column(dialect, "created_at")]),
        )

        sql, params = insert.to_sql()
        assert "INSERTED.[id]" in sql
        assert "INSERTED.[created_at]" in sql


class TestCreateIndexExpression:
    """Test cases for CREATE INDEX expression formatting."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect()

    def test_basic_index(self, dialect):
        """Test basic CREATE INDEX."""
        from rhosocial.activerecord.backend.expression import CreateIndexExpression

        idx = CreateIndexExpression(
            dialect=dialect,
            index_name="idx_users_email",
            table_name="users",
            columns=["email"],
        )

        sql, params = dialect.format_create_index_statement(idx)
        assert "CREATE INDEX [idx_users_email]" in sql
        assert "ON [users]" in sql
        assert "([email])" in sql

    def test_unique_index(self, dialect):
        """Test CREATE UNIQUE INDEX."""
        from rhosocial.activerecord.backend.expression import CreateIndexExpression

        idx = CreateIndexExpression(
            dialect=dialect,
            index_name="idx_users_email_unique",
            table_name="users",
            columns=["email"],
            unique=True,
        )

        sql, params = dialect.format_create_index_statement(idx)
        assert "CREATE UNIQUE INDEX" in sql

    def test_composite_index(self, dialect):
        """Test CREATE INDEX with multiple columns."""
        from rhosocial.activerecord.backend.expression import CreateIndexExpression

        idx = CreateIndexExpression(
            dialect=dialect,
            index_name="idx_orders_composite",
            table_name="orders",
            columns=["user_id", "created_at"],
        )

        sql, params = dialect.format_create_index_statement(idx)
        assert "[user_id]" in sql
        assert "[created_at]" in sql


class TestJoinExpression:
    """Test cases for JOIN expression formatting."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect()

    def test_inner_join(self, dialect):
        """Test INNER JOIN formatting."""
        from rhosocial.activerecord.backend.expression import (
            QueryExpression,
            TableExpression,
            Column,
            JoinExpression,
        )
        from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate

        join = JoinExpression(
            dialect=dialect,
            left_table=TableExpression(dialect, "users", alias="u"),
            right_table=TableExpression(dialect, "orders", alias="o"),
            join_type="INNER JOIN",
            condition=ComparisonPredicate(
                dialect,
                "=",
                Column(dialect, "id", "u"),
                Column(dialect, "user_id", "o"),
            ),
        )

        query = QueryExpression(
            dialect=dialect,
            select=[Column(dialect, "name", "u")],
            from_=join,
        )

        sql, params = query.to_sql()
        assert "INNER JOIN" in sql
        assert "[users] AS [u]" in sql
        assert "[orders] AS [o]" in sql

    def test_left_join(self, dialect):
        """Test LEFT JOIN formatting."""
        from rhosocial.activerecord.backend.expression import (
            QueryExpression,
            TableExpression,
            Column,
            JoinExpression,
        )
        from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate

        join = JoinExpression(
            dialect=dialect,
            left_table=TableExpression(dialect, "users", alias="u"),
            right_table=TableExpression(dialect, "profiles", alias="p"),
            join_type="LEFT JOIN",
            condition=ComparisonPredicate(
                dialect,
                "=",
                Column(dialect, "id", "u"),
                Column(dialect, "user_id", "p"),
            ),
        )

        query = QueryExpression(
            dialect=dialect,
            select=[Column(dialect, "name", "u")],
            from_=join,
        )

        sql, params = query.to_sql()
        assert "LEFT JOIN" in sql
