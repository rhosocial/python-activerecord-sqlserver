# tests/rhosocial/activerecord_sqlserver_test/feature/connection/conftest.py
"""Pytest configuration for connection pool tests.

The pool fixtures exercise the pool itself, so their connections open on the
directory's own database: the testsuite creates it once per directory and
scenario, and this file declares the ``ensure_database`` / ``prepare`` /
``teardown`` contract that pins the directory's tests to one worker per
scenario.  Without the contract two workers could plant the shared
``concurrent_test_*`` tables in the same database at the same time.

The tables these tests need are created and dropped by the ``*_with_tables``
fixtures, so the contract's ``prepare`` / ``teardown`` have nothing to do.
"""

from typing import Generator

import pytest
import pytest_asyncio
from rhosocial.activerecord.connection.pool import (
    AsyncBackendPool,
    BackendPool,
    PoolConfig,
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


def _pool_config(environment, *, timeout: float, validate_on_borrow: bool) -> PoolConfig:
    """Return the pool configuration for the directory's database."""
    config = environment.make_config()
    return PoolConfig(
        min_size=1,
        max_size=5,
        timeout=timeout,
        validate_on_borrow=validate_on_borrow,
        validation_query="SELECT 1",
        backend_factory=lambda: environment.scenario.backend_class(connection_config=config),
    )


def _async_pool_config(environment, *, timeout: float, validate_on_borrow: bool) -> PoolConfig:
    """Return the async pool configuration for the directory's database."""
    config = environment.make_config()
    return PoolConfig(
        min_size=1,
        max_size=5,
        timeout=timeout,
        validate_on_borrow=validate_on_borrow,
        validation_query="SELECT 1",
        backend_factory=lambda: environment.scenario.async_backend_class(connection_config=config),
    )


# --- directory contract: keep this directory on one worker per scenario ---


def ensure_database(environment):
    """Create the directory's database before the first test of this scenario."""
    environment.reset_database()


def prepare(environment):
    """Nothing to prepare: the ``*_with_tables`` fixtures own their tables."""


def teardown(environment):
    """Nothing to drop: the ``*_with_tables`` fixtures drop their tables."""


# --- Pool Fixtures ---


@pytest.fixture(scope="function")
def sqlserver_pool(environment) -> Generator[BackendPool, None, None]:
    """Create a BackendPool with SQL Server backends for testing."""
    pool = BackendPool.create(_pool_config(environment, timeout=30.0, validate_on_borrow=True))
    yield pool
    pool.close(timeout=5.0, force=True)


@pytest_asyncio.fixture(scope="function")
async def async_sqlserver_pool(environment) -> AsyncBackendPool:
    """Create an AsyncBackendPool with SQL Server backends for testing."""
    pool = await AsyncBackendPool.create(
        _async_pool_config(environment, timeout=30.0, validate_on_borrow=True)
    )
    yield pool
    await pool.close(timeout=5.0, force=True)


@pytest.fixture(scope="function")
def sqlserver_pool_large(environment) -> Generator[BackendPool, None, None]:
    """Create a larger BackendPool for stress testing."""
    pool = BackendPool.create(_pool_config(environment, timeout=60.0, validate_on_borrow=False))
    yield pool
    pool.close(timeout=5.0, force=True)


@pytest_asyncio.fixture(scope="function")
async def async_sqlserver_pool_large(environment) -> AsyncBackendPool:
    """Create a larger AsyncBackendPool for stress testing."""
    pool = await AsyncBackendPool.create(
        _async_pool_config(environment, timeout=60.0, validate_on_borrow=False)
    )
    yield pool
    await pool.close(timeout=5.0, force=True)


# --- Table Setup Fixtures ---


@pytest.fixture(scope="function")
def sqlserver_pool_with_tables(sqlserver_pool: BackendPool) -> Generator[BackendPool, None, None]:
    """Create a pool with test tables initialized."""
    with sqlserver_pool.connection() as backend:
        backend.execute("DROP TABLE IF EXISTS concurrent_test_users")
        backend.execute("DROP TABLE IF EXISTS concurrent_test_posts")
        backend.execute("""
            CREATE TABLE concurrent_test_users (
                id INT IDENTITY(1,1) PRIMARY KEY,
                thread_id INTEGER,
                name VARCHAR(255),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        backend.execute("""
            CREATE TABLE concurrent_test_posts (
                id INT IDENTITY(1,1) PRIMARY KEY,
                thread_id INTEGER,
                user_id INTEGER,
                title VARCHAR(255),
                content NVARCHAR(MAX)
            )
        """)

    yield sqlserver_pool

    with sqlserver_pool.connection() as backend:
        backend.execute("DROP TABLE IF EXISTS concurrent_test_posts")
        backend.execute("DROP TABLE IF EXISTS concurrent_test_users")


@pytest_asyncio.fixture(scope="function")
async def async_sqlserver_pool_with_tables(
    async_sqlserver_pool: AsyncBackendPool,
) -> AsyncBackendPool:
    """Create an async pool with test tables initialized."""
    async with async_sqlserver_pool.connection() as backend:
        await backend.execute("DROP TABLE IF EXISTS concurrent_test_users")
        await backend.execute("DROP TABLE IF EXISTS concurrent_test_posts")
        await backend.execute("""
            CREATE TABLE concurrent_test_users (
                id INT IDENTITY(1,1) PRIMARY KEY,
                task_id INTEGER,
                name VARCHAR(255),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await backend.execute("""
            CREATE TABLE concurrent_test_posts (
                id INT IDENTITY(1,1) PRIMARY KEY,
                task_id INTEGER,
                user_id INTEGER,
                title VARCHAR(255),
                content NVARCHAR(MAX)
            )
        """)

    yield async_sqlserver_pool

    async with async_sqlserver_pool.connection() as backend:
        await backend.execute("DROP TABLE IF EXISTS concurrent_test_posts")
        await backend.execute("DROP TABLE IF EXISTS concurrent_test_users")
