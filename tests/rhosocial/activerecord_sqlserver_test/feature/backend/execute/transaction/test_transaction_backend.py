import pytest
import pytest_asyncio

from rhosocial.activerecord.backend.errors import DatabaseError, TransactionError

_SETUP_SQL = """
    DROP TABLE IF EXISTS tx_test;

    CREATE TABLE tx_test (
        id INT IDENTITY(1,1) PRIMARY KEY,
        value NVARCHAR(50) NOT NULL
    );
"""

_CLEANUP_SQL = """
    DROP TABLE IF EXISTS tx_test;
"""


@pytest.fixture(scope="function")
def tx_backend(sqlserver_backend_single):
    sqlserver_backend_single.executescript(_SETUP_SQL)
    yield sqlserver_backend_single
    try:
        sqlserver_backend_single.executescript(_CLEANUP_SQL)
    except Exception:
        pass


@pytest_asyncio.fixture(scope="function")
async def async_tx_backend(async_sqlserver_backend):
    await async_sqlserver_backend.executescript(_SETUP_SQL)
    yield async_sqlserver_backend
    try:
        await async_sqlserver_backend.executescript(_CLEANUP_SQL)
    except Exception:
        pass


class TestTransactionCommit:
    def test_transaction_commit(self, tx_backend):
        backend = tx_backend
        try:
            backend.transaction_manager.begin()
            backend.execute("INSERT INTO tx_test (value) VALUES (?)", ("commit_test",))
            backend.transaction_manager.commit()
        except Exception:
            backend.transaction_manager.rollback()
            raise

        result = backend.execute("SELECT value FROM tx_test WHERE value = ?", ("commit_test",))
        assert len(result.data) > 0
        assert result.data[0]["value"] == "commit_test"

    def test_transaction_rollback(self, tx_backend):
        backend = tx_backend
        backend.transaction_manager.begin()
        backend.execute("INSERT INTO tx_test (value) VALUES (?)", ("rollback_test",))
        backend.transaction_manager.rollback()

        result = backend.execute("SELECT value FROM tx_test WHERE value = ?", ("rollback_test",))
        assert result.data is None or len(result.data) == 0

    def test_autocommit_off_requires_explicit_commit(self, tx_backend):
        backend = tx_backend
        backend.execute("INSERT INTO tx_test (value) VALUES (?)", ("no_tx_test",))
        # autocommit is off by default for queries without explicit transaction
        # but _handle_auto_commit_if_needed commits after each statement
        result = backend.execute("SELECT value FROM tx_test WHERE value = ?", ("no_tx_test",))
        assert len(result.data) > 0

    def test_nested_transaction_savepoint(self, tx_backend):
        backend = tx_backend
        backend.transaction_manager.begin()
        backend.execute("INSERT INTO tx_test (value) VALUES (?)", ("outer",))

        sp = backend.transaction_manager.savepoint()
        backend.execute("INSERT INTO tx_test (value) VALUES (?)", ("inner",))
        backend.transaction_manager.rollback(sp)

        backend.transaction_manager.commit()

        result_outer = backend.execute(
            "SELECT value FROM tx_test WHERE value = ?", ("outer",)
        )
        assert len(result_outer.data) > 0

        result_inner = backend.execute(
            "SELECT value FROM tx_test WHERE value = ?", ("inner",)
        )
        assert result_inner.data is None or len(result_inner.data) == 0

    def test_error_in_transaction_requires_rollback(self, tx_backend):
        backend = tx_backend
        backend.transaction_manager.begin()
        backend.execute("INSERT INTO tx_test (value) VALUES (?)", ("before_error",))

        with pytest.raises(DatabaseError):
            backend.execute("INSERT INTO nonexistent_table (value) VALUES (?)", ("fail",))

        backend.transaction_manager.rollback()

        result = backend.execute(
            "SELECT value FROM tx_test WHERE value = ?", ("before_error",)
        )
        assert result.data is None or len(result.data) == 0


class TestAsyncTransactionCommit:
    @pytest.mark.asyncio
    async def test_async_transaction_commit(self, async_tx_backend):
        backend = async_tx_backend
        try:
            await backend.transaction_manager.begin()
            await backend.execute(
                "INSERT INTO tx_test (value) VALUES (?)", ("async_commit_test",)
            )
            await backend.transaction_manager.commit()
        except Exception:
            await backend.transaction_manager.rollback()
            raise

        result = await backend.execute(
            "SELECT value FROM tx_test WHERE value = ?", ("async_commit_test",)
        )
        assert len(result.data) > 0
        assert result.data[0]["value"] == "async_commit_test"

    @pytest.mark.asyncio
    async def test_async_transaction_rollback(self, async_tx_backend):
        backend = async_tx_backend
        await backend.transaction_manager.begin()
        await backend.execute(
            "INSERT INTO tx_test (value) VALUES (?)", ("async_rollback_test",)
        )
        await backend.transaction_manager.rollback()

        result = await backend.execute(
            "SELECT value FROM tx_test WHERE value = ?", ("async_rollback_test",)
        )
        assert result.data is None or len(result.data) == 0

    @pytest.mark.asyncio
    async def test_async_nested_transaction_savepoint(self, async_tx_backend):
        backend = async_tx_backend
        await backend.transaction_manager.begin()
        await backend.execute("INSERT INTO tx_test (value) VALUES (?)", ("async_outer",))

        sp = await backend.transaction_manager.savepoint()
        await backend.execute("INSERT INTO tx_test (value) VALUES (?)", ("async_inner",))
        await backend.transaction_manager.rollback(sp)

        await backend.transaction_manager.commit()

        result_outer = await backend.execute(
            "SELECT value FROM tx_test WHERE value = ?", ("async_outer",)
        )
        assert len(result_outer.data) > 0

        result_inner = await backend.execute(
            "SELECT value FROM tx_test WHERE value = ?", ("async_inner",)
        )
        assert result_inner.data is None or len(result_inner.data) == 0
