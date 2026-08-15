# src/rhosocial/activerecord/backend/impl/sqlserver/async_transaction.py
"""
SQL Server asynchronous transaction management.
"""

import logging
from typing import List, Optional

from rhosocial.activerecord.backend.transaction import (
    AsyncTransactionManager,
    TransactionState,
    IsolationLevel,
    TransactionMode,
)
from rhosocial.activerecord.backend.errors import (
    TransactionError,
    UnsupportedTransactionModeError,
)
from .transaction import SQLServerIsolationLevel, ISOLATION_LEVEL_MAP


class AsyncSQLServerTransactionManager(AsyncTransactionManager):
    """Asynchronous SQL Server transaction manager.

    Provides async transaction management with savepoint support.
    Inherits the level tracking, nesting (savepoint-based) and owner-task
    bookkeeping from the core :class:`AsyncTransactionManager`, while the
    ``_do_*`` layer emits SQL Server-specific statements.
    """

    def __init__(self, backend, logger=None):
        super().__init__(backend, logger)
        self._savepoints: List[str] = []
        self._sqlserver_isolation_level: Optional[SQLServerIsolationLevel] = None
        self._name: Optional[str] = None

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
        else:
            self._sqlserver_isolation_level = None

        # Base begin() increments _transaction_level first (so is_active is
        # already True while _do_begin() executes, preventing auto-commit),
        # issues a real BEGIN at level 1 and a savepoint for nested levels.
        await super().begin()

        if self._transaction_level == 1:
            self._savepoints = []

        self.log(logging.DEBUG, f"Async transaction started (isolation={self._sqlserver_isolation_level})")

    async def _do_begin(self) -> None:
        """Execute the SET TRANSACTION ISOLATION LEVEL (if any) and BEGIN TRANSACTION."""
        if self._sqlserver_isolation_level:
            set_iso_sql = f"SET TRANSACTION ISOLATION LEVEL {self._sqlserver_isolation_level.value}"
            await self._backend.execute(set_iso_sql)

        parts = ["BEGIN TRANSACTION"]

        if self._name:
            parts.append(self._name)

        sql = " ".join(parts)
        await self._backend.execute(sql)

    async def _do_commit(self) -> None:
        """Execute the COMMIT TRANSACTION statement."""
        sql = "COMMIT TRANSACTION"
        if self._name:
            sql += f" {self._name}"
        await self._backend.execute(sql)

    async def _do_rollback(self) -> None:
        """Execute the ROLLBACK TRANSACTION statement."""
        sql = "ROLLBACK TRANSACTION"
        if self._name:
            sql += f" {self._name}"
        await self._backend.execute(sql)

    async def _do_create_savepoint(self, name: str) -> None:
        """Create a savepoint using SQL Server's SAVE TRANSACTION syntax."""
        quoted = self._backend.dialect.format_identifier(name)
        sql = f"SAVE TRANSACTION {quoted}"
        await self._backend.execute(sql)

    async def _do_release_savepoint(self, name: str) -> None:
        """Release a savepoint (no-op in SQL Server)."""
        if name in self._savepoints:
            self._savepoints.remove(name)

    async def _do_rollback_savepoint(self, name: str) -> None:
        """Rollback to a savepoint using SQL Server's ROLLBACK TRANSACTION syntax."""
        quoted = self._backend.dialect.format_identifier(name)
        sql = f"ROLLBACK TRANSACTION {quoted}"
        await self._backend.execute(sql)

    async def commit(self) -> None:
        """Commit the current async transaction."""
        if not self.is_active:
            raise TransactionError("No active transaction to commit")

        self.log(logging.DEBUG, "Committing async transaction")

        try:
            await super().commit()
        except Exception as e:
            self.log(logging.ERROR, f"Failed to commit async transaction: {str(e)}")
            raise

    async def rollback(self, savepoint: Optional[str] = None) -> None:
        """Rollback the async transaction or to a savepoint.

        Args:
            savepoint: If provided, rollback to this savepoint
        """
        if not self.is_active:
            raise TransactionError("No active transaction to rollback")

        if savepoint:
            await self._rollback_to_savepoint(savepoint)
        else:
            self.log(logging.DEBUG, "Rolling back async transaction")
            try:
                await super().rollback()
            except Exception as e:
                self.log(logging.ERROR, f"Failed to rollback async transaction: {str(e)}")
                raise

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
            self.log(logging.WARNING, f"Savepoint '{name}' already exists")

        quoted = self._backend.dialect.format_identifier(name)
        sql = f"SAVE TRANSACTION {quoted}"
        await self._backend.execute(sql)
        self._savepoints.append(name)
        self._active_savepoints.append(name)

        self.log(logging.DEBUG, f"Async savepoint created: {name}")
        return name

    async def _rollback_to_savepoint(self, name: str) -> None:
        """Rollback to a specific savepoint."""
        if name not in self._savepoints:
            raise TransactionError(f"Savepoint '{name}' not found")

        quoted = self._backend.dialect.format_identifier(name)
        sql = f"ROLLBACK TRANSACTION {quoted}"
        await self._backend.execute(sql)

        idx = self._savepoints.index(name) + 1
        self._savepoints = self._savepoints[:idx]
        active_idx = self._active_savepoints.index(name) + 1 if name in self._active_savepoints else 0
        self._active_savepoints = self._active_savepoints[:active_idx]

        self.log(logging.DEBUG, f"Rolled back to async savepoint: {name}")

    async def release_savepoint(self, name: str) -> None:
        """Release a savepoint (no-op in SQL Server).

        Args:
            name: Savepoint name
        """
        if name in self._savepoints:
            self._savepoints.remove(name)
            if name in self._active_savepoints:
                self._active_savepoints.remove(name)
            self.log(logging.DEBUG, f"Async savepoint released: {name}")

    def savepoints(self) -> List[str]:
        """Get list of current savepoints."""
        return self._savepoints.copy()
