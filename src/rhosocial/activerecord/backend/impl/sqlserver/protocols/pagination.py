# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/pagination.py
from typing import Protocol, runtime_checkable


@runtime_checkable
class SQLServerPaginationSupport(Protocol):
    def supports_offset_fetch(self) -> bool: ...
    def supports_order_by_in_subquery(self) -> bool: ...