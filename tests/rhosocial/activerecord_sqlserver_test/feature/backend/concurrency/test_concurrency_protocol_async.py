# tests/rhosocial/activerecord_sqlserver_test/feature/backend/concurrency/test_concurrency_protocol_async.py
"""
Async Concurrency Tests for asyncio.create_task Scenarios

CRITICAL FINDINGS from these tests:

mysql-connector-python's async connection does NOT support concurrent operations.
The error "read() called while another coroutine is already waiting for incoming data"
indicates that a single connection can only handle ONE operation at a time.

This means:
1. Shared backend is NOT safe for ANY concurrent operations (even reads)
2. Each concurrent task MUST have its own backend/connection instance
3. The "queue-worker pool" pattern with shared backend is NOT viable for MySQL async

Architecture:
- One ActiveRecord class -> One backend instance -> One connection
- asyncio.create_task creates concurrent coroutines sharing the same event loop
- mysql-connector-python async: Single connection = single concurrent operation

Recommended Pattern:
- For concurrent tasks: Each task creates its own backend instance
- Connection pooling is not supported by mysql-connector-python async
- Use separate connections for true concurrency
"""

import asyncio
import pytest
import pytest_asyncio
import logging
from typing import ClassVar, Optional

from rhosocial.activerecord.model import AsyncActiveRecord
from rhosocial.activerecord.base.field_proxy import FieldProxy
from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend

logger = logging.getLogger(__name__)


# --- Test Models ---

class ConcurrentUser(AsyncActiveRecord):
    """User model for concurrency testing."""
    __table_name__ = "concurrent_users"
    c: ClassVar[FieldProxy] = FieldProxy()

    id: Optional[int] = None
    username: str
    email: str
    value: int = 0
    created_at: Optional[str] = None


class ConcurrentTask(AsyncActiveRecord):
    """Task model for concurrency testing with status tracking."""
    __table_name__ = "concurrent_tasks"
    c: ClassVar[FieldProxy] = FieldProxy()

    id: Optional[int] = None
    task_name: str
    status: str = "pending"
    worker_id: Optional[int] = None
    result: Optional[str] = None


# --- Schema Definitions ---

USERS_SCHEMA = """
CREATE TABLE concurrent_users (
    id INT IDENTITY(1,1) PRIMARY KEY,
    username VARCHAR(191) NOT NULL UNIQUE,
    email VARCHAR(191) NOT NULL,
    value INT NOT NULL DEFAULT 0,
    created_at VARCHAR(MAX)
)
"""

TASKS_SCHEMA = """
CREATE TABLE concurrent_tasks (
    id INT IDENTITY(1,1) PRIMARY KEY,
    task_name VARCHAR(191) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    worker_id INT,
    result VARCHAR(MAX)
)
"""


# --- Fixtures ---

@pytest_asyncio.fixture(scope="function")
async def concurrent_user_model(async_sqlserver_backend_single):
    """Setup ConcurrentUser model with shared backend."""
    backend = async_sqlserver_backend_single

    # Create schema
    await backend.execute("DROP TABLE IF EXISTS concurrent_users")
    await backend.execute(USERS_SCHEMA)

    # Configure model
    ConcurrentUser.__backend__ = backend
    ConcurrentUser.__connection_config__ = backend.config

    yield ConcurrentUser

    # Cleanup
    try:
        await backend.execute("DROP TABLE IF EXISTS concurrent_users")
    except Exception:
        pass


@pytest_asyncio.fixture(scope="function")
async def concurrent_task_model(async_sqlserver_backend_single):
    """Setup ConcurrentTask model with shared backend."""
    backend = async_sqlserver_backend_single

    # Create schema
    await backend.execute("DROP TABLE IF EXISTS concurrent_tasks")
    await backend.execute(TASKS_SCHEMA)

    # Configure model
    ConcurrentTask.__backend__ = backend
    ConcurrentTask.__connection_config__ = backend.config

    yield ConcurrentTask

    # Cleanup
    try:
        await backend.execute("DROP TABLE IF EXISTS concurrent_tasks")
    except Exception:
        pass


@pytest_asyncio.fixture(scope="function")
async def mysql_config(async_sqlserver_backend_single):
    """Get MySQL connection config for creating independent backends."""
    return async_sqlserver_backend_single.config


# --- Test 1: Shared Backend Concurrent Reads Behavior ---

