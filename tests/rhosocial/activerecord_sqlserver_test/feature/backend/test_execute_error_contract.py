# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_execute_error_contract.py
"""Execute error contract for the SQL Server backend, without a database.

The contract under test is core's phase-specific error taxonomy:

* a session-control statement that fails while wrapping an ``EXPLAIN`` runs
  through the mapped path, so the driver failure becomes a taxonomy error;
* the ``finally`` that turns the session flag back off must log and keep the
  original failure, never replace it;
* ``execute_many`` / ``executescript`` share ``execute``'s classifier and do
  not replace an error that is already a framework error;
* an auto-commit failure is a ``TransactionError`` chained to the driver
  failure.

Cursors and connections are doubles: the backend is instantiated but never
connects, so no SQL Server instance is required.
"""

import pytest

pyodbc = pytest.importorskip("pyodbc")

from rhosocial.activerecord.backend.errors import (  # noqa: E402
    DatabaseError,
    DeadlockError,
    QueryError,
    TransactionError,
)
from rhosocial.activerecord.backend.impl.sqlserver.backend.backend import (  # noqa: E402
    SQLServerBackend,
)
from rhosocial.activerecord.backend.impl.sqlserver.mixins import (  # noqa: E402
    SQLServerBackendMixin,
)


class _ScriptedCursor:
    """Cursor double answering each statement through a scripted handler."""

    description = None
    rowcount = 0
    lastrowid = None
    noscan = None

    def __init__(self, handler):
        self._handler = handler
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append(sql)
        return self._handler(sql, params)

    def executemany(self, sql, params_list):
        self.executed.append(sql)
        return self._handler(sql, params_list)

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def close(self):
        pass


class _Connection:
    """Connection double recording commits and handing out scripted cursors."""

    def __init__(self, handler):
        self._handler = handler
        self.commits = 0
        self.commit_error = None

    def commit(self):
        self.commits += 1
        if self.commit_error is not None:
            raise self.commit_error

    def cursor(self):
        return _ScriptedCursor(self._handler)


@pytest.fixture
def offline_backend():
    """An unconnected backend used only for its execution/error wiring."""
    return SQLServerBackend(
        host="localhost",
        database="execute_contract",
        username="sa",
        password="not-used",
    )


def _install(backend, handler):
    """Attach a fake connection and route ``_get_cursor`` to scripted cursors."""
    connection = _Connection(handler)
    backend._connection = connection
    backend._get_cursor = lambda: _ScriptedCursor(handler)
    return connection


def _raising(error):
    """Return a handler that raises ``error`` for every statement."""

    def handler(sql, params=None):
        raise error

    return handler


class TestExplainSessionFlag:
    def test_failing_set_on_raises_mapped_error_with_original_cause(self, offline_backend):
        driver_error = pyodbc.ProgrammingError(102, "Incorrect syntax near 'SET'.")
        _install(offline_backend, _raising(driver_error))

        with pytest.raises(QueryError) as info:
            offline_backend.execute("SET SHOWPLAN_TEXT ON;SELECT 1")

        assert info.value.__cause__ is driver_error
        assert "Incorrect syntax near 'SET'" in str(info.value)
        assert info.value.driver_code == 102
        assert info.value.backend == "sqlserver"

    def test_cleanup_failure_does_not_replace_original_error(self, offline_backend):
        deadlock = pyodbc.DatabaseError(1205, "Transaction was deadlocked on lock resources")
        off_error = pyodbc.ProgrammingError(102, "Incorrect syntax near 'OFF'.")
        seen = []

        def handler(sql, params=None):
            seen.append(sql)
            if sql.startswith("SET ") and sql.endswith(" OFF"):
                raise off_error
            if sql.startswith("SET "):
                return None
            raise deadlock

        _install(offline_backend, handler)

        with pytest.raises(DeadlockError) as info:
            offline_backend.execute("SET SHOWPLAN_TEXT ON;SELECT 1")

        assert info.value.__cause__ is deadlock
        assert "deadlocked" in str(info.value)
        assert "SET SHOWPLAN_TEXT OFF" in seen


class TestExecuteManyContract:
    def test_deadlock_maps_to_deadlock_error(self, offline_backend):
        deadlock = pyodbc.DatabaseError(1205, "Deadlock victim")
        _install(offline_backend, _raising(deadlock))

        with pytest.raises(DeadlockError) as info:
            offline_backend.execute_many("UPDATE t SET v = ?", [(1,)])

        assert info.value.__cause__ is deadlock
        assert info.value.driver_code == 1205
        assert info.value.transient is True

    def test_success_goes_through_the_auto_commit_contract(self, offline_backend):
        offline_backend.config.autocommit = False
        connection = _install(offline_backend, lambda sql, params=None: None)

        result = offline_backend.execute_many("UPDATE t SET v = ?", [(1,)])

        assert result.affected_rows == 0
        assert connection.commits == 1

    def test_framework_error_is_not_re_mapped(self, offline_backend):
        framework_error = QueryError("already classified")
        _install(offline_backend, _raising(framework_error))

        with pytest.raises(QueryError) as info:
            offline_backend.execute_many("UPDATE t SET v = ?", [(1,)])

        assert info.value is framework_error

    def test_commit_failure_raises_transaction_error(self, offline_backend):
        offline_backend.config.autocommit = False
        commit_error = pyodbc.OperationalError(
            "08S01", "[08S01] Communication link failure"
        )
        connection = _install(offline_backend, lambda sql, params=None: None)
        connection.commit_error = commit_error

        with pytest.raises(TransactionError) as info:
            offline_backend.execute_many("UPDATE t SET v = ?", [(1,)])

        assert info.value.__cause__ is commit_error


class TestExecutescriptContract:
    def test_driver_error_is_classified(self, offline_backend):
        driver_error = pyodbc.ProgrammingError(102, "Incorrect syntax near 'GO'")
        _install(offline_backend, _raising(driver_error))

        with pytest.raises(QueryError) as info:
            offline_backend.executescript("SELECT 1\nGO\nSELECT 2")

        assert info.value.__cause__ is driver_error
        assert info.value.driver_code == 102

    def test_framework_error_is_not_re_mapped(self, offline_backend):
        framework_error = TransactionError("already classified")
        _install(offline_backend, _raising(framework_error))

        with pytest.raises(TransactionError) as info:
            offline_backend.executescript("SELECT 1\nGO\nSELECT 2")

        assert info.value is framework_error


class TestAutoCommitContract:
    def test_commit_failure_raises_transaction_error(self, offline_backend):
        offline_backend.config.autocommit = False
        commit_error = pyodbc.OperationalError(
            "08S01", "[08S01] Communication link failure"
        )
        connection = _install(offline_backend, lambda sql, params=None: None)
        connection.commit_error = commit_error

        with pytest.raises(TransactionError) as info:
            offline_backend.execute("INSERT INTO t (v) VALUES (1)")

        assert info.value.__cause__ is commit_error


class TestHandlerShortCircuit:
    def test_backend_handler_raises_framework_error_unchanged(self, offline_backend):
        framework_error = TransactionError("already classified")

        with pytest.raises(TransactionError) as info:
            offline_backend._handle_error(framework_error)

        assert info.value is framework_error

    def test_mixin_handler_raises_framework_error_unchanged(self, offline_backend):
        framework_error = DatabaseError("already classified")

        with pytest.raises(DatabaseError) as info:
            SQLServerBackendMixin._handle_error(offline_backend, framework_error)

        assert info.value is framework_error
