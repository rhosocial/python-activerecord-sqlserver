# tests/rhosocial/activerecord_sqlserver_test/feature/connection/conftest.py
"""Pytest configuration for connection pool tests.

The pool fixtures exercise the pool itself, so their connections open on the
directory's own database: ``database_config`` creates it once per scenario and
hands every pool fixture the scenario and its connection configuration.
Depending on ``database_config`` is also what pins this directory's tests to one
worker per scenario -- without it two workers could plant the shared
``concurrent_test_*`` tables in the same database at the same time, which is
what turned MySQL's concurrency tests red.

The tables the ``*_with_tables`` fixtures create and drop through the pool are
declared in ``pool_definitions.py``: a definition class takes a ``dialect``
only, so this conftest holds no SQL of its own.
"""
from rhosocial.activerecord.testsuite.pytest_plugin import Declaration

from typing import Generator

import pytest
import pytest_asyncio
from rhosocial.activerecord.connection.pool import (
    AsyncBackendPool,
    BackendPool,
    PoolConfig,
)

from pool_definitions import (
    AsyncConcurrentTestPostsDefinition,
    AsyncConcurrentTestUsersDefinition,
    ConcurrentTestPostsDefinition,
    ConcurrentTestUsersDefinition,
)


# No event loop workaround is needed on Windows. This backend's async driver
# (aioodbc, which drives pyodbc) runs its work in a thread pool rather than
# registering the socket with the loop, so the platform's default
# ProactorEventLoop serves it fine; only a driver that registers the socket
# itself (the way psycopg does) requires a selector loop. A
# `WindowsSelectorEventLoopPolicy` switch used to sit here, copied from the
# postgres suite -- it is deprecated for removal in Python 3.16, and
# switching it would take asyncio subprocess and pipe I/O down with it. Do
# not reintroduce it: if a future driver needs a selector loop, follow the
# postgres suite's pytest_asyncio_loop_factories hook instead, which scopes
# the choice to the tests rather than the process.


# --- directory contract: the directory's identity for xdist grouping ---




# This directory owns a database shared by all its tests within a scenario;
# pin them to one worker so setup/teardown never races on the same database.
DECLARATION = Declaration(
    parallel=True,
    purpose="Directory-owned database shared by this test group.",
)

@pytest.fixture(scope="session")
def database_config(backend_scenario):
    """The scenario, its connection configuration, and the database name.

    The pool fixtures above own their connections, so this directory creates
    no shared ``database`` backend; the database is still the directory's own
    (``test_connection``), emptied once per scenario here -- the job the old
    ``ensure_database`` hook did -- so every pool opens on a clean database
    with ``READ_COMMITTED_SNAPSHOT`` on.
    """
    name = "test_connection"
    backend_scenario.reset_database(name)
    return backend_scenario, backend_scenario.make_config(name), name


# --- Pool Fixtures ---


@pytest.fixture(scope="function")
def sqlserver_pool(database_config) -> Generator[BackendPool, None, None]:
    """Create a BackendPool with SQL Server backends for testing."""
    scenario, config, _name = database_config
    pool_config = PoolConfig(
        min_size=1,
        max_size=5,
        timeout=30.0,
        validate_on_borrow=True,
        validation_query="SELECT 1",
        backend_factory=lambda: scenario.backend_class(connection_config=config),
    )

    pool = BackendPool.create(pool_config)
    yield pool
    pool.close(timeout=5.0, force=True)


@pytest_asyncio.fixture(scope="function")
async def async_sqlserver_pool(database_config) -> AsyncBackendPool:
    """Create an AsyncBackendPool with SQL Server backends for testing."""
    scenario, config, _name = database_config
    pool_config = PoolConfig(
        min_size=1,
        max_size=5,
        timeout=30.0,
        validate_on_borrow=True,
        validation_query="SELECT 1",
        backend_factory=lambda: scenario.async_backend_class(connection_config=config),
    )

    pool = await AsyncBackendPool.create(pool_config)
    yield pool
    await pool.close(timeout=5.0, force=True)


@pytest.fixture(scope="function")
def sqlserver_pool_large(database_config) -> Generator[BackendPool, None, None]:
    """Create a larger BackendPool for stress testing."""
    scenario, config, _name = database_config
    pool_config = PoolConfig(
        min_size=1,
        max_size=5,
        timeout=60.0,
        validate_on_borrow=False,  # Faster for stress tests
        backend_factory=lambda: scenario.backend_class(connection_config=config),
    )

    pool = BackendPool.create(pool_config)
    yield pool
    pool.close(timeout=5.0, force=True)


@pytest_asyncio.fixture(scope="function")
async def async_sqlserver_pool_large(database_config) -> AsyncBackendPool:
    """Create a larger AsyncBackendPool for stress testing."""
    scenario, config, _name = database_config
    pool_config = PoolConfig(
        min_size=1,
        max_size=5,
        timeout=60.0,
        validate_on_borrow=False,
        backend_factory=lambda: scenario.async_backend_class(connection_config=config),
    )

    pool = await AsyncBackendPool.create(pool_config)
    yield pool
    await pool.close(timeout=5.0, force=True)


# --- Table Setup Fixtures ---


@pytest.fixture(scope="function")
def sqlserver_pool_with_tables(sqlserver_pool: BackendPool) -> Generator[BackendPool, None, None]:
    """Create a pool with test tables initialized."""
    definitions = (
        ConcurrentTestPostsDefinition,
        ConcurrentTestUsersDefinition,
    )
    with sqlserver_pool.connection() as backend:
        fixtures = [definition(backend.dialect) for definition in definitions]
        for fixture in fixtures:
            backend.execute(*fixture.drop_table.to_sql())
            backend.execute(*fixture.create_table.to_sql())

    yield sqlserver_pool

    with sqlserver_pool.connection() as backend:
        for fixture in reversed(fixtures):
            backend.execute(*fixture.drop_table.to_sql())


@pytest_asyncio.fixture(scope="function")
async def async_sqlserver_pool_with_tables(
    async_sqlserver_pool: AsyncBackendPool,
) -> AsyncBackendPool:
    """Create an async pool with test tables initialized."""
    definitions = (
        AsyncConcurrentTestPostsDefinition,
        AsyncConcurrentTestUsersDefinition,
    )
    async with async_sqlserver_pool.connection() as backend:
        fixtures = [definition(backend.dialect) for definition in definitions]
        for fixture in fixtures:
            await backend.execute(*fixture.drop_table.to_sql())
            await backend.execute(*fixture.create_table.to_sql())

    yield async_sqlserver_pool

    async with async_sqlserver_pool.connection() as backend:
        for fixture in reversed(fixtures):
            await backend.execute(*fixture.drop_table.to_sql())