@pytest.mark.asyncio
async def test_shared_backend_concurrent_reads_behavior(concurrent_user_model):
    """
    Test concurrent read behavior on shared backend.

    aioodbc wraps pyodbc, and the underlying ODBC driver does NOT support
    concurrent commands on a single connection: issuing a second statement
    while one is still streaming results raises
    "Connection is busy with results for another command (0) (SQLExecDirectW)".

    This test documents that a shared async connection is NOT safe for
    concurrent reads either - concurrent tasks MUST use their own backend
    instances (see the recommended pattern below).
    """
    # Setup: Insert test data first (sequentially)
    for i in range(10):
        user = concurrent_user_model(
            username=f"user_{i}",
            email=f"user_{i}@test.com",
            value=i
        )
        await user.save()

    errors = []

    async def reader_task(task_id: int, user_id: int):
        """Task that reads a user."""
        try:
            user = await concurrent_user_model.find_one(user_id)
            return user
        except Exception as e:
            errors.append((task_id, str(e)))
            return None

    # Create multiple concurrent read tasks
    tasks = [
        asyncio.create_task(reader_task(i, (i % 10) + 1))
        for i in range(20)
    ]

    # Wait for all tasks to complete
    await asyncio.gather(*tasks)

    # sqlserver/pyodbc driver: concurrent commands on a shared connection
    # raise "Connection is busy with results for another command"
    assert len(errors) > 0, (
        "Shared backend concurrent reads should fail with 'Connection is busy' "
        "on the pyodbc/ODBC driver"
    )

    print(f"\nDocumented: Shared backend concurrent reads FAIL with pyodbc/ODBC "
          f"('Connection is busy', {len(errors)} errors out of 20)")


# --- Test 2: Sequential Operations Work (SANITY CHECK) ---

@pytest.mark.asyncio
async def test_sequential_operations_work(concurrent_user_model):
    """
    Sanity check: Sequential operations on shared backend work fine.
    This confirms the issue is specifically about CONCURRENT access.
    """
    # Sequential inserts
    for i in range(10):
        user = concurrent_user_model(
            username=f"seq_user_{i}",
            email=f"seq_{i}@test.com",
            value=i
        )
        await user.save()

    # Sequential reads
    for i in range(10):
        user = await concurrent_user_model.find_one(i + 1)
        assert user is not None
        assert user.username == f"seq_user_{i}"

    # Sequential updates
    for i in range(10):
        user = await concurrent_user_model.find_one(i + 1)
        user.value = i * 100
        await user.save()

    # Verify updates
    for i in range(10):
        user = await concurrent_user_model.find_one(i + 1)
        assert user.value == i * 100

    print("\nConfirmed: Sequential operations on shared backend work correctly")


# --- Test 3: RECOMMENDED Pattern - Independent Backends ---

@pytest.mark.asyncio
async def test_recommended_pattern_independent_backends(mysql_config):
    """
    RECOMMENDED PATTERN: Each task creates its own backend instance.

    This pattern ensures complete isolation between tasks:
    - Each task has its own connection
    - True concurrent execution is possible
    - Transactions are isolated per task
    - No race conditions on shared connection state
    """
    config = mysql_config

    results = []
    errors = []

    # First, create the table using a separate backend
    setup_backend = AsyncSQLServerBackend(connection_config=config)
    await setup_backend.connect()
    await setup_backend.execute("DROP TABLE IF EXISTS concurrent_users")
    await setup_backend.execute(USERS_SCHEMA)
    await setup_backend.disconnect()

    async def isolated_worker_task(task_id: int):
        """
        Worker task that creates its own backend instance.
        This is the RECOMMENDED pattern for concurrent execution.
        """
        backend = None
        try:
            # Create independent backend for this task
            backend = AsyncSQLServerBackend(connection_config=config)
            await backend.connect()

            # Configure a task-specific model class
            class WorkerUser(AsyncActiveRecord):
                __table_name__ = "concurrent_users"
                c: ClassVar[FieldProxy] = FieldProxy()
                id: Optional[int] = None
                username: str
                email: str
                value: int = 0
                created_at: Optional[str] = None

            WorkerUser.__backend__ = backend
            WorkerUser.__connection_config__ = config

            # Perform operations (can use transaction safely)
            async with backend.transaction():
                user = WorkerUser(
                    username=f"isolated_user_{task_id}",
                    email=f"isolated_{task_id}@test.com",
                    value=task_id * 10
                )
                await user.save()

                # Simulate work
                await asyncio.sleep(0.05)

                # Transaction commits automatically if no exception
                results.append((task_id, user.id, "committed"))

        except Exception as e:
            errors.append((task_id, str(e)))
        finally:
            if backend:
                try:
                    await backend.disconnect()
                except Exception:
                    pass

    # Run multiple tasks concurrently, each with its own backend
    tasks = [
        asyncio.create_task(isolated_worker_task(i))
        for i in range(10)
    ]

    await asyncio.gather(*tasks)

    # All tasks should succeed
    assert len(errors) == 0, f"Errors with independent backends: {errors}"
    assert len(results) == 10

    # Verify all records exist
    backend = AsyncSQLServerBackend(connection_config=config)
    await backend.connect()

    try:
        users = await backend.fetch_all(
            "SELECT * FROM concurrent_users WHERE username LIKE 'isolated_user_%'"
        )
        assert len(users) == 10
    finally:
        await backend.execute("DROP TABLE IF EXISTS concurrent_users")
        await backend.disconnect()

    print(f"\nSUCCESS: All 10 concurrent tasks with independent backends completed")


