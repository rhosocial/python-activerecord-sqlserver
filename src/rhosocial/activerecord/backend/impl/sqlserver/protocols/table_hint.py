# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/table_hint.py
from typing import Protocol, List, runtime_checkable


@runtime_checkable
class SQLServerTableHintSupport(Protocol):
    def supports_table_hints(self) -> bool: ...
    def format_table_hint(self, hints: List[str]) -> str: ...