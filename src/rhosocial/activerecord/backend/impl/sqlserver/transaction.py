# src/rhosocial/activerecord/backend/impl/sqlserver/transaction.py
"""
SQL Server transaction management.

This module provides transaction management for SQL Server,
supporting savepoints, isolation levels, and SQL Server-specific features.
"""

import logging
from enum import Enum
from typing import List, Optional

from rhosocial.activerecord.backend.transaction import (
    TransactionManager,
    TransactionState,
    IsolationLevel,
    TransactionMode,
)
from rhosocial.activerecord.backend.errors import (
    TransactionError,
    UnsupportedTransactionModeError,
)


class SQLServerIsolationLevel(Enum):
    """SQL Server-specific isolation levels."""
    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SNAPSHOT = "SNAPSHOT"
    SERIALIZABLE = "SERIALIZABLE"


ISOLATION_LEVEL_MAP = {
    IsolationLevel.READ_UNCOMMITTED: SQLServerIsolationLevel.READ_UNCOMMITTED,
    IsolationLevel.READ_COMMITTED: SQLServerIsolationLevel.READ_COMMITTED,
    IsolationLevel.REPEATABLE_READ: SQLServerIsolationLevel.REPEATABLE_READ,
    IsolationLevel.SERIALIZABLE: SQLServerIsolationLevel.SERIALIZABLE,
}


