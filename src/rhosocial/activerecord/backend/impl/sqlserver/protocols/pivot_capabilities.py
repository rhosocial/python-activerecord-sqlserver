# sqlserver/protocols/pivot_generated.py
"""Auto-generated protocol declarations (P7, 2026-09-01).

Functional-group principle: every public format_*/supports_* on a
backend mixin is declared here so dialect users can program against
the capability contract.  Regenerate via scripts/p7_generate_protocols.py
when mixins gain new public rendering methods.
"""

from typing import Any, Dict, List, Optional, Tuple

from typing import Protocol

class SQLServerPivotSupport(Protocol):
    """Auto-generated capability protocol (P7)."""

    def supports_pivot(self) -> bool:
        ...  # pragma: no cover
    def supports_unpivot(self) -> bool:
        ...  # pragma: no cover
    def format_pivot(self, expr: 'SQLServerPivotExpression') -> Tuple[str, tuple]:
        ...  # pragma: no cover
    def format_unpivot(self, expr: 'SQLServerUnpivotExpression') -> Tuple[str, tuple]:
        ...  # pragma: no cover
