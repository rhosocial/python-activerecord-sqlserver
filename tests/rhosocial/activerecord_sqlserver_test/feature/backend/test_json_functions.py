# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_json_functions.py
"""
MySQL JSON function support tests.

This module tests SQLServer-specific JSON function functionality including:
- Function version detection
- JSON_EXTRACT formatting
- JSON_UNQUOTE formatting
- JSON_OBJECT formatting
- JSON_ARRAY formatting
- JSON_CONTAINS formatting
- JSON_SET formatting
- JSON_REMOVE formatting
- JSON_TYPE formatting
- JSON_VALID formatting
- JSON_SEARCH formatting
"""
import pytest
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


class TestJSONFunctionProtocol:
    """Test JSON function protocol implementation."""

    def test_supports_json_function_basic(self):
        """Test basic JSON function support (SQLServer 10.2.3+)."""
        dialect_102 = SQLServerDialect(version=(10, 2, 0))
        assert not dialect_102.supports_json_function('JSON_EXTRACT')

        dialect_1023 = SQLServerDialect(version=(10, 2, 3))
        assert dialect_1023.supports_json_function('JSON_EXTRACT')

        dialect_103 = SQLServerDialect(version=(10, 3, 0))
        assert dialect_103.supports_json_function('JSON_EXTRACT')

    def test_supports_json_function_json_table(self):
        """Test JSON_TABLE support - SQLServer does NOT support JSON_TABLE."""
        dialect_103 = SQLServerDialect(version=(10, 3, 0))
        assert not dialect_103.supports_json_function('JSON_TABLE')

        dialect_105 = SQLServerDialect(version=(10, 5, 0))
        assert not dialect_105.supports_json_function('JSON_TABLE')

    def test_supports_json_function_json_value(self):
        """Test JSON_VALUE support (SQLServer 10.2.3+)."""
        dialect_102 = SQLServerDialect(version=(10, 2, 0))
        assert not dialect_102.supports_json_function('JSON_VALUE')

        dialect_1023 = SQLServerDialect(version=(10, 2, 3))
        assert dialect_1023.supports_json_function('JSON_VALUE')

    def test_format_json_extract_single_path(self):
        """Test JSON_EXTRACT with single path."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_extract('data', '$.name')

        assert sql == 'JSON_EXTRACT(data, %s)'
        assert params == ('$.name',)

    def test_format_json_extract_multiple_paths(self):
        """Test JSON_EXTRACT with multiple paths."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_extract('data', '$.name', ['$.age', '$.city'])

        assert sql == 'JSON_EXTRACT(data, %s, %s, %s)'
        assert params == ('$.name', '$.age', '$.city')

    def test_format_json_unquote(self):
        """Test JSON_UNQUOTE function."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_unquote('data->"$.name"')

        assert sql == 'JSON_UNQUOTE(data->"$.name")'
        assert params == ()

    def test_format_json_object_empty(self):
        """Test JSON_OBJECT with no arguments."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_object([])

        assert sql == 'JSON_OBJECT()'
        assert params == ()

    def test_format_json_object_single_pair(self):
        """Test JSON_OBJECT with single key-value pair."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_object([('name', 'John')])

        assert sql == 'JSON_OBJECT(%s, %s)'
        assert params == ('name', 'John')

    def test_format_json_object_multiple_pairs(self):
        """Test JSON_OBJECT with multiple key-value pairs."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_object([('name', 'John'), ('age', 30), ('city', 'NYC')])

        assert sql == 'JSON_OBJECT(%s, %s, %s, %s, %s, %s)'
        assert params == ('name', 'John', 'age', 30, 'city', 'NYC')

    def test_format_json_array_empty(self):
        """Test JSON_ARRAY with no arguments."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_array([])

        assert sql == 'JSON_ARRAY()'
        assert params == ()

    def test_format_json_array_single_value(self):
        """Test JSON_ARRAY with single value."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_array([1])

        assert sql == 'JSON_ARRAY(%s)'
        assert params == (1,)

    def test_format_json_array_multiple_values(self):
        """Test JSON_ARRAY with multiple values."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_array([1, 'hello', None, True])

        assert sql == 'JSON_ARRAY(%s, %s, %s, %s)'
        assert params == (1, 'hello', None, True)

    def test_format_json_contains_no_path(self):
        """Test JSON_CONTAINS without path."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_contains('data', '{"name": "John"}')

        assert sql == 'JSON_CONTAINS(data, %s)'
        assert params == ('{"name": "John"}',)

    def test_format_json_contains_with_path(self):
        """Test JSON_CONTAINS with path."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_contains('data', '"John"', '$.name')

        assert sql == 'JSON_CONTAINS(data, %s, %s)'
        assert params == ('"John"', '$.name')

    def test_format_json_set_single_pair(self):
        """Test JSON_SET with single path-value pair."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_set('data', '$.name', 'John')

        assert sql == 'JSON_SET(data, %s, %s)'
        assert params == ('$.name', 'John')

    def test_format_json_set_multiple_pairs(self):
        """Test JSON_SET with multiple path-value pairs."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_set(
            'data', '$.name', 'John',
            path_value_pairs=[('$.age', 30), ('$.city', 'NYC')]
        )

        assert sql == 'JSON_SET(data, %s, %s, %s, %s, %s, %s)'
        assert params == ('$.name', 'John', '$.age', 30, '$.city', 'NYC')

    def test_format_json_remove_single_path(self):
        """Test JSON_REMOVE with single path."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_remove('data', '$.temp')

        assert sql == 'JSON_REMOVE(data, %s)'
        assert params == ('$.temp',)

    def test_format_json_remove_multiple_paths(self):
        """Test JSON_REMOVE with multiple paths."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_remove('data', '$.temp', paths=['$.cache', '$.old'])

        assert sql == 'JSON_REMOVE(data, %s, %s, %s)'
        assert params == ('$.temp', '$.cache', '$.old')

    def test_format_json_type(self):
        """Test JSON_TYPE function."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_type('data')

        assert sql == 'JSON_TYPE(data)'
        assert params == ()

    def test_format_json_valid(self):
        """Test JSON_VALID function."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_valid('data')

        assert sql == 'JSON_VALID(data)'
        assert params == ()

    def test_format_json_search_one(self):
        """Test JSON_SEARCH with 'one' mode."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_search('data', 'John', all_=False)

        assert "JSON_SEARCH(data, 'one', %s)" in sql
        assert params == ('John',)

    def test_format_json_search_all(self):
        """Test JSON_SEARCH with 'all' mode."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_search('data', 'John', all_=True)

        assert "JSON_SEARCH(data, 'all', %s)" in sql
        assert params == ('John',)

    def test_format_json_search_with_path(self):
        """Test JSON_SEARCH with path."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_search('data', 'John', path='$.users', all_=True)

        assert "JSON_SEARCH(data, 'all', %s, NULL, %s)" in sql
        assert params == ('John', '$.users')


