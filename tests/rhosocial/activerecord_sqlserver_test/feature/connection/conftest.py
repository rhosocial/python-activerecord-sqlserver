# tests/rhosocial/activerecord_sqlserver_test/feature/connection/conftest.py
"""
Pytest configuration for connection pool tests.

This module provides fixtures for testing connection pools with SQL Server backends.
"""

import asyncio
import sys
import os
from typing import Dict, Any, Generator

import pytest
import pytest_asyncio
import yaml

from rhosocial.activerecord.backend.impl.mysql import SQLServerBackend, AsyncSQLServerBackend
from rhosocial.activerecord.backend.impl.mysql.config import SQLServerConnectionConfig
from rhosocial.activerecord.connection.pool import (
    PoolConfig,
    BackendPool,
    AsyncBackendPool,
)


def ensure_compatible_event_loop():
    """Ensure event loop compatibility on Windows."""
    if sys.platform == "win32":
        policy = asyncio.get_event_loop_policy()
        if not isinstance(policy, asyncio.WindowsSelectorEventLoopPolicy):
            new_policy = asyncio.WindowsSelectorEventLoopPolicy()
            asyncio.set_event_loop_policy(new_policy)


ensure_compatible_event_loop()

# --- Scenario Loading Logic ---

SCENARIO_MAP: Dict[str, Dict[str, Any]] = {}


def register_scenario(name: str, config: Dict[str, Any]):
    SCENARIO_MAP[name] = config


def _load_scenarios_from_config():
    """Load scenarios from a configuration file."""
    config_path = None
    env_config_path = os.getenv("MYSQL_SCENARIOS_CONFIG_PATH")

    if env_config_path and os.path.exists(env_config_path):
        config_path = env_config_path
    else:
        default_path = os.path.join(os.path.dirname(__file__), "../../../../config", "mysql_scenarios.yaml")
        if os.path.exists(default_path):
            config_path = default_path
        elif env_config_path:
            print(f"Warning: Scenario file specified in MYSQL_SCENARIOS_CONFIG_PATH not found: {env_config_path}")
            return

    if not config_path:
        raise FileNotFoundError(
            "No SQLServer scenarios configuration file found. "
            "Set MYSQL_SCENARIOS_CONFIG_PATH or place mysql_scenarios.yaml in tests/config."
        )

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        if "scenarios" not in config_data:
            raise ValueError(f"Configuration file {config_path} does not contain 'scenarios' key")

        for scenario_name, config in config_data["scenarios"].items():
            if config:
                register_scenario(scenario_name, config)

    except ImportError:
        raise ImportError("PyYAML is required to load scenario configuration files")  # noqa: B904


_load_scenarios_from_config()


def get_scenario_config(name: str) -> Dict[str, Any]:
    if name not in SCENARIO_MAP:
        if SCENARIO_MAP:
            name = next(iter(SCENARIO_MAP))
        else:
            raise ValueError("No scenarios registered or enabled")
    return SCENARIO_MAP[name]


def get_scenario_names():
    return list(SCENARIO_MAP.keys())


# --- Pool Fixtures ---


def create_mysql_backend_factory(config_dict: Dict[str, Any]):
    """Create a factory function that produces SQLServerBackend instances."""

    def factory():
        config_copy = config_dict.copy()
        ssl_disabled = config_copy.pop("ssl_disabled", None)
        config = SQLServerConnectionConfig(**config_copy)
        if ssl_disabled is not None:
            config.ssl_disabled = ssl_disabled
        backend = SQLServerBackend(connection_config=config)
        backend.connect()
        return backend

    return factory


def create_async_mysql_backend_factory(config_dict: Dict[str, Any]):
    """Create a factory function that produces AsyncSQLServerBackend instances."""

    def factory():
        config_copy = config_dict.copy()
        ssl_disabled = config_copy.pop("ssl_disabled", None)
        config = SQLServerConnectionConfig(**config_copy)
        if ssl_disabled is not None:
            config.ssl_disabled = ssl_disabled
        backend = AsyncSQLServerBackend(connection_config=config)
        # Note: connect() will be called by the pool when needed
        return backend

    return factory


