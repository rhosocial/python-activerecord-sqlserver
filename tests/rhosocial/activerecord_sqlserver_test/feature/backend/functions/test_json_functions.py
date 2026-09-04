# tests/rhosocial/activerecord_sqlserver_test/feature/backend/functions/test_json_functions.py
"""
SQL Server JSON function protocol tests.

This module tests SQL Server-specific JSON function functionality including:
- Function version detection (JSON requires SQL Server 2016+)
- JSON_VALUE formatting
- JSON_OBJECT/JSON_ARRAY formatting (SQL Server 2022+)
- JSON_MODIFY formatting
- ISJSON formatting
- OPENJSON containment checks
"""
import pytest
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

SQL_SERVER_2014 = (12, 0, 0)
SQL_SERVER_2016 = (13, 0, 0)
SQL_SERVER_2017 = (14, 0, 0)
SQL_SERVER_2022 = (16, 0, 0)


class TestJSONFunctionProtocol:
    """Test JSON function protocol implementation."""

    def test_supports_json_function_basic(self):
        """Test basic JSON function support (SQL Server 2016+)."""
        dialect_2014 = SQLServerDialect(version=SQL_SERVER_2014)
        assert not dialect_2014.supports_json_function('JSON_VALUE')

        dialect_2016 = SQLServerDialect(version=SQL_SERVER_2016)
        assert dialect_2016.supports_json_function('JSON_VALUE')

        dialect_2017 = SQLServerDialect(version=SQL_SERVER_2017)
        assert dialect_2017.supports_json_function('JSON_VALUE')

    def test_supports_json_function_json_table(self):
        """Test JSON_TABLE support - SQL Server does NOT support JSON_TABLE."""
        dialect_2016 = SQLServerDialect(version=SQL_SERVER_2016)
        assert not dialect_2016.supports_json_function('JSON_TABLE')

        dialect_2022 = SQLServerDialect(version=SQL_SERVER_2022)
        assert not dialect_2022.supports_json_function('JSON_TABLE')

    def test_supports_json_function_json_value(self):
        """Test JSON_VALUE support (SQL Server 2016+)."""
        dialect_2014 = SQLServerDialect(version=SQL_SERVER_2014)
        assert not dialect_2014.supports_json_function('JSON_VALUE')

        dialect_2016 = SQLServerDialect(version=SQL_SERVER_2016)
        assert dialect_2016.supports_json_function('JSON_VALUE')

    def test_format_json_extract_single_path(self):
        """Test JSON_VALUE extraction with a single path."""
        dialect = SQLServerDialect(version=SQL_SERVER_2016)

        sql, params = dialect.format_json_extract('data', '$.name')

        assert sql == 'JSON_VALUE(data, ?)'
        assert params == ('$.name',)

    def test_format_json_extract_multiple_paths(self):
        """Test JSON_VALUE raises for multiple paths (no T-SQL equivalent)."""
        dialect = SQLServerDialect(version=SQL_SERVER_2016)

        with pytest.raises(UnsupportedFeatureError):
            dialect.format_json_extract('data', '$.name', ['$.age', '$.city'])

    def test_format_json_unquote(self):
        """Test JSON_UNQUOTE is not supported (JSON_VALUE returns scalars unquoted)."""
        dialect = SQLServerDialect(version=SQL_SERVER_2016)

        with pytest.raises(UnsupportedFeatureError):
            dialect.format_json_unquote('data')

    def test_format_json_object_empty(self):
        """Test JSON_OBJECT with no arguments."""
        dialect = SQLServerDialect(version=SQL_SERVER_2022)

        sql, params = dialect.format_json_object([])

        assert sql == 'JSON_OBJECT()'
        assert params == ()

    def test_format_json_object_single_pair(self):
        """Test JSON_OBJECT with single key-value pair."""
        dialect = SQLServerDialect(version=SQL_SERVER_2022)

        sql, params = dialect.format_json_object([('name', 'John')])

        assert sql == 'JSON_OBJECT(? : ?)'
        assert params == ('name', 'John')

    def test_format_json_object_multiple_pairs(self):
        """Test JSON_OBJECT with multiple key-value pairs."""
        dialect = SQLServerDialect(version=SQL_SERVER_2022)

        sql, params = dialect.format_json_object([('name', 'John'), ('age', 30), ('city', 'NYC')])

        assert sql == 'JSON_OBJECT(? : ?, ? : ?, ? : ?)'
        assert params == ('name', 'John', 'age', 30, 'city', 'NYC')

    def test_format_json_array_empty(self):
        """Test JSON_ARRAY with no arguments."""
        dialect = SQLServerDialect(version=SQL_SERVER_2022)

        sql, params = dialect.format_json_array([])

        assert sql == 'JSON_ARRAY()'
        assert params == ()

    def test_format_json_array_single_value(self):
        """Test JSON_ARRAY with single value."""
        dialect = SQLServerDialect(version=SQL_SERVER_2022)

        sql, params = dialect.format_json_array([1])

        assert sql == 'JSON_ARRAY(?)'
        assert params == (1,)

    def test_format_json_array_multiple_values(self):
        """Test JSON_ARRAY with multiple values."""
        dialect = SQLServerDialect(version=SQL_SERVER_2022)

        sql, params = dialect.format_json_array([1, 'hello', None, True])

        assert sql == 'JSON_ARRAY(?, ?, ?, ?)'
        assert params == (1, 'hello', None, True)

    def test_format_json_contains_no_path(self):
        """Test OPENJSON containment check without path."""
        dialect = SQLServerDialect(version=SQL_SERVER_2016)

        sql, params = dialect.format_json_contains('data', '{"name": "John"}')

        assert 'EXISTS' in sql
        assert 'OPENJSON(data, ?)' in sql
        assert params == ('$', '{"name": "John"}')

    def test_format_json_contains_with_path(self):
        """Test OPENJSON containment check with path."""
        dialect = SQLServerDialect(version=SQL_SERVER_2016)

        sql, params = dialect.format_json_contains('data', 'sqlserver', '$.tags')

        assert 'EXISTS' in sql
        assert 'OPENJSON(data, ?)' in sql
        assert params == ('$.tags', 'sqlserver')

    def test_format_json_set_single_pair(self):
        """Test JSON_MODIFY with single path-value pair."""
        dialect = SQLServerDialect(version=SQL_SERVER_2016)

        sql, params = dialect.format_json_set('data', '$.name', 'John')

        assert sql == 'JSON_MODIFY(data, ?, ?)'
        assert params == ('$.name', 'John')

    def test_format_json_set_multiple_pairs(self):
        """Test JSON_MODIFY raises for multiple path-value pairs."""
        dialect = SQLServerDialect(version=SQL_SERVER_2016)

        with pytest.raises(UnsupportedFeatureError):
            dialect.format_json_set(
                'data', '$.name', 'John',
                path_value_pairs=[('$.age', 30), ('$.city', 'NYC')]
            )

    def test_format_json_remove_single_path(self):
        """Test JSON_MODIFY property removal with a single path."""
        dialect = SQLServerDialect(version=SQL_SERVER_2016)

        sql, params = dialect.format_json_remove('data', '$.temp')

        assert sql == 'JSON_MODIFY(data, ?, NULL)'
        assert params == ('$.temp',)

    def test_format_json_remove_multiple_paths(self):
        """Test JSON_MODIFY removal raises for multiple paths."""
        dialect = SQLServerDialect(version=SQL_SERVER_2016)

        with pytest.raises(UnsupportedFeatureError):
            dialect.format_json_remove('data', '$.temp', paths=['$.cache', '$.old'])

    def test_format_json_type(self):
        """Test JSON_TYPE is not supported by SQL Server."""
        dialect = SQLServerDialect(version=SQL_SERVER_2016)

        with pytest.raises(UnsupportedFeatureError):
            dialect.format_json_type('data')

    def test_format_json_valid(self):
        """Test ISJSON formatting."""
        dialect = SQLServerDialect(version=SQL_SERVER_2016)

        sql, params = dialect.format_json_valid('data')

        assert sql == 'ISJSON(data)'
        assert params == ()

    def test_format_json_search_one(self):
        """Test JSON_SEARCH is not supported by SQL Server."""
        dialect = SQLServerDialect(version=SQL_SERVER_2016)

        with pytest.raises(UnsupportedFeatureError):
            dialect.format_json_search('data', 'John', all_=False)

    def test_format_json_search_all(self):
        """Test JSON_SEARCH with 'all' mode is not supported."""
        dialect = SQLServerDialect(version=SQL_SERVER_2016)

        with pytest.raises(UnsupportedFeatureError):
            dialect.format_json_search('data', 'John', all_=True)

    def test_format_json_search_with_path(self):
        """Test JSON_SEARCH with path is not supported."""
        dialect = SQLServerDialect(version=SQL_SERVER_2016)

        with pytest.raises(UnsupportedFeatureError):
            dialect.format_json_search('data', 'John', path='$.users', all_=True)


