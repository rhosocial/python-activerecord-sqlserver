# tests/rhosocial/activerecord_sqlserver_test/feature/backend/transaction/test_transaction_savepoint.py
"""
SQL Server transaction savepoint tests.

This module tests advanced savepoint functionality for both sync and async backends.
"""
import pytest
import pytest_asyncio
from decimal import Decimal

from rhosocial.activerecord.backend.errors import TransactionError


class TestSyncTransactionSavepoint:
    """Synchronous transaction savepoint tests."""

    @pytest.fixture
    def test_table(self, sqlserver_backend_single):
        """Create a test table."""
        sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_savepoint_table")
        sqlserver_backend_single.execute("""
            CREATE TABLE test_savepoint_table (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(255),
                amount DECIMAL(10, 2)
            )
        """)
        yield "test_savepoint_table"
        sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_savepoint_table")

    def test_create_savepoint_without_active_transaction(self, sqlserver_backend_single, test_table):
        """Test creating a savepoint without an active transaction auto-starts one."""
        tx_manager = sqlserver_backend_single.transaction_manager

        sqlserver_backend_single.execute("SELECT 1")

        tx_manager.begin()
        savepoint_name = tx_manager.savepoint("auto_start_sp")
        assert savepoint_name == "auto_start_sp"
        assert tx_manager.is_active

        sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("AutoStartTest", Decimal("100.00"))
        )

        tx_manager.commit()

        rows = sqlserver_backend_single.fetch_all("SELECT name FROM test_savepoint_table")
        assert len(rows) == 1
        assert rows[0]["name"] == "AutoStartTest"

    def test_explicit_savepoint_operations(self, sqlserver_backend_single, test_table):
        """Test explicit savepoint creation, release, and rollback."""
        tx_manager = sqlserver_backend_single.transaction_manager

        tx_manager.begin()

        sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("BeforeSP", Decimal("100.00"))
        )

        tx_manager.savepoint("sp1")

        sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("InSP", Decimal("200.00"))
        )

        tx_manager.rollback("sp1")

        sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("AfterRollback", Decimal("300.00"))
        )

        tx_manager.commit()

        rows = sqlserver_backend_single.fetch_all("SELECT name FROM test_savepoint_table ORDER BY id")
        assert len(rows) == 2
        assert rows[0]["name"] == "BeforeSP"
        assert rows[1]["name"] == "AfterRollback"

    def test_release_savepoint(self, sqlserver_backend_single, test_table):
        """Test releasing savepoint (SQL Server: marks as released)."""
        tx_manager = sqlserver_backend_single.transaction_manager

        tx_manager.begin()

        sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("BeforeSP", Decimal("100.00"))
        )

        tx_manager.savepoint("sp1")

        sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("InSP", Decimal("200.00"))
        )

        tx_manager.release_savepoint("sp1")

        assert "sp1" not in tx_manager.savepoints()

        tx_manager.commit()

        rows = sqlserver_backend_single.fetch_all("SELECT name FROM test_savepoint_table")
        assert len(rows) == 2

    def test_nested_savepoints(self, sqlserver_backend_single, test_table):
        """Test nested savepoints."""
        tx_manager = sqlserver_backend_single.transaction_manager

        tx_manager.begin()

        sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("Level0", Decimal("100.00"))
        )

        tx_manager.savepoint("sp1")

        sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("Level1", Decimal("200.00"))
        )

        tx_manager.savepoint("sp2")

        sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("Level2", Decimal("300.00"))
        )

        tx_manager.rollback("sp1")

        sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("AfterRollback", Decimal("400.00"))
        )

        tx_manager.commit()

        rows = sqlserver_backend_single.fetch_all("SELECT name FROM test_savepoint_table ORDER BY id")
        assert len(rows) == 2
        assert rows[0]["name"] == "Level0"
        assert rows[1]["name"] == "AfterRollback"

    def test_savepoint_with_auto_generated_name(self, sqlserver_backend_single, test_table):
        """Test savepoint with auto-generated name."""
        tx_manager = sqlserver_backend_single.transaction_manager

        tx_manager.begin()

        sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("AutoTest", Decimal("100.00"))
        )

        sp_name = tx_manager.savepoint("auto_savepoint")
        assert sp_name == "auto_savepoint"

        tx_manager.commit()

        rows = sqlserver_backend_single.fetch_all("SELECT name FROM test_savepoint_table")
        assert len(rows) == 1
        assert rows[0]["name"] == "AutoTest"

    def test_get_active_savepoint(self, sqlserver_backend_single, test_table):
        """Test getting current active savepoints."""
        tx_manager = sqlserver_backend_single.transaction_manager

        tx_manager.begin()

        sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("Test", Decimal("100.00"))
        )

        tx_manager.savepoint("sp1")
        tx_manager.savepoint("sp2")

        assert "sp1" in tx_manager.savepoints()
        assert "sp2" in tx_manager.savepoints()

        tx_manager.commit()

    def test_supports_savepoint(self, sqlserver_backend_single, test_table):
        """Test that SQL Server supports savepoints."""
        dialect = sqlserver_backend_single.dialect
        assert dialect.supports_savepoint() is True

    def test_invalid_savepoint_operations(self, sqlserver_backend_single, test_table):
        """Test invalid savepoint operations."""
        tx_manager = sqlserver_backend_single.transaction_manager

        with pytest.raises(TransactionError):
            tx_manager.savepoint("nos transaction")

        with pytest.raises(TransactionError):
            tx_manager.rollback("nonexistent")

        tx_manager.begin()

        tx_manager.savepoint("valid_sp")

        with pytest.raises(TransactionError):
            tx_manager.rollback("nonexistent")


