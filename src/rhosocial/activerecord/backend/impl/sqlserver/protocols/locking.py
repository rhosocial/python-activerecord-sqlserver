# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/locking.py
from typing import Protocol, runtime_checkable

from rhosocial.activerecord.backend.dialect.protocols import LockingSupport


@runtime_checkable
class SQLServerLockingSupport(LockingSupport, Protocol):
    def supports_readpast(self) -> bool: ...
    def format_table_hint_locking(self, hint_type: str) -> str: ...