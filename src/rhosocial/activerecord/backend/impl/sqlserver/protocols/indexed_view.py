# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/indexed_view.py
from typing import Protocol, Tuple, runtime_checkable


@runtime_checkable
class SQLServerIndexedViewSupport(Protocol):
    def supports_indexed_view(self) -> bool: ...
    def format_create_indexed_view_statement(self, expr) -> Tuple[str, tuple]: ...