class TestAsyncTransactionSavepoint:
    """Asynchronous transaction savepoint tests."""

    @pytest_asyncio.fixture
    async def async_test_table(self, async_sqlserver_backend_single):
        """Create a test table."""
        await async_sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_savepoint_table")
        await async_sqlserver_backend_single.execute("""
            CREATE TABLE test_savepoint_table (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(255),
                amount DECIMAL(10, 2)
            )
        """)
        yield "test_savepoint_table"
        await async_sqlserver_backend_single.execute("DROP TABLE IF EXISTS test_savepoint_table")

    @pytest.mark.asyncio
    async def test_async_create_savepoint_without_active_transaction(self, async_sqlserver_backend_single, async_test_table):
        """Test async creating a savepoint without an active transaction auto-starts one."""
        tx_manager = async_sqlserver_backend_single.transaction_manager

        await async_sqlserver_backend_single.execute("SELECT 1")

        await tx_manager.begin()
        await tx_manager.savepoint("auto_start_sp")
        assert tx_manager.is_active

        await async_sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("AutoStartTest", Decimal("100.00"))
        )

        await tx_manager.commit()

        rows = await async_sqlserver_backend_single.fetch_all("SELECT name FROM test_savepoint_table")
        assert len(rows) == 1
        assert rows[0]["name"] == "AutoStartTest"

    @pytest.mark.asyncio
    async def test_async_explicit_savepoint_operations(self, async_sqlserver_backend_single, async_test_table):
        """Test async explicit savepoint creation, release, and rollback."""
        tx_manager = async_sqlserver_backend_single.transaction_manager

        await tx_manager.begin()

        await async_sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("BeforeSP", Decimal("100.00"))
        )

        await tx_manager.savepoint("sp1")

        await async_sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("InSP", Decimal("200.00"))
        )

        await tx_manager.rollback("sp1")

        await async_sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("AfterRollback", Decimal("300.00"))
        )

        await tx_manager.commit()

        rows = await async_sqlserver_backend_single.fetch_all("SELECT name FROM test_savepoint_table ORDER BY id")
        assert len(rows) == 2
        assert rows[0]["name"] == "BeforeSP"
        assert rows[1]["name"] == "AfterRollback"

    @pytest.mark.asyncio
    async def test_async_release_savepoint(self, async_sqlserver_backend_single, async_test_table):
        """Test async releasing savepoint."""
        tx_manager = async_sqlserver_backend_single.transaction_manager

        await tx_manager.begin()

        await async_sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("BeforeSP", Decimal("100.00"))
        )

        await tx_manager.savepoint("sp1")

        await async_sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("InSP", Decimal("200.00"))
        )

        await tx_manager.release_savepoint("sp1")

        await tx_manager.commit()

        rows = await async_sqlserver_backend_single.fetch_all("SELECT name FROM test_savepoint_table")
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_async_nested_savepoints(self, async_sqlserver_backend_single, async_test_table):
        """Test async nested savepoints."""
        tx_manager = async_sqlserver_backend_single.transaction_manager

        await tx_manager.begin()

        await async_sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("Level0", Decimal("100.00"))
        )

        await tx_manager.savepoint("sp1")

        await async_sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("Level1", Decimal("200.00"))
        )

        await tx_manager.savepoint("sp2")

        await async_sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("Level2", Decimal("300.00"))
        )

        await tx_manager.rollback("sp1")

        await async_sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("AfterRollback", Decimal("400.00"))
        )

        await tx_manager.commit()

        rows = await async_sqlserver_backend_single.fetch_all("SELECT name FROM test_savepoint_table ORDER BY id")
        assert len(rows) == 2
        assert rows[0]["name"] == "Level0"
        assert rows[1]["name"] == "AfterRollback"

    @pytest.mark.asyncio
    async def test_async_get_active_savepoint(self, async_sqlserver_backend_single, async_test_table):
        """Test async getting current active savepoints."""
        tx_manager = async_sqlserver_backend_single.transaction_manager

        await tx_manager.begin()

        await async_sqlserver_backend_single.execute(
            "INSERT INTO test_savepoint_table (name, amount) VALUES (?, ?)",
            ("Test", Decimal("100.00"))
        )

        await tx_manager.savepoint("sp1")
        await tx_manager.savepoint("sp2")

        assert "sp1" in tx_manager.savepoints()
        assert "sp2" in tx_manager.savepoints()

        await tx_manager.commit()

    @pytest.mark.asyncio
    async def test_async_supports_savepoint(self, async_sqlserver_backend_single, async_test_table):
        """Test that SQL Server supports savepoints."""
        dialect = async_sqlserver_backend_single.dialect
        assert dialect.supports_savepoint() is True

    @pytest.mark.asyncio
    async def test_async_invalid_savepoint_operations(self, async_sqlserver_backend_single, async_test_table):
        """Test async invalid savepoint operations."""
        tx_manager = async_sqlserver_backend_single.transaction_manager

        with pytest.raises(TransactionError):
            await tx_manager.savepoint("no_transaction")

        with pytest.raises(TransactionError):
            await tx_manager.rollback("nonexistent")

        await tx_manager.begin()

        await tx_manager.savepoint("valid_sp")

        with pytest.raises(TransactionError):
            await tx_manager.rollback("nonexistent")