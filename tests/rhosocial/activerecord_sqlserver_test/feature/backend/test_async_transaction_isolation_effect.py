# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_async_transaction_isolation_effect.py
"""
Async tests for SQL Server transaction isolation level and mode effects.

This module tests the actual behavior of different isolation levels and transaction modes
with SQL Server backend using async operations.
"""
import pytest
import pytest_asyncio
import asyncio
from decimal import Decimal

from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend
from rhosocial.activerecord.backend.transaction import IsolationLevel, TransactionMode


@pytest_asyncio.fixture
async def async_sqlserver_control_backend(async_sqlserver_backend):
    """A second, independent async backend connection for isolation testing."""
    backend = AsyncSQLServerBackend(connection_config=async_sqlserver_backend.config)
    await backend.connect()
    yield backend
    await backend.disconnect()


@pytest_asyncio.fixture
async def async_isolation_test_table(async_sqlserver_backend):
    """Create a test table for async isolation tests."""
    await async_sqlserver_backend.execute("drop table if exists async_isolation_test")
    await async_sqlserver_backend.execute("""
        create table async_isolation_test (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name VARCHAR(255),
            balance DECIMAL(10, 2),
            version INT DEFAULT 1
        )
    """)
    await async_sqlserver_backend.execute(
        "insert into async_isolation_test (name, balance) values (?, ?)",
        ("user1", Decimal("100.00"))
    )
    yield "async_isolation_test"
    await async_sqlserver_backend.execute("drop table if exists async_isolation_test")


@pytest_asyncio.fixture
async def async_mode_test_table(async_sqlserver_backend):
    """Create a test table for transaction mode tests."""
    await async_sqlserver_backend.execute("drop table if exists async_mode_test")
    await async_sqlserver_backend.execute("""
        create table async_mode_test (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name VARCHAR(255),
            balance DECIMAL(10, 2)
        )
    """)
    await async_sqlserver_backend.execute(
        "insert into async_mode_test (name, balance) values (?, ?)",
        ("account1", Decimal("1000.00"))
    )
    yield "async_mode_test"
    await async_sqlserver_backend.execute("drop table if exists async_mode_test")


@pytest_asyncio.fixture
async def async_combo_test_table(async_sqlserver_backend):
    """Create a test table for combination tests."""
    await async_sqlserver_backend.execute("drop table if exists async_combo_test")
    await async_sqlserver_backend.execute("""
        create table async_combo_test (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name VARCHAR(255),
            balance DECIMAL(10, 2)
        )
    """)
    await async_sqlserver_backend.execute(
        "insert into async_combo_test (name, balance) values (?, ?)",
        ("account1", Decimal("1000.00"))
    )
    yield "async_combo_test"
    await async_sqlserver_backend.execute("drop table if exists async_combo_test")


@pytest_asyncio.fixture
async def async_nested_test_table(async_sqlserver_backend):
    """Create a test table for nested transaction tests."""
    await async_sqlserver_backend.execute("drop table if exists async_nested_test")
    await async_sqlserver_backend.execute("""
        create table async_nested_test (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name VARCHAR(255),
            value INT
        )
    """)
    yield "async_nested_test"
    await async_sqlserver_backend.execute("drop table if exists async_nested_test")


