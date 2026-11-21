# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/partition_add_suggestion.py
"""SQL Server's partition add suggestion.

SQL Server has no ``ADD PARTITION``: a boundary is added with ``NEXT USED``
followed by ``SPLIT RANGE``. The chain is suggested only for RANGE plans whose
function and boundary are known and whose capability probes allow the split.
"""

from __future__ import annotations

from typing import List, TYPE_CHECKING

from ....expression.bases import BaseExpression
from ....suggestion import PartitionAddSuggestion
from ..expression.partition import SQLServerPartitionFunctionSplitExpression
from ._common import SQLServerPartitionSuggestionBase, _is_range

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.statements import PartitionStrategy

__all__ = ["SQLServerPartitionAddSuggestionMixin"]


class SQLServerPartitionAddSuggestionMixin(SQLServerPartitionSuggestionBase):
    """Suggest NEXT USED + SPLIT RANGE as SQL Server's way to add a partition."""

    def suggest_partition_add(
        self,
        strategy: "PartitionStrategy",
        plan: object,
    ) -> PartitionAddSuggestion:
        """Suggest NEXT USED + SPLIT RANGE: SQL Server's way to add a partition."""
        if not _is_range(strategy):
            return PartitionAddSuggestion(False)
        if not self.supports_split_partition():  # type: ignore[attr-defined]
            return PartitionAddSuggestion(False)
        function = self._suggestion_function(plan)
        boundary = self._suggestion_boundary(plan, newest=True)
        if function is None or boundary is None:
            return PartitionAddSuggestion(False)

        operations: List[BaseExpression] = []
        next_used = self._suggestion_next_used(plan, self._suggestion_scheme(plan))
        if next_used is not None:
            operations.append(next_used)
        operations.append(SQLServerPartitionFunctionSplitExpression(self, function, boundary))
        return PartitionAddSuggestion(tuple(operations))
