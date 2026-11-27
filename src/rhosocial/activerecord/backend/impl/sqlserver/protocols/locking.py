# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/locking.py
from typing import Protocol, Tuple, runtime_checkable

from rhosocial.activerecord.backend.dialect.protocols import LockingSupport


@runtime_checkable
class SQLServerLockingSupport(LockingSupport, Protocol):
    def supports_readpast(self) -> bool: ...
    def render_table_hint_locking(self, expr: str) -> Tuple[str, tuple]: ...