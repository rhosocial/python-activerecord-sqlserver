# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_set_type_backend.py
"""
SQLServer SET type integration tests using real database connection.

This module tests the SQLServer-specific SET type functionality with actual database operations.
"""
import pytest
import pytest_asyncio


class TestSQLServerSetTypeBackend:
    """Synchronous tests for SQLServer SET type with real database."""

    def test_supports_set_type(self, sqlserver_backend):
        """Test that SET type is supported."""
        dialect = sqlserver_backend.dialect
        assert dialect.supports_set_type()

    def test_create_table_with_set_column(self, sqlserver_backend):
        """Test creating table with SET column type."""
        sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_set_table (
                id INT IDENTITY(1,1) PRIMARY KEY,
                tags SET('red', 'green', 'blue', 'yellow'),
                status SET('active', 'pending', 'archived')
            )
        """)

        sqlserver_backend.execute(
            "INSERT INTO test_set_table (tags, status) VALUES ('red', 'active')"
        )

        result = sqlserver_backend.execute(
            "SELECT tags, status FROM test_set_table WHERE id = 1"
        )

        assert len(result.data) == 1
        assert result.data[0]['tags'] == 'red'
        assert result.data[0]['status'] == 'active'

        sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_set_table")

    def test_insert_and_query_set_value(self, sqlserver_backend):
        """Test inserting and querying SET values."""
        sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_set_insert (
                id INT IDENTITY(1,1) PRIMARY KEY,
                colors SET('red', 'green', 'blue')
            )
        """)

        sqlserver_backend.execute(
            "INSERT INTO test_set_insert (colors) VALUES ('red')"
        )

        sqlserver_backend.execute(
            "INSERT INTO test_set_insert (colors) VALUES ('red,green')"
        )

        sqlserver_backend.execute(
            "INSERT INTO test_set_insert (colors) VALUES ('blue,red,green')"
        )

        result = sqlserver_backend.execute(
            "SELECT colors FROM test_set_insert ORDER BY id"
        )

        assert result.data[0]['colors'] == 'red'
        assert result.data[1]['colors'] == 'red,green'
        assert result.data[2]['colors'] == 'red,green,blue'

        sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_set_insert")

    def test_find_in_set_function(self, sqlserver_backend):
        """Test FIND_IN_SET function for SET columns."""
        sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_find_in_set (
                id INT IDENTITY(1,1) PRIMARY KEY,
                tags SET('sqlserver', 'python', 'database', 'backend')
            )
        """)

        sqlserver_backend.execute(
            "INSERT INTO test_find_in_set (tags) VALUES ('sqlserver,python')"
        )
        sqlserver_backend.execute(
            "INSERT INTO test_find_in_set (tags) VALUES ('database')"
        )
        sqlserver_backend.execute(
            "INSERT INTO test_find_in_set (tags) VALUES ('backend,sqlserver')"
        )

        result = sqlserver_backend.execute(
            "SELECT id, tags FROM test_find_in_set WHERE FIND_IN_SET('sqlserver', tags) > 0"
        )

        assert len(result.data) == 2
        assert result.data[0]['id'] == 1
        assert result.data[1]['id'] == 3

        sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_find_in_set")

    def test_format_set_literal_integration(self, sqlserver_backend):
        """Test format_set_literal with database execution."""
        sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_set_literal (
                id INT IDENTITY(1,1) PRIMARY KEY,
                colors SET('red', 'green', 'blue')
            )
        """)

        dialect = sqlserver_backend.dialect
        sql_literal, params = dialect.format_set_literal(['red', 'blue'], ['red', 'green', 'blue'])

        sqlserver_backend.execute(
            f"INSERT INTO test_set_literal (colors) VALUES ({sql_literal})",
            params
        )

        result = sqlserver_backend.execute(
            "SELECT colors FROM test_set_literal WHERE id = 1"
        )

        assert result.data[0]['colors'] == 'red,blue'

        sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_set_literal")

    def test_format_find_in_set_integration(self, sqlserver_backend):
        """Test format_find_in_set with database execution."""
        sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_find_format (
                id INT IDENTITY(1,1) PRIMARY KEY,
                tags SET('a', 'b', 'c', 'd')
            )
        """)

        sqlserver_backend.execute("INSERT INTO test_find_format (tags) VALUES ('a,b')")
        sqlserver_backend.execute("INSERT INTO test_find_format (tags) VALUES ('c,d')")
        sqlserver_backend.execute("INSERT INTO test_find_format (tags) VALUES ('a,c')")

        dialect = sqlserver_backend.dialect
        condition, params = dialect.format_find_in_set('a', 'tags')

        result = sqlserver_backend.execute(
            f"SELECT id, tags FROM test_find_format WHERE {condition}",
            params
        )

        assert len(result.data) == 2
        ids = [row['id'] for row in result.data]
        assert 1 in ids
        assert 3 in ids

        sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_find_format")

    def test_format_set_contains_integration(self, sqlserver_backend):
        """Test format_set_contains with database execution."""
        sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_contains_format (
                id INT IDENTITY(1,1) PRIMARY KEY,
                permissions SET('read', 'write', 'execute', 'admin')
            )
        """)

        sqlserver_backend.execute("INSERT INTO test_contains_format (permissions) VALUES ('read,write')")
        sqlserver_backend.execute("INSERT INTO test_contains_format (permissions) VALUES ('read,execute')")
        sqlserver_backend.execute("INSERT INTO test_contains_format (permissions) VALUES ('read,write,admin')")

        dialect = sqlserver_backend.dialect
        condition, params = dialect.format_set_contains('permissions', ['read', 'write'])

        result = sqlserver_backend.execute(
            f"SELECT id, permissions FROM test_contains_format WHERE {condition}",
            params
        )

        assert len(result.data) == 2
        permissions_values = [row['permissions'] for row in result.data]
        assert 'read,write' in permissions_values
        assert 'read,write,admin' in permissions_values

        sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_contains_format")

    def test_set_with_null_value(self, sqlserver_backend):
        """Test SET column with NULL values."""
        sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_set_null (
                id INT IDENTITY(1,1) PRIMARY KEY,
                tags SET('a', 'b', 'c') NULL
            )
        """)

        sqlserver_backend.execute("INSERT INTO test_set_null (tags) VALUES (NULL)")
        sqlserver_backend.execute("INSERT INTO test_set_null (tags) VALUES ('a,b')")

        result = sqlserver_backend.execute(
            "SELECT tags FROM test_set_null ORDER BY id"
        )

        assert result.data[0]['tags'] is None
        assert result.data[1]['tags'] == 'a,b'

        sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_set_null")

    def test_set_count_function(self, sqlserver_backend):
        """Test counting SET values."""
        sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_set_count (
                id INT IDENTITY(1,1) PRIMARY KEY,
                tags SET('a', 'b', 'c', 'd')
            )
        """)

        sqlserver_backend.execute("INSERT INTO test_set_count (tags) VALUES ('a')")
        sqlserver_backend.execute("INSERT INTO test_set_count (tags) VALUES ('a,b')")
        sqlserver_backend.execute("INSERT INTO test_set_count (tags) VALUES ('a,b,c,d')")

        result = sqlserver_backend.execute(
            "SELECT COUNT(*) as cnt FROM test_set_count WHERE FIND_IN_SET('a', tags) > 0"
        )

        assert result.data[0]['cnt'] == 3

        sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_set_count")


