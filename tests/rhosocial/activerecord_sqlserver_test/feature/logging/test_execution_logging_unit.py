# tests/rhosocial/activerecord_sqlserver_test/feature/logging/test_execution_logging_unit.py
"""Database-free coverage tests for SQL Server execution logging.

Every case here drives the backend through fakes: no SQL Server, no pyodbc
connection and no aioodbc connection is opened.  The tests pin the canonical
library logger name, the batch logging contract (parameter sets, never
parameter values), the ``_handle_error`` branches and the transaction
commit/rollback failure guards.

The sync and async cases share method names; the async execution path also
needs its own ``_execute_statement`` coverage because that statement splitter
has no sync twin.
"""

import logging

import pytest

pyodbc = pytest.importorskip("pyodbc")

from rhosocial.activerecord.backend.errors import (  # noqa: E402
    DatabaseError,
    DeadlockError,
    IntegrityError,
    OperationalError,
    TransactionError,
)
from rhosocial.activerecord.backend.options import ExecutionOptions, StatementType  # noqa: E402
from rhosocial.activerecord.logging.redaction import SensitiveValue  # noqa: E402
from rhosocial.activerecord.backend.impl.sqlserver.backend import backend as backend_mod  # noqa: E402
from rhosocial.activerecord.backend.impl.sqlserver.backend import async_backend as async_backend_mod  # noqa: E402
from rhosocial.activerecord.backend.impl.sqlserver.backend.backend import SQLServerBackend  # noqa: E402
from rhosocial.activerecord.backend.impl.sqlserver.backend.async_backend import (  # noqa: E402
    AsyncSQLServerBackend,
)
from rhosocial.activerecord.backend.impl.sqlserver.mixins import backend_mixin  # noqa: E402
from rhosocial.activerecord.backend.impl.sqlserver import transaction as transaction_mod  # noqa: E402
from rhosocial.activerecord.backend.impl.sqlserver import async_transaction as async_transaction_mod  # noqa: E402
from rhosocial.activerecord.backend.impl.sqlserver.cli import info as cli_info_mod  # noqa: E402


LOGGER_NAME = "rhosocial.activerecord.backend.sqlserver"
BATCH_SQL = "INSERT INTO unit_users (name, token) VALUES (?, ?)"


class FakeSyncCursor:
    """Minimal DB-API cursor recording the calls the backend makes."""

    def __init__(self, rowcount=2, execute_error=None):
        self.rowcount = rowcount
        self.execute_error = execute_error
        self.description = None
        self.executed = []
        self.batches = []
        self.closed = 0

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        if self.execute_error is not None:
            raise self.execute_error
        return self

    def executemany(self, sql, params_list):
        self.batches.append((sql, list(params_list)))

    def fetchone(self):
        return (1,)

    def fetchall(self):
        return []

    def close(self):
        self.closed += 1


class FakeSyncConnection:
    """Connection stand-in whose cursors never touch a driver."""

    def __init__(self, **cursor_kwargs):
        self.cursors = []
        self._cursor_kwargs = cursor_kwargs
        self.commits = 0

    def cursor(self):
        cursor = FakeSyncCursor(**self._cursor_kwargs)
        self.cursors.append(cursor)
        return cursor

    def commit(self):
        self.commits += 1


class FakeAsyncCursor:
    """Async cursor stand-in supporting the ``async with`` protocol."""

    def __init__(self, rowcount=2, execute_error=None):
        self.rowcount = rowcount
        self.execute_error = execute_error
        self.description = None
        self.lastrowid = None
        self.executed = []
        self.batches = []
        self.closed = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, sql, params=()):
        self.executed.append((sql, params))
        if self.execute_error is not None:
            raise self.execute_error
        return self

    async def executemany(self, sql, params_list):
        self.batches.append((sql, list(params_list)))

    async def fetchone(self):
        return (1,)

    async def fetchall(self):
        return []

    async def close(self):
        self.closed += 1


class FakeAsyncConnection:
    """Async connection stand-in whose cursors never touch a driver."""

    def __init__(self, **cursor_kwargs):
        self.cursors = []
        self._cursor_kwargs = cursor_kwargs

    async def cursor(self):
        cursor = FakeAsyncCursor(**self._cursor_kwargs)
        self.cursors.append(cursor)
        return cursor

    async def close(self):
        pass


@pytest.fixture
def log_records():
    """Capture records emitted on the canonical SQL Server logger."""
    logger = logging.getLogger(LOGGER_NAME)
    previous_level = logger.level
    previous_propagate = logger.propagate
    records = []

    class _Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = _Capture()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate


@pytest.fixture
def sqlserver_backend():
    """Construct a backend without connecting to a server."""
    return SQLServerBackend(database="unit_db", autocommit=True)


@pytest.fixture
def async_sqlserver_backend(monkeypatch):
    """Construct an async backend without an aioodbc installation.

    ``AsyncSQLServerBackend.__init__`` only rejects a missing driver; the
    driver is not used until ``connect``.  Substituting a sentinel keeps these
    tests runnable on machines where aioodbc is not installed while CI still
    exercises the same constructor with the real package.
    """
    if async_backend_mod.aioodbc is None:
        monkeypatch.setattr(async_backend_mod, "aioodbc", object())
    return AsyncSQLServerBackend(database="unit_db", autocommit=True)


