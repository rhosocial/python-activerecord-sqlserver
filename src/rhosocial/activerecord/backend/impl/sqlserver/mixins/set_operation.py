# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/set_operation.py
"""SQL Server set-operation capability declarations.

Set-operation *formatting* is provided by the core
``SetOperationMixin.format_set_operation``: the node now carries the operation
as a word form (``union`` / ``union_all`` / ``intersect`` / ``except``) and
nothing else, so the trailing ``alias`` / ``ORDER BY`` / ``OFFSET FETCH`` /
``FOR UPDATE`` parameters the old override read are gone, and T-SQL spells all
four operations exactly as the shared renderer writes them. The override that
used to live here has therefore been removed along with the node fields it
read; this file keeps the capability declarations.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression import bases


class SQLServerSetOperationMixin:
    """SQL Server set operation capability declarations."""

    def supports_union(self) -> bool:
        """UNION is supported."""
        return True

    def supports_union_all(self) -> bool:
        """UNION ALL is supported."""
        return True

    def supports_intersect(self) -> bool:
        """INTERSECT is supported."""
        return True

    def supports_except(self) -> bool:
        """EXCEPT is supported."""
        return True

    def supports_set_operation_order_by(self) -> bool:
        """Set operations support ORDER BY."""
        return True

    def supports_set_operation_limit_offset(self) -> bool:
        """Set operations support OFFSET FETCH."""
        return True
