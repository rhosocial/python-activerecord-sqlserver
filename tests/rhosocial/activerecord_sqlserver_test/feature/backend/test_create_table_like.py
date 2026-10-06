# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_create_table_like.py
"""
SQL Server CREATE TABLE behavior tests.

SQL Server has no CREATE TABLE ... LIKE syntax and no TEMPORARY keyword.
This module verifies that ``CreateTableLikeExpression`` raises
``UnsupportedFeatureError`` (the dialect keeps
``supports_create_table_like`` at ``False``), temporary tables render
``#``-prefixed names, and identifiers use brackets.
"""
import pytest
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import CreateTableExpression, ColumnDefinition
from rhosocial.activerecord.backend.expression.statements import (
    ColumnConstraint,
    ColumnConstraintType,
    CreateTableLikeExpression,
)
from rhosocial.activerecord.backend.expression.types import IntegerType, VarCharType
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.expression.objects import Table


class TestSQLServerCreateTableLike:
    """Tests for CREATE TABLE behavior on SQL Server."""

    def test_like_not_supported_by_dialect(self):
        """Test the dialect does not advertise CREATE TABLE ... LIKE support."""
        assert SQLServerDialect().supports_create_table_like() is False

    def test_basic_like_raises(self):
        """Test that CREATE TABLE ... LIKE raises UnsupportedFeatureError."""
        dialect = SQLServerDialect()
        create_expr = CreateTableLikeExpression(
            dialect=dialect,
            table=Table(dialect, "users_copy"),
            like_table=Table(dialect, "users"),
        )
        with pytest.raises(UnsupportedFeatureError):
            create_expr.to_sql()

    def test_like_with_if_not_exists_raises(self):
        """Test CREATE TABLE ... LIKE with IF NOT EXISTS raises."""
        dialect = SQLServerDialect()
        create_expr = CreateTableLikeExpression(
            dialect=dialect,
            table=Table(dialect, "users_copy"),
            like_table=Table(dialect, "users"),
            if_not_exists=True,
        )
        with pytest.raises(UnsupportedFeatureError):
            create_expr.to_sql()

    def test_like_with_temporary_raises(self):
        """Test CREATE TABLE ... LIKE with temporary raises."""
        dialect = SQLServerDialect()
        create_expr = CreateTableLikeExpression(
            dialect=dialect,
            table=Table(dialect, "temp_users"),
            like_table=Table(dialect, "users"),
            temporary=True,
        )
        with pytest.raises(UnsupportedFeatureError):
            create_expr.to_sql()

    def test_like_with_schema_qualified_table_raises(self):
        """Test CREATE TABLE ... LIKE with schema-qualified source raises."""
        dialect = SQLServerDialect()
        create_expr = CreateTableLikeExpression(
            dialect=dialect,
            table=Table(dialect, "users_copy"),
            like_table=Table(dialect, "users", schema_name="production"),
        )
        with pytest.raises(UnsupportedFeatureError):
            create_expr.to_sql()

    def test_like_with_temporary_and_if_not_exists_raises(self):
        """Test CREATE TABLE ... LIKE with temporary and IF NOT EXISTS raises."""
        dialect = SQLServerDialect()
        create_expr = CreateTableLikeExpression(
            dialect=dialect,
            table=Table(dialect, "temp_users_copy"),
            like_table=Table(dialect, "users", catalog_name="test_db"),
            temporary=True,
            if_not_exists=True,
        )
        with pytest.raises(UnsupportedFeatureError):
            create_expr.to_sql()

    def test_temporary_uses_hash_prefix(self):
        """Test that a temporary table renders a #-prefixed table name."""
        dialect = SQLServerDialect()
        columns = [
            ColumnDefinition(dialect, "id", IntegerType(dialect), constraints=[
                ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)
            ]),
        ]
        create_expr = CreateTableExpression(
            dialect=dialect,
            table=Table(dialect, "temp_users"),
            columns=columns,
            temporary=True,
        )
        sql, params = create_expr.to_sql()

        assert "CREATE TABLE" in sql
        assert "[#temp_users]" in sql
        assert "TEMPORARY" not in sql
        assert params == ()

    def test_fallback_to_base_when_no_like(self):
        """Test that base implementation is used when LIKE is not specified."""
        dialect = SQLServerDialect()
        columns = [
            ColumnDefinition(dialect, "id", IntegerType(dialect), constraints=[
                ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY)
            ]),
            ColumnDefinition(dialect, "name", VarCharType(dialect, length=255), constraints=[
                ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)
            ])
        ]
        create_expr = CreateTableExpression(
            dialect=dialect,
            table=Table(dialect, "users"),
            columns=columns
        )
        sql, params = create_expr.to_sql()

        # Should use base implementation with bracketed identifiers
        assert "CREATE TABLE" in sql
        assert "[users]" in sql
        assert "[id]" in sql
        assert "[name]" in sql
        assert "PRIMARY KEY" in sql
        assert "NOT NULL" in sql
