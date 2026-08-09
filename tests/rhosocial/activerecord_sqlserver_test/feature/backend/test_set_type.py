# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_set_type.py
"""
SQL Server SET type approximation tests.

SQL Server has no MySQL-style SET column type. Comma-separated values are
stored in VARCHAR columns; these tests cover the protocol detection and the
comma-separated membership predicates the dialect provides.
"""
import pytest
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


class TestSetTypeProtocol:
    """Test SET type protocol implementation."""

    def test_supports_set_type(self):
        """Test that SQL Server does NOT support the MySQL SET type."""
        dialect_2012 = SQLServerDialect(version=(11, 0, 0))
        assert not dialect_2012.supports_set_type()

        dialect_2016 = SQLServerDialect(version=(13, 0, 0))
        assert not dialect_2016.supports_set_type()

        dialect_2022 = SQLServerDialect(version=(16, 0, 0))
        assert not dialect_2022.supports_set_type()

    def test_format_set_literal_single_value(self):
        """Test comma-separated literal with single value."""
        dialect = SQLServerDialect(version=(16, 0, 0))

        sql, params = dialect.format_set_literal(['value1'])

        assert sql == '?'
        assert params == ('value1',)

    def test_format_set_literal_multiple_values(self):
        """Test comma-separated literal with multiple values."""
        dialect = SQLServerDialect(version=(16, 0, 0))

        sql, params = dialect.format_set_literal(['value3', 'value1', 'value2'])

        assert sql == '?'
        assert params == ('value1,value2,value3',)

    def test_format_set_literal_empty(self):
        """Test comma-separated literal with empty list."""
        dialect = SQLServerDialect(version=(16, 0, 0))

        sql, params = dialect.format_set_literal([])

        assert sql == '?'
        assert params == ('',)

    def test_format_set_literal_with_validation(self):
        """Test comma-separated literal with column values validation."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        column_values = ['red', 'green', 'blue']

        sql, params = dialect.format_set_literal(['red', 'blue'], column_values)

        assert sql == '?'
        assert params == ('blue,red',)

    def test_format_set_literal_invalid_value_raises_error(self):
        """Test that invalid values raise error."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        column_values = ['red', 'green', 'blue']

        with pytest.raises(ValueError, match="Invalid SET values"):
            dialect.format_set_literal(['red', 'yellow'], column_values)

    def test_format_set_literal_max_members_exceeded(self):
        """Test that exceeding 64 members raises error."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        values = [f'val{i}' for i in range(65)]

        with pytest.raises(ValueError, match="maximum 64 members"):
            dialect.format_set_literal(values)

    def test_format_set_literal_max_members_allowed(self):
        """Test that 64 members is allowed."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        values = [f'val{i:02d}' for i in range(64)]

        sql, params = dialect.format_set_literal(values)

        assert sql == '?'
        assert len(params[0].split(',')) == 64

    def test_format_find_in_set(self):
        """Test comma-separated membership check formatting."""
        dialect = SQLServerDialect(version=(16, 0, 0))

        sql, params = dialect.format_find_in_set('value1', 'tags')

        assert 'LIKE' in sql
        assert '[tags]' in sql
        assert params == ('value1',)

    def test_format_find_in_set_different_column(self):
        """Test membership check with different column name."""
        dialect = SQLServerDialect(version=(16, 0, 0))

        sql, params = dialect.format_find_in_set('active', 'status')

        assert 'LIKE' in sql
        assert '[status]' in sql
        assert params == ('active',)

    def test_format_set_contains_single_value(self):
        """Test set contains check with single value."""
        dialect = SQLServerDialect(version=(16, 0, 0))

        sql, params = dialect.format_set_contains('tags', ['value1'])

        assert 'LIKE' in sql
        assert '[tags]' in sql
        assert params == ('value1',)

    def test_format_set_contains_multiple_values(self):
        """Test set contains check with multiple values."""
        dialect = SQLServerDialect(version=(16, 0, 0))

        sql, params = dialect.format_set_contains('tags', ['value1', 'value2'])

        assert 'LIKE' in sql
        assert ' AND ' in sql
        assert params == ('value1', 'value2')

    def test_format_set_contains_three_values(self):
        """Test set contains check with three values."""
        dialect = SQLServerDialect(version=(16, 0, 0))

        sql, params = dialect.format_set_contains('status', ['active', 'pending', 'verified'])

        assert sql.count('LIKE') == 3
        assert sql.count(' AND ') == 2
        assert params == ('active', 'pending', 'verified')


class TestAsyncSetTypeProtocol:
    """Test async SET type protocol (same as sync, but verifies parity)."""

    @pytest.mark.asyncio
    async def test_async_supports_set_type(self):
        """Test async version of supports_set_type."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert not dialect.supports_set_type()

    @pytest.mark.asyncio
    async def test_async_format_set_literal(self):
        """Test async version of comma-separated literal formatting."""
        dialect = SQLServerDialect(version=(16, 0, 0))

        sql, params = dialect.format_set_literal(['a', 'b', 'c'])

        assert sql == '?'
        assert params == ('a,b,c',)

    @pytest.mark.asyncio
    async def test_async_format_find_in_set(self):
        """Test async version of membership check formatting."""
        dialect = SQLServerDialect(version=(16, 0, 0))

        sql, params = dialect.format_find_in_set('test', 'column')

        assert 'LIKE' in sql
        assert params == ('test',)

    @pytest.mark.asyncio
    async def test_async_format_set_contains(self):
        """Test async version of set contains formatting."""
        dialect = SQLServerDialect(version=(16, 0, 0))

        sql, params = dialect.format_set_contains('tags', ['a', 'b'])

        assert ' AND ' in sql
        assert params == ('a', 'b')
