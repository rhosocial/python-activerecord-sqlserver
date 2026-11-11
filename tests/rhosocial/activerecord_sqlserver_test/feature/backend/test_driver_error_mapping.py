# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_driver_error_mapping.py
"""Unit tests for the SQL Server driver-error taxonomy mapping.

No database is required: synthetic pyodbc exceptions carry the native error
number and message the driver would supply, and the mapping methods run on an
unconnected backend.
"""

import pytest

pyodbc = pytest.importorskip("pyodbc")

from rhosocial.activerecord.backend.errors import (  # noqa: E402
    ConnectionError,
    DatabaseError,
    DeadlockError,
    IntegrityError,
    LockError,
    OperationalError,
    QueryError,
)
from rhosocial.activerecord.backend.impl.sqlserver.backend.backend import (  # noqa: E402
    SQLServerBackend,
)


@pytest.fixture
def offline_backend():
    """An unconnected backend used only for its error translation."""
    return SQLServerBackend(
        host="localhost",
        database="taxonomy_test",
        username="sa",
        password="not-used",
    )


def _handle(backend, error):
    with pytest.raises(DatabaseError) as info:
        backend._handle_error(error)
    return info.value


class TestDriverErrorMapping:
    def test_unique_violation_from_code(self, offline_backend):
        error = pyodbc.IntegrityError(
            "23000",
            "[23000] Violation of UNIQUE KEY constraint 'UQ' (2627)",
        )
        mapped = _handle(offline_backend, error)
        assert isinstance(mapped, IntegrityError)
        assert "Unique constraint violation" in str(mapped)
        assert mapped.driver_code == 2627
        assert mapped.operation == "execute"
        assert mapped.backend == "sqlserver"
        assert mapped.transient is False
        assert mapped.retryable is False
        assert mapped.__cause__ is error

    def test_unique_violation_from_numeric_first_arg(self, offline_backend):
        error = pyodbc.Error(2601, "Cannot insert duplicate key row")
        mapped = _handle(offline_backend, error)
        assert isinstance(mapped, IntegrityError)
        assert mapped.driver_code == 2601

    def test_foreign_key_violation(self, offline_backend):
        error = pyodbc.IntegrityError(
            "23000",
            "[23000] The INSERT conflicted with the FOREIGN KEY constraint (547)",
        )
        mapped = _handle(offline_backend, error)
        assert isinstance(mapped, IntegrityError)
        assert "Foreign key constraint violation" in str(mapped)
        assert mapped.driver_code == 547
        assert mapped.transient is False

    def test_not_null_violation(self, offline_backend):
        error = pyodbc.Error(
            515,
            "Cannot insert the value NULL into column 'name'; column does not allow nulls",
        )
        mapped = _handle(offline_backend, error)
        assert isinstance(mapped, IntegrityError)
        assert mapped.driver_code == 515
        assert "cannot be null" in str(mapped)
        assert mapped.transient is False

    def test_deadlock(self, offline_backend):
        error = pyodbc.DatabaseError(1205, "Deadlock victim")
        mapped = _handle(offline_backend, error)
        assert isinstance(mapped, DeadlockError)
        assert mapped.driver_code == 1205
        assert mapped.transient is True
        assert mapped.retryable is True

    def test_lock_timeout(self, offline_backend):
        error = pyodbc.DatabaseError(1222, "Lock request time out period exceeded")
        mapped = _handle(offline_backend, error)
        assert isinstance(mapped, LockError)
        assert mapped.driver_code == 1222
        assert mapped.transient is True
        assert mapped.retryable is True

    def test_login_failed(self, offline_backend):
        error = pyodbc.OperationalError(18456, "Login failed for user 'sa'")
        mapped = _handle(offline_backend, error)
        assert isinstance(mapped, ConnectionError)
        assert mapped.driver_code == 18456
        assert "Login failed" in str(mapped)
        assert mapped.transient is False
        assert mapped.retryable is False

    def test_cannot_open_database(self, offline_backend):
        error = pyodbc.OperationalError(4060, "Cannot open database requested by login")
        mapped = _handle(offline_backend, error)
        assert isinstance(mapped, ConnectionError)
        assert mapped.driver_code == 4060
        assert mapped.transient is False

    def test_invalid_object(self, offline_backend):
        error = pyodbc.ProgrammingError(208, "Invalid object name 'missing_table'")
        mapped = _handle(offline_backend, error)
        assert isinstance(mapped, QueryError)
        assert mapped.driver_code == 208
        assert mapped.transient is False

    def test_syntax_error(self, offline_backend):
        error = pyodbc.ProgrammingError(102, "Incorrect syntax near 'BOGUS'")
        mapped = _handle(offline_backend, error)
        assert isinstance(mapped, QueryError)
        assert mapped.driver_code == 102
        assert mapped.transient is False

    def test_syntax_error_from_message_without_code(self, offline_backend):
        error = pyodbc.Error("Incorrect syntax near the keyword 'SELECT'")
        mapped = _handle(offline_backend, error)
        assert isinstance(mapped, QueryError)
        assert mapped.driver_code is None

    def test_permission_denied_is_not_retryable(self, offline_backend):
        error = pyodbc.DatabaseError(229, "Permission denied on object 'users'")
        mapped = _handle(offline_backend, error)
        assert type(mapped) is DatabaseError
        assert mapped.driver_code == 229
        assert mapped.transient is False
        assert mapped.retryable is False

    def test_connection_loss_is_transient_operational_error(self, offline_backend):
        error = pyodbc.OperationalError(
            "08001",
            "[08001] Connection was closed while executing the statement",
        )
        mapped = _handle(offline_backend, error)
        assert isinstance(mapped, OperationalError)
        assert mapped.transient is True
        assert mapped.retryable is True

    def test_network_code_is_transient_operational_error(self, offline_backend):
        error = pyodbc.Error(11001, "Host not found")
        mapped = _handle(offline_backend, error)
        assert isinstance(mapped, OperationalError)
        assert mapped.driver_code == 11001
        assert mapped.transient is True

    def test_generic_database_error(self, offline_backend):
        error = pyodbc.DatabaseError("HY000", "[HY000] General database failure")
        mapped = _handle(offline_backend, error)
        assert type(mapped) is DatabaseError
        assert mapped.driver_code is None
        assert mapped.transient is False
        assert mapped.retryable is False
        assert mapped.__cause__ is error
