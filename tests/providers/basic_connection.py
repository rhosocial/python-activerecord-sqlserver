# tests/providers/basic_connection.py
"""
Concrete implementation of IBasicConnectionProvider for SQL Server backend.

This provider sets up connection pools and models for testing
ActiveRecord context awareness.
"""
from typing import Type, Tuple, Optional, List

from rhosocial.activerecord.model import ActiveRecord, AsyncActiveRecord
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig
from rhosocial.activerecord.connection.pool import BackendPool, AsyncBackendPool, PoolConfig
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

from rhosocial.activerecord.testsuite.feature.basic.connection.interfaces import IBasicConnectionProvider
from .scenarios import get_scenario, get_enabled_scenarios


class SyncTestUser(ActiveRecord):
    """Sync test user model for connection pool tests."""
    __table_name__ = "test_users"
    id: Optional[int] = None
    name: str
    email: str


class AsyncTestUser(AsyncActiveRecord):
    """Async test user model for connection pool tests."""
    __table_name__ = "test_users"
    id: Optional[int] = None
    name: str
    email: str


class BasicConnectionProvider(IBasicConnectionProvider):
    """
    SQL Server backend implementation for basic connection pool context tests.
    """

    def __init__(self):
        self._active_backends: List = []
        self._active_async_backends: List = []

    def get_test_scenarios(self) -> list:
        """Returns available test scenarios."""
        return list(get_enabled_scenarios().keys())

    def _create_test_table(self, backend):
        """Create the test_users table."""
        try:
            backend.execute("DROP TABLE IF EXISTS test_users", options=ExecutionOptions(stmt_type=StatementType.DDL))
        except Exception:
            pass

        backend.execute("""
            CREATE TABLE test_users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL
            )
        """, options=ExecutionOptions(stmt_type=StatementType.DDL))

    async def _create_test_table_async(self, backend):
        """Create the test_users table asynchronously."""
        try:
            await backend.execute("DROP TABLE IF EXISTS test_users", options=ExecutionOptions(stmt_type=StatementType.DDL))
        except Exception:
            pass

        await backend.execute("""
            CREATE TABLE test_users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL
            )
        """, options=ExecutionOptions(stmt_type=StatementType.DDL))

    def setup_sync_pool_and_model(self, scenario_name: str) -> Tuple[BackendPool, Type[ActiveRecord]]:
        """Setup sync connection pool and model for context tests."""
        _, config = get_scenario(scenario_name)

        pool_config = PoolConfig(
            min_size=1,
            max_size=5,
            backend_factory=lambda: SQLServerBackend(connection_config=config)
        )
        pool = BackendPool.create(pool_config)

        with pool.connection() as backend:
            self._create_test_table(backend)
            self._active_backends.append(backend)

        SyncTestUser.configure(config, SQLServerBackend)
        self._active_backends.append(SyncTestUser.__backend__)

        return pool, SyncTestUser

    async def setup_async_pool_and_model(self, scenario_name: str) -> Tuple[AsyncBackendPool, Type[AsyncActiveRecord]]:
        """Setup async connection pool and model for context tests."""
        from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend

        _, config = get_scenario(scenario_name)

        pool_config = PoolConfig(
            min_size=1,
            max_size=5,
            backend_factory=lambda: AsyncSQLServerBackend(connection_config=config)
        )

        pool = await AsyncBackendPool.create(pool_config)

        async with pool.connection() as backend:
            await self._create_test_table_async(backend)
            self._active_async_backends.append(backend)

        await AsyncTestUser.configure(config, AsyncSQLServerBackend)
        self._active_async_backends.append(AsyncTestUser.__backend__)

        return pool, AsyncTestUser

    def cleanup_sync(self, scenario_name: str, pool: BackendPool):
        """Cleanup after sync tests."""
        pool.close(timeout=1.0)

        for backend in self._active_backends:
            try:
                backend.disconnect()
            except Exception:
                pass
        self._active_backends.clear()

    async def cleanup_async(self, scenario_name: str, pool: AsyncBackendPool):
        """Cleanup after async tests."""
        await pool.close(timeout=1.0)

        for backend in self._active_async_backends:
            try:
                await backend.disconnect()
            except Exception:
                pass
        self._active_async_backends.clear()

    def setup_sync_pool_for_crud(self, scenario_name: str) -> Tuple[BackendPool, Type[ActiveRecord]]:
        """Setup sync connection pool for CRUD tests."""
        return self.setup_sync_pool_and_model(scenario_name)

    async def setup_async_pool_for_crud(self, scenario_name: str) -> Tuple[AsyncBackendPool, Type[AsyncActiveRecord]]:
        """Setup async connection pool for CRUD tests."""
        return await self.setup_async_pool_and_model(scenario_name)