class SQLServerTransactionManager(TransactionManager):
    """SQL Server transaction manager with savepoint support.
    
    SQL Server supports:
    - Multiple isolation levels including SNAPSHOT
    - Savepoints for partial rollback
    - Named transactions
    - Distributed transactions (via MSDTC)
    - Lock hints for granular control
    """
    
    def __init__(self, backend, logger=None):
        super().__init__(backend, logger)
        self._sqlserver_isolation_level: Optional[SQLServerIsolationLevel] = None
        self._name: Optional[str] = None
    
    def begin(
        self,
        isolation_level: Optional[IsolationLevel] = None,
        mode: Optional[TransactionMode] = None,
        name: Optional[str] = None,
        snapshot: bool = False,
        **kwargs
    ) -> None:
        """
        Begin a new transaction.
        
        Args:
            isolation_level: Transaction isolation level
            mode: Transaction mode (READ ONLY not supported)
            name: Optional transaction name (SQL Server-specific)
            snapshot: If True, use SNAPSHOT isolation level
            **kwargs: Additional options
        
        Raises:
            UnsupportedTransactionModeError: If READ ONLY mode requested
            TransactionError: If transaction already active
        """
        if self._state == TransactionState.ACTIVE:
            raise TransactionError("Transaction already active")
        
        if mode == TransactionMode.READ_ONLY:
            raise UnsupportedTransactionModeError(
                feature="READ ONLY transactions",
                backend="SQL Server",
                message="SQL Server does not support READ ONLY transactions. "
                        "Use locking hints for read-only access."
            )
        
        self._name = name

        # Resolve isolation level from parameter, base class property, or snapshot flag
        effective_iso = isolation_level
        if effective_iso is None and isinstance(self._isolation_level, IsolationLevel):
            effective_iso = self._isolation_level

        if snapshot:
            self._sqlserver_isolation_level = SQLServerIsolationLevel.SNAPSHOT
        elif effective_iso:
            self._sqlserver_isolation_level = ISOLATION_LEVEL_MAP.get(effective_iso)

        self._do_begin()

        self._state = TransactionState.ACTIVE
        self._savepoints = []

        self.log(logging.DEBUG, f"Transaction started (isolation={self._sqlserver_isolation_level})")
    
    def _do_begin(self) -> None:
        """Execute the BEGIN TRANSACTION statement."""
        parts = ["BEGIN TRANSACTION"]
        
        if self._name:
            parts.append(self._name)
        
        sql = " ".join(parts)
        self._backend.execute(sql)
        
        if self._sqlserver_isolation_level:
            set_iso_sql = f"SET TRANSACTION ISOLATION LEVEL {self._sqlserver_isolation_level.value}"
            self._backend.execute(set_iso_sql)
    
    def commit(self) -> None:
        """Commit the current transaction."""
        if self._state != TransactionState.ACTIVE:
            raise TransactionError("No active transaction to commit")
        
        self.log(logging.DEBUG, "Committing transaction")
        
        try:
            self._do_commit()
            self._state = TransactionState.COMMITTED
            self._savepoints = []
            
        except Exception as e:
            self._state = TransactionState.FAILED
            self.log(logging.ERROR, f"Failed to commit transaction: {str(e)}")
            raise
    
    def _do_commit(self) -> None:
        """Execute the COMMIT TRANSACTION statement."""
        sql = "COMMIT TRANSACTION"
        if self._name:
            sql += f" {self._name}"
        self._backend.execute(sql)
    
    def rollback(self, savepoint: Optional[str] = None) -> None:
        """
        Rollback the transaction or to a savepoint.
        
        Args:
            savepoint: If provided, rollback to this savepoint instead of full rollback
        """
        if self._state != TransactionState.ACTIVE:
            raise TransactionError("No active transaction to rollback")
        
        if savepoint:
            self._rollback_to_savepoint(savepoint)
        else:
            self._do_rollback()
            self._state = TransactionState.ROLLED_BACK
            self._savepoints = []
    
    def _do_rollback(self) -> None:
        """Execute the ROLLBACK TRANSACTION statement."""
        sql = "ROLLBACK TRANSACTION"
        if self._name:
            sql += f" {self._name}"
        self._backend.execute(sql)
    
    def savepoint(self, name: Optional[str] = None) -> str:
        """
        Create a savepoint within the current transaction.

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
            self.log(logging.WARNING, f"Savepoint '{name}' already exists, will be overwritten")

        sql = f"SAVE TRANSACTION {name}"
        self._backend.execute(sql)
        self._savepoints.append(name)

        self.log(logging.DEBUG, f"Savepoint created: {name}")
        return name
    
    def _rollback_to_savepoint(self, name: str) -> None:
        """Rollback to a specific savepoint."""
        if name not in self._savepoints:
            raise TransactionError(f"Savepoint '{name}' not found")
        
        sql = f"ROLLBACK TRANSACTION {name}"
        self._backend.execute(sql)
        
        idx = self._savepoints.index(name) + 1
        self._savepoints = self._savepoints[:idx]
        
        self.log(logging.DEBUG, f"Rolled back to savepoint: {name}")
    
    def release_savepoint(self, name: str) -> None:
        """
        Release a savepoint (no-op in SQL Server).
        
        SQL Server doesn't have a RELEASE SAVEPOINT command.
        Savepoints are automatically released on commit/rollback.
        
        Args:
            name: Savepoint name
        """
        if name in self._savepoints:
            self._savepoints.remove(name)
            self.log(logging.DEBUG, f"Savepoint released (marked): {name}")
    
    @property
    def is_active(self) -> bool:
        """Check if a transaction is currently active."""
        return self._state == TransactionState.ACTIVE
    
    def savepoints(self) -> List[str]:
        """Get list of current savepoints."""
        return self._savepoints.copy()
    
    def set_lock_timeout(self, timeout: int) -> None:
        """
        Set the lock timeout for the current session.
        
        Args:
            timeout: Lock timeout in milliseconds. -1 = wait indefinitely, 0 = no wait
        """
        if self._state != TransactionState.ACTIVE:
            raise TransactionError("No active transaction")
        
        self._backend.execute(f"SET LOCK_TIMEOUT {timeout}")
        self.log(logging.DEBUG, f"Lock timeout set to {timeout}ms")
    
    def set_deadlock_priority(self, priority) -> None:
        """
        Set the deadlock priority for the current session.
        
        Args:
            priority: "LOW", "NORMAL", "HIGH", or -10 to 10
        """
        if self._state != TransactionState.ACTIVE:
            raise TransactionError("No active transaction")
        
        if isinstance(priority, int):
            sql = f"SET DEADLOCK_PRIORITY {priority}"
        else:
            sql = f"SET DEADLOCK_PRIORITY {priority.upper()}"
        
        self._backend.execute(sql)
        self.log(logging.DEBUG, f"Deadlock priority set to {priority}")


class SQLServerNestedTransactionManager(SQLServerTransactionManager):
    """
    Support for SQL Server nested transactions.
    
    SQL Server supports nested transactions syntactically, but they
    behave differently from truly nested transactions. The commit of
    an inner transaction is only effective if the outer transaction commits.
    
    Note: ROLLBACK in any nested level rolls back the entire transaction.
    """
    
    def __init__(self, backend, logger=None):
        super().__init__(backend, logger)
        self._nest_level = 0
    
    def begin(self, **kwargs) -> None:
        """Begin a transaction, potentially nested."""
        if self._state == TransactionState.ACTIVE:
            self._nest_level += 1
            self.log(logging.DEBUG, f"Nested transaction begin (level={self._nest_level})")
            
            sql = "BEGIN TRANSACTION"
            self._backend.execute(sql)
        else:
            super().begin(**kwargs)
            self._nest_level = 1
    
    def commit(self) -> None:
        """Commit transaction, handling nesting."""
        if self._nest_level > 1:
            self._nest_level -= 1
            self.log(logging.DEBUG, f"Nested transaction commit (level={self._nest_level})")
            self._backend.execute("COMMIT TRANSACTION")
        else:
            super().commit()
            self._nest_level = 0
    
    def rollback(self, savepoint: Optional[str] = None) -> None:
        """Rollback transaction, handling nesting."""
        if savepoint:
            self._rollback_to_savepoint(savepoint)
        elif self._nest_level > 1:
            self._nest_level -= 1
            self.log(logging.DEBUG, f"Nested transaction rollback (level={self._nest_level})")
            self._backend.execute("ROLLBACK TRANSACTION")
        else:
            super().rollback()
            self._nest_level = 0
    
    @property
    def nest_level(self) -> int:
        """Get current nesting level."""
        return self._nest_level
