# src/rhosocial/activerecord/backend/impl/sqlserver/error_mapping.py
"""Translate SQL Server driver errors onto the shared semantic taxonomy.

Recognition follows the phase 3b order: native error number first, then the
pyodbc exception class, then message text as a last resort. A mapped error
carries ``operation``, ``driver_code``, ``backend`` and ``transient``
diagnostics so callers and logs can tell why the operation failed without
parsing the message again.

pyodbc 5.x raises DB-API exceptions whose ``args`` are normally
``(sqlstate, message)``; the SQL Server native error number is embedded in the
message as ``[2627]`` or ``(2627)``. The helpers below accept either form, so
synthetic exceptions built for tests resolve the same way as driver-raised
ones.
"""

import re
from typing import Optional

from rhosocial.activerecord.backend.errors import (
    ConnectionError,
    DatabaseError,
    DeadlockError,
    IntegrityError,
    LockError,
    OperationalError,
    QueryError,
    attach_diagnostics,
)

BACKEND_NAME = "sqlserver"
OPERATION_NAME = "execute"

# SQL Server native error numbers.
UNIQUE_VIOLATION_CODES = frozenset({2627, 2601})
FOREIGN_KEY_VIOLATION_CODE = 547
NOT_NULL_VIOLATION_CODE = 515
DEADLOCK_CODE = 1205
LOCK_TIMEOUT_CODE = 1222
LOGIN_FAILED_CODE = 18456
CANNOT_OPEN_DATABASE_CODE = 4060
INVALID_OBJECT_CODE = 208
SYNTAX_ERROR_CODES = frozenset({102, 156})
PERMISSION_DENIED_CODES = frozenset({229, 230})
NETWORK_ERROR_CODES = frozenset({
    53,      # named pipes / server not found
    64,      # network connection dropped
    232,     # named pipes pipe end
    233,     # named pipes pipe end
    10054,   # TCP connection reset
    40197,   # service error
    40501,   # service busy
    40613,   # database currently unavailable
    11001,   # host not found
})

_UNIQUE_MESSAGE_PATTERNS = (
    "duplicate key",
    "duplicate entry",
    "unique constraint",
    "unique key",
    "violation of unique",
)
_FOREIGN_KEY_MESSAGE_PATTERNS = (
    "foreign key",
    "reference constraint",
)
_NOT_NULL_MESSAGE_PATTERNS = (
    "does not allow nulls",
    "cannot insert the value null",
    "not null constraint",
)
_INTEGRITY_MESSAGE_PATTERNS = (
    "integrity violation",
    "integrity constraint",
    "constraint violation",
    "check constraint",
)
_DEADLOCK_MESSAGE_PATTERNS = (
    "deadlock",
)
_LOCK_TIMEOUT_MESSAGE_PATTERNS = (
    "lock request time out",
    "lock timeout",
    "lock wait timeout",
    "lock wait time out",
)
_LOGIN_MESSAGE_PATTERNS = (
    "login failed",
    "authentication failed",
)
_CANNOT_OPEN_DATABASE_PATTERNS = (
    "cannot open database",
    "unable to open database",
)
_INVALID_OBJECT_MESSAGE_PATTERNS = (
    "invalid object name",
    "invalid column name",
)
_SYNTAX_MESSAGE_PATTERNS = (
    "incorrect syntax",
    "syntax error",
    "unclosed quotation mark",
)
_PERMISSION_MESSAGE_PATTERNS = (
    "permission denied",
    "permission was denied",
)
_CONNECTION_MESSAGE_PATTERNS = (
    "connection refused",
    "connection reset",
    "connection was closed",
    "connection is closed",
    "connection was broken",
    "broken pipe",
    "communication link failure",
    "named pipes provider",
    "network-related",
    "network error",
    "tcp provider",
    "server was not found",
    "error locating server",
    "unable to connect",
    "could not open a connection",
    "connection timeout",
    "query timeout expired",
    "timeout expired",
)

