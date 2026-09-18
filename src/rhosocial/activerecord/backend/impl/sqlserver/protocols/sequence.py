# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/sequence.py
from typing import Any, Protocol, Tuple, runtime_checkable


@runtime_checkable
class SQLServerSequenceSupport(Protocol):
    def supports_sequence_as_data_type(self) -> bool: ...
    def format_next_value_for(self, sequence: Any) -> Tuple[str, tuple]: ...