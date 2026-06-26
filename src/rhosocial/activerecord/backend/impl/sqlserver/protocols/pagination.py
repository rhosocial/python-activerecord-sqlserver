# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/pagination.py
from typing import Protocol


class SQLServerPaginationSupport(Protocol):
    def supports_offset_fetch(self) -> bool: ...
    def supports_order_by_in_subquery(self) -> bool: ...