# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_json_functions_backend.py
"""
SQLServer JSON function integration tests using real database connection.

This module tests the SQLServer-specific JSON function functionality with actual database operations.

Note: JSON type and functions require SQLServer 10.2.3+
"""
import pytest


class TestSQLServerJSONFunctionBackend:
    """Synchronous tests for SQLServer JSON functions with real database."""

    def test_supports_json_function(self, sqlserver_backend):
        """Test that JSON functions are supported."""
        dialect = sqlserver_backend.dialect
        if dialect.version >= (10, 2, 3):
            assert dialect.supports_json_function('JSON_EXTRACT')
        else:
            assert not dialect.supports_json_function('JSON_EXTRACT')

    def test_create_table_with_json_column(self, sqlserver_backend, json_column_adapter):
        """Test creating table with JSON column type."""
        if sqlserver_backend.dialect.version < (10, 2, 3):
            pytest.skip("JSON type requires SQLServer 10.2.3+")

        sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_json_table (
                id INT AUTO_INCREMENT PRIMARY KEY,
                data JSON
            )
            """)

        sqlserver_backend.execute(
            "INSERT INTO test_json_table (data) VALUES ('{\"name\": \"John\"}')"
        )

        result = sqlserver_backend.execute(
            "SELECT data FROM test_json_table WHERE id = 1",
            column_adapters={'data': (json_column_adapter, dict)}
        )

        assert result.data[0]['data']['name'] == 'John'

        sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_json_table")

    def test_json_extract_function(self, sqlserver_backend):
        """Test JSON_EXTRACT function."""
        if sqlserver_backend.dialect.version < (10, 2, 3):
            pytest.skip("JSON functions require SQLServer 10.2.3+")

        sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_json_extract (
                id INT AUTO_INCREMENT PRIMARY KEY,
                data JSON
            )
            """)

        sqlserver_backend.execute(
            "INSERT INTO test_json_extract (data) VALUES ('{\"name\": \"John\", \"age\": 30}')"
        )

        result = sqlserver_backend.execute(
            "SELECT JSON_EXTRACT(data, '$.name') as name FROM test_json_extract"
        )

        assert result.data[0]['name'] == '"John"'

        sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_json_extract")

    def test_json_object_function(self, sqlserver_backend, json_column_adapter):
        """Test JSON_OBJECT function."""
        if sqlserver_backend.dialect.version < (10, 2, 3):
            pytest.skip("JSON functions require SQLServer 10.2.3+")

        result = sqlserver_backend.execute(
            "SELECT JSON_OBJECT('name', 'John', 'age', 30) as obj",
            column_adapters={'obj': (json_column_adapter, dict)}
        )

        assert result.data[0]['obj']['name'] == 'John'

    def test_json_array_function(self, sqlserver_backend, json_column_adapter):
        """Test JSON_ARRAY function."""
        if sqlserver_backend.dialect.version < (10, 2, 3):
            pytest.skip("JSON functions require SQLServer 10.2.3+")

        result = sqlserver_backend.execute(
            "SELECT JSON_ARRAY(1, 2, 3) as arr",
            column_adapters={'arr': (json_column_adapter, list)}
        )

        assert result.data[0]['arr'] == [1, 2, 3]

    def test_json_contains_function(self, sqlserver_backend):
        """Test JSON_CONTAINS function."""
        if sqlserver_backend.dialect.version < (10, 2, 3):
            pytest.skip("JSON functions require SQLServer 10.2.3+")

        sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_json_contains (
                id INT AUTO_INCREMENT PRIMARY KEY,
                data JSON
            )
            """)

        sqlserver_backend.execute(
            "INSERT INTO test_json_contains (data) VALUES ('{\"tags\": [\"sqlserver\", \"database\"]}')"
        )

        result = sqlserver_backend.execute(
            "SELECT id FROM test_json_contains WHERE JSON_CONTAINS(data, '\"sqlserver\"', '$.tags')"
        )

        assert len(result.data) == 1

        sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_json_contains")

    def test_format_json_extract_integration(self, sqlserver_backend):
        """Test format_json_extract with database execution."""
        if sqlserver_backend.dialect.version < (10, 2, 3):
            pytest.skip("JSON functions require SQLServer 10.2.3+")

        sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_format_json_extract (
                id INT AUTO_INCREMENT PRIMARY KEY,
                data JSON
            )
            """)

        sqlserver_backend.execute(
            "INSERT INTO test_format_json_extract (data) VALUES ('{\"name\": \"John\"}')"
        )

        dialect = sqlserver_backend.dialect
        sql, params = dialect.format_json_extract('data', '$.name')

        result = sqlserver_backend.execute(
            f"SELECT {sql} as name FROM test_format_json_extract",
            params
        )

        assert '"John"' in str(result.data[0]['name'])

        sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_format_json_extract")