@pytest.fixture(scope="function", params=get_scenario_names())
def mysql_pool(request) -> Generator[BackendPool, None, None]:
    """Create a BackendPool with SQL Server backends for testing."""
    scenario_name = request.param
    config_dict = get_scenario_config(scenario_name).copy()

    pool_config = PoolConfig(
        min_size=1,
        max_size=5,
        timeout=30.0,
        validate_on_borrow=True,
        validation_query="SELECT 1",
        backend_factory=create_mysql_backend_factory(config_dict),
    )

    pool = BackendPool.create(pool_config)
    yield pool
    pool.close(timeout=5.0, force=True)


@pytest_asyncio.fixture(scope="function", params=get_scenario_names())
async def async_mysql_pool(request) -> AsyncBackendPool:
    """Create an AsyncBackendPool with SQL Server backends for testing."""
    scenario_name = request.param
    config_dict = get_scenario_config(scenario_name).copy()

    pool_config = PoolConfig(
        min_size=1,
        max_size=5,
        timeout=30.0,
        validate_on_borrow=True,
        validation_query="SELECT 1",
        backend_factory=create_async_mysql_backend_factory(config_dict),
    )

    pool = await AsyncBackendPool.create(pool_config)
    yield pool
    await pool.close(timeout=5.0, force=True)


@pytest.fixture(scope="function", params=get_scenario_names())
def mysql_pool_large(request) -> Generator[BackendPool, None, None]:
    """Create a larger BackendPool for stress testing."""
    scenario_name = request.param
    config_dict = get_scenario_config(scenario_name).copy()

    pool_config = PoolConfig(
        min_size=1,
        max_size=5,
        timeout=60.0,
        validate_on_borrow=False,  # Faster for stress tests
        backend_factory=create_mysql_backend_factory(config_dict),
    )

    pool = BackendPool.create(pool_config)
    yield pool
    pool.close(timeout=5.0, force=True)


@pytest_asyncio.fixture(scope="function", params=get_scenario_names())
async def async_mysql_pool_large(request) -> AsyncBackendPool:
    """Create a larger AsyncBackendPool for stress testing."""
    scenario_name = request.param
    config_dict = get_scenario_config(scenario_name).copy()

    pool_config = PoolConfig(
        min_size=1,
        max_size=5,
        timeout=60.0,
        validate_on_borrow=False,
        backend_factory=create_async_mysql_backend_factory(config_dict),
    )

    pool = await AsyncBackendPool.create(pool_config)
    yield pool
    await pool.close(timeout=5.0, force=True)


# --- Table Setup Fixtures ---


@pytest.fixture(scope="function")
def mysql_pool_with_tables(mysql_pool: BackendPool) -> Generator[BackendPool, None, None]:
    """Create a pool with test tables initialized."""
    with mysql_pool.connection() as backend:
        backend.execute("DROP TABLE IF EXISTS concurrent_test_users")
        backend.execute("DROP TABLE IF EXISTS concurrent_test_posts")
        backend.execute("""
            CREATE TABLE concurrent_test_users (
                id INT IDENTITY(1,1) PRIMARY KEY,
                thread_id INTEGER,
                name VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        backend.execute("""
            CREATE TABLE concurrent_test_posts (
                id INT IDENTITY(1,1) PRIMARY KEY,
                thread_id INTEGER,
                user_id INTEGER,
                title VARCHAR(255),
                content TEXT
            )
        """)

    yield mysql_pool

    with mysql_pool.connection() as backend:
        backend.execute("DROP TABLE IF EXISTS concurrent_test_posts")
        backend.execute("DROP TABLE IF EXISTS concurrent_test_users")


@pytest_asyncio.fixture(scope="function")
async def async_mysql_pool_with_tables(async_mysql_pool: AsyncBackendPool) -> AsyncBackendPool:
    """Create an async pool with test tables initialized."""
    async with async_mysql_pool.connection() as backend:
        await backend.execute("DROP TABLE IF EXISTS concurrent_test_users")
        await backend.execute("DROP TABLE IF EXISTS concurrent_test_posts")
        await backend.execute("""
            CREATE TABLE concurrent_test_users (
                id INT IDENTITY(1,1) PRIMARY KEY,
                task_id INTEGER,
                name VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await backend.execute("""
            CREATE TABLE concurrent_test_posts (
                id INT IDENTITY(1,1) PRIMARY KEY,
                task_id INTEGER,
                user_id INTEGER,
                title VARCHAR(255),
                content TEXT
            )
        """)

    yield async_mysql_pool

    async with async_mysql_pool.connection() as backend:
        await backend.execute("DROP TABLE IF EXISTS concurrent_test_posts")
        await backend.execute("DROP TABLE IF EXISTS concurrent_test_users")
