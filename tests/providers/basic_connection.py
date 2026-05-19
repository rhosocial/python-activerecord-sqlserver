from typing import Type, Tuple, Optional, List

from rhosocial.activerecord.model import ActiveRecord, AsyncActiveRecord
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig
from rhosocial.activerecord.connection.pool import BackendPool, AsyncBackendPool, PoolConfig
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

from rhosocial.activerecord.backend.expression.statements import (
    DropTableExpression, CreateTableExpression, ColumnDefinition, ColumnConstraint,
    ColumnConstraintType
)

from rhosocial.activerecord.testsuite.feature.basic.connection.interfaces import IBasicConnectionProvider
from .scenarios import get_scenario, get_enabled_scenarios


class SyncTestUser(ActiveRecord):
    __table_name__ = "test_users"
    id: Optional[int] = None
    name: str
    email: str


class AsyncTestUser(AsyncActiveRecord):
    __table_name__ = "test_users"
    id: Optional[int] = None
    name: str
    email: str


class BasicConnectionProvider(IBasicConnectionProvider):

    def __init__(self):
        self._active_backends: List = []
        self._active_async_backends: List = []

    def get_test_scenarios(self) -> list:
        return list(get_enabled_scenarios().keys())

    def _create_test_table(self, backend):
        expr = DropTableExpression(backend.dialect, "test_users", if_exists=True)
        backend.execute(*expr.to_sql(), options=ExecutionOptions(stmt_type=StatementType.DDL))
        columns = [
            ColumnDefinition("id", "INT", [
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True),
            ]),
            ColumnDefinition("name", "NVARCHAR(255)", [
                ColumnConstraint(ColumnConstraintType.NOT_NULL),
            ]),
            ColumnDefinition("email", "NVARCHAR(255)", [
                ColumnConstraint(ColumnConstraintType.NOT_NULL),
            ]),
        ]
        create_expr = CreateTableExpression(backend.dialect, "test_users", columns=columns)
        backend.execute(*create_expr.to_sql(), options=ExecutionOptions(stmt_type=StatementType.DDL))

    async def _create_test_table_async(self, backend):
        expr = DropTableExpression(backend.dialect, "test_users", if_exists=True)
        await backend.execute(*expr.to_sql(), options=ExecutionOptions(stmt_type=StatementType.DDL))
        columns = [
            ColumnDefinition("id", "INT", [
                ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True),
            ]),
            ColumnDefinition("name", "NVARCHAR(255)", [
                ColumnConstraint(ColumnConstraintType.NOT_NULL),
            ]),
            ColumnDefinition("email", "NVARCHAR(255)", [
                ColumnConstraint(ColumnConstraintType.NOT_NULL),
            ]),
        ]
        create_expr = CreateTableExpression(backend.dialect, "test_users", columns=columns)
        await backend.execute(*create_expr.to_sql(), options=ExecutionOptions(stmt_type=StatementType.DDL))

    def setup_sync_pool_and_model(self, scenario_name: str) -> Tuple[BackendPool, Type[ActiveRecord]]:
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
        pool.close(timeout=1.0)
        for backend in self._active_backends:
            try:
                backend.disconnect()
            except Exception:
                pass
        self._active_backends.clear()

    async def cleanup_async(self, scenario_name: str, pool: AsyncBackendPool):
        await pool.close(timeout=1.0)
        for backend in self._active_async_backends:
            try:
                await backend.disconnect()
            except Exception:
                pass
        self._active_async_backends.clear()

    def setup_sync_pool_for_crud(self, scenario_name: str) -> Tuple[BackendPool, Type[ActiveRecord]]:
        return self.setup_sync_pool_and_model(scenario_name)

    async def setup_async_pool_for_crud(self, scenario_name: str) -> Tuple[AsyncBackendPool, Type[AsyncActiveRecord]]:
        return await self.setup_async_pool_and_model(scenario_name)
