# sqlserver/protocols/routine_generated.py
"""Auto-generated protocol declarations (P7, 2026-09-01).

Functional-group principle: every public format_*/supports_* on a
backend mixin is declared here so dialect users can program against
the capability contract.  Regenerate via scripts/p7_generate_protocols.py
when mixins gain new public rendering methods.
"""

from typing import Any, Dict, List, Optional, Tuple

from typing import Protocol

class SQLServerRoutineSupport(Protocol):
    """Auto-generated capability protocol (P7)."""

    def supports_create_procedure(self) -> bool:
        ...  # pragma: no cover
    def supports_drop_procedure(self) -> bool:
        ...  # pragma: no cover
    def format_sqlserver_object_name(self, name: str, schema: Optional[str]=None) -> str:
        ...  # pragma: no cover
    def format_create_procedure_statement(self, expr: 'SQLServerCreateProcedureExpression') -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_drop_routine_statement(self, expr: 'SQLServerDropRoutineExpression') -> Tuple[str, tuple]:
        ...  # pragma: no cover
