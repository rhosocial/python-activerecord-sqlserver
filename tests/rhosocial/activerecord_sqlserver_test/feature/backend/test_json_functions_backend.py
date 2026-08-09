# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_json_functions_backend.py
"""
SQL Server JSON function integration tests using real database connection.

This module tests the SQL Server JSON function functionality with actual
database operations. SQL Server stores JSON in NVARCHAR(MAX) columns and
exposes JSON_VALUE, JSON_QUERY, ISJSON, JSON_MODIFY, OPENJSON (2016+),
plus JSON_OBJECT and JSON_ARRAY (2022+).
"""
import pytest


class TestSQLServerJSONFunctionBackend:
    """Synchronous tests for SQL Server JSON functions with real database."""

    def test_supports_json_function(self, sqlserver_backend):
        """Test that JSON functions are supported."""
        dialect = sqlserver_backend.dialect
        if dialect.version >= (13, 0, 0):
            assert dialect.supports_json_function('JSON_VALUE')
        else:
            assert not dialect.supports_json_function('JSON_VALUE')

    def test_create_table_with_json_column(self, sqlserver_backend, json_column_adapter):
        """Test creating table with NVARCHAR(MAX) JSON column type."""
        if sqlserver_backend.dialect.version < (13, 0, 0):
            pytest.skip("JSON functions require SQL Server 2016+")

        sqlserver_backend.execute("""
            CREATE TABLE #test_json_table (
                id INT IDENTITY(1,1) PRIMARY KEY,
                data NVARCHAR(MAX)
            )
            """)

        sqlserver_backend.execute(
            "INSERT INTO #test_json_table (data) VALUES ('{\"name\": \"John\"}')"
        )

        result = sqlserver_backend.execute(
            "SELECT data FROM #test_json_table WHERE id = 1",
            column_adapters={'data': (json_column_adapter, dict)}
        )

        assert result.data[0]['data']['name'] == 'John'

        sqlserver_backend.execute("DROP TABLE IF EXISTS #test_json_table")

    def test_json_value_function(self, sqlserver_backend):
        """Test JSON_VALUE function."""
        if sqlserver_backend.dialect.version < (13, 0, 0):
            pytest.skip("JSON functions require SQL Server 2016+")

        sqlserver_backend.execute("""
            CREATE TABLE #test_json_extract (
                id INT IDENTITY(1,1) PRIMARY KEY,
                data NVARCHAR(MAX)
            )
            """)

        sqlserver_backend.execute(
            "INSERT INTO #test_json_extract (data) VALUES ('{\"name\": \"John\", \"age\": 30}')"
        )

        result = sqlserver_backend.execute(
            "SELECT JSON_VALUE(data, '$.name') as name FROM #test_json_extract"
        )

        assert result.data[0]['name'] == 'John'

        sqlserver_backend.execute("DROP TABLE IF EXISTS #test_json_extract")

    def test_json_object_function(self, sqlserver_backend, json_column_adapter):
        """Test JSON_OBJECT function."""
        if sqlserver_backend.dialect.version < (16, 0, 0):
            pytest.skip("JSON_OBJECT requires SQL Server 2022+")

        result = sqlserver_backend.execute(
            "SELECT JSON_OBJECT('name': 'John', 'age': 30) as obj",
            column_adapters={'obj': (json_column_adapter, dict)}
        )

        assert result.data[0]['obj']['name'] == 'John'

    def test_json_array_function(self, sqlserver_backend, json_column_adapter):
        """Test JSON_ARRAY function."""
        if sqlserver_backend.dialect.version < (16, 0, 0):
            pytest.skip("JSON_ARRAY requires SQL Server 2022+")

        result = sqlserver_backend.execute(
            "SELECT JSON_ARRAY(1, 2, 3) as arr",
            column_adapters={'arr': (json_column_adapter, list)}
        )

        assert result.data[0]['arr'] == [1, 2, 3]

    def test_json_contains_function(self, sqlserver_backend):
        """Test OPENJSON containment check."""
        if sqlserver_backend.dialect.version < (13, 0, 0):
            pytest.skip("JSON functions require SQL Server 2016+")

        sqlserver_backend.execute("""
            CREATE TABLE #test_json_contains (
                id INT IDENTITY(1,1) PRIMARY KEY,
                data NVARCHAR(MAX)
            )
            """)

        sqlserver_backend.execute(
            "INSERT INTO #test_json_contains (data) VALUES ('{\"tags\": [\"sqlserver\", \"database\"]}')"
        )

        result = sqlserver_backend.execute(
            "SELECT id FROM #test_json_contains "
            "WHERE EXISTS (SELECT 1 FROM OPENJSON(data, '$.tags') WHERE value = 'sqlserver')"
        )

        assert len(result.data) == 1

        sqlserver_backend.execute("DROP TABLE IF EXISTS #test_json_contains")

    def test_format_json_extract_integration(self, sqlserver_backend):
        """Test format_json_extract with database execution."""
        if sqlserver_backend.dialect.version < (13, 0, 0):
            pytest.skip("JSON functions require SQL Server 2016+")

        sqlserver_backend.execute("""
            CREATE TABLE #test_format_json_extract (
                id INT IDENTITY(1,1) PRIMARY KEY,
                data NVARCHAR(MAX)
            )
            """)

        sqlserver_backend.execute(
            "INSERT INTO #test_format_json_extract (data) VALUES ('{\"name\": \"John\"}')"
        )

        dialect = sqlserver_backend.dialect
        sql, params = dialect.format_json_extract('data', '$.name')

        result = sqlserver_backend.execute(
            f"SELECT {sql} as name FROM #test_format_json_extract",
            params
        )

        assert 'John' in str(result.data[0]['name'])

        sqlserver_backend.execute("DROP TABLE IF EXISTS #test_format_json_extract")


