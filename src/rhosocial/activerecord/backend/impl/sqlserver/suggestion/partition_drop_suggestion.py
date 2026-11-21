# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/partition_drop_suggestion.py
"""SQL Server's partition drop suggestion.

SQL Server has no ``DROP PARTITION``: removing a boundary is a ``MERGE RANGE``
on the partition function. The answer is the explicit "unsupported" state
(``False``) for other strategies, ``None`` when no boundary is known, and a
real expression chain otherwise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....suggestion import PartitionDropSuggestion
from ..expression.partition import SQLServerPartitionFunctionMergeExpression
from ._common import SQLServerPartitionSuggestionBase, _is_range

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.statements import PartitionByClause

__all__ = ["SQLServerPartitionDropSuggestionMixin"]


class SQLServerPartitionDropSuggestionMixin(SQLServerPartitionSuggestionBase):
    """Suggest MERGE RANGE, since SQL Server has no DROP PARTITION."""

    def suggest_partition_drop(
        self,
        strategy: "PartitionByClause",
        plan: object,
    ) -> PartitionDropSuggestion:
        """Suggest MERGE RANGE: SQL Server has no DROP PARTITION."""
        if not _is_range(strategy):
            return PartitionDropSuggestion(False)
        if not self.supports_merge_partition():  # type: ignore[attr-defined]
            return PartitionDropSuggestion(False)
        function = self._suggestion_function(plan)
        boundary = self._suggestion_boundary(plan, newest=False)
        if function is None:
            return PartitionDropSuggestion(False)
        if boundary is None:
            return PartitionDropSuggestion(None)
        return PartitionDropSuggestion(
            (SQLServerPartitionFunctionMergeExpression(self, function, boundary),)
        )
