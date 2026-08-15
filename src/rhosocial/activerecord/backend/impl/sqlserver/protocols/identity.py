# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/identity.py
from typing import Protocol, runtime_checkable


@runtime_checkable
class SQLServerIdentitySupport(Protocol):
    def supports_identity_insert(self) -> bool: ...
    def format_set_identity_insert(self, table: str, on: bool) -> str: ...