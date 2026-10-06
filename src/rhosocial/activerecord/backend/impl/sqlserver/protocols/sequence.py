# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/sequence.py
from typing import TYPE_CHECKING, Protocol, Tuple, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover
    from ..expression.sequence import SQLServerNextValueForExpression


@runtime_checkable
class SQLServerSequenceSupport(Protocol):
    def supports_sequence_as_data_type(self) -> bool: ...
    def format_next_value_for(
        self, expr: "SQLServerNextValueForExpression"
    ) -> Tuple[str, tuple]: ...
