# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/output.py
from typing import Protocol, Tuple, List, runtime_checkable


@runtime_checkable
class SQLServerOutputSupport(Protocol):
    def supports_output_clause(self) -> bool: ...
    def format_output_clause(self, columns: List[str], clause_type: str) -> Tuple[str, tuple]: ...