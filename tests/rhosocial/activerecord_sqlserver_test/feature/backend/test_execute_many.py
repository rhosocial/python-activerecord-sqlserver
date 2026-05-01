# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_execute_many.py
"""
SQL Server execute_many tests for batch operations.

This module tests execute_many functionality for both sync and async backends.
"""
import pytest
import pytest_asyncio
from decimal import Decimal


class TestSyncExecuteMany:
    """Synchronous execute_many tests for SQL Server backend."""

    @pytest.fixture
    def test_table(self, sqlserver_backend_single):
        """Create a test table."""
        sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_batch_table")
        sqlserver_backend_single.execute("""
            CREATE TABLE test_batch_table (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(255),
                age INT,
                balance DECIMAL(10, 2)
            )
        """)
        yield "test_batch_table"
        sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_batch_table")

    def test_execute_many_insert(self, sqlserver_backend_single, test_table):
        """Test batch insert with execute_many."""
        params_list = [
            ("Alice", 25, Decimal("100.00")),
            ("Bob", 30, Decimal("200.00")),
            ("Charlie", 35, Decimal("300.00")),
        ]

        sqlserver_backend_single.execute_many(
            "INSERT INTO test_batch_table (name, age, balance) VALUES (?, ?, ?)",
            params_list
        )

        rows = sqlserver_backend_single.fetch_all(
            "SELECT name, age, balance FROM test_batch_table ORDER BY name"
        )
        assert len(rows) == 3
        assert rows[0]["name"] == "Alice"
        assert rows[1]["name"] == "Bob"
        assert rows[2]["name"] == "Charlie"

    def test_execute_many_update(self, sqlserver_backend_single, test_table):
        """Test batch update with execute_many."""
        sqlserver_backend_single.execute_many(
            "INSERT INTO test_batch_table (name, age, balance) VALUES (?, ?, ?)",
            [
                ("Alice", 25, Decimal("100.00")),
                ("Bob", 30, Decimal("200.00")),
            ]
        )

        params_list = [
            (26, Decimal("150.00"), "Alice"),
            (31, Decimal("250.00"), "Bob"),
        ]

        sqlserver_backend_single.execute_many(
            "UPDATE test_batch_table SET age = ?, balance = ? WHERE name = ?",
            params_list
        )

    def test_execute_many_delete(self, sqlserver_backend_single, test_table):
        """Test batch delete with execute_many."""
        sqlserver_backend_single.execute_many(
            "INSERT INTO test_batch_table (name, age, balance) VALUES (?, ?, ?)",
            [
                ("Alice", 25, Decimal("100.00")),
                ("Bob", 30, Decimal("200.00")),
                ("Charlie", 35, Decimal("300.00")),
            ]
        )

        params_list = [("Alice",), ("Bob",)]

        sqlserver_backend_single.execute_many(
            "DELETE FROM test_batch_table WHERE name = ?",
            params_list
        )

        rows = sqlserver_backend_single.fetch_all("SELECT name FROM test_batch_table")
        assert len(rows) == 1
        assert rows[0]["name"] == "Charlie"

    def test_execute_many_empty_list(self, sqlserver_backend_single, test_table):
        """Test execute_many with empty parameter list."""
        sqlserver_backend_single.execute_many(
            "INSERT INTO test_batch_table (name, age, balance) VALUES (?, ?, ?)",
            []
        )

    def test_execute_many_single_row(self, sqlserver_backend_single, test_table):
        """Test execute_many with single row of parameters."""
        params_list = [("Single", 25, Decimal("100.00"))]

        sqlserver_backend_single.execute_many(
            "INSERT INTO test_batch_table (name, age, balance) VALUES (?, ?, ?)",
            params_list
        )

        rows = sqlserver_backend_single.fetch_all("SELECT name FROM test_batch_table")
        assert len(rows) == 1
        assert rows[0]["name"] == "Single"


class TestAsyncExecuteMany:
    """Asynchronous execute_many tests for SQL Server backend."""

    @pytest_asyncio.fixture
    async def async_test_table(self, async_sqlserver_backend_single):
        """Create a test table."""
        await async_sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_batch_table")
        await async_sqlserver_backend_single.execute("""
            CREATE TABLE test_batch_table (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(255),
                age INT,
                balance DECIMAL(10, 2)
            )
        """)
        yield "test_batch_table"
        await async_sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_batch_table")

    @pytest.mark.asyncio
    async def test_async_execute_many_insert(self, async_sqlserver_backend_single, async_test_table):
        """Test async batch insert with execute_many."""
        params_list = [
            ("Alice", 25, Decimal("100.00")),
            ("Bob", 30, Decimal("200.00")),
            ("Charlie", 35, Decimal("300.00")),
        ]

        result = await async_sqlserver_backend_single.execute_many(
            "INSERT INTO test_batch_table (name, age, balance) VALUES (?, ?, ?)",
            params_list
        )

        assert result.affected_rows == 3
        assert result.data is None

        rows = await async_sqlserver_backend_single.fetch_all(
            "SELECT name, age, balance FROM test_batch_table ORDER BY name"
        )
        assert len(rows) == 3
        assert rows[0]["name"] == "Alice"
        assert rows[1]["name"] == "Bob"
        assert rows[2]["name"] == "Charlie"

    @pytest.mark.asyncio
    async def test_async_execute_many_empty_list(self, async_sqlserver_backend_single, async_test_table):
        """Test async execute_many with empty parameter list."""
        result = await async_sqlserver_backend_single.execute_many(
            "INSERT INTO test_batch_table (name, age, balance) VALUES (?, ?, ?)",
            []
        )

        assert result.affected_rows == 0