class TestAsyncSQLServerJSONFunctionBackend:
    """Asynchronous tests for SQL Server JSON functions with real database."""

    @pytest.mark.asyncio
    async def test_async_supports_json_function(self, async_sqlserver_backend):
        """Test that JSON functions are supported (async)."""
        dialect = async_sqlserver_backend.dialect
        if dialect.version >= (13, 0, 0):
            assert dialect.supports_json_function('JSON_VALUE')
        else:
            assert not dialect.supports_json_function('JSON_VALUE')

    @pytest.mark.asyncio
    async def test_async_create_table_with_json_column(self, async_sqlserver_backend, json_column_adapter):
        """Test creating table with NVARCHAR(MAX) JSON column type (async)."""
        if async_sqlserver_backend.dialect.version < (13, 0, 0):
            pytest.skip("JSON functions require SQL Server 2016+")

        await async_sqlserver_backend.execute("""
            CREATE TABLE #test_async_json_table (
                id INT IDENTITY(1,1) PRIMARY KEY,
                data NVARCHAR(MAX)
            )
            """)

        await async_sqlserver_backend.execute(
            "INSERT INTO #test_async_json_table (data) VALUES ('{\"name\": \"Jane\"}')"
        )

        result = await async_sqlserver_backend.execute(
            "SELECT data FROM #test_async_json_table WHERE id = 1",
            column_adapters={'data': (json_column_adapter, dict)}
        )

        assert result.data[0]['data']['name'] == 'Jane'

        await async_sqlserver_backend.execute("DROP TABLE IF EXISTS #test_async_json_table")

    @pytest.mark.asyncio
    async def test_async_json_value_function(self, async_sqlserver_backend):
        """Test JSON_VALUE function (async)."""
        if async_sqlserver_backend.dialect.version < (13, 0, 0):
            pytest.skip("JSON functions require SQL Server 2016+")

        await async_sqlserver_backend.execute("""
            CREATE TABLE #test_async_json_extract (
                id INT IDENTITY(1,1) PRIMARY KEY,
                data NVARCHAR(MAX)
            )
            """)

        await async_sqlserver_backend.execute(
            "INSERT INTO #test_async_json_extract (data) VALUES ('{\"name\": \"Jane\"}')"
        )

        result = await async_sqlserver_backend.execute(
            "SELECT JSON_VALUE(data, '$.name') as name FROM #test_async_json_extract"
        )

        assert result.data[0]['name'] == 'Jane'

        await async_sqlserver_backend.execute("DROP TABLE IF EXISTS #test_async_json_extract")

    @pytest.mark.asyncio
    async def test_async_json_object_function(self, async_sqlserver_backend, json_column_adapter):
        """Test JSON_OBJECT function (async)."""
        if async_sqlserver_backend.dialect.version < (16, 0, 0):
            pytest.skip("JSON_OBJECT requires SQL Server 2022+")

        result = await async_sqlserver_backend.execute(
            "SELECT JSON_OBJECT('name': 'Jane') as obj",
            column_adapters={'obj': (json_column_adapter, dict)}
        )

        assert result.data[0]['obj']['name'] == 'Jane'

    @pytest.mark.asyncio
    async def test_async_json_array_function(self, async_sqlserver_backend, json_column_adapter):
        """Test JSON_ARRAY function (async)."""
        if async_sqlserver_backend.dialect.version < (16, 0, 0):
            pytest.skip("JSON_ARRAY requires SQL Server 2022+")

        result = await async_sqlserver_backend.execute(
            "SELECT JSON_ARRAY('a', 'b', 'c') as arr",
            column_adapters={'arr': (json_column_adapter, list)}
        )

        assert result.data[0]['arr'] == ['a', 'b', 'c']

    @pytest.mark.asyncio
    async def test_async_json_contains_function(self, async_sqlserver_backend):
        """Test OPENJSON containment check (async)."""
        if async_sqlserver_backend.dialect.version < (13, 0, 0):
            pytest.skip("JSON functions require SQL Server 2016+")

        await async_sqlserver_backend.execute("""
            CREATE TABLE #test_async_json_contains (
                id INT IDENTITY(1,1) PRIMARY KEY,
                data NVARCHAR(MAX)
            )
            """)

        await async_sqlserver_backend.execute(
            "INSERT INTO #test_async_json_contains (data) VALUES ('{\"tags\": [\"async\", \"test\"]}')"
        )

        result = await async_sqlserver_backend.execute(
            "SELECT id FROM #test_async_json_contains "
            "WHERE EXISTS (SELECT 1 FROM OPENJSON(data, '$.tags') WHERE value = 'async')"
        )

        assert len(result.data) == 1

        await async_sqlserver_backend.execute("DROP TABLE IF EXISTS #test_async_json_contains")

    @pytest.mark.asyncio
    async def test_async_format_json_extract_integration(self, async_sqlserver_backend):
        """Test format_json_extract with database execution (async)."""
        if async_sqlserver_backend.dialect.version < (13, 0, 0):
            pytest.skip("JSON functions require SQL Server 2016+")

        await async_sqlserver_backend.execute("""
            CREATE TABLE #test_async_format_json_extract (
                id INT IDENTITY(1,1) PRIMARY KEY,
                data NVARCHAR(MAX)
            )
            """)

        await async_sqlserver_backend.execute(
            "INSERT INTO #test_async_format_json_extract (data) VALUES ('{\"name\": \"Jane\"}')"
        )

        dialect = async_sqlserver_backend.dialect
        sql, params = dialect.format_json_extract('data', '$.name')

        result = await async_sqlserver_backend.execute(
            f"SELECT {sql} as name FROM #test_async_format_json_extract",
            params
        )

        assert 'Jane' in str(result.data[0]['name'])

        await async_sqlserver_backend.execute("DROP TABLE IF EXISTS #test_async_format_json_extract")
