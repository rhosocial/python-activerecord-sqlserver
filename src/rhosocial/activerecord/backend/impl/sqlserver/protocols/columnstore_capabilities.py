# sqlserver/protocols/columnstore_generated.py
"""Auto-generated protocol declarations (P7, 2026-09-01).

Functional-group principle: every public format_*/supports_* on a
backend mixin is declared here so dialect users can program against
the capability contract.  Regenerate via scripts/p7_generate_protocols.py
when mixins gain new public rendering methods.
"""

from typing import Any, Dict, List, Optional, Tuple

from typing import Protocol

class SQLServerColumnstoreIndexSupport(Protocol):
    """Auto-generated capability protocol (P7)."""

    def supports_nonclustered_columnstore(self) -> bool:
        ...  # pragma: no cover
    def supports_clustered_columnstore(self) -> bool:
        ...  # pragma: no cover
    def supports_columnstore_order(self) -> bool:
        ...  # pragma: no cover
    def format_create_columnstore_index_statement(self, expr: 'SQLServerColumnstoreIndexExpression') -> Tuple[str, tuple]:
        ...  # pragma: no cover
