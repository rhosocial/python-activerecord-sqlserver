# sqlserver/protocols/memory_optimized_generated.py
"""Auto-generated protocol declarations (P7, 2026-09-01).

Functional-group principle: every public format_*/supports_* on a
backend mixin is declared here so dialect users can program against
the capability contract.  Regenerate via scripts/p7_generate_protocols.py
when mixins gain new public rendering methods.
"""

from typing import Any, Dict, List, Optional, Tuple

from typing import Protocol

class SQLServerMemoryOptimizedSupport(Protocol):
    """Auto-generated capability protocol (P7)."""

    def supports_memory_optimized_tables(self) -> bool:
        ...  # pragma: no cover
    def format_memory_optimized_option(self, durability: str='SCHEMA_ONLY') -> str:
        ...  # pragma: no cover
    def format_hash_index_definition(self, columns: Sequence[str], bucket_count: int, name: Optional[str]=None, unique: bool=False) -> str:
        ...  # pragma: no cover
