# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/table.py
from typing import Protocol, Tuple, runtime_checkable

from rhosocial.activerecord.backend.dialect.protocols import TableObjectSupport


@runtime_checkable
class SQLServerTableSupport(TableObjectSupport, Protocol):
    def supports_select_into(self) -> bool: ...
    def supports_tablesample(self) -> bool: ...
    def format_select_into_statement(self, expr) -> Tuple[str, tuple]: ...