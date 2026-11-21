# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/partition_table_drop_suggestion.py
"""SQL Server's partition table-drop suggestion.

Suggests dropping the scaffolding in dependency order: scheme first, then
function. No ``DROP TABLE`` is suggested -- moving data out of a table the
scheme is built on is a decision the caller owns.
"""

from __future__ import annotations

from typing import List, TYPE_CHECKING

from ....expression.bases import BaseExpression
from ....suggestion import PartitionTableDropSuggestion
from ..expression.partition import (
    SQLServerDropPartitionFunctionExpression,
    SQLServerDropPartitionSchemeExpression,
)
from ._common import SQLServerPartitionSuggestionBase, _is_range

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.statements import PartitionByClause

__all__ = ["SQLServerPartitionTableDropSuggestionMixin"]


class SQLServerPartitionTableDropSuggestionMixin(SQLServerPartitionSuggestionBase):
    """Suggest dropping SQL Server's partition scheme then function."""

    def suggest_partition_table_drop(
        self,
        strategy: "PartitionByClause",
        plan: object,
    ) -> PartitionTableDropSuggestion:
        """Suggest dropping the scaffolding: scheme first, then function.

        SQL Server refuses to drop a partition function while a scheme maps it,
        so the order is part of the answer. No ``DROP TABLE`` is suggested:
        dropping the scheme while a table is built on it is refused too, and
        moving every row out would be a data-affecting decision the caller owns.
        """
        if not _is_range(strategy):
            return PartitionTableDropSuggestion(False)
        if not self.supports_partition_function():  # type: ignore[attr-defined]
            return PartitionTableDropSuggestion(False)
        function = self._suggestion_function(plan)
        if function is None:
            return PartitionTableDropSuggestion(False)

        operations: List[BaseExpression] = []
        scheme = self._suggestion_scheme(plan)
        if scheme is not None:
            if not self.supports_partition_scheme():  # type: ignore[attr-defined]
                return PartitionTableDropSuggestion(False)
            operations.append(SQLServerDropPartitionSchemeExpression(self, scheme))
        operations.append(SQLServerDropPartitionFunctionExpression(self, function))
        return PartitionTableDropSuggestion(tuple(operations))