def _messages(records):
    return [record.getMessage() for record in records]


class TestExecutionLogging:
    """Synchronous execution logging coverage."""

    def test_changed_modules_use_the_expected_objects(self):
        assert backend_mod.SQLServerBackend is SQLServerBackend
        assert async_backend_mod.AsyncSQLServerBackend is AsyncSQLServerBackend
        assert backend_mixin.SQLServerBackendMixin is not None
        assert transaction_mod.SQLServerTransactionManager is not None
        assert async_transaction_mod.AsyncSQLServerTransactionManager is not None

    def test_backend_logger_name(self, sqlserver_backend):
        assert sqlserver_backend._logger_name == LOGGER_NAME
        assert sqlserver_backend._get_logger_name() == LOGGER_NAME
        assert sqlserver_backend.logger.name == LOGGER_NAME

    def test_execute_many_logs_parameter_sets_not_values(
        self, sqlserver_backend, log_records
    ):
        sqlserver_backend._connection = FakeSyncConnection()
        params_list = [
            ("alice", SensitiveValue("s3cr3t-value")),
            ("bob", SensitiveValue("s3cr3t-value")),
        ]

        result = sqlserver_backend.execute_many(BATCH_SQL, params_list)

        assert result.affected_rows == 2
        cursor = sqlserver_backend._connection.cursors[-1]
        assert cursor.batches == [(
            BATCH_SQL,
            [("alice", "s3cr3t-value"), ("bob", "s3cr3t-value")],
        )]
        text = "\n".join(_messages(log_records))
        assert "parameter_sets: 2" in text
        assert "s3cr3t-value" not in text

    def test_execute_many_empty_parameter_list(self, sqlserver_backend, log_records):
        sqlserver_backend._connection = FakeSyncConnection()

        result = sqlserver_backend.execute_many(BATCH_SQL, [])

        assert result.affected_rows == 0
        assert result.data is None
        text = "\n".join(_messages(log_records))
        assert "parameter_sets: 0" in text
        assert "rows_affected=0" in text

    def test_executescript_logs_script_start(self, sqlserver_backend, log_records):
        sqlserver_backend._connection = FakeSyncConnection()

        sqlserver_backend.executescript("SELECT 1\nGO\nSELECT 2")

        executed = [
            call for cursor in sqlserver_backend._connection.cursors
            for call in cursor.executed
        ]
        assert ("SELECT 1", ()) in executed
        assert ("SELECT 2", ()) in executed
        text = "\n".join(_messages(log_records))
        assert "Executing SQL script" in text
        assert "SQL script executed successfully" in text

    def test_handle_error_branches(self, sqlserver_backend, log_records):
        with pytest.raises(IntegrityError, match="Unique constraint violation"):
            sqlserver_backend._handle_error(
                pyodbc.IntegrityError("23000", "[23000] Duplicate key")
            )
        with pytest.raises(IntegrityError, match="Foreign key constraint violation"):
            sqlserver_backend._handle_error(
                pyodbc.IntegrityError("23000", "[23000] Foreign key reference")
            )
        with pytest.raises(IntegrityError):
            sqlserver_backend._handle_error(
                pyodbc.IntegrityError("23000", "[23000] Integrity constraint")
            )
        with pytest.raises(DatabaseError):
            sqlserver_backend._handle_error(
                pyodbc.DatabaseError("HY000", "[HY000] General database failure")
            )
        with pytest.raises(DeadlockError):
            sqlserver_backend._handle_error(
                pyodbc.DatabaseError(1205, "Deadlock victim")
            )

        text = "\n".join(_messages(log_records))
        assert "Unique constraint violation" in text
        assert "Foreign key constraint violation" in text
        assert "Integrity error" in text
        assert "Database error" in text
        assert "Deadlock detected" in text

    def test_transaction_failure_guards(self, log_records):
        manager = transaction_mod.SQLServerTransactionManager(
            object(), logging.getLogger(LOGGER_NAME)
        )
        manager._transaction_level = 1

        def fail():
            raise RuntimeError("simulated driver failure")

        manager._do_commit = fail
        with pytest.raises(TransactionError):
            manager.commit()

        manager._do_rollback = fail
        with pytest.raises(TransactionError):
            manager.rollback()

        text = "\n".join(_messages(log_records))
        assert "Failed to commit transaction" in text
        assert "Failed to rollback transaction" in text

    def test_cli_info_uses_the_library_logger(self):
        assert cli_info_mod.logger.name == cli_info_mod.__name__


