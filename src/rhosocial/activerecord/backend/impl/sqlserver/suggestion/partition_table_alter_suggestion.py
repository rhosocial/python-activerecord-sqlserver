# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/partition_table_alter_suggestion.py
"""SQL Server's partition table-alter suggestion.

SQL Server has no in-place ALTER of a partitioned table's scheme, so there is
no honest expression chain to return: the answer is the explicit "unsupported"
state (``False``) for every strategy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....suggestion import PartitionTableAlterSuggestion
from ._common import SQLServerPartitionSuggestionBase

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.statements import PartitionStrategy

__all__ = ["SQLServerPartitionTableAlterSuggestionMixin"]


class SQLServerPartitionTableAlterSuggestionMixin(SQLServerPartitionSuggestionBase):
    """Answer SQL Server's lack of an in-place partitioned-table ALTER."""

    def suggest_partition_table_alter(
        self,
        strategy: "PartitionStrategy",
        plan: object,
    ) -> PartitionTableAlterSuggestion:
        """SQL Server has no in-place ALTER of a partitioned table's scheme.

        Changing a function's type or direction means dropping and recreating
        the scaffolding, which moves every row; the maintenance executor
        refused that and asked the caller to do it explicitly. There is no
        honest expression chain here, so the answer is ``False``.
        """
        return PartitionTableAlterSuggestion(False)
