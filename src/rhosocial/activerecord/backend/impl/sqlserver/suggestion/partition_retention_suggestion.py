# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/partition_retention_suggestion.py
"""SQL Server's partition retention suggestion.

A boundary qualifies when it is less than or equal to the cutoff: SQL Server's
function boundary is the upper bound of the partition on its left in both RANGE
LEFT and RANGE RIGHT. Removal is a MERGE, never a DROP PARTITION, and moving
rows is inherent to the operation.
"""

from __future__ import annotations

from typing import Any, List, Sequence, TYPE_CHECKING

from ....suggestion import PartitionRetentionSuggestion
from ..expression.partition import SQLServerPartitionFunctionMergeExpression
from ._common import SQLServerPartitionSuggestionBase, _coerce_boundary, _get, _is_range

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.statements import PartitionStrategy

__all__ = ["SQLServerPartitionRetentionSuggestionMixin"]


class SQLServerPartitionRetentionSuggestionMixin(SQLServerPartitionSuggestionBase):
    """Suggest one MERGE RANGE per boundary at or before the cutoff."""

    def suggest_partition_retention(
        self,
        strategy: "PartitionStrategy",
        plan: object,
    ) -> PartitionRetentionSuggestion:
        """Suggest one MERGE RANGE per boundary at or before the cutoff.

        SQL Server's function boundary is the upper bound of the partition on
        its left in both RANGE LEFT and RANGE RIGHT, so a boundary qualifies
        when it is less than or equal to the cutoff. Removal is a MERGE, never
        a DROP PARTITION, and moving rows is inherent to the operation.
        """
        if not _is_range(strategy):
            return PartitionRetentionSuggestion(False)
        if not self.supports_merge_partition():  # type: ignore[attr-defined]
            return PartitionRetentionSuggestion(False)
        function = self._suggestion_function(plan)
        data_type = _get(plan, "data_type")
        boundaries = _get(plan, "boundaries")
        cutoff = _get(plan, "cutoff")
        if (
            function is None
            or not isinstance(data_type, str)
            or not data_type.strip()
            or not isinstance(boundaries, (list, tuple))
            or cutoff is None
        ):
            return PartitionRetentionSuggestion(False)

        try:
            threshold = _coerce_boundary(data_type, cutoff)
            candidates: List[Any] = [
                boundary
                for boundary in boundaries
                if _coerce_boundary(data_type, boundary) <= threshold
            ]
        except (TypeError, ValueError, ArithmeticError):
            return PartitionRetentionSuggestion(False)

        if not candidates:
            return PartitionRetentionSuggestion(None)
        operations: Sequence[SQLServerPartitionFunctionMergeExpression] = tuple(
            SQLServerPartitionFunctionMergeExpression(self, function, boundary)
            for boundary in candidates
        )
        return PartitionRetentionSuggestion(tuple(operations))