# --- Test 4: Transaction Isolation with Independent Backends ---

@pytest.mark.asyncio
async def test_transaction_isolation_with_independent_backends(mysql_config):
    """
    Test that transactions are properly isolated when each task
    has its own backend instance.
    """
    config = mysql_config

    # Setup table
    setup_backend = AsyncSQLServerBackend(connection_config=config)
    await setup_backend.connect()
    await setup_backend.execute("DROP TABLE IF EXISTS concurrent_users")
    await setup_backend.execute(USERS_SCHEMA)
    await setup_backend.disconnect()

    results = {"committed": [], "rolled_back": []}
    errors = []

    async def transaction_task(task_id: int, should_commit: bool):
        """Task that performs a transaction."""
        backend = None
        try:
            backend = AsyncSQLServerBackend(connection_config=config)
            await backend.connect()

            class TxUser(AsyncActiveRecord):
                __table_name__ = "concurrent_users"
                c: ClassVar[FieldProxy] = FieldProxy()
                id: Optional[int] = None
                username: str
                email: str
                value: int = 0
                created_at: Optional[str] = None

            TxUser.__backend__ = backend
            TxUser.__connection_config__ = config

            try:
                async with backend.transaction():
                    user = TxUser(
                        username=f"tx_user_{task_id}",
                        email=f"tx_{task_id}@test.com",
                        value=task_id
                    )
                    await user.save()

                    # Simulate work
                    await asyncio.sleep(0.05)

                    if not should_commit:
                        raise Exception("Intentional rollback")

                    results["committed"].append(task_id)
            except Exception as e:
                if "Intentional rollback" in str(e):
                    results["rolled_back"].append(task_id)
                else:
                    raise

        except Exception as e:
            errors.append((task_id, str(e)))
        finally:
            if backend:
                try:
                    await backend.disconnect()
                except Exception:
                    pass

    # Run tasks concurrently - some commit, some rollback
    tasks = [
        asyncio.create_task(transaction_task(i, i % 2 == 0))
        for i in range(10)
    ]

    await asyncio.gather(*tasks)

    # Verify results
    assert len(errors) == 0, f"Unexpected errors: {errors}"
    assert len(results["committed"]) == 5  # Even task_ids
    assert len(results["rolled_back"]) == 5  # Odd task_ids

    # Verify database state
    backend = AsyncSQLServerBackend(connection_config=config)
    await backend.connect()

    try:
        users = await backend.fetch_all(
            "SELECT * FROM concurrent_users WHERE username LIKE 'tx_user_%'"
        )
        # Only committed transactions should have records
        assert len(users) == 5

        committed_ids = set(int(u['username'].split('_')[-1]) for u in users)
        for i in range(10):
            if i % 2 == 0:
                assert i in committed_ids, f"Expected tx_user_{i} to be committed"
            else:
                assert i not in committed_ids, f"Expected tx_user_{i} to be rolled back"
    finally:
        await backend.execute("DROP TABLE IF EXISTS concurrent_users")
        await backend.disconnect()

    print(f"\nConfirmed: Transaction isolation works with independent backends")
    print(f"  Committed: {results['committed']}")
    print(f"  Rolled back: {results['rolled_back']}")


# --- Test 5: Sequential vs Concurrent Comparison ---

