# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_niladic_functions.py
"""
SQL Server niladic function integration tests.

SQL Server accepts the SQL:2003 niladic form (no parentheses) for
CURRENT_TIMESTAMP but has no NOW(), CURRENT_DATE or CURRENT_TIME. The dialect
maps those to SQL Server equivalents:

- NOW()         -> SYSDATETIME()
- CURRENT_DATE  -> CAST(GETDATE() AS DATE)
- CURRENT_TIME  -> CAST(GETDATE() AS TIME)

These tests verify the rendered SQL and execute it against a real database
in both DDL DEFAULT and SELECT contexts.
"""
import pytest

from rhosocial.activerecord.backend.expression import (
    CreateTableExpression,
    DropTableExpression,
    QueryExpression,
)
from rhosocial.activerecord.backend.expression.core import FunctionCall
from rhosocial.activerecord.backend.expression.functions.datetime import (
    current_timestamp,
    current_date,
    current_time,
    now,
)
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
)
from rhosocial.activerecord.backend.expression.types import IntegerType, TimestampType
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType


DQL_OPTIONS = ExecutionOptions(stmt_type=StatementType.DQL)


class TestSQLServerNiladicSelectContext:
    """Test niladic functions in SELECT context against real SQL Server."""

    def test_select_current_timestamp_niladic(self, sqlserver_backend):
        """SELECT CURRENT_TIMESTAMP (niladic) works in SQL Server."""
        query = QueryExpression(
            dialect=sqlserver_backend.dialect,
            select=[current_timestamp(sqlserver_backend.dialect)],
        )
        sql, params = query.to_sql()
        assert sql == "SELECT CURRENT_TIMESTAMP"
        assert "(" not in sql.replace("SELECT ", "")
        result = sqlserver_backend.execute(sql, params, options=DQL_OPTIONS)
        assert result.data is not None
        assert len(result.data) == 1

    def test_select_sysdatetime(self, sqlserver_backend):
        """SELECT SYSDATETIME() (the SQL Server equivalent of NOW()) works."""
        query = QueryExpression(
            dialect=sqlserver_backend.dialect,
            select=[FunctionCall(sqlserver_backend.dialect, 'SYSDATETIME')],
        )
        sql, params = query.to_sql()
        assert "SYSDATETIME()" in sql
        result = sqlserver_backend.execute(sql, params, options=DQL_OPTIONS)
        assert result.data is not None
        assert len(result.data) == 1

    def test_select_current_date(self, sqlserver_backend):
        """SELECT CAST(GETDATE() AS DATE) (CURRENT_DATE equivalent) works."""
        query = QueryExpression(
            dialect=sqlserver_backend.dialect,
            select=[current_date(sqlserver_backend.dialect)],
        )
        sql, params = query.to_sql()
        assert "CAST(GETDATE() AS DATE)" in sql
        result = sqlserver_backend.execute(sql, params, options=DQL_OPTIONS)
        assert result.data is not None
        assert len(result.data) == 1

    def test_select_current_time(self, sqlserver_backend):
        """SELECT CAST(GETDATE() AS TIME) (CURRENT_TIME equivalent) works."""
        query = QueryExpression(
            dialect=sqlserver_backend.dialect,
            select=[current_time(sqlserver_backend.dialect)],
        )
        sql, params = query.to_sql()
        assert "CAST(GETDATE() AS TIME)" in sql
        result = sqlserver_backend.execute(sql, params, options=DQL_OPTIONS)
        assert result.data is not None
        assert len(result.data) == 1

    def test_select_now(self, sqlserver_backend):
        """SELECT SYSDATETIME() (regular function, always with parentheses) works."""
        query = QueryExpression(
            dialect=sqlserver_backend.dialect,
            select=[now(sqlserver_backend.dialect)],
        )
        sql, params = query.to_sql()
        assert "SYSDATETIME()" in sql
        result = sqlserver_backend.execute(sql, params, options=DQL_OPTIONS)
        assert result.data is not None
        assert len(result.data) == 1


