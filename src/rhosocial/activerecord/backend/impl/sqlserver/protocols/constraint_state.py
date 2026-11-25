# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/constraint_state.py
"""SQL Server constraint-state capability contract.

The probe and the two formatters live in one protocol: a backend that claims
``CHECK`` / ``NOCHECK CONSTRAINT`` must render both state verbs, and each
formatter takes exactly its own node.
"""

from typing import Protocol, Tuple, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - import only for type checkers
    from ..expression.constraint_state import (
        SQLServerCheckConstraintStatement,
        SQLServerNocheckConstraintStatement,
    )


@runtime_checkable
class SQLServerConstraintStateSupport(Protocol):
    def supports_constraint_check_nocheck(self) -> bool: ...

    def format_check_constraint_statement(
        self, expr: "SQLServerCheckConstraintStatement"
    ) -> Tuple[str, tuple]: ...

    def format_nocheck_constraint_statement(
        self, expr: "SQLServerNocheckConstraintStatement"
    ) -> Tuple[str, tuple]: ...
