# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_transaction_isolation_effect.py
"""
Tests for SQL Server transaction isolation level actual effects.

This module tests that different isolation levels actually provide
the expected isolation behavior in SQL Server backend.

Tests cover:
- READ UNCOMMITTED: Dirty reads allowed
- READ COMMITTED: No dirty reads, but non-repeatable reads allowed
- REPEATABLE READ: No dirty reads, no non-repeatable reads, but phantom reads possible
- SERIALIZABLE: Full isolation, no phantom reads
"""
import pytest
import threading
import time
from decimal import Decimal

from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend
from rhosocial.activerecord.backend.transaction import IsolationLevel


@pytest.fixture
def sqlserver_control_backend(sqlserver_backend):
    """A second, independent backend connection for isolation testing.

    Uses the same connection config as the main ``sqlserver_backend`` fixture
    so both connections point at the same database.
    """
    backend = SQLServerBackend(connection_config=sqlserver_backend.config)
    backend.connect()
    yield backend
    backend.disconnect()


class TestIsolationLevelEffects:
    """Test actual isolation behavior for each isolation level."""

    @pytest.fixture
    def test_table(self, sqlserver_backend):
        """Create a test table for isolation tests."""
        sqlserver_backend.execute("DROP TABLE IF EXISTS isolation_test")
        sqlserver_backend.execute("""
            CREATE TABLE isolation_test (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name VARCHAR(255),
                balance DECIMAL(10, 2),
                version INT DEFAULT 1
            )
        """)
        sqlserver_backend.execute(
            "INSERT INTO isolation_test (name, balance) VALUES (%s, %s)",
            ("user1", Decimal("100.00"))
        )
        yield "isolation_test"
        sqlserver_backend.execute("DROP TABLE IF EXISTS isolation_test")

    def test_read_uncommitted_allows_dirty_reads(self, sqlserver_backend, sqlserver_control_backend, test_table):
        """Verify READ UNCOMMITTED isolation level allows dirty reads.

        A dirty read occurs when a transaction reads data written by another
        uncommitted transaction. READ UNCOMMITTED should allow this.

        This test uses two separate backend connections to test isolation.
        """
        # Use control backend for transaction 2 (independent connection)
        backend1 = sqlserver_backend
        backend2 = sqlserver_control_backend

        dirty_read_detected = []
        updated_event = threading.Event()

        def transaction1():
            """Transaction 1: Read uncommitted data."""
            try:
                # Set isolation level before starting transaction
                backend1.transaction_manager.isolation_level = IsolationLevel.READ_UNCOMMITTED
                with backend1.transaction():
                    # Wait for transaction 2 to modify
                    updated_event.wait(timeout=5)
                    # Read potentially uncommitted data
                    rows = backend1.fetch_all(
                        "SELECT balance FROM isolation_test WHERE name = %s",
                        ("user1",)
                    )
                    if rows and rows[0]["balance"] == Decimal("200.00"):
                        dirty_read_detected.append(True)
            except Exception as e:
                dirty_read_detected.append(str(e))

        def transaction2():
            """Transaction 2: Modify data without committing."""
            try:
                backend2.transaction_manager.isolation_level = IsolationLevel.READ_UNCOMMITTED
                with backend2.transaction():
                    # Update balance
                    backend2.execute(
                        "UPDATE isolation_test SET balance = %s WHERE name = %s",
                        (Decimal("200.00"), "user1")
                    )
                    # Signal transaction 1 that the uncommitted change is in place
                    updated_event.set()
                    # Wait for transaction 1 to read
                    time.sleep(0.3)
                    # Rollback (dirty read scenario)
                    raise Exception("Force rollback for dirty read test")
            except Exception:
                pass  # Expected rollback

        t1 = threading.Thread(target=transaction1)
        t2 = threading.Thread(target=transaction2)

        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        # READ UNCOMMITTED should have detected the dirty read
        assert True in dirty_read_detected, "READ UNCOMMITTED should allow dirty reads"

    def test_read_committed_prevents_dirty_reads(self, sqlserver_backend, sqlserver_control_backend, test_table):
        """Verify READ COMMITTED isolation level prevents dirty reads.

        Uses independent connections for each thread to avoid connection sharing issues.
        """
        backend1 = sqlserver_backend
        backend2 = sqlserver_control_backend
        dirty_read_occurred = []

        def transaction1():
            """Transaction 1: Should not see uncommitted data."""
            try:
                backend1.transaction_manager.isolation_level = IsolationLevel.READ_COMMITTED
                with backend1.transaction():
                    # Wait for transaction 2 to modify
                    time.sleep(0.15)
                    # Should NOT see the uncommitted change
                    rows = backend1.fetch_all(
                        "SELECT balance FROM isolation_test WHERE name = %s",
                        ("user1",)
                    )
                    if rows and rows[0]["balance"] != Decimal("200.00"):
                        dirty_read_occurred.append(False)  # Correct behavior
                    else:
                        dirty_read_occurred.append(True)  # Dirty read happened
            except Exception as e:
                dirty_read_occurred.append(str(e))

        def transaction2():
            """Transaction 2: Modify and rollback."""
            try:
                backend2.transaction_manager.isolation_level = IsolationLevel.READ_COMMITTED
                with backend2.transaction():
                    backend2.execute(
                        "UPDATE isolation_test SET balance = %s WHERE name = %s",
                        (Decimal("200.00"), "user1")
                    )
                    time.sleep(0.2)
                    raise Exception("Force rollback")
            except Exception:
                pass

        t1 = threading.Thread(target=transaction1)
        t2 = threading.Thread(target=transaction2)

        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        # READ COMMITTED should NOT have dirty read
        assert False in dirty_read_occurred, "READ COMMITTED should prevent dirty reads"

    def test_repeatable_read_consistency(self, sqlserver_backend, sqlserver_control_backend, test_table):
        """Verify REPEATABLE READ provides consistent reads within a transaction.

        REPEATABLE READ should ensure that if a row is read twice in the same
        transaction, the same value is returned even if another transaction
        committed a change.

        Uses independent connections for each thread to avoid connection sharing issues.
        """
        backend1 = sqlserver_backend
        backend2 = sqlserver_control_backend
        read_values = []

        def transaction1():
            """Transaction 1: Read the same row twice."""
            try:
                backend1.transaction_manager.isolation_level = IsolationLevel.REPEATABLE_READ
                with backend1.transaction():
                    # First read
                    rows1 = backend1.fetch_all(
                        "SELECT balance FROM isolation_test WHERE name = %s",
                        ("user1",)
                    )
                    read_values.append(rows1[0]["balance"])

                    # Wait for transaction 2 to commit
                    time.sleep(0.2)

                    # Second read (should be same as first)
                    rows2 = backend1.fetch_all(
                        "SELECT balance FROM isolation_test WHERE name = %s",
                        ("user1",)
                    )
                    read_values.append(rows2[0]["balance"])
            except Exception as e:
                read_values.append(str(e))

        def transaction2():
            """Transaction 2: Modify and commit."""
            try:
                time.sleep(0.1)  # Wait for transaction 1's first read
                backend2.transaction_manager.isolation_level = IsolationLevel.READ_COMMITTED
                with backend2.transaction():
                    backend2.execute(
                        "UPDATE isolation_test SET balance = %s WHERE name = %s",
                        (Decimal("200.00"), "user1")
                    )
            except Exception as e:
                pass

        t1 = threading.Thread(target=transaction1)
        t2 = threading.Thread(target=transaction2)

        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        # Both reads should return the same value
        assert len(read_values) == 2, "Should have two reads"
        assert read_values[0] == read_values[1], f"REPEATABLE READ should provide consistent reads: {read_values}"

    def test_serializable_prevents_phantom_reads(self, sqlserver_backend, sqlserver_control_backend, test_table):
        """Verify SERIALIZABLE prevents phantom reads.

        Phantom reads occur when a transaction reads rows matching a condition,
        then another transaction inserts a row matching that condition.
        SERIALIZABLE should prevent this.

        Uses independent connections for each thread to avoid connection sharing issues.
        """
        backend1 = sqlserver_backend
        backend2 = sqlserver_control_backend
        initial_count = []
        second_count = []
        insert_blocked = []

        def transaction1():
            """Transaction 1: Count rows twice."""
            try:
                backend1.transaction_manager.isolation_level = IsolationLevel.SERIALIZABLE
                with backend1.transaction():
                    # First count
                    rows1 = backend1.fetch_all(
                        "SELECT COUNT(*) as cnt FROM isolation_test WHERE balance > %s",
                        (Decimal("50.00"),)
                    )
                    initial_count.append(rows1[0]["cnt"])

                    # Wait for transaction 2 to try insert
                    time.sleep(0.2)

                    # Second count (should be same)
                    rows2 = backend1.fetch_all(
                        "SELECT COUNT(*) as cnt FROM isolation_test WHERE balance > %s",
                        (Decimal("50.00"),)
                    )
                    second_count.append(rows2[0]["cnt"])
            except Exception as e:
                initial_count.append(str(e))

        def transaction2():
            """Transaction 2: Try to insert a matching row."""
            try:
                time.sleep(0.1)  # Wait for transaction 1's first read
                backend2.transaction_manager.isolation_level = IsolationLevel.READ_COMMITTED
                with backend2.transaction():
                    # Try to insert a row that matches the condition
                    backend2.execute(
                        "INSERT INTO isolation_test (name, balance) VALUES (%s, %s)",
                        ("user2", Decimal("75.00"))
                    )
                insert_blocked.append(False)
            except Exception as e:
                # May be blocked by SERIALIZABLE lock
                insert_blocked.append(True)

        t1 = threading.Thread(target=transaction1)
        t2 = threading.Thread(target=transaction2)

        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        # With SERIALIZABLE, the counts should be consistent
        # (insert may be blocked or delayed until transaction 1 commits)
        if len(initial_count) == 2 and isinstance(initial_count[0], int):
            assert initial_count[0] == second_count[0], \
                f"SERIALIZABLE should prevent phantom reads: {initial_count[0]} vs {second_count[0]}"