class TestSQLServerNiladicDDLContext:
    """Test niladic functions in DDL DEFAULT context against real SQL Server."""

    def test_ddl_default_current_timestamp_niladic(self, sqlserver_backend):
        """DEFAULT CURRENT_TIMESTAMP (niladic) works in SQL Server DDL."""
        dialect = sqlserver_backend.dialect
        table_name = 'test_niladic_ddl_1'

        # Clean up
        sqlserver_backend.execute(*DropTableExpression(
            dialect=dialect, table=table_name, if_exists=True
        ).to_sql())

        create = CreateTableExpression(
            dialect=dialect,
            table=table_name,
            columns=[
                ColumnDefinition('id', IntegerType(), constraints=[
                    ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                    ColumnConstraint(ColumnConstraintType.NOT_NULL, is_auto_increment=True),
                ]),
                ColumnDefinition('ts', TimestampType(), constraints=[
                    ColumnConstraint(ColumnConstraintType.DEFAULT,
                                     default_value=current_timestamp(dialect)),
                ]),
            ],
            if_not_exists=True,
        )
        sql, params = create.to_sql()
        assert "DEFAULT CURRENT_TIMESTAMP" in sql
        assert "DEFAULT CURRENT_TIMESTAMP()" not in sql

        try:
            sqlserver_backend.execute(sql, params)
            # Verify table was created
            cols = sqlserver_backend.introspector.list_columns(table_name)
            col_names = [c.name for c in cols]
            assert 'ts' in col_names
        finally:
            sqlserver_backend.execute(*DropTableExpression(
                dialect=dialect, table=table_name, if_exists=True
            ).to_sql())

    def test_ddl_default_sysdatetime(self, sqlserver_backend):
        """DEFAULT SYSDATETIME() works in SQL Server DDL."""
        dialect = sqlserver_backend.dialect
        table_name = 'test_niladic_ddl_2'

        # Clean up
        sqlserver_backend.execute(*DropTableExpression(
            dialect=dialect, table=table_name, if_exists=True
        ).to_sql())

        create = CreateTableExpression(
            dialect=dialect,
            table=table_name,
            columns=[
                ColumnDefinition('id', IntegerType(), constraints=[
                    ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                    ColumnConstraint(ColumnConstraintType.NOT_NULL, is_auto_increment=True),
                ]),
                ColumnDefinition('ts', TimestampType(precision=6), constraints=[
                    ColumnConstraint(ColumnConstraintType.DEFAULT,
                                     default_value=FunctionCall(dialect, 'SYSDATETIME')),
                ]),
            ],
            if_not_exists=True,
        )
        sql, params = create.to_sql()
        assert "DEFAULT SYSDATETIME()" in sql

        try:
            sqlserver_backend.execute(sql, params)
            # Verify table was created
            cols = sqlserver_backend.introspector.list_columns(table_name)
            col_names = [c.name for c in cols]
            assert 'ts' in col_names
        finally:
            sqlserver_backend.execute(*DropTableExpression(
                dialect=dialect, table=table_name, if_exists=True
            ).to_sql())


class TestAsyncSQLServerNiladicSelectContext:
    """Async niladic function tests in SELECT context against real SQL Server."""

    @pytest.mark.asyncio
    async def test_async_select_current_timestamp_niladic(self, async_sqlserver_backend):
        """SELECT CURRENT_TIMESTAMP (niladic) works in SQL Server (async)."""
        query = QueryExpression(
            dialect=async_sqlserver_backend.dialect,
            select=[current_timestamp(async_sqlserver_backend.dialect)],
        )
        sql, params = query.to_sql()
        assert sql == "SELECT CURRENT_TIMESTAMP"
        result = await async_sqlserver_backend.execute(sql, params, options=DQL_OPTIONS)
        assert result.data is not None
        assert len(result.data) == 1


class TestAsyncSQLServerNiladicDDLContext:
    """Async niladic function tests in DDL DEFAULT context against real SQL Server."""

    @pytest.mark.asyncio
    async def test_async_ddl_default_current_timestamp_niladic(self, async_sqlserver_backend):
        """DEFAULT CURRENT_TIMESTAMP (niladic) works in SQL Server DDL (async)."""
        dialect = async_sqlserver_backend.dialect
        table_name = 'test_async_niladic_ddl_1'

        # Clean up
        await async_sqlserver_backend.execute(*DropTableExpression(
            dialect=dialect, table=table_name, if_exists=True
        ).to_sql())

        create = CreateTableExpression(
            dialect=dialect,
            table=table_name,
            columns=[
                ColumnDefinition('id', IntegerType(), constraints=[
                    ColumnConstraint(ColumnConstraintType.PRIMARY_KEY),
                    ColumnConstraint(ColumnConstraintType.NOT_NULL, is_auto_increment=True),
                ]),
                ColumnDefinition('ts', TimestampType(), constraints=[
                    ColumnConstraint(ColumnConstraintType.DEFAULT,
                                     default_value=current_timestamp(dialect)),
                ]),
            ],
            if_not_exists=True,
        )
        sql, params = create.to_sql()

        try:
            await async_sqlserver_backend.execute(sql, params)
            cols = await async_sqlserver_backend.introspector.list_columns(table_name)
            col_names = [c.name for c in cols]
            assert 'ts' in col_names
        finally:
            await async_sqlserver_backend.execute(*DropTableExpression(
                dialect=dialect, table=table_name, if_exists=True
            ).to_sql())
