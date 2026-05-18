# src/rhosocial/activerecord/backend/impl/sqlserver/async_transaction.py
"""
SQL Server asynchronous transaction management.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List, Optional

from rhosocial.activerecord.backend.transaction import (
    TransactionState,
    IsolationLevel,
    TransactionMode,
)
from rhosocial.activerecord.backend.errors import (
    TransactionError,
    UnsupportedTransactionModeError,
)
from .transaction import SQLServerIsolationLevel, ISOLATION_LEVEL_MAP


class AsyncSQLServerTransactionManager:
    """Asynchronous SQL Server transaction manager.

    Provides async transaction management with savepoint support.
    """

    def __init__(self, backend, logger=None):
        self._backend = backend
        self._logger = logger
        self._state = TransactionState.INACTIVE
        self._savepoints: List[str] = []
        self._sqlserver_isolation_level: Optional[SQLServerIsolationLevel] = None
        self._name: Optional[str] = None

    @property
    def is_active(self) -> bool:
        """Check if a transaction is currently active."""
        return self._state == TransactionState.ACTIVE

    @property
    def state(self) -> TransactionState:
        """Get the current transaction state."""
        return self._state

    @property
    def isolation_level(self) -> Optional[IsolationLevel]:
        """Get the current isolation level."""
        return self._isolation_level

    @isolation_level.setter
    def isolation_level(self, level: Optional[IsolationLevel]):
        """Set the isolation level for the next transaction."""
        self._isolation_level = level

    async def begin(
        self,
        isolation_level: Optional[IsolationLevel] = None,
        mode: Optional[TransactionMode] = None,
        name: Optional[str] = None,
        snapshot: bool = False,
        **kwargs
    ) -> None:
        """Begin a new async transaction.

        Args:
            isolation_level: Transaction isolation level
            mode: Transaction mode (READ ONLY not supported)
            name: Optional transaction name
            snapshot: If True, use SNAPSHOT isolation level
        """
        if self._state == TransactionState.ACTIVE:
            raise TransactionError("Transaction already active")

        if mode == TransactionMode.READ_ONLY:
            raise UnsupportedTransactionModeError(
                feature="READ ONLY transactions",
                backend="SQL Server",
                message="SQL Server does not support READ ONLY transactions."
            )

        self._name = name

        # Resolve isolation level from parameter, base class property, or snapshot flag
        effective_iso = isolation_level
        if effective_iso is None and isinstance(getattr(self, '_isolation_level', None), IsolationLevel):
            effective_iso = self._isolation_level

        if snapshot:
            self._sqlserver_isolation_level = SQLServerIsolationLevel.SNAPSHOT
        elif effective_iso:
            self._sqlserver_isolation_level = ISOLATION_LEVEL_MAP.get(effective_iso)

        await self._do_begin()

        self._state = TransactionState.ACTIVE
        self._savepoints = []

        self._log(logging.DEBUG, f"Async transaction started (isolation={self._sqlserver_isolation_level})")

    async def _do_begin(self) -> None:
        """Execute the BEGIN TRANSACTION statement."""
        parts = ["BEGIN TRANSACTION"]

        if self._name:
            parts.append(self._name)

        sql = " ".join(parts)
        await self._backend.execute(sql)

        if self._sqlserver_isolation_level:
            set_iso_sql = f"SET TRANSACTION ISOLATION LEVEL {self._sqlserver_isolation_level.value}"
            await self._backend.execute(set_iso_sql)

    async def commit(self) -> None:
        """Commit the current async transaction."""
        if self._state != TransactionState.ACTIVE:
            raise TransactionError("No active transaction to commit")

        self._log(logging.DEBUG, "Committing async transaction")

        try:
            await self._do_commit()
            self._state = TransactionState.COMMITTED
            self._savepoints = []

        except Exception as e:
            self._state = TransactionState.FAILED
            self._log(logging.ERROR, f"Failed to commit async transaction: {str(e)}")
            raise

    async def _do_commit(self) -> None:
        """Execute the COMMIT TRANSACTION statement."""
        sql = "COMMIT TRANSACTION"
        if self._name:
            sql += f" {self._name}"
        await self._backend.execute(sql)

    async def rollback(self, savepoint: Optional[str] = None) -> None:
        """Rollback the async transaction or to a savepoint.

        Args:
            savepoint: If provided, rollback to this savepoint
        """
        if self._state != TransactionState.ACTIVE:
            raise TransactionError("No active transaction to rollback")

        if savepoint:
            await self._rollback_to_savepoint(savepoint)
        else:
            await self._do_rollback()
            self._state = TransactionState.ROLLED_BACK
            self._savepoints = []

    async def _do_rollback(self) -> None:
        """Execute the ROLLBACK TRANSACTION statement."""
        sql = "ROLLBACK TRANSACTION"
        if self._name:
            sql += f" {self._name}"
        await self._backend.execute(sql)

    async def savepoint(self, name: Optional[str] = None) -> str:
        """Create a savepoint within the current async transaction.

        Args:
            name: Savepoint name. If None, auto-generated.

        Returns:
            str: The name of the created savepoint
        """
        if self._state != TransactionState.ACTIVE:
            raise TransactionError("No active transaction for savepoint")

        if name is None:
            name = f"sp_{len(self._savepoints) + 1}"

        if name in self._savepoints:
            self._log(logging.WARNING, f"Savepoint '{name}' already exists")

        sql = f"SAVE TRANSACTION {name}"
        await self._backend.execute(sql)
        self._savepoints.append(name)

        self._log(logging.DEBUG, f"Async savepoint created: {name}")
        return name

    async def _rollback_to_savepoint(self, name: str) -> None:
        """Rollback to a specific savepoint."""
        if name not in self._savepoints:
            raise TransactionError(f"Savepoint '{name}' not found")

        sql = f"ROLLBACK TRANSACTION {name}"
        await self._backend.execute(sql)

        idx = self._savepoints.index(name) + 1
        self._savepoints = self._savepoints[:idx]

        self._log(logging.DEBUG, f"Rolled back to async savepoint: {name}")

    async def release_savepoint(self, name: str) -> None:
        """Release a savepoint (no-op in SQL Server).

        Args:
            name: Savepoint name
        """
        if name in self._savepoints:
            self._savepoints.remove(name)
            self._log(logging.DEBUG, f"Async savepoint released: {name}")

    def savepoints(self) -> List[str]:
        """Get list of current savepoints."""
        return self._savepoints.copy()

    @asynccontextmanager
    async def transaction(self):
        """Async context manager for transaction."""
        await self.begin()
        try:
            yield self
        except Exception:
            await self.rollback()
            raise
        else:
            await self.commit()

    def _log(self, level: int, message: str) -> None:
        """Log a message."""
        if self._logger:
            self._logger.log(level, message)
