# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_create_table_like.py
"""
SQL Server CREATE TABLE behavior tests.

SQL Server has no CREATE TABLE ... LIKE syntax and no TEMPORARY keyword.
This module verifies that ``like_table`` raises ``UnsupportedFeatureError``,
temporary tables render ``#``-prefixed names, and identifiers use brackets.
"""
import pytest
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import CreateTableExpression, ColumnDefinition
from rhosocial.activerecord.backend.expression.statements import ColumnConstraint, ColumnConstraintType
from rhosocial.activerecord.backend.expression.types import IntegerType, VarCharType
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


class TestSQLServerCreateTableLike:
    """Tests for CREATE TABLE behavior on SQL Server."""

    def test_basic_like_raises(self):
        """Test that CREATE TABLE ... LIKE raises UnsupportedFeatureError."""
        dialect = SQLServerDialect()
        create_expr = CreateTableExpression(
            dialect=dialect,
            table="users_copy",
            columns=[],
            dialect_options={'like_table': 'users'}
        )
        with pytest.raises(UnsupportedFeatureError):
            create_expr.to_sql()

    def test_like_with_if_not_exists_raises(self):
        """Test CREATE TABLE ... LIKE with IF NOT EXISTS raises."""
        dialect = SQLServerDialect()
        create_expr = CreateTableExpression(
            dialect=dialect,
            table="users_copy",
            columns=[],
            if_not_exists=True,
            dialect_options={'like_table': 'users'}
        )
        with pytest.raises(UnsupportedFeatureError):
            create_expr.to_sql()

    def test_like_with_temporary_raises(self):
        """Test CREATE TABLE ... LIKE with temporary raises."""
        dialect = SQLServerDialect()
        create_expr = CreateTableExpression(
            dialect=dialect,
            table="temp_users",
            columns=[],
            temporary=True,
            dialect_options={'like_table': 'users'}
        )
        with pytest.raises(UnsupportedFeatureError):
            create_expr.to_sql()

    def test_like_with_schema_qualified_table_raises(self):
        """Test CREATE TABLE ... LIKE with schema-qualified source raises."""
        dialect = SQLServerDialect()
        create_expr = CreateTableExpression(
            dialect=dialect,
            table="users_copy",
            columns=[],
            dialect_options={'like_table': ('production', 'users')}
        )
        with pytest.raises(UnsupportedFeatureError):
            create_expr.to_sql()

    def test_like_ignores_columns_raises(self):
        """Test that LIKE syntax raises even when columns are present."""
        dialect = SQLServerDialect()
        columns = [
            ColumnDefinition("id", IntegerType(), constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)
            ]),
            ColumnDefinition("name", VarCharType(length=255))
        ]
        create_expr = CreateTableExpression(
            dialect=dialect,
            table="users_copy",
            columns=columns,
            dialect_options={'like_table': 'users'}
        )
        with pytest.raises(UnsupportedFeatureError):
            create_expr.to_sql()

    def test_like_with_temporary_and_if_not_exists_raises(self):
        """Test CREATE TABLE ... LIKE with temporary and IF NOT EXISTS raises."""
        dialect = SQLServerDialect()
        create_expr = CreateTableExpression(
            dialect=dialect,
            table="temp_users_copy",
            columns=[],
            temporary=True,
            if_not_exists=True,
            dialect_options={'like_table': ('test_db', 'users')}
        )
        with pytest.raises(UnsupportedFeatureError):
            create_expr.to_sql()

    def test_temporary_uses_hash_prefix(self):
        """Test that a temporary table renders a #-prefixed table name."""
        dialect = SQLServerDialect()
        columns = [
            ColumnDefinition("id", IntegerType(), constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)
            ]),
        ]
        create_expr = CreateTableExpression(
            dialect=dialect,
            table="temp_users",
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
            ColumnDefinition("id", IntegerType(), constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)
            ]),
            ColumnDefinition("name", VarCharType(length=255), constraints=[
                ColumnConstraint(ColumnConstraintType.NOT_NULL)
            ])
        ]
        create_expr = CreateTableExpression(
            dialect=dialect,
            table="users",
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