class TestAsyncJSONFunctionProtocol:
    """Test async JSON function protocol (same as sync, but verifies parity)."""

    @pytest.mark.asyncio
    async def test_async_supports_json_function(self):
        """Test async version of supports_json_function."""
        dialect = SQLServerDialect(version=(10, 2, 3))
        assert dialect.supports_json_function('JSON_EXTRACT')

    @pytest.mark.asyncio
    async def test_async_format_json_extract(self):
        """Test async version of JSON_EXTRACT formatting."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_extract('data', '$.name')

        assert 'JSON_EXTRACT' in sql
        assert params == ('$.name',)

    @pytest.mark.asyncio
    async def test_async_format_json_object(self):
        """Test async version of JSON_OBJECT formatting."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_object([('key', 'value')])

        assert 'JSON_OBJECT' in sql
        assert params == ('key', 'value')

    @pytest.mark.asyncio
    async def test_async_format_json_array(self):
        """Test async version of JSON_ARRAY formatting."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_array([1, 2, 3])

        assert 'JSON_ARRAY' in sql
        assert params == (1, 2, 3)

    @pytest.mark.asyncio
    async def test_async_format_json_contains(self):
        """Test async version of JSON_CONTAINS formatting."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_contains('data', '"value"', '$.path')

        assert 'JSON_CONTAINS' in sql
        assert '"value"' in params

    @pytest.mark.asyncio
    async def test_async_format_json_set(self):
        """Test async version of JSON_SET formatting."""
        dialect = SQLServerDialect(version=(10, 2, 3))

        sql, params = dialect.format_json_set('data', '$.key', 'value')

        assert 'JSON_SET' in sql
        assert '$.key' in params
