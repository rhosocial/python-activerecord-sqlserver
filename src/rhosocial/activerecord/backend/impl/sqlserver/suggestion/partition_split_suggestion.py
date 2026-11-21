# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/partition_split_suggestion.py
"""SQL Server's partition split suggestion.

Suggests NEXT USED + SPLIT RANGE, a data-affecting operation the caller opts
into explicitly. The chain is suggested only for RANGE plans whose function and
boundary are known and whose capability probes allow the split.
"""

from __future__ import annotations

from typing import List, TYPE_CHECKING

from ....expression.bases import BaseExpression
from ....suggestion import PartitionSplitSuggestion
from ..expression.partition import SQLServerPartitionFunctionSplitExpression
from ._common import SQLServerPartitionSuggestionBase, _is_range

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.statements import PartitionStrategy

__all__ = ["SQLServerPartitionSplitSuggestionMixin"]


class SQLServerPartitionSplitSuggestionMixin(SQLServerPartitionSuggestionBase):
    """Suggest NEXT USED + SPLIT RANGE for SQL Server."""

    def suggest_partition_split(
        self,
        strategy: "PartitionStrategy",
        plan: object,
    ) -> PartitionSplitSuggestion:
        """Suggest NEXT USED + SPLIT RANGE (a data-affecting operation)."""
        if not _is_range(strategy):
            return PartitionSplitSuggestion(False)
        if not self.supports_split_partition():  # type: ignore[attr-defined]
            return PartitionSplitSuggestion(False)
        function = self._suggestion_function(plan)
        boundary = self._suggestion_boundary(plan, newest=True)
        if function is None or boundary is None:
            return PartitionSplitSuggestion(False)

        operations: List[BaseExpression] = []
        next_used = self._suggestion_next_used(plan, self._suggestion_scheme(plan))
        if next_used is not None:
            operations.append(next_used)
        operations.append(SQLServerPartitionFunctionSplitExpression(self, function, boundary))
        return PartitionSplitSuggestion(tuple(operations))