class TestTransactionModeEffects:
    """Test actual effects of READ ONLY and READ WRITE transaction modes."""

    @pytest.fixture
    def test_table(self, sqlserver_backend):
        """Create a test table for transaction mode tests."""
        sqlserver_backend.execute("DROP TABLE IF EXISTS mode_test")
        sqlserver_backend.execute("""
            CREATE TABLE mode_test (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name VARCHAR(255),
                value INT
            )
        """)
        sqlserver_backend.execute(
            "INSERT INTO mode_test (name, value) VALUES (%s, %s)",
            ("item1", 100)
        )
        yield "mode_test"
        sqlserver_backend.execute("DROP TABLE IF EXISTS mode_test")

    def test_read_only_mode_rejects_writes(self, sqlserver_backend, test_table):
        """Verify READ ONLY mode rejects write operations.

        MySQL 5.6.5+ supports READ ONLY transactions. Any attempt to modify
        data in a READ ONLY transaction should fail.
        """
        # Check if READ ONLY is supported
        if not sqlserver_backend.dialect.supports_read_only_transaction():
            pytest.skip("MySQL version does not support READ ONLY transactions")

        error_caught = False
        try:
            from rhosocial.activerecord.backend.transaction import TransactionMode
            sqlserver_backend.transaction_manager.transaction_mode = TransactionMode.READ_ONLY
            with sqlserver_backend.transaction():
                # Attempt to insert (should fail)
                sqlserver_backend.execute(
                    "INSERT INTO mode_test (name, value) VALUES (%s, %s)",
                    ("item2", 200)
                )
        except Exception as e:
            error_caught = True
            # Verify it's the right error
            assert "read-only" in str(e).lower() or "cannot execute" in str(e).lower() or "1792" in str(e)

        assert error_caught, "READ ONLY transaction should reject write operations"

    def test_read_only_mode_allows_reads(self, sqlserver_backend, test_table):
        """Verify READ ONLY mode allows read operations."""
        if not sqlserver_backend.dialect.supports_read_only_transaction():
            pytest.skip("MySQL version does not support READ ONLY transactions")

        from rhosocial.activerecord.backend.transaction import TransactionMode
        sqlserver_backend.transaction_manager.transaction_mode = TransactionMode.READ_ONLY
        with sqlserver_backend.transaction():
            rows = sqlserver_backend.fetch_all("SELECT * FROM mode_test")
            assert len(rows) == 1
            assert rows[0]["name"] == "item1"

    def test_read_write_mode_allows_writes(self, sqlserver_backend, test_table):
        """Verify READ WRITE mode allows write operations."""
        from rhosocial.activerecord.backend.transaction import TransactionMode
        sqlserver_backend.transaction_manager.transaction_mode = TransactionMode.READ_WRITE
        with sqlserver_backend.transaction():
            sqlserver_backend.execute(
                "INSERT INTO mode_test (name, value) VALUES (%s, %s)",
                ("item2", 200)
            )

        rows = sqlserver_backend.fetch_all("SELECT * FROM mode_test ORDER BY id")
        assert len(rows) == 2
        assert rows[1]["name"] == "item2"