@pytest.mark.asyncio
async def test_sequential_vs_concurrent_comparison(mysql_config):
    """
    Compare sequential operations on shared backend vs concurrent
    operations with independent backends.

    This demonstrates the trade-off:
    - Shared backend: Must be sequential, but no connection overhead
    - Independent backends: Can be concurrent, but connection overhead
    """
    config = mysql_config

    # Setup table
    setup_backend = AsyncSQLServerBackend(connection_config=config)
    await setup_backend.connect()
    await setup_backend.execute("DROP TABLE IF EXISTS concurrent_users")
    await setup_backend.execute(USERS_SCHEMA)
    await setup_backend.disconnect()

    # Test 1: Sequential with shared backend
    shared_backend = AsyncSQLServerBackend(connection_config=config)
    await shared_backend.connect()

    class SharedUser(AsyncActiveRecord):
        __table_name__ = "concurrent_users"
        c: ClassVar[FieldProxy] = FieldProxy()
        id: Optional[int] = None
        username: str
        email: str
        value: int = 0
        created_at: Optional[str] = None

    SharedUser.__backend__ = shared_backend
    SharedUser.__connection_config__ = config

    import time
    start_sequential = time.time()

    for i in range(20):
        user = SharedUser(username=f"seq_{i}", email=f"seq_{i}@test.com", value=i)
        await user.save()

    sequential_time = time.time() - start_sequential

    await shared_backend.execute("DELETE FROM concurrent_users")
    await shared_backend.disconnect()

    # Test 2: Concurrent with independent backends
    async def concurrent_insert(task_id: int):
        backend = AsyncSQLServerBackend(connection_config=config)
        await backend.connect()
        try:
            class ConcurrentUser(AsyncActiveRecord):
                __table_name__ = "concurrent_users"
                c: ClassVar[FieldProxy] = FieldProxy()
                id: Optional[int] = None
                username: str
                email: str
                value: int = 0
                created_at: Optional[str] = None

            ConcurrentUser.__backend__ = backend
            ConcurrentUser.__connection_config__ = config

            user = ConcurrentUser(
                username=f"concurrent_{task_id}",
                email=f"concurrent_{task_id}@test.com",
                value=task_id
            )
            await user.save()
        finally:
            await backend.disconnect()

    start_concurrent = time.time()

    tasks = [asyncio.create_task(concurrent_insert(i)) for i in range(20)]
    await asyncio.gather(*tasks)

    concurrent_time = time.time() - start_concurrent

    # Verify all records exist
    verify_backend = AsyncSQLServerBackend(connection_config=config)
    await verify_backend.connect()
    users = await verify_backend.fetch_all("SELECT * FROM concurrent_users")
    await verify_backend.execute("DROP TABLE IF EXISTS concurrent_users")
    await verify_backend.disconnect()

    assert len(users) == 20

    print(f"\nPerformance Comparison:")
    print(f"  Sequential (shared backend): {sequential_time:.3f}s")
    print(f"  Concurrent (independent backends): {concurrent_time:.3f}s")

    # Note: Concurrent may not always be faster due to connection overhead
    # But it enables true parallelism which is important for I/O-bound work


# --- Test 6: Document Best Practices ---

@pytest.mark.asyncio
async def test_concurrency_best_practices_documentation(mysql_config):
    """
    This test documents the best practices for asyncio.create_task concurrency
    with SQL Server backend.

    SUMMARY:
    ========
    1. DO NOT share backend between concurrent tasks
    2. Each concurrent task should create its own backend instance
    3. Sequential operations on shared backend are safe
    4. Connection pooling is not supported by mysql-connector-python async

    SAFE PATTERNS:
    - Sequential operations with shared backend
    - Concurrent tasks with independent backends
    - Transactions with independent backends

    UNSAFE PATTERNS:
    - Concurrent tasks sharing a backend (even for reads)
    - Transactions with shared backend across tasks
    """
    config = mysql_config

    # Setup table
    setup_backend = AsyncSQLServerBackend(connection_config=config)
    await setup_backend.connect()
    await setup_backend.execute("DROP TABLE IF EXISTS concurrent_users")
    await setup_backend.execute(USERS_SCHEMA)
    await setup_backend.disconnect()

    # SAFE PATTERN: Concurrent tasks with independent backends
    async def safe_concurrent_task(task_id: int):
        backend = AsyncSQLServerBackend(connection_config=config)
        await backend.connect()
        try:
            class SafeUser(AsyncActiveRecord):
                __table_name__ = "concurrent_users"
                c: ClassVar[FieldProxy] = FieldProxy()
                id: Optional[int] = None
                username: str
                email: str
                value: int = 0
                created_at: Optional[str] = None

            SafeUser.__backend__ = backend
            SafeUser.__connection_config__ = config

            # Can safely use transactions
            async with backend.transaction():
                user = SafeUser(
                    username=f"safe_user_{task_id}",
                    email=f"safe_{task_id}@test.com",
                    value=task_id
                )
                await user.save()
        finally:
            await backend.disconnect()

    # Run 10 concurrent tasks safely
    tasks = [asyncio.create_task(safe_concurrent_task(i)) for i in range(10)]
    await asyncio.gather(*tasks)

    # Verify
    verify_backend = AsyncSQLServerBackend(connection_config=config)
    await verify_backend.connect()
    users = await verify_backend.fetch_all("SELECT * FROM concurrent_users")
    await verify_backend.execute("DROP TABLE IF EXISTS concurrent_users")
    await verify_backend.disconnect()

    assert len(users) == 10

    print("\n" + "=" * 60)
    print("BEST PRACTICES FOR asyncio.create_task WITH MySQL BACKEND")
    print("=" * 60)
    print("""
1. Each concurrent task MUST have its own backend instance
2. DO NOT share backend between tasks using asyncio.create_task
3. mysql-connector-python async does NOT support concurrent operations
   on a single connection
4. Connection pooling is NOT supported by async connector
5. For concurrent I/O-bound work, create new connections per task
""")
    print("=" * 60)