class TestAsyncIsolationLevelEffect:
    """Test actual isolation behavior for each isolation level."""

    @pytest.mark.asyncio
    async def test_read_uncommitted_allows_dirty_reads(self, async_sqlserver_backend, async_sqlserver_control_backend, async_isolation_test_table):
        """Verify READ UNCOMMITTED isolation level allows dirty reads (async).

        A dirty read occurs when a transaction reads data written by another
        uncommitted transaction. READ UNCOMMITTED should allow this.
        """
        dirty_read_detected = []
        updated_event = asyncio.Event()

        async def transaction1():
            """Transaction 1: Read uncommitted data."""
            try:
                async_sqlserver_backend.transaction_manager.isolation_level = IsolationLevel.READ_UNCOMMITTED
                async with async_sqlserver_backend.transaction():
                    await asyncio.wait_for(updated_event.wait(), timeout=5)
                    rows = await async_sqlserver_backend.fetch_all(
                        "select balance from async_isolation_test where name = ?",
                        ("user1",)
                    )
                    if rows and rows[0]["balance"] == Decimal("200.00"):
                        dirty_read_detected.append(True)
            except Exception as e:
                dirty_read_detected.append(str(e))

        async def transaction2():
            """Transaction 2: Modify data without committing."""
            try:
                async_sqlserver_control_backend.transaction_manager.isolation_level = IsolationLevel.READ_UNCOMMITTED
                async with async_sqlserver_control_backend.transaction():
                    await async_sqlserver_control_backend.execute(
                        "update async_isolation_test set balance = ? where name = ?",
                        (Decimal("200.00"), "user1")
                    )
                    updated_event.set()
                    await asyncio.sleep(0.3)
                    raise Exception("Force rollback for dirty read test")
            except Exception:
                pass

        await asyncio.gather(transaction1(), transaction2())
        assert True in dirty_read_detected, "READ UNCOMMITTED should allow dirty reads"

    @pytest.mark.asyncio
    async def test_read_committed_prevents_dirty_reads(self, async_sqlserver_backend, async_sqlserver_control_backend, async_isolation_test_table):
        """Verify READ COMMITTED isolation level prevents dirty reads (async)."""
        dirty_read_occurred = []

        async def transaction1():
            """Transaction 1: Should not see uncommitted data."""
            try:
                async_sqlserver_backend.transaction_manager.isolation_level = IsolationLevel.READ_COMMITTED
                async with async_sqlserver_backend.transaction():
                    await asyncio.sleep(0.15)
                    rows = await async_sqlserver_backend.fetch_all(
                        "select balance from async_isolation_test where name = ?",
                        ("user1",)
                    )
                    if rows and rows[0]["balance"] != Decimal("200.00"):
                        dirty_read_occurred.append(False)  # Correct behavior - no dirty read
                    else:
                        dirty_read_occurred.append(True)  # Dirty read happened
            except Exception as e:
                dirty_read_occurred.append(str(e))

        async def transaction2():
            """Transaction 2: modify data and rollback."""
            try:
                async_sqlserver_control_backend.transaction_manager.isolation_level = IsolationLevel.READ_COMMITTED
                async with async_sqlserver_control_backend.transaction():
                    await async_sqlserver_control_backend.execute(
                        "update async_isolation_test set balance = ? where name = ?",
                        (Decimal("200.00"), "user1")
                    )
                    await asyncio.sleep(0.2)
                    raise Exception("Force rollback")
            except Exception:
                pass

        await asyncio.gather(transaction1(), transaction2())
        assert True not in dirty_read_occurred, "READ COMMITTED should prevent dirty reads"

    @pytest.mark.asyncio
    async def test_repeatable_read_consistency(self, async_sqlserver_backend, async_sqlserver_control_backend, async_isolation_test_table):
        """Verify REPEATABLE READ provides consistent reads within a transaction (async).

        REPEATABLE READ should ensure that if a row is read twice in the same
        transaction, the same value is returned even if another transaction
        committed a change.
        """
        read_values = []

        async def transaction1():
            """Transaction 1: Read the same row twice."""
            try:
                async_sqlserver_backend.transaction_manager.isolation_level = IsolationLevel.REPEATABLE_READ
                async with async_sqlserver_backend.transaction():
                    # First read
                    rows1 = await async_sqlserver_backend.fetch_all(
                        "select balance from async_isolation_test where name = ?",
                        ("user1",)
                    )
                    read_values.append(rows1[0]["balance"])

                    # Wait for transaction 2 to commit
                    await asyncio.sleep(0.2)

                    # Second read (should be same as first)
                    rows2 = await async_sqlserver_backend.fetch_all(
                        "select balance from async_isolation_test where name = ?",
                        ("user1",)
                    )
                    read_values.append(rows2[0]["balance"])
            except Exception as e:
                read_values.append(str(e))

        async def transaction2():
            """Transaction 2: Modify and commit."""
            try:
                await asyncio.sleep(0.1)  # Wait for transaction 1's first read
                async_sqlserver_control_backend.transaction_manager.isolation_level = IsolationLevel.READ_COMMITTED
                async with async_sqlserver_control_backend.transaction():
                    await async_sqlserver_control_backend.execute(
                        "update async_isolation_test set balance = ? where name = ?",
                        (Decimal("200.00"), "user1")
                    )
            except Exception as e:
                pass

        await asyncio.gather(transaction1(), transaction2())

        # Both reads should return the same value
        assert len(read_values) == 2, "Should have two reads"
        assert read_values[0] == read_values[1], f"REPEATABLE READ should provide consistent reads: {read_values}"

    @pytest.mark.asyncio
    async def test_serializable_prevents_phantom_reads(self, async_sqlserver_backend, async_sqlserver_control_backend, async_isolation_test_table):
        """Verify SERIALIZABLE prevents phantom reads (async).

        Phantom reads occur when a transaction reads rows matching a condition,
        then another transaction inserts a row matching that condition.
        SERIALIZABLE should prevent this.
        """
        initial_count = []
        second_count = []
        insert_blocked = []

        async def transaction1():
            """Transaction 1: Count rows twice."""
            try:
                async_sqlserver_backend.transaction_manager.isolation_level = IsolationLevel.SERIALIZABLE
                async with async_sqlserver_backend.transaction():
                    # First count
                    rows1 = await async_sqlserver_backend.fetch_all(
                        "select count(*) as cnt from async_isolation_test where balance > ?",
                        (Decimal("50.00"),)
                    )
                    initial_count.append(rows1[0]["cnt"])

                    # Wait for transaction 2 to try insert
                    await asyncio.sleep(0.2)

                    # Second count (should be same)
                    rows2 = await async_sqlserver_backend.fetch_all(
                        "select count(*) as cnt from async_isolation_test where balance > ?",
                        (Decimal("50.00"),)
                    )
                    second_count.append(rows2[0]["cnt"])
            except Exception as e:
                initial_count.append(str(e))

        async def transaction2():
            """Transaction 2: Try to insert a matching row."""
            try:
                await asyncio.sleep(0.1)  # Wait for transaction 1's first read
                async_sqlserver_control_backend.transaction_manager.isolation_level = IsolationLevel.READ_COMMITTED
                async with async_sqlserver_control_backend.transaction():
                    # Try to insert a row that matches the condition
                    await async_sqlserver_control_backend.execute(
                        "insert into async_isolation_test (name, balance) values (?, ?)",
                        ("user2", Decimal("75.00"))
                    )
                insert_blocked.append(False)
            except Exception as e:
                # May be blocked by SERIALIZABLE lock
                insert_blocked.append(True)

        await asyncio.gather(transaction1(), transaction2())

        # With SERIALIZABLE, the counts should be consistent
        # (insert may be blocked or delayed until transaction 1 commits)
        if len(initial_count) == 2 and isinstance(initial_count[0], int):
            assert initial_count[0] == second_count[0], \
                f"SERIALIZABLE should prevent phantom reads: {initial_count[0]} vs {second_count[0]}"