# ``[2627]``, ``(2627)``, ``Msg 2627`` and ``error 2627`` cover the forms
# pyodbc, ODBC and SQL Server itself produce. The four-digit bound avoids
# mistaking SQLSTATE values such as ``08001`` for native error numbers.
_MESSAGE_CODE_PATTERNS = (
    re.compile(r"\[(\d{1,4})\]"),
    re.compile(r"\((\d{1,4})\)"),
    re.compile(r"\bmsg\s*(\d{1,4})\b", re.IGNORECASE),
    re.compile(r"\berror\s+(\d{1,4})\b", re.IGNORECASE),
)


def normalize_integrity_message(message: str) -> str:
    """Add the cross-backend ``cannot be null`` phrase to 515 messages."""
    lowered = message.lower()
    if "does not allow nulls" in lowered or "cannot insert the value null" in lowered:
        if "cannot be null" not in lowered:
            message = message + " - cannot be null"
    return message


def extract_driver_code(error: Exception) -> Optional[int]:
    """Return the SQL Server native error number, when one can be recovered.

    ``args`` is tried first because a numeric first argument is the most
    direct signal. The message is then scanned for the ``[2627]``/``(2627)``/
    ``Msg 2627`` forms SQL Server uses. SQLSTATE strings such as ``23000``
    are deliberately not treated as native error numbers.
    """
    for arg in getattr(error, "args", ()) or ():
        if isinstance(arg, int) and not isinstance(arg, bool):
            return arg
        if isinstance(arg, str) and arg.isdigit() and len(arg) <= 4:
            return int(arg)

    message = str(error)
    for pattern in _MESSAGE_CODE_PATTERNS:
        match = pattern.search(message)
        if match:
            return int(match.group(1))
    return None


def _matches(lowered: str, patterns) -> bool:
    return any(pattern in lowered for pattern in patterns)


def _translated(
    error_type,
    message: str,
    driver_code: Optional[int],
    *,
    transient: bool,
) -> DatabaseError:
    return attach_diagnostics(
        error_type(message),
        operation=OPERATION_NAME,
        sqlstate=None,
        driver_code=driver_code,
        backend=BACKEND_NAME,
        transient=transient,
    )