class TestAsyncSQLServerSetTypeBackend:
    """Asynchronous tests for SQLServer SET type with real database."""

    @pytest.mark.asyncio
    async def test_async_supports_set_type(self, async_sqlserver_backend):
        """Test that SET type is supported (async)."""
        dialect = async_sqlserver_backend.dialect
        assert dialect.supports_set_type()

    @pytest.mark.asyncio
    async def test_async_create_table_with_set_column(self, async_sqlserver_backend):
        """Test creating table with SET column type (async)."""
        await async_sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_async_set_table (
                id INT IDENTITY(1,1) PRIMARY KEY,
                categories SET('news', 'sports', 'tech', 'entertainment')
            )
        """)

        await async_sqlserver_backend.execute(
            "INSERT INTO test_async_set_table (categories) VALUES ('news,sports')"
        )

        result = await async_sqlserver_backend.execute(
            "SELECT categories FROM test_async_set_table WHERE id = 1"
        )

        assert len(result.data) == 1
        assert result.data[0]['categories'] == 'news,sports'

        await async_sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_set_table")

    @pytest.mark.asyncio
    async def test_async_insert_and_query_set_value(self, async_sqlserver_backend):
        """Test inserting and querying SET values (async)."""
        await async_sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_async_set_insert (
                id INT IDENTITY(1,1) PRIMARY KEY,
                colors SET('red', 'green', 'blue')
            )
        """)

        await async_sqlserver_backend.execute(
            "INSERT INTO test_async_set_insert (colors) VALUES ('red')"
        )

        await async_sqlserver_backend.execute(
            "INSERT INTO test_async_set_insert (colors) VALUES ('green,blue')"
        )

        result = await async_sqlserver_backend.execute(
            "SELECT colors FROM test_async_set_insert ORDER BY id"
        )

        assert result.data[0]['colors'] == 'red'
        assert result.data[1]['colors'] == 'green,blue'

        await async_sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_set_insert")

    @pytest.mark.asyncio
    async def test_async_find_in_set_function(self, async_sqlserver_backend):
        """Test FIND_IN_SET function for SET columns (async)."""
        await async_sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_async_find (
                id INT IDENTITY(1,1) PRIMARY KEY,
                tags SET('sqlserver', 'python', 'database')
            )
        """)

        await async_sqlserver_backend.execute(
            "INSERT INTO test_async_find (tags) VALUES ('sqlserver,python')"
        )
        await async_sqlserver_backend.execute(
            "INSERT INTO test_async_find (tags) VALUES ('database')"
        )

        result = await async_sqlserver_backend.execute(
            "SELECT id, tags FROM test_async_find WHERE FIND_IN_SET('sqlserver', tags) > 0"
        )

        assert len(result.data) == 1
        assert result.data[0]['id'] == 1

        await async_sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_find")

    @pytest.mark.asyncio
    async def test_async_format_set_literal_integration(self, async_sqlserver_backend):
        """Test format_set_literal with database execution (async)."""
        await async_sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_async_set_literal (
                id INT IDENTITY(1,1) PRIMARY KEY,
                colors SET('red', 'green', 'blue')
            )
        """)

        dialect = async_sqlserver_backend.dialect
        sql_literal, params = dialect.format_set_literal(['green', 'red'], ['red', 'green', 'blue'])

        await async_sqlserver_backend.execute(
            f"INSERT INTO test_async_set_literal (colors) VALUES ({sql_literal})",
            params
        )

        result = await async_sqlserver_backend.execute(
            "SELECT colors FROM test_async_set_literal WHERE id = 1"
        )

        assert result.data[0]['colors'] == 'red,green'

        await async_sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_set_literal")

    @pytest.mark.asyncio
    async def test_async_format_find_in_set_integration(self, async_sqlserver_backend):
        """Test format_find_in_set with database execution (async)."""
        await async_sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_async_find_format (
                id INT IDENTITY(1,1) PRIMARY KEY,
                tags SET('x', 'y', 'z')
            )
        """)

        await async_sqlserver_backend.execute("INSERT INTO test_async_find_format (tags) VALUES ('x,y')")
        await async_sqlserver_backend.execute("INSERT INTO test_async_find_format (tags) VALUES ('z')")

        dialect = async_sqlserver_backend.dialect
        condition, params = dialect.format_find_in_set('x', 'tags')

        result = await async_sqlserver_backend.execute(
            f"SELECT id, tags FROM test_async_find_format WHERE {condition}",
            params
        )

        assert len(result.data) == 1
        assert result.data[0]['id'] == 1

        await async_sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_find_format")

    @pytest.mark.asyncio
    async def test_async_format_set_contains_integration(self, async_sqlserver_backend):
        """Test format_set_contains with database execution (async)."""
        await async_sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_async_contains (
                id INT IDENTITY(1,1) PRIMARY KEY,
                roles SET('admin', 'user', 'guest', 'moderator')
            )
        """)

        await async_sqlserver_backend.execute("INSERT INTO test_async_contains (roles) VALUES ('admin,user')")
        await async_sqlserver_backend.execute("INSERT INTO test_async_contains (roles) VALUES ('guest')")
        await async_sqlserver_backend.execute("INSERT INTO test_async_contains (roles) VALUES ('admin,moderator')")

        dialect = async_sqlserver_backend.dialect
        condition, params = dialect.format_set_contains('roles', ['admin'])

        result = await async_sqlserver_backend.execute(
            f"SELECT id, roles FROM test_async_contains WHERE {condition}",
            params
        )

        assert len(result.data) == 2
        ids = [row['id'] for row in result.data]
        assert 1 in ids
        assert 3 in ids

        await async_sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_contains")

    @pytest.mark.asyncio
    async def test_async_set_with_null_value(self, async_sqlserver_backend):
        """Test SET column with NULL values (async)."""
        await async_sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_async_set_null (
                id INT IDENTITY(1,1) PRIMARY KEY,
                status SET('active', 'inactive') NULL
            )
        """)

        await async_sqlserver_backend.execute("INSERT INTO test_async_set_null (status) VALUES (NULL)")
        await async_sqlserver_backend.execute("INSERT INTO test_async_set_null (status) VALUES ('active')")

        result = await async_sqlserver_backend.execute(
            "SELECT status FROM test_async_set_null ORDER BY id"
        )

        assert result.data[0]['status'] is None
        assert result.data[1]['status'] == 'active'

        await async_sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_set_null")
