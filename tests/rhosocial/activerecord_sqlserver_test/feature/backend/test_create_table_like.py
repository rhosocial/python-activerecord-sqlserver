# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_create_table_like.py
"""
MySQL CREATE TABLE ... LIKE syntax tests.

This module tests the SQLServer-specific LIKE syntax for CREATE TABLE statements.
"""
import pytest
from rhosocial.activerecord.backend.expression import CreateTableExpression, ColumnDefinition
from rhosocial.activerecord.backend.expression.statements import ColumnConstraint, ColumnConstraintType
from rhosocial.activerecord.backend.expression.types import IntegerType, VarCharType
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


class TestMySQLCreateTableLike:
    """Tests for MySQL CREATE TABLE ... LIKE syntax."""

    def test_basic_like_syntax(self):
        """Test basic CREATE TABLE ... LIKE syntax."""
        dialect = SQLServerDialect()
        create_expr = CreateTableExpression(
            dialect=dialect,
            table="users_copy",
            columns=[],
            dialect_options={'like_table': 'users'}
        )
        sql, params = create_expr.to_sql()

        assert sql == "CREATE TABLE `users_copy` LIKE `users`"
        assert params == ()

    def test_like_with_if_not_exists(self):
        """Test CREATE TABLE ... LIKE with IF NOT EXISTS."""
        dialect = SQLServerDialect()
        create_expr = CreateTableExpression(
            dialect=dialect,
            table="users_copy",
            columns=[],
            if_not_exists=True,
            dialect_options={'like_table': 'users'}
        )
        sql, params = create_expr.to_sql()

        assert sql == "CREATE TABLE IF NOT EXISTS `users_copy` LIKE `users`"
        assert params == ()

    def test_like_with_temporary(self):
        """Test CREATE TEMPORARY TABLE ... LIKE."""
        dialect = SQLServerDialect()
        create_expr = CreateTableExpression(
            dialect=dialect,
            table="temp_users",
            columns=[],
            temporary=True,
            dialect_options={'like_table': 'users'}
        )
        sql, params = create_expr.to_sql()

        assert sql == "CREATE TABLE TEMPORARY `temp_users` LIKE `users`"
        assert params == ()

    def test_like_with_schema_qualified_table(self):
        """Test CREATE TABLE ... LIKE with schema-qualified source table."""
        dialect = SQLServerDialect()
        create_expr = CreateTableExpression(
            dialect=dialect,
            table="users_copy",
            columns=[],
            dialect_options={'like_table': ('production', 'users')}
        )
        sql, params = create_expr.to_sql()

        assert sql == "CREATE TABLE `users_copy` LIKE `production`.`users`"
        assert params == ()

    def test_like_ignores_columns(self):
        """Test that LIKE syntax ignores columns parameter."""
        dialect = SQLServerDialect()
        columns = [
            ColumnDefinition("id", IntegerType(), constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)
            ]),
            ColumnDefinition("name", VarCharType(255))
        ]
        create_expr = CreateTableExpression(
            dialect=dialect,
            table="users_copy",
            columns=columns,
            dialect_options={'like_table': 'users'}
        )
        sql, params = create_expr.to_sql()

        # LIKE syntax should take precedence, columns should be ignored
        assert sql == "CREATE TABLE `users_copy` LIKE `users`"
        assert params == ()

    def test_like_with_temporary_and_if_not_exists(self):
        """Test CREATE TEMPORARY TABLE ... LIKE with IF NOT EXISTS."""
        dialect = SQLServerDialect()
        create_expr = CreateTableExpression(
            dialect=dialect,
            table="temp_users_copy",
            columns=[],
            temporary=True,
            if_not_exists=True,
            dialect_options={'like_table': ('test_db', 'users')}
        )
        sql, params = create_expr.to_sql()

        assert sql == "CREATE TABLE TEMPORARY IF NOT EXISTS `temp_users_copy` LIKE `test_db`.`users`"
        assert params == ()

    def test_fallback_to_base_when_no_like(self):
        """Test that base implementation is used when LIKE is not specified."""
        dialect = SQLServerDialect()
        columns = [
            ColumnDefinition("id", IntegerType(), constraints=[
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)
            ]),
            ColumnDefinition("name", VarCharType(255), constraints=[
                ColumnConstraint(ColumnConstraintType.NOT_NULL)
            ])
        ]
        create_expr = CreateTableExpression(
            dialect=dialect,
            table="users",
            columns=columns
        )
        sql, params = create_expr.to_sql()

        # Should use base implementation
        assert "CREATE TABLE" in sql
        assert "`users`" in sql
        assert "`id`" in sql
        assert "`name`" in sql
        assert "PRIMARY KEY" in sql
        assert "NOT NULL" in sql
