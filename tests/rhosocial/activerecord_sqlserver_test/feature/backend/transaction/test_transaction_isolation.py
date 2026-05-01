# tests/rhosocial/activerecord_sqlserver_test/feature/backend/transaction/test_transaction_isolation.py
"""
SQL Server transaction isolation level tests.

This module tests transaction isolation levels for both sync and async backends.
"""
import pytest
import pytest_asyncio
from decimal import Decimal

from rhosocial.activerecord.backend.errors import IsolationLevelError
from rhosocial.activerecord.backend.transaction import IsolationLevel


class TestSyncTransactionIsolation:
    """Synchronous transaction isolation level tests."""

    @pytest.fixture
    def test_table(self, sqlserver_backend_single):
        """Create a test table."""
        sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_isolation_table")
        sqlserver_backend_single.execute("""
            CREATE TABLE test_isolation_table (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(255),
                amount DECIMAL(10, 2)
            )
        """)
        yield "test_isolation_table"
        sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_isolation_table")

    def test_set_isolation_level_before_transaction(self, sqlserver_backend_single, test_table):
        """Test setting isolation level before starting a transaction."""
        tx_manager = sqlserver_backend_single.transaction_manager
        tx_manager.isolation_level = IsolationLevel.READ_COMMITTED

        with sqlserver_backend_single.transaction():
            sqlserver_backend_single.execute(
                "INSERT INTO test_isolation_table (name, amount) VALUES (?, ?)",
                ("IsolationTest", Decimal("100.00"))
            )

        rows = sqlserver_backend_single.fetch_all("SELECT name FROM test_isolation_table")
        assert len(rows) == 1
        assert rows[0]["name"] == "IsolationTest"

    def test_set_repeatable_read_isolation_level(self, sqlserver_backend_single, test_table):
        """Test REPEATABLE READ isolation level."""
        tx_manager = sqlserver_backend_single.transaction_manager
        tx_manager.isolation_level = IsolationLevel.REPEATABLE_READ

        with sqlserver_backend_single.transaction():
            sqlserver_backend_single.execute(
                "INSERT INTO test_isolation_table (name, amount) VALUES (?, ?)",
                ("RepeatableTest", Decimal("200.00"))
            )

        rows = sqlserver_backend_single.fetch_all("SELECT name FROM test_isolation_table")
        assert len(rows) == 1

    def test_set_serializable_isolation_level(self, sqlserver_backend_single, test_table):
        """Test SERIALIZABLE isolation level."""
        tx_manager = sqlserver_backend_single.transaction_manager
        tx_manager.isolation_level = IsolationLevel.SERIALIZABLE

        with sqlserver_backend_single.transaction():
            sqlserver_backend_single.execute(
                "INSERT INTO test_isolation_table (name, amount) VALUES (?, ?)",
                ("SerializableTest", Decimal("300.00"))
            )

        rows = sqlserver_backend_single.fetch_all("SELECT name FROM test_isolation_table")
        assert len(rows) == 1

    def test_set_read_uncommitted_isolation_level(self, sqlserver_backend_single, test_table):
        """Test READ UNCOMMITTED isolation level."""
        tx_manager = sqlserver_backend_single.transaction_manager
        tx_manager.isolation_level = IsolationLevel.READ_UNCOMMITTED

        with sqlserver_backend_single.transaction():
            sqlserver_backend_single.execute(
                "INSERT INTO test_isolation_table (name, amount) VALUES (?, ?)",
                ("ReadUncommittedTest", Decimal("400.00"))
            )

        rows = sqlserver_backend_single.fetch_all("SELECT name FROM test_isolation_table")
        assert len(rows) == 1

    def test_isolation_level_in_begin(self, sqlserver_backend_single, test_table):
        """Test setting isolation level in begin transaction."""
        tx_manager = sqlserver_backend_single.transaction_manager

        tx_manager.begin(isolation_level=IsolationLevel.READ_COMMITTED)

        sqlserver_backend_single.execute(
            "INSERT INTO test_isolation_table (name, amount) VALUES (?, ?)",
            ("BeginIsolation", Decimal("500.00"))
        )

        tx_manager.commit()

        rows = sqlserver_backend_single.fetch_all("SELECT name FROM test_isolation_table")
        assert len(rows) == 1

    def test_supports_isolation_level(self, sqlserver_backend_single, test_table):
        """Test that SQL Server supports isolation levels."""
        dialect = sqlserver_backend_single.dialect
        assert dialect.supports_isolation_level() is True


class TestAsyncTransactionIsolation:
    """Asynchronous transaction isolation level tests."""

    @pytest_asyncio.fixture
    async def async_test_table(self, async_sqlserver_backend_single):
        """Create a test table."""
        await async_sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_isolation_table")
        await async_sqlserver_backend_single.execute("""
            CREATE TABLE test_isolation_table (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(255),
                amount DECIMAL(10, 2)
            )
        """)
        yield "test_isolation_table"
        await async_sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_isolation_table")

    @pytest.mark.asyncio
    async def test_async_set_isolation_level_before_transaction(self, async_sqlserver_backend_single, async_test_table):
        """Test async setting isolation level before starting a transaction."""
        tx_manager = async_sqlserver_backend_single.transaction_manager
        tx_manager.isolation_level = IsolationLevel.READ_COMMITTED

        async with async_sqlserver_backend_single.transaction():
            await async_sqlserver_backend_single.execute(
                "INSERT INTO test_isolation_table (name, amount) VALUES (?, ?)",
                ("IsolationTest", Decimal("100.00"))
            )

        rows = await async_sqlserver_backend_single.fetch_all("SELECT name FROM test_isolation_table")
        assert len(rows) == 1
        assert rows[0]["name"] == "IsolationTest"

    @pytest.mark.asyncio
    async def test_async_set_serializable_isolation_level(self, async_sqlserver_backend_single, async_test_table):
        """Test async SERIALIZABLE isolation level."""
        tx_manager = async_sqlserver_backend_single.transaction_manager
        tx_manager.isolation_level = IsolationLevel.SERIALIZABLE

        async with async_sqlserver_backend_single.transaction():
            await async_sqlserver_backend_single.execute(
                "INSERT INTO test_isolation_table (name, amount) VALUES (?, ?)",
                ("SerializableTest", Decimal("300.00"))
            )

        rows = await async_sqlserver_backend_single.fetch_all("SELECT name FROM test_isolation_table")
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_async_isolation_level_in_begin(self, async_sqlserver_backend_single, async_test_table):
        """Test async setting isolation level in begin transaction."""
        tx_manager = async_sqlserver_backend_single.transaction_manager

        await tx_manager.begin(isolation_level=IsolationLevel.READ_COMMITTED)

        await async_sqlserver_backend_single.execute(
            "INSERT INTO test_isolation_table (name, amount) VALUES (?, ?)",
            ("BeginIsolation", Decimal("500.00"))
        )

        await tx_manager.commit()

        rows = await async_sqlserver_backend_single.fetch_all("SELECT name FROM test_isolation_table")
        assert len(rows) == 1