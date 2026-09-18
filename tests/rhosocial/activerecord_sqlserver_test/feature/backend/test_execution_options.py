from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from rhosocial.activerecord.backend.base import StorageBackend
from rhosocial.activerecord.backend.errors import DatabaseError
from rhosocial.activerecord.backend.impl.sqlserver import (
    AsyncSQLServerBackend,
    SQLServerBackend,
    SQLServerExecutionOptions,
)
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig
from rhosocial.activerecord.backend.options import ExecutionOptions, StatementType


SQL = "SELECT {fn UCASE(?)} AS [value], '?' AS [literal]"
PARAMS = ("{not an ODBC escape}",)
OPTION_CASES = [
    pytest.param(SQLServerExecutionOptions(StatementType.DQL, noscan=True), id="true"),
    pytest.param(SQLServerExecutionOptions(StatementType.DQL, noscan=False), id="false"),
    pytest.param(SQLServerExecutionOptions(StatementType.DQL, noscan=None), id="none"),
    pytest.param(ExecutionOptions(StatementType.DQL), id="core"),
]


@pytest.fixture(scope="session", autouse=True)
def _prepare_read_committed_snapshot():
    return None


@pytest.fixture(autouse=True)
def block_connections(monkeypatch):
    monkeypatch.setattr(
        SQLServerBackend, "connect", MagicMock(side_effect=AssertionError("Unexpected database connection"))
    )
    monkeypatch.setattr(
        AsyncSQLServerBackend, "connect", AsyncMock(side_effect=AssertionError("Unexpected database connection"))
    )


class NativeCursor:
    def __init__(self, noscan):
        self._noscan = noscan
        self.accesses = []

    @property
    def noscan(self):
        self.accesses.append(("get",))
        return self._noscan

    @noscan.setter
    def noscan(self, value):
        self.accesses.append(("set", value))
        self._noscan = value


class AsyncCursor:
    def __init__(self, previous, error=None):
        self._impl = NativeCursor(previous)
        self.noscan = "wrapper must not change"
        self.operations = []
        self.executions = []
        self.error = error
        self.description = None
        self.rowcount = 0
        self.lastrowid = None
        self.exit_value = None

    async def _run_operation(self, operation, *args):
        self.operations.append((operation, args))
        return operation(*args)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self.exit_value = self._impl._noscan

    async def execute(self, sql, params):
        self.executions.append((sql, params, self._impl._noscan, self.noscan))
        if self.error is not None:
            raise self.error


def make_backend(backend_class):
    config = SQLServerConnectionConfig(host="localhost", database="master", username="sa", password="")
    backend = backend_class(connection_config=config)
    backend._connection = object()
    return backend


def expected_accesses(noscan, previous):
    return [] if noscan is None else [("get",), ("set", noscan), ("set", previous)]


def test_execution_options_default():
    options = SQLServerExecutionOptions(StatementType.DQL)
    assert isinstance(options, ExecutionOptions)
    assert options.noscan is None


@pytest.mark.parametrize("options", OPTION_CASES)
@pytest.mark.parametrize("fails", [False, True], ids=["success", "error"])
@pytest.mark.parametrize("outer", [None, True, False])
def test_sync_execution_restores_cursor_and_context(monkeypatch, options, fails, outer):
    backend = make_backend(SQLServerBackend)
    assert backend._execution_noscan.get() is None
    noscan = getattr(options, "noscan", None)
    previous = noscan is not True
    cursor = NativeCursor(previous)
    error = RuntimeError("execution failed")
    executions = []
    delegated = []

    def execute(sql, params):
        executions.append((sql, params, cursor._noscan))
        if fails:
            raise error

    cursor.execute = execute

    def core_execute(self, sql, params, *, options):
        delegated.append((sql, params, options, self._execution_noscan.get()))
        return self._execute_query(cursor, sql, params)

    monkeypatch.setattr(StorageBackend, "execute", core_execute)
    token = backend._execution_noscan.set(outer)
    try:
        if fails:
            with pytest.raises(RuntimeError, match="execution failed") as caught:
                backend.execute(SQL, PARAMS, options=options)
            assert caught.value is error
        else:
            assert backend.execute(SQL, PARAMS, options=options) is cursor
        assert backend._execution_noscan.get() is outer
        assert cursor._noscan is previous
        assert cursor.accesses == expected_accesses(noscan, previous)
        assert delegated == [(SQL, PARAMS, options, noscan)]
        assert delegated[0][2] is options
        assert executions == [(SQL, PARAMS, previous if noscan is None else noscan)]
    finally:
        backend._execution_noscan.reset(token)

    assert backend._execution_noscan.get() is None
    fails = False
    cursor.accesses.clear()
    assert backend.execute(SQL, PARAMS) is cursor
    assert backend._execution_noscan.get() is None
    assert executions[-1] == (SQL, PARAMS, previous)
    assert len(executions) == 2
    assert type(delegated[-1][2]) is ExecutionOptions
    assert delegated[-1][3] is None
    assert cursor.accesses == []


