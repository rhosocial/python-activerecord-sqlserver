# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/partition_merge_suggestion.py
"""SQL Server's partition merge suggestion.

Suggests MERGE RANGE, a data-affecting operation the caller opts into
explicitly. The answer is the explicit "unsupported" state (``False``) for
other strategies and a real expression chain for a known RANGE boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....suggestion import PartitionMergeSuggestion
from ..expression.partition import SQLServerPartitionFunctionMergeExpression
from ._common import SQLServerPartitionSuggestionBase, _is_range

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.statements import PartitionStrategy

__all__ = ["SQLServerPartitionMergeSuggestionMixin"]


class SQLServerPartitionMergeSuggestionMixin(SQLServerPartitionSuggestionBase):
    """Suggest MERGE RANGE for SQL Server."""

    def suggest_partition_merge(
        self,
        strategy: "PartitionStrategy",
        plan: object,
    ) -> PartitionMergeSuggestion:
        """Suggest MERGE RANGE (a data-affecting operation)."""
        if not _is_range(strategy):
            return PartitionMergeSuggestion(False)
        if not self.supports_merge_partition():  # type: ignore[attr-defined]
            return PartitionMergeSuggestion(False)
        function = self._suggestion_function(plan)
        boundary = self._suggestion_boundary(plan, newest=False)
        if function is None or boundary is None:
            return PartitionMergeSuggestion(False)
        return PartitionMergeSuggestion(
            (SQLServerPartitionFunctionMergeExpression(self, function, boundary),)
        )
