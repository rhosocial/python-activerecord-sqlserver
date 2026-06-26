# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/locking.py
from typing import Protocol

from rhosocial.activerecord.backend.dialect.protocols import LockingSupport


class SQLServerLockingSupport(LockingSupport, Protocol):
    def supports_readpast(self) -> bool: ...
    def format_table_hint_locking(self, hint_type: str) -> str: ...