@pytest.mark.parametrize("options", OPTION_CASES)
@pytest.mark.parametrize("fails", [False, True], ids=["success", "error"])
@pytest.mark.parametrize("previous", [False, True])
@pytest.mark.asyncio
async def test_async_statement_uses_native_noscan(monkeypatch, options, fails, previous):
    backend = make_backend(AsyncSQLServerBackend)
    noscan = getattr(options, "noscan", None)
    cursor = AsyncCursor(previous, RuntimeError("execution failed") if fails else None)
    monkeypatch.setattr(backend, "_get_cursor", AsyncMock(return_value=cursor))
    monkeypatch.setattr(backend, "_handle_auto_commit_if_needed", AsyncMock())

    if fails:
        with pytest.raises(DatabaseError, match="execution failed"):
            await backend.execute(SQL, PARAMS, options=options)
    else:
        result = await backend.execute(SQL, PARAMS, options=options)
        assert result.affected_rows == 0
        assert result.data is None

    assert cursor.executions == [
        (SQL, PARAMS, previous if noscan is None else noscan, "wrapper must not change")
    ]
    assert cursor._impl._noscan is previous
    assert cursor.exit_value is previous
    assert cursor.noscan == "wrapper must not change"
    assert cursor._impl.accesses == expected_accesses(noscan, previous)
    assert cursor.operations == ([] if noscan is None else [
        (getattr, (cursor._impl, "noscan")),
        (setattr, (cursor._impl, "noscan", noscan)),
        (setattr, (cursor._impl, "noscan", previous)),
    ])

    cursor.error = None
    cursor.operations.clear()
    cursor._impl.accesses.clear()
    await backend.execute(SQL, PARAMS)
    assert cursor.executions[-1] == (SQL, PARAMS, previous, "wrapper must not change")
    assert len(cursor.executions) == 2
    assert cursor.operations == []
    assert cursor._impl.accesses == []


@pytest.mark.parametrize("noscan", [True, False, None])
@pytest.mark.parametrize("fails", [False, True], ids=["success", "error"])
@pytest.mark.asyncio
async def test_async_cursor_noscan_context_restores_native_value(noscan, fails):
    backend = make_backend(AsyncSQLServerBackend)
    previous = noscan is not True
    cursor = AsyncCursor(previous)
    error = RuntimeError("context failed")

    async def use_context():
        async with backend._cursor_noscan(cursor, noscan):
            assert cursor._impl._noscan is (previous if noscan is None else noscan)
            assert cursor.noscan == "wrapper must not change"
            if fails:
                raise error

    if fails:
        with pytest.raises(RuntimeError, match="context failed") as caught:
            await use_context()
        assert caught.value is error
    else:
        await use_context()
    assert cursor._impl._noscan is previous
    assert cursor.noscan == "wrapper must not change"
    assert cursor._impl.accesses == expected_accesses(noscan, previous)


@pytest.mark.asyncio
async def test_async_cursor_noscan_none_does_not_require_native_cursor():
    backend = make_backend(AsyncSQLServerBackend)
    cursor = SimpleNamespace()
    async with backend._cursor_noscan(cursor, None):
        assert vars(cursor) == {}
    assert vars(cursor) == {}