def classify_sqlserver_error(error: Exception) -> DatabaseError:
    """Map a pyodbc or synthetic driver exception onto a taxonomy error.

    The returned instance is annotated but not raised; callers raise it
    ``from error`` so the driver exception stays in the chain.

    Args:
        error: Exception raised by pyodbc, aioodbc or a test double.

    Returns:
        An :class:`~rhosocial.activerecord.backend.errors.DatabaseError`
        instance from the shared taxonomy.
    """
    message = str(error)
    lowered = message.lower()
    driver_code = extract_driver_code(error)

    # 1. Native error number: stable across message wording changes.
    if driver_code in UNIQUE_VIOLATION_CODES:
        return _translated(
            IntegrityError,
            f"Unique constraint violation: {message}",
            driver_code,
            transient=False,
        )
    if driver_code == FOREIGN_KEY_VIOLATION_CODE:
        return _translated(
            IntegrityError,
            f"Foreign key constraint violation: {message}",
            driver_code,
            transient=False,
        )
    if driver_code == NOT_NULL_VIOLATION_CODE:
        return _translated(
            IntegrityError,
            normalize_integrity_message(message),
            driver_code,
            transient=False,
        )
    if driver_code == DEADLOCK_CODE:
        return _translated(DeadlockError, message, driver_code, transient=True)
    if driver_code == LOCK_TIMEOUT_CODE:
        return _translated(LockError, message, driver_code, transient=True)
    if driver_code == LOGIN_FAILED_CODE:
        return _translated(
            ConnectionError,
            f"Login failed: {message}",
            driver_code,
            transient=False,
        )
    if driver_code == CANNOT_OPEN_DATABASE_CODE:
        return _translated(ConnectionError, message, driver_code, transient=False)
    if driver_code == INVALID_OBJECT_CODE:
        return _translated(QueryError, message, driver_code, transient=False)
    if driver_code in SYNTAX_ERROR_CODES:
        return _translated(QueryError, message, driver_code, transient=False)
    if driver_code in PERMISSION_DENIED_CODES:
        # Retrying a permission failure never helps; keep the generic type so
        # callers that only distinguish infrastructure from data still work.
        return _translated(DatabaseError, message, driver_code, transient=False)
    if driver_code in NETWORK_ERROR_CODES:
        return _translated(OperationalError, message, driver_code, transient=True)

    # 2. Message text. It is the fallback for drivers that omit the number and
    # for synthetic exceptions used in unit tests.
    if _matches(lowered, _UNIQUE_MESSAGE_PATTERNS):
        return _translated(
            IntegrityError,
            f"Unique constraint violation: {message}",
            driver_code,
            transient=False,
        )
    if _matches(lowered, _FOREIGN_KEY_MESSAGE_PATTERNS):
        return _translated(
            IntegrityError,
            f"Foreign key constraint violation: {message}",
            driver_code,
            transient=False,
        )
    if _matches(lowered, _NOT_NULL_MESSAGE_PATTERNS):
        return _translated(
            IntegrityError,
            normalize_integrity_message(message),
            driver_code,
            transient=False,
        )
    if _matches(lowered, _INTEGRITY_MESSAGE_PATTERNS):
        return _translated(
            IntegrityError,
            normalize_integrity_message(message),
            driver_code,
            transient=False,
        )
    if _matches(lowered, _DEADLOCK_MESSAGE_PATTERNS):
        return _translated(DeadlockError, message, driver_code, transient=True)
    if _matches(lowered, _LOCK_TIMEOUT_MESSAGE_PATTERNS):
        return _translated(LockError, message, driver_code, transient=True)
    if _matches(lowered, _LOGIN_MESSAGE_PATTERNS):
        return _translated(
            ConnectionError,
            f"Login failed: {message}",
            driver_code,
            transient=False,
        )
    if _matches(lowered, _CANNOT_OPEN_DATABASE_PATTERNS):
        return _translated(ConnectionError, message, driver_code, transient=False)
    if _matches(lowered, _INVALID_OBJECT_MESSAGE_PATTERNS):
        return _translated(QueryError, message, driver_code, transient=False)
    if _matches(lowered, _SYNTAX_MESSAGE_PATTERNS):
        return _translated(QueryError, message, driver_code, transient=False)
    if _matches(lowered, _PERMISSION_MESSAGE_PATTERNS):
        return _translated(DatabaseError, message, driver_code, transient=False)
    if _matches(lowered, _CONNECTION_MESSAGE_PATTERNS):
        return _translated(OperationalError, message, driver_code, transient=True)

    # 3. Driver exception class. pyodbc maps SQLSTATE families onto DB-API
    # classes, so this catches errors whose text is not distinctive.
    try:
        import pyodbc
    except ImportError:  # pragma: no cover - pyodbc is a hard dependency
        pyodbc = None

    if pyodbc is not None:
        if isinstance(error, pyodbc.IntegrityError):
            return _translated(
                IntegrityError,
                normalize_integrity_message(message),
                driver_code,
                transient=False,
            )
        if isinstance(error, pyodbc.ProgrammingError):
            return _translated(QueryError, message, driver_code, transient=False)
        if isinstance(error, pyodbc.InterfaceError):
            return _translated(ConnectionError, message, driver_code, transient=False)
        if isinstance(error, pyodbc.OperationalError):
            return _translated(OperationalError, message, driver_code, transient=True)
        if isinstance(error, (pyodbc.DatabaseError, pyodbc.Error)):
            return _translated(DatabaseError, message, driver_code, transient=False)

    # 4. Unknown exception: keep the generic database error contract.
    return _translated(DatabaseError, message, driver_code, transient=False)
