# tests/rhosocial/activerecord_sqlserver_test/feature/backend/conftest.py
"""Fixtures for the backend-owned tests.

The backend runs these against a real server. The scenario supplies the
connection parameters; the database name is derived from the directory that
owns the test, so two directories never share tables.
"""
import os
from typing import Any, Dict, Tuple, Type

import pytest
import pytest_asyncio

import support.sqlserver

from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.backend.async_backend import (
    AsyncSQLServerBackend,
)
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig

# --- Scenario Loading Logic ---

SCENARIO_MAP: Dict[str, Dict[str, Any]] = dict(support.sqlserver.SCENARIO_MAP)


def _apply_scenario_filter():
    """Filter SCENARIO_MAP based on the active scenarios env var.

    Keeps the backend-feature scenarios consistent with the scenarios active
    for the rest of the test run.
    """
    filter_str = os.getenv("SQLSERVER_ACTIVE_SCENARIOS") or os.getenv(
        "TESTSUITE_ACTIVE_SCENARIOS"
    )
    if not filter_str:
        return
    allowed = set(s.strip() for s in filter_str.split(",") if s.strip())
    if not allowed:
        return
    for name in [n for n in SCENARIO_MAP if n not in allowed]:
        del SCENARIO_MAP[name]


_apply_scenario_filter()


def get_enabled_scenarios() -> Dict[str, Any]:
    return SCENARIO_MAP


def get_scenario_names():
    return list(get_enabled_scenarios().keys())


_PREPARED_DATABASES = set()


def database_for(request) -> str:
    """Derive the logical database the directory owning the test runs in."""
    parts = list(request.node.path.parts)
    try:
        index = max(i for i, part in enumerate(parts) if part == "backend")
    except ValueError:
        return "test_backend"
    names = [part for part in parts[index + 1 : -1] if part]
    return "test_backend" + "".join("_" + name for name in names)


def _prepare_database(scenario_name: str, database: str) -> None:
    """Create or clear the directory's database once per scenario."""
    key = (scenario_name, database)
    if key in _PREPARED_DATABASES:
        return
    support.sqlserver.scenario(scenario_name).reset_database(database)
    _PREPARED_DATABASES.add(key)


def get_scenario(
    name: str, database: str
) -> Tuple[Type[SQLServerBackend], SQLServerConnectionConfig]:
    if name not in SCENARIO_MAP:
        if not SCENARIO_MAP:
            raise ValueError("No scenarios registered")
        name = next(iter(SCENARIO_MAP))
    _prepare_database(name, database)
    return SQLServerBackend, support.sqlserver.scenario(name).make_config(database)


def pytest_collection_modifyitems(config, items):
    """Pin an execution directory's tests to one worker.

    These directories create and drop tables in the directory's own database,
    so two workers must never run tests from the same directory at once.  The
    construct directories never open a database, so they stay free to run in
    parallel.
    """
    for item in items:
        parts = item.path.parts
        if "backend" not in parts or "execute" not in parts:
            continue
        item.add_marker(
            pytest.mark.xdist_group("sqlserver-backend::" + str(item.path.parent))
        )


# --- Provider Logic ---


class BackendFeatureProvider:
    def __init__(self):
        self._backend = None
        self._async_backend = None

    def setup_backend(self, scenario_name: str, database: str):
        if self._backend:
            return self._backend
        backend_class, config = get_scenario(scenario_name, database)
        self._backend = backend_class(connection_config=config)
        self._backend.connect()
        self._backend.introspect_and_adapt()
        return self._backend

    async def setup_async_backend(self, scenario_name: str, database: str):
        if self._async_backend:
            return self._async_backend
        _, config = get_scenario(scenario_name, database)
        self._async_backend = AsyncSQLServerBackend(connection_config=config)
        await self._async_backend.connect()
        await self._async_backend.introspect_and_adapt()
        return self._async_backend

    def cleanup(self):
        if self._backend:
            self._backend.disconnect()
            self._backend = None

    async def async_cleanup(self):
        if self._async_backend:
            await self._async_backend.disconnect()
            self._async_backend = None


# --- Fixtures ---


@pytest.fixture(scope="function", params=get_scenario_names())
def sqlserver_backend(request):
    scenario_name = request.param
    provider = BackendFeatureProvider()
    backend = provider.setup_backend(scenario_name, database_for(request))
    yield backend
    provider.cleanup()


@pytest.fixture(scope="function")
def sqlserver_backend_single(request):
    """Non-parameterized fixture using the first available scenario."""
    scenario_names = get_scenario_names()
    if not scenario_names:
        pytest.skip("No SQL Server scenarios configured")
    scenario_name = scenario_names[0]
    provider = BackendFeatureProvider()
    backend = provider.setup_backend(scenario_name, database_for(request))
    yield backend
    provider.cleanup()


@pytest_asyncio.fixture(scope="function", params=get_scenario_names())
async def async_sqlserver_backend(request):
    scenario_name = request.param
    provider = BackendFeatureProvider()
    backend = await provider.setup_async_backend(scenario_name, database_for(request))
    yield backend
    await provider.async_cleanup()


@pytest_asyncio.fixture(scope="function")
async def async_sqlserver_backend_single(request):
    """Non-parameterized async fixture using the first available scenario."""
    scenario_names = get_scenario_names()
    if not scenario_names:
        pytest.skip("No SQL Server scenarios configured")
    scenario_name = scenario_names[0]
    provider = BackendFeatureProvider()
    backend = await provider.setup_async_backend(scenario_name, database_for(request))
    yield backend
    await provider.async_cleanup()


@pytest.fixture(scope="function")
def sqlserver_dialect():
    """Fixture providing SQLServerDialect instance for testing."""
    from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

    return SQLServerDialect(version=(16, 0, 0))


@pytest.fixture(scope="module")
def json_column_adapter():
    """
    Module-scoped fixture providing the SQL Server JSON string adapter.

    This adapter can be used with column_adapters parameter to automatically
    parse JSON values returned as strings by pyodbc.

    Usage:
        result = sqlserver_backend.execute(
            "SELECT data FROM table",
            column_adapters={'data': (json_column_adapter, dict)}
        )
    """
    from rhosocial.activerecord.backend.impl.sqlserver.adapters import SQLServerJSONAdapter

    return SQLServerJSONAdapter()