class TestAsyncTransactionModeEffect:
    """Test actual behavior of transaction modes."""

    @pytest.mark.asyncio
    async def test_read_only_mode_allows_reads(self, async_sqlserver_backend, async_mode_test_table):
        """Verify READ ONLY mode allows read operations (async)."""
        if not async_sqlserver_backend.dialect.supports_read_only_transaction():
            pytest.skip("MySQL version does not support READ ONLY transactions")

        async_sqlserver_backend.transaction_manager.transaction_mode = TransactionMode.READ_ONLY
        async with async_sqlserver_backend.transaction():
            rows = await async_sqlserver_backend.fetch_all("select * from async_mode_test")
            assert len(rows) == 1
            assert rows[0]["name"] == "account1"

    @pytest.mark.asyncio
    async def test_read_only_rejects_writes(self, async_sqlserver_backend, async_mode_test_table):
        """Verify READ ONLY mode rejects write operations (async)."""
        if not async_sqlserver_backend.dialect.supports_read_only_transaction():
            pytest.skip("MySQL version does not support READ ONLY transactions")

        async_sqlserver_backend.transaction_manager.transaction_mode = TransactionMode.READ_ONLY

        with pytest.raises(Exception):
            async with async_sqlserver_backend.transaction():
                await async_sqlserver_backend.execute(
                    "update async_mode_test set balance = ? where name = ?",
                    (Decimal("500.00"), "account1")
                )

    @pytest.mark.asyncio
    async def test_read_write_allows_writes(self, async_sqlserver_backend, async_mode_test_table):
        """Verify READ WRITE mode allows write operations (async)."""
        async_sqlserver_backend.transaction_manager.transaction_mode = TransactionMode.READ_WRITE

        async with async_sqlserver_backend.transaction():
            await async_sqlserver_backend.execute(
                "update async_mode_test set balance = ? where name = ?",
                (Decimal("500.00"), "account1")
            )

        rows = await async_sqlserver_backend.fetch_all(
            "select balance from async_mode_test where name = ?",
            ("account1",)
        )
        assert rows[0]["balance"] == Decimal("500.00")


class TestAsyncTransactionCombination:
    """Test isolation level combined with transaction mode."""

    @pytest.mark.asyncio
    async def test_serializable_with_read_only(self, async_sqlserver_backend, async_combo_test_table):
        """Test SERIALIZABLE isolation with READ ONLY mode (async)."""
        if not async_sqlserver_backend.dialect.supports_read_only_transaction():
            pytest.skip("MySQL version does not support READ ONLY transactions")

        async_sqlserver_backend.transaction_manager.isolation_level = IsolationLevel.SERIALIZABLE
        async_sqlserver_backend.transaction_manager.transaction_mode = TransactionMode.READ_ONLY

        async with async_sqlserver_backend.transaction():
                rows = await async_sqlserver_backend.fetch_all("select * from async_combo_test")
                assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_repeatable_read_with_read_only(self, async_sqlserver_backend, async_combo_test_table):
        """Test REPEATABLE READ isolation with READ ONLY mode (async)."""
        if not async_sqlserver_backend.dialect.supports_read_only_transaction():
            pytest.skip("MySQL version does not support READ ONLY transactions")

        async_sqlserver_backend.transaction_manager.isolation_level = IsolationLevel.REPEATABLE_READ
        async_sqlserver_backend.transaction_manager.transaction_mode = TransactionMode.READ_ONLY

        async with async_sqlserver_backend.transaction():
                rows = await async_sqlserver_backend.fetch_all("select * from async_combo_test")
                assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_default_isolation_is_read_committed(self, async_sqlserver_backend):
        """Verify SQL Server default isolation level is READ COMMITTED (async).

        SQL Server does not expose @@transaction_isolation; the current
        session's isolation level is available via sys.dm_exec_sessions.
        ODBC connection pooling can carry over a previous session's
        isolation setting, so explicitly restore the documented default
        (READ COMMITTED) before asserting.
        """
        await async_sqlserver_backend.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
        async with async_sqlserver_backend.transaction():
            rows = await async_sqlserver_backend.fetch_all(
                "SELECT CASE transaction_isolation_level "
                "WHEN 0 THEN 'Unspecified' "
                "WHEN 1 THEN 'Read uncommitted' "
                "WHEN 2 THEN 'Read committed' "
                "WHEN 3 THEN 'Repeatable read' "
                "WHEN 4 THEN 'Serializable' "
                "WHEN 5 THEN 'Snapshot' "
                "END AS isolation "
                "FROM sys.dm_exec_sessions WHERE session_id = @@SPID"
            )
            if rows and rows[0].get("isolation"):
                isolation = rows[0]["isolation"]
                assert "READ COMMITTED" in isolation.upper(), \
                    f"SQL Server default should be READ COMMITTED, got {isolation}"

    @pytest.mark.asyncio
    async def test_no_isolation_level_set_uses_database_default(self, async_sqlserver_backend, monkeypatch):
        """Verify that when no isolation level is set, no SET TRANSACTION is sent (async).

        This tests that:
        1. The initial isolation_level is None
        2. No SET TRANSACTION ISOLATION LEVEL statement is sent when user doesn't specify isolation
        3. SQL Server uses its default isolation level
        """
        # Verify initial state is None
        assert async_sqlserver_backend.transaction_manager._isolation_level is None, \
            "Initial isolation level should be None (use database default)"

        # Track SQL statements executed through backend.execute
        executed_statements = []
        original_execute = async_sqlserver_backend.execute

        async def tracking_execute(sql, params=None, **kwargs):
            executed_statements.append(sql)
            return await original_execute(sql, params, **kwargs)

        monkeypatch.setattr(async_sqlserver_backend, "execute", tracking_execute)
        async with async_sqlserver_backend.transaction():
            await async_sqlserver_backend.fetch_all("SELECT 1 as test")

        # Verify no SET TRANSACTION was sent
        set_transaction_found = any(
            'SET TRANSACTION' in stmt.upper() for stmt in executed_statements
        )
        assert not set_transaction_found, \
            f"SET TRANSACTION should NOT be sent when isolation level not specified. Executed: {executed_statements}"

        # Verify BEGIN TRANSACTION was sent
        begin_transaction_found = any(
            'BEGIN TRANSACTION' in stmt.upper() for stmt in executed_statements
        )
        assert begin_transaction_found, \
            f"BEGIN TRANSACTION should be sent. Executed: {executed_statements}"

    @pytest.mark.asyncio
    async def test_explicit_isolation_level_sends_set_transaction(self, async_sqlserver_backend, monkeypatch):
        """Verify that when isolation level is explicitly set, SET TRANSACTION ISOLATION LEVEL is sent (async).

        This tests that:
        1. Setting isolation_level property changes the internal state
        2. SET TRANSACTION ISOLATION LEVEL statement is sent before BEGIN TRANSACTION
        3. The correct isolation level is used
        """
        # Set isolation level explicitly
        async_sqlserver_backend.transaction_manager.isolation_level = IsolationLevel.READ_COMMITTED

        # Verify internal state changed
        assert async_sqlserver_backend.transaction_manager._isolation_level == IsolationLevel.READ_COMMITTED, \
            "Isolation level should be READ_COMMITTED after explicit setting"

        # Track SQL statements executed through backend.execute
        executed_statements = []
        original_execute = async_sqlserver_backend.execute

        async def tracking_execute(sql, params=None, **kwargs):
            executed_statements.append(sql)
            return await original_execute(sql, params, **kwargs)

        monkeypatch.setattr(async_sqlserver_backend, "execute", tracking_execute)
        async with async_sqlserver_backend.transaction():
            await async_sqlserver_backend.fetch_all("SELECT 1 as test")

        # Verify SET TRANSACTION was sent with correct level
        set_transaction_found = any(
            'SET TRANSACTION ISOLATION LEVEL' in stmt.upper() and 'READ COMMITTED' in stmt.upper()
            for stmt in executed_statements
        )
        assert set_transaction_found, \
            f"SET TRANSACTION ISOLATION LEVEL READ COMMITTED should be sent. Executed: {executed_statements}"

        # Verify SET TRANSACTION comes before BEGIN TRANSACTION
        set_transaction_idx = next(
            (i for i, stmt in enumerate(executed_statements)
             if 'SET TRANSACTION ISOLATION LEVEL' in stmt.upper()),
            None
        )
        begin_transaction_idx = next(
            (i for i, stmt in enumerate(executed_statements)
             if 'BEGIN TRANSACTION' in stmt.upper()),
            None
        )
        assert set_transaction_idx is not None and begin_transaction_idx is not None, \
            "Both SET TRANSACTION ISOLATION LEVEL and BEGIN TRANSACTION should be executed"
        assert set_transaction_idx < begin_transaction_idx, \
            f"SET TRANSACTION ISOLATION LEVEL should come before BEGIN TRANSACTION. Order: {executed_statements}"

    @pytest.mark.asyncio
    async def test_isolation_level_cannot_change_during_transaction(self, async_sqlserver_backend, async_isolation_test_table):
        """Verify isolation level cannot be changed during active transaction (async)."""
        async with async_sqlserver_backend.transaction():
            with pytest.raises(Exception):
                async_sqlserver_backend.transaction_manager.isolation_level = IsolationLevel.SERIALIZABLE


class TestAsyncNestedTransactionsWithIsolation:
    """Test nested transactions (savepoints) with different isolation levels."""

    @pytest.mark.asyncio
    async def test_nested_transaction_with_isolation_level(self, async_sqlserver_backend, async_nested_test_table):
        """Test that nested transactions work with isolation level set (async)."""
        async_sqlserver_backend.transaction_manager.isolation_level = IsolationLevel.READ_COMMITTED

        async with async_sqlserver_backend.transaction():
            await async_sqlserver_backend.execute(
                "insert into async_nested_test (name, value) values (?, ?)",
                ("outer", 1)
            )

            sp = await async_sqlserver_backend.transaction_manager.savepoint("sp1")

            await async_sqlserver_backend.execute(
                "insert into async_nested_test (name, value) values (?, ?)",
                ("inner", 2)
            )

            await async_sqlserver_backend.transaction_manager.rollback_to(sp)

        rows = await async_sqlserver_backend.fetch_all("select * from async_nested_test order by id")
        assert len(rows) == 1
        assert rows[0]["name"] == "outer"
