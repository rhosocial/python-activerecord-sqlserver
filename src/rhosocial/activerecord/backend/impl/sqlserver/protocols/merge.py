# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/merge.py
from typing import Protocol, Tuple, List, Optional, runtime_checkable


@runtime_checkable
class SQLServerMergeSupport(Protocol):
    def supports_merge_output(self) -> bool: ...
    def supports_merge_holdlock(self) -> bool: ...
    def format_merge_output_clause(
        self, columns: List[str], action_type: Optional[str] = None
    ) -> Tuple[str, tuple]: ...