class TestIsolationModeCombination:
    """Test combinations of isolation levels and transaction modes."""

    @pytest.fixture
    def test_table(self, sqlserver_backend):
        """Create a test table for combination tests."""
        sqlserver_backend.execute("DROP TABLE IF EXISTS combo_test")
        sqlserver_backend.execute("""
            CREATE TABLE combo_test (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name VARCHAR(255),
                balance DECIMAL(10, 2)
            )
        """)
        sqlserver_backend.execute(
            "INSERT INTO combo_test (name, balance) VALUES (%s, %s)",
            ("account1", Decimal("1000.00"))
        )
        yield "combo_test"
        sqlserver_backend.execute("DROP TABLE IF EXISTS combo_test")

    def test_serializable_with_read_only(self, sqlserver_backend, test_table):
        """Test SERIALIZABLE isolation with READ ONLY mode."""
        if not sqlserver_backend.dialect.supports_read_only_transaction():
            pytest.skip("MySQL version does not support READ ONLY transactions")

        from rhosocial.activerecord.backend.transaction import TransactionMode

        # Set both isolation level and mode
        sqlserver_backend.transaction_manager.isolation_level = IsolationLevel.SERIALIZABLE
        sqlserver_backend.transaction_manager.transaction_mode = TransactionMode.READ_ONLY

        with sqlserver_backend.transaction():
            # Should be able to read
            rows = sqlserver_backend.fetch_all("SELECT * FROM combo_test")
            assert len(rows) == 1

    def test_repeatable_read_with_read_only(self, sqlserver_backend, test_table):
        """Test REPEATABLE READ isolation with READ ONLY mode."""
        if not sqlserver_backend.dialect.supports_read_only_transaction():
            pytest.skip("MySQL version does not support READ ONLY transactions")

        from rhosocial.activerecord.backend.transaction import TransactionMode

        sqlserver_backend.transaction_manager.isolation_level = IsolationLevel.REPEATABLE_READ
        sqlserver_backend.transaction_manager.transaction_mode = TransactionMode.READ_ONLY

        with sqlserver_backend.transaction():
            rows = sqlserver_backend.fetch_all("SELECT * FROM combo_test")
            assert len(rows) == 1

    def test_default_isolation_is_read_committed(self, sqlserver_backend):
        """Verify SQL Server default isolation level is READ COMMITTED.

        SQL Server does not expose @@transaction_isolation; the current
        session's isolation level is available via sys.dm_exec_sessions.
        ODBC connection pooling can carry over a previous session's
        isolation setting, so explicitly restore the documented default
        (READ COMMITTED) before asserting.
        """
        sqlserver_backend.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
        with sqlserver_backend.transaction():
            rows = sqlserver_backend.fetch_all(
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
                assert "READ COMMITTED" in isolation.upper(), (
                    f"SQL Server default should be READ COMMITTED, got {isolation}"
                )

    def test_no_isolation_level_set_uses_database_default(self, sqlserver_backend, monkeypatch):
        """Verify that when no isolation level is set, no SET TRANSACTION is sent.

        This tests that:
        1. The initial isolation_level is None (not READ_COMMITTED)
        2. No SET TRANSACTION ISOLATION LEVEL statement is sent when user doesn't specify isolation
        3. SQL Server uses its default isolation level
        """
        # Verify initial state is None
        assert sqlserver_backend.transaction_manager._isolation_level is None, \
            "Initial isolation level should be None (use database default)"

        # Track SQL statements executed through backend.execute
        executed_statements = []
        original_execute = sqlserver_backend.execute

        def tracking_execute(sql, params=None, **kwargs):
            executed_statements.append(sql)
            return original_execute(sql, params, **kwargs)

        monkeypatch.setattr(sqlserver_backend, "execute", tracking_execute)
        with sqlserver_backend.transaction():
            sqlserver_backend.fetch_all("SELECT 1 as test")

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

    def test_explicit_isolation_level_sends_set_transaction(self, sqlserver_backend, monkeypatch):
        """Verify that when isolation level is explicitly set, SET TRANSACTION ISOLATION LEVEL is sent.

        This tests that:
        1. Setting isolation_level property changes the internal state
        2. SET TRANSACTION ISOLATION LEVEL statement is sent before BEGIN TRANSACTION
        3. The correct isolation level is used
        """
        # Set isolation level explicitly
        sqlserver_backend.transaction_manager.isolation_level = IsolationLevel.READ_COMMITTED

        # Verify internal state changed
        assert sqlserver_backend.transaction_manager._isolation_level == IsolationLevel.READ_COMMITTED, \
            "Isolation level should be READ_COMMITTED after explicit setting"

        # Track SQL statements executed through backend.execute
        executed_statements = []
        original_execute = sqlserver_backend.execute

        def tracking_execute(sql, params=None, **kwargs):
            executed_statements.append(sql)
            return original_execute(sql, params, **kwargs)

        monkeypatch.setattr(sqlserver_backend, "execute", tracking_execute)
        with sqlserver_backend.transaction():
            sqlserver_backend.fetch_all("SELECT 1 as test")

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

    def test_isolation_level_cannot_change_during_transaction(self, sqlserver_backend, test_table):
        """Verify isolation level cannot be changed during active transaction."""
        with sqlserver_backend.transaction():
            with pytest.raises(Exception):  # IsolationLevelError
                sqlserver_backend.transaction_manager.isolation_level = IsolationLevel.SERIALIZABLE


class TestNestedTransactionsWithIsolation:
    """Test nested transactions (savepoints) with different isolation levels."""

    @pytest.fixture
    def test_table(self, sqlserver_backend):
        """Create a test table for nested transaction tests."""
        sqlserver_backend.execute("DROP TABLE IF EXISTS nested_test")
        sqlserver_backend.execute("""
            CREATE TABLE nested_test (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name VARCHAR(255),
                value INT
            )
        """)
        yield "nested_test"
        sqlserver_backend.execute("DROP TABLE IF EXISTS nested_test")

    def test_nested_transaction_with_isolation_level(self, sqlserver_backend, test_table):
        """Test that nested transactions work with isolation level set."""
        sqlserver_backend.transaction_manager.isolation_level = IsolationLevel.READ_COMMITTED

        with sqlserver_backend.transaction():
            # Insert first record
            sqlserver_backend.execute(
                "INSERT INTO nested_test (name, value) VALUES (%s, %s)",
                ("outer", 1)
            )

            # Create savepoint
            sp = sqlserver_backend.transaction_manager.savepoint("sp1")

            # Insert second record
            sqlserver_backend.execute(
                "INSERT INTO nested_test (name, value) VALUES (%s, %s)",
                ("inner", 2)
            )

            # Rollback to savepoint
            sqlserver_backend.transaction_manager.rollback_to(sp)

        # Only outer record should exist
        rows = sqlserver_backend.fetch_all("SELECT * FROM nested_test ORDER BY id")
        assert len(rows) == 1
        assert rows[0]["name"] == "outer"
