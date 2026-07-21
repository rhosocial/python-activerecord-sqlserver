# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_enum_adapter_backend.py
"""
SQLServer ENUM type adapter integration tests using real database connection.

This module tests the SQLServer-specific ENUM adapter with actual database operations.
"""
import pytest
import pytest_asyncio
from enum import Enum
from rhosocial.activerecord.backend.impl.sqlserver.adapters import SQLServerEnumAdapter


class Status(str, Enum):
    """String-based enum for testing."""
    DRAFT = 'draft'
    PUBLISHED = 'published'
    ARCHIVED = 'archived'


class Priority(int, Enum):
    """Integer-based enum for testing."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class TestSQLServerEnumAdapterBackend:
    """Synchronous tests for SQLServer ENUM adapter with real database."""

    def test_adapter_registered_in_backend(self, sqlserver_backend):
        """Test that SQLServerEnumAdapter is registered in backend."""
        from enum import Enum

        adapter = sqlserver_backend.adapter_registry.get_adapter(Enum, str)

        assert adapter is not None
        assert isinstance(adapter, SQLServerEnumAdapter)

    def test_string_enum_round_trip(self, sqlserver_backend):
        """Test string enum round trip through adapter registry."""
        from enum import Enum

        adapter = sqlserver_backend.adapter_registry.get_adapter(Enum, str)

        assert isinstance(adapter, SQLServerEnumAdapter)

        db_value = adapter.to_database(Status.PUBLISHED, str)
        assert db_value == 'published'

        py_value = adapter.from_database('published', Status)
        assert py_value == Status.PUBLISHED

    def test_int_enum_round_trip(self, sqlserver_backend):
        """Test integer enum round trip through adapter registry."""
        from enum import Enum

        adapter = sqlserver_backend.adapter_registry.get_adapter(Enum, int)

        assert isinstance(adapter, SQLServerEnumAdapter)

        db_value = adapter.to_database(Priority.HIGH, int)
        assert db_value == 3

        py_value = adapter.from_database(3, Priority)
        assert py_value == Priority.HIGH

    def test_enum_with_sql_execution(self, sqlserver_backend):
        """Test enum handling in actual SQL execution."""
        sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_enum_table (
                id INT AUTO_INCREMENT PRIMARY KEY,
                status VARCHAR(20),
                priority INT
            )
        """)

        sqlserver_backend.execute(
            "INSERT INTO test_enum_table (status, priority) VALUES (%s, %s)",
            ('published', 3)
        )

        result = sqlserver_backend.execute(
            "SELECT status, priority FROM test_enum_table WHERE id = %s",
            (1,)
        )

        assert result.data[0]['status'] == 'published'
        assert result.data[0]['priority'] == 3

        sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_enum_table")

    def test_enum_null_handling_with_database(self, sqlserver_backend):
        """Test NULL enum handling with database."""
        sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_enum_null (
                id INT AUTO_INCREMENT PRIMARY KEY,
                status VARCHAR(20) NULL
            )
        """)

        sqlserver_backend.execute(
            "INSERT INTO test_enum_null (status) VALUES (NULL)"
        )

        result = sqlserver_backend.execute(
            "SELECT status FROM test_enum_null WHERE id = %s",
            (1,)
        )

        assert result.data[0]['status'] is None

        sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_enum_null")

    def test_native_sqlserver_enum_type(self, sqlserver_backend):
        """Test integration with SQLServer native ENUM column type."""
        sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_native_enum (
                id INT AUTO_INCREMENT PRIMARY KEY,
                status ENUM('draft', 'published', 'archived')
            )
        """)

        from enum import Enum
        adapter = sqlserver_backend.adapter_registry.get_adapter(Enum, str)

        db_value = adapter.to_database(Status.PUBLISHED, str)
        sqlserver_backend.execute(
            "INSERT INTO test_native_enum (status) VALUES (%s)",
            (db_value,)
        )

        result = sqlserver_backend.execute(
            "SELECT status FROM test_native_enum WHERE id = %s",
            (1,)
        )

        db_result = result.data[0]['status']
        py_status = adapter.from_database(db_result, Status)

        assert py_status == Status.PUBLISHED

        sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_native_enum")


class TestAsyncSQLServerEnumAdapterBackend:
    """Asynchronous tests for SQLServer ENUM adapter with real database."""

    @pytest.mark.asyncio
    async def test_async_adapter_registered_in_backend(self, async_sqlserver_backend):
        """Test that SQLServerEnumAdapter is registered in async backend."""
        from enum import Enum

        adapter = async_sqlserver_backend.adapter_registry.get_adapter(Enum, str)

        assert adapter is not None
        assert isinstance(adapter, SQLServerEnumAdapter)

    @pytest.mark.asyncio
    async def test_async_string_enum_round_trip(self, async_sqlserver_backend):
        """Test string enum round trip through adapter registry (async)."""
        from enum import Enum

        adapter = async_sqlserver_backend.adapter_registry.get_adapter(Enum, str)

        assert isinstance(adapter, SQLServerEnumAdapter)

        db_value = adapter.to_database(Status.DRAFT, str)
        assert db_value == 'draft'

        py_value = adapter.from_database('draft', Status)
        assert py_value == Status.DRAFT

    @pytest.mark.asyncio
    async def test_async_int_enum_round_trip(self, async_sqlserver_backend):
        """Test integer enum round trip through adapter registry (async)."""
        from enum import Enum

        adapter = async_sqlserver_backend.adapter_registry.get_adapter(Enum, int)

        assert isinstance(adapter, SQLServerEnumAdapter)

        db_value = adapter.to_database(Priority.MEDIUM, int)
        assert db_value == 2

        py_value = adapter.from_database(2, Priority)
        assert py_value == Priority.MEDIUM

    @pytest.mark.asyncio
    async def test_async_enum_with_sql_execution(self, async_sqlserver_backend):
        """Test enum handling in actual SQL execution (async)."""
        await async_sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_async_enum_table (
                id INT AUTO_INCREMENT PRIMARY KEY,
                status VARCHAR(20),
                priority INT
            )
        """)

        await async_sqlserver_backend.execute(
            "INSERT INTO test_async_enum_table (status, priority) VALUES (%s, %s)",
            ('archived', 1)
        )

        result = await async_sqlserver_backend.execute(
            "SELECT status, priority FROM test_async_enum_table WHERE id = %s",
            (1,)
        )

        assert result.data[0]['status'] == 'archived'
        assert result.data[0]['priority'] == 1

        await async_sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_enum_table")

    @pytest.mark.asyncio
    async def test_async_enum_null_handling_with_database(self, async_sqlserver_backend):
        """Test NULL enum handling with database (async)."""
        await async_sqlserver_backend.execute("""
            CREATE TEMPORARY TABLE test_async_enum_null (
                id INT AUTO_INCREMENT PRIMARY KEY,
                status VARCHAR(20) NULL
            )
        """)

        await async_sqlserver_backend.execute(
            "INSERT INTO test_async_enum_null (status) VALUES (NULL)"
        )

        result = await async_sqlserver_backend.execute(
            "SELECT status FROM test_async_enum_null WHERE id = %s",
            (1,)
        )

        assert result.data[0]['status'] is None

        await async_sqlserver_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_enum_null")
