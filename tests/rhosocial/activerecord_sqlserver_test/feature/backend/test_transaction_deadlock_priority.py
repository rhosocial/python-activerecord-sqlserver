# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_transaction_deadlock_priority.py
"""Offline tests for SQLServerTransactionManager.set_deadlock_priority delegation."""
from unittest.mock import MagicMock

import pytest

from rhosocial.activerecord.backend.transaction import TransactionState
from rhosocial.activerecord.backend.impl.sqlserver.transaction import (
    SQLServerTransactionManager,
)


def make_manager() -> tuple[SQLServerTransactionManager, MagicMock]:
    backend = MagicMock()
    mgr = SQLServerTransactionManager(backend)
    return mgr, backend


class TestSetDeadlockPriority:
    def test_delegates_to_backend(self):
        mgr, backend = make_manager()
        mgr._state = TransactionState.ACTIVE
        mgr.set_deadlock_priority("LOW")
        backend.set_deadlock_priority.assert_called_once_with("LOW")

    def test_integer_delegates_to_backend(self):
        mgr, backend = make_manager()
        mgr._state = TransactionState.ACTIVE
        mgr.set_deadlock_priority(-5)
        backend.set_deadlock_priority.assert_called_once_with(-5)

    def test_raises_without_active_transaction(self):
        mgr, backend = make_manager()
        mgr._state = TransactionState.INACTIVE
        with pytest.raises(Exception, match="No active transaction"):
            mgr.set_deadlock_priority("LOW")
        backend.set_deadlock_priority.assert_not_called()