class TestAsyncJSONFunctionProtocol:
    """Test async JSON function protocol (same as sync, but verifies parity)."""

    @pytest.mark.asyncio
    async def test_async_supports_json_function(self):
        """Test async version of supports_json_function."""
        dialect = SQLServerDialect(version=SQL_SERVER_2016)
        assert dialect.supports_json_function('JSON_VALUE')

    @pytest.mark.asyncio
    async def test_async_format_json_extract(self):
        """Test async version of JSON_VALUE formatting."""
        dialect = SQLServerDialect(version=SQL_SERVER_2016)

        sql, params = dialect.format_json_extract('data', '$.name')

        assert 'JSON_VALUE' in sql
        assert params == ('$.name',)

    @pytest.mark.asyncio
    async def test_async_format_json_object(self):
        """Test async version of JSON_OBJECT formatting."""
        dialect = SQLServerDialect(version=SQL_SERVER_2022)

        sql, params = dialect.format_json_object([('key', 'value')])

        assert 'JSON_OBJECT' in sql
        assert params == ('key', 'value')

    @pytest.mark.asyncio
    async def test_async_format_json_array(self):
        """Test async version of JSON_ARRAY formatting."""
        dialect = SQLServerDialect(version=SQL_SERVER_2022)

        sql, params = dialect.format_json_array([1, 2, 3])

        assert 'JSON_ARRAY' in sql
        assert params == (1, 2, 3)

    @pytest.mark.asyncio
    async def test_async_format_json_contains(self):
        """Test async version of OPENJSON containment check."""
        dialect = SQLServerDialect(version=SQL_SERVER_2016)

        sql, params = dialect.format_json_contains('data', 'value', '$.path')

        assert 'OPENJSON' in sql
        assert 'value' in params

    @pytest.mark.asyncio
    async def test_async_format_json_set(self):
        """Test async version of JSON_MODIFY formatting."""
        dialect = SQLServerDialect(version=SQL_SERVER_2016)

        sql, params = dialect.format_json_set('data', '$.key', 'value')

        assert 'JSON_MODIFY' in sql
        assert '$.key' in params
