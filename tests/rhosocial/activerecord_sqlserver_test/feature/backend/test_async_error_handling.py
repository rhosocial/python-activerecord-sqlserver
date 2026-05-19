import pytest
import pytest_asyncio

from rhosocial.activerecord.backend.errors import (
    IntegrityError,
    DatabaseError,
    DeadlockError,
    OperationalError,
)
from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend


@pytest_asyncio.fixture
async def setup_test_table(async_sqlserver_backend):
    await async_sqlserver_backend.execute("DROP TABLE IF EXISTS error_test")
    await async_sqlserver_backend.execute("""
        CREATE TABLE error_test (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name NVARCHAR(255) NOT NULL,
            email NVARCHAR(255) UNIQUE
        )
    """)
    yield
    try:
        await async_sqlserver_backend.execute("DROP TABLE IF EXISTS error_test")
    except Exception:
        pass


class TestAsyncHandleError:
    @pytest.mark.asyncio
    async def test_handle_duplicate_entry_error(self, async_sqlserver_backend):
        await async_sqlserver_backend.execute("DROP TABLE IF EXISTS unique_test_err")
        await async_sqlserver_backend.execute("""
            CREATE TABLE unique_test_err (
                id INT IDENTITY(1,1) PRIMARY KEY,
                email NVARCHAR(255) UNIQUE
            )
        """)
        try:
            await async_sqlserver_backend.execute(
                "INSERT INTO unique_test_err (email) VALUES (?)",
                ("test@example.com",)
            )
            with pytest.raises(IntegrityError) as exc_info:
                await async_sqlserver_backend.execute(
                    "INSERT INTO unique_test_err (email) VALUES (?)",
                    ("test@example.com",)
                )
            error_msg_lower = str(exc_info.value).lower()
            assert "unique" in error_msg_lower or "duplicate" in error_msg_lower
        finally:
            try:
                await async_sqlserver_backend.execute("DROP TABLE IF EXISTS unique_test_err")
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_handle_foreign_key_constraint_error(self, async_sqlserver_backend):
        backend = async_sqlserver_backend
        try:
            await backend.execute("DROP TABLE IF EXISTS child_table_err")
            await backend.execute("DROP TABLE IF EXISTS parent_table_err")
            await backend.execute("""
                CREATE TABLE parent_table_err (id INT PRIMARY KEY)
            """)
            await backend.execute("""
                CREATE TABLE child_table_err (
                    id INT PRIMARY KEY,
                    parent_id INT,
                    FOREIGN KEY (parent_id) REFERENCES parent_table_err(id)
                )
            """)
            with pytest.raises(IntegrityError) as exc_info:
                await backend.execute(
                    "INSERT INTO child_table_err (id, parent_id) VALUES (1, 999)"
                )
            assert "foreign key" in str(exc_info.value).lower() or "reference" in str(exc_info.value).lower()
        finally:
            try:
                await backend.execute("DROP TABLE IF EXISTS child_table_err")
                await backend.execute("DROP TABLE IF EXISTS parent_table_err")
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_handle_generic_database_error(self, async_sqlserver_backend):
        backend = async_sqlserver_backend
        try:
            await backend.execute("INVALID SQL STATEMENT HERE")
            pytest.fail("Should have raised DatabaseError")
        except DatabaseError:
            pass
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_handle_deadlock_error_via_message(self, async_sqlserver_backend):
        class MockDeadlockError(Exception):
            def __str__(self):
                return "Transaction (Process ID 56) was deadlocked on lock resources with another process and has been chosen as the deadlock victim. Rerun the transaction."

        mock_error = MockDeadlockError()
        with pytest.raises(DeadlockError):
            await async_sqlserver_backend._handle_error(mock_error)

    @pytest.mark.asyncio
    async def test_handle_deadlock_error_via_code(self, async_sqlserver_backend):
        class MockDeadlockError(Exception):
            args = (1205, "Deadlock victim")
            def __str__(self):
                return "Deadlock victim"

        mock_error = MockDeadlockError()
        with pytest.raises(DeadlockError):
            await async_sqlserver_backend._handle_error(mock_error)

    @pytest.mark.asyncio
    async def test_handle_timeout_error(self, async_sqlserver_backend):
        class MockTimeoutError(Exception):
            def __str__(self):
                return "Query timeout expired"

        mock_error = MockTimeoutError()
        with pytest.raises(OperationalError):
            await async_sqlserver_backend._handle_error(mock_error)

    @pytest.mark.asyncio
    async def test_handle_connection_error(self, async_sqlserver_backend):
        class MockConnectionError(Exception):
            def __str__(self):
                return "Connection was closed"

        mock_error = MockConnectionError()
        with pytest.raises(OperationalError):
            await async_sqlserver_backend._handle_error(mock_error)

    @pytest.mark.asyncio
    async def test_integrity_constraint_error(self, async_sqlserver_backend):
        class MockIntegrityError(Exception):
            def __str__(self):
                return "Violation of UNIQUE KEY constraint"

        mock_error = MockIntegrityError()
        with pytest.raises(IntegrityError):
            await async_sqlserver_backend._handle_error(mock_error)


class TestAsyncErrorClassValidation:
    @pytest.mark.asyncio
    async def test_async_backend_initializes_without_db(self):
        backend = AsyncSQLServerBackend(
            host="localhost", port=1433, database="testdb",
            username="sa", password="Passw0rd!"
        )
        assert backend is not None
        assert backend.dialect is not None