class TestAsyncSQLServerJSONFunctionBackend:
    """Asynchronous tests for SQLServer JSON functions with real database."""

    @pytest.mark.asyncio
    async def test_async_supports_json_function(self, async_sqlserver_backend):
        """Test that JSON functions are supported (async)."""
        dialect = async_sqlserver_backend.dialect
        if dialect.version >= (10, 2, 3):
            assert dialect.supports_json_function('JSON_EXTRACT')
        else:
            assert not dialect.supports_json_function('JSON_EXTRACT')

    @pytest.mark.asyncio
    async def test_async_create_table_with_json_column(self, async_sqlserver_backend, json_column_adapter):
        """Test creating table with JSON column type (async)."""
        if async_sqlserver_backend.dialect.version < (10, 2, 3):
            pytest.skip("JSON type requires SQLServer 10.2.3+")

        await async_sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_async_json_table (
                id INT AUTO_INCREMENT PRIMARY KEY,
                data JSON
            )
            """)

        await async_sqlserver_backend.execute(
            "INSERT INTO test_async_json_table (data) VALUES ('{\"name\": \"Jane\"}')"
        )

        result = await async_sqlserver_backend.execute(
            "SELECT data FROM test_async_json_table WHERE id = 1",
            column_adapters={'data': (json_column_adapter, dict)}
        )

        assert result.data[0]['data']['name'] == 'Jane'

        await async_sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_json_table")

    @pytest.mark.asyncio
    async def test_async_json_extract_function(self, async_sqlserver_backend):
        """Test JSON_EXTRACT function (async)."""
        if async_sqlserver_backend.dialect.version < (10, 2, 3):
            pytest.skip("JSON functions require SQLServer 10.2.3+")

        await async_sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_async_json_extract (
                id INT AUTO_INCREMENT PRIMARY KEY,
                data JSON
            )
            """)

        await async_sqlserver_backend.execute(
            "INSERT INTO test_async_json_extract (data) VALUES ('{\"name\": \"Jane\"}')"
        )

        result = await async_sqlserver_backend.execute(
            "SELECT JSON_EXTRACT(data, '$.name') as name FROM test_async_json_extract"
        )

        assert result.data[0]['name'] == '"Jane"'

        await async_sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_json_extract")

    @pytest.mark.asyncio
    async def test_async_json_object_function(self, async_sqlserver_backend, json_column_adapter):
        """Test JSON_OBJECT function (async)."""
        if async_sqlserver_backend.dialect.version < (10, 2, 3):
            pytest.skip("JSON functions require SQLServer 10.2.3+")

        result = await async_sqlserver_backend.execute(
            "SELECT JSON_OBJECT('name', 'Jane') as obj",
            column_adapters={'obj': (json_column_adapter, dict)}
        )

        assert result.data[0]['obj']['name'] == 'Jane'

    @pytest.mark.asyncio
    async def test_async_json_array_function(self, async_sqlserver_backend, json_column_adapter):
        """Test JSON_ARRAY function (async)."""
        if async_sqlserver_backend.dialect.version < (10, 2, 3):
            pytest.skip("JSON functions require SQLServer 10.2.3+")

        result = await async_sqlserver_backend.execute(
            "SELECT JSON_ARRAY('a', 'b', 'c') as arr",
            column_adapters={'arr': (json_column_adapter, list)}
        )

        assert result.data[0]['arr'] == ['a', 'b', 'c']

    @pytest.mark.asyncio
    async def test_async_json_contains_function(self, async_sqlserver_backend):
        """Test JSON_CONTAINS function (async)."""
        if async_sqlserver_backend.dialect.version < (10, 2, 3):
            pytest.skip("JSON functions require SQLServer 10.2.3+")

        await async_sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_async_json_contains (
                id INT AUTO_INCREMENT PRIMARY KEY,
                data JSON
            )
            """)

        await async_sqlserver_backend.execute(
            "INSERT INTO test_async_json_contains (data) VALUES ('{\"tags\": [\"async\", \"test\"]}')"
        )

        result = await async_sqlserver_backend.execute(
            "SELECT id FROM test_async_json_contains WHERE JSON_CONTAINS(data, '\"async\"', '$.tags')"
        )

        assert len(result.data) == 1

        await async_sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_json_contains")

    @pytest.mark.asyncio
    async def test_async_format_json_extract_integration(self, async_sqlserver_backend):
        """Test format_json_extract with database execution (async)."""
        if async_sqlserver_backend.dialect.version < (10, 2, 3):
            pytest.skip("JSON functions require SQLServer 10.2.3+")

        await async_sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_async_format_json_extract (
                id INT AUTO_INCREMENT PRIMARY KEY,
                data JSON
            )
            """)

        await async_sqlserver_backend.execute(
            "INSERT INTO test_async_format_json_extract (data) VALUES ('{\"name\": \"Jane\"}')"
        )

        dialect = async_sqlserver_backend.dialect
        sql, params = dialect.format_json_extract('data', '$.name')

        result = await async_sqlserver_backend.execute(
            f"SELECT {sql} as name FROM test_async_format_json_extract",
            params
        )

        assert '"Jane"' in str(result.data[0]['name'])

        await async_sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_format_json_extract")