class TestAsyncExecutionLogging:
    """Asynchronous execution logging coverage (same method names as sync)."""

    async def test_changed_modules_use_the_expected_objects(self):
        assert backend_mod.SQLServerBackend is SQLServerBackend
        assert async_backend_mod.AsyncSQLServerBackend is AsyncSQLServerBackend
        assert backend_mixin.SQLServerBackendMixin is not None
        assert transaction_mod.SQLServerTransactionManager is not None
        assert async_transaction_mod.AsyncSQLServerTransactionManager is not None

    async def test_backend_logger_name(self, async_sqlserver_backend):
        assert async_sqlserver_backend._logger_name == LOGGER_NAME
        assert async_sqlserver_backend._get_logger_name() == LOGGER_NAME
        assert async_sqlserver_backend.logger.name == LOGGER_NAME

    async def test_execute_many_logs_parameter_sets_not_values(
        self, async_sqlserver_backend, log_records
    ):
        async_sqlserver_backend._connection = FakeAsyncConnection()
        params_list = [
            ("alice", SensitiveValue("s3cr3t-value")),
            ("bob", SensitiveValue("s3cr3t-value")),
        ]

        result = await async_sqlserver_backend.execute_many(BATCH_SQL, params_list)

        assert result.affected_rows == 2
        cursor = async_sqlserver_backend._connection.cursors[-1]
        assert cursor.batches == [(
            BATCH_SQL,
            [("alice", "s3cr3t-value"), ("bob", "s3cr3t-value")],
        )]
        text = "\n".join(_messages(log_records))
        assert "parameter_sets: 2" in text
        assert "s3cr3t-value" not in text

    async def test_execute_many_empty_parameter_list(
        self, async_sqlserver_backend, log_records
    ):
        async_sqlserver_backend._connection = FakeAsyncConnection()

        result = await async_sqlserver_backend.execute_many(BATCH_SQL, [])

        assert result.affected_rows == 0
        assert result.data is None
        text = "\n".join(_messages(log_records))
        assert "parameter_sets: 0" in text
        assert "rows_affected=0" in text

    async def test_executescript_logs_script_start(
        self, async_sqlserver_backend, log_records
    ):
        async_sqlserver_backend._connection = FakeAsyncConnection()

        await async_sqlserver_backend.executescript("SELECT 1\nGO\nSELECT 2")

        executed = [
            call for cursor in async_sqlserver_backend._connection.cursors
            for call in cursor.executed
        ]
        assert ("SELECT 1", ()) in executed
        assert ("SELECT 2", ()) in executed
        text = "\n".join(_messages(log_records))
        assert "Executing SQL script (async)" in text
        assert "SQL script executed successfully" in text

    async def test_handle_error_branches(self, async_sqlserver_backend, log_records):
        with pytest.raises(IntegrityError, match="Unique constraint violation"):
            await async_sqlserver_backend._handle_error(
                Exception("integrity violation: duplicate key")
            )
        with pytest.raises(IntegrityError, match="Foreign key constraint violation"):
            await async_sqlserver_backend._handle_error(
                Exception("integrity violation: foreign key constraint")
            )
        with pytest.raises(IntegrityError):
            await async_sqlserver_backend._handle_error(
                Exception("integrity violation")
            )
        with pytest.raises(DeadlockError):
            await async_sqlserver_backend._handle_error(
                Exception("deadlock detected, error 1205")
            )
        with pytest.raises(OperationalError):
            await async_sqlserver_backend._handle_error(
                Exception("connection timeout expired")
            )
        with pytest.raises(DatabaseError):
            await async_sqlserver_backend._handle_error(
                Exception("unexpected database failure")
            )

        text = "\n".join(_messages(log_records))
        assert "Unique constraint violation" in text
        assert "Foreign key constraint violation" in text
        assert "Integrity error" in text
        assert "Deadlock detected" in text
        assert "Operational error" in text
        assert "Database error" in text

    async def test_execute_statement_logs_and_reports_failures(
        self, async_sqlserver_backend, log_records
    ):
        options = ExecutionOptions(stmt_type=StatementType.DQL)
        async_sqlserver_backend._connection = FakeAsyncConnection()

        result = await async_sqlserver_backend._execute_statement(
            "SELECT 1", None, options
        )

        assert result.data is None
        text = "\n".join(_messages(log_records))
        assert "Executing SQL: SELECT 1" in text
        assert "parameters: None" in text

        log_records.clear()
        async_sqlserver_backend._connection = FakeAsyncConnection(
            execute_error=RuntimeError("unexpected query failure")
        )
        with pytest.raises(DatabaseError):
            await async_sqlserver_backend._execute_statement(
                "SELECT 1", None, options
            )
        text = "\n".join(_messages(log_records))
        assert "Query failed, exception will be re-raised" in text

    async def test_transaction_failure_guards(self, log_records):
        manager = async_transaction_mod.AsyncSQLServerTransactionManager(
            object(), logging.getLogger(LOGGER_NAME)
        )
        manager._transaction_level = 1

        async def fail():
            raise RuntimeError("simulated driver failure")

        manager._do_commit = fail
        with pytest.raises(TransactionError):
            await manager.commit()

        manager._do_rollback = fail
        with pytest.raises(TransactionError):
            await manager.rollback()

        text = "\n".join(_messages(log_records))
        assert "Failed to commit async transaction" in text
        assert "Failed to rollback async transaction" in text

    async def test_cli_info_uses_the_library_logger(self):
        assert cli_info_mod.logger.name == cli_info_mod.__name__
