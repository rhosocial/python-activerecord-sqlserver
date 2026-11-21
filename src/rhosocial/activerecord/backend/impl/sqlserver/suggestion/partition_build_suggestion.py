# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/partition_build_suggestion.py
"""SQL Server's partition build suggestion.

Suggests the function -> scheme -> ON chain for CREATE TABLE time. Real chains
are returned only when the plan names a function, data type and boundaries and
the dialect's capability probes allow each tier; otherwise the explicit
"unsupported" state (``False``).
"""

from __future__ import annotations

from typing import List, TYPE_CHECKING

from ....expression import Column
from ....expression.bases import BaseExpression
from ....suggestion import PartitionBuildSuggestion
from ..expression.partition import (
    SQLServerPartitionByRangeClause,
    SQLServerPartitionFunctionExpression,
)
from ._common import SQLServerPartitionSuggestionBase, _get, _is_range

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.statements import PartitionStrategy

__all__ = ["SQLServerPartitionBuildSuggestionMixin"]


class SQLServerPartitionBuildSuggestionMixin(SQLServerPartitionSuggestionBase):
    """Suggest the function -> scheme -> ON chain for SQL Server CREATE TABLE."""

    def suggest_partition_build(
        self,
        strategy: "PartitionStrategy",
        plan: object,
    ) -> PartitionBuildSuggestion:
        """Suggest the function -> scheme -> ON chain for CREATE TABLE time."""
        if not _is_range(strategy):
            return PartitionBuildSuggestion(False)
        if not self.supports_partition_function():  # type: ignore[attr-defined]
            return PartitionBuildSuggestion(False)
        function = self._suggestion_function(plan)
        data_type = _get(plan, "data_type")
        boundaries = _get(plan, "boundaries")
        if (
            function is None
            or not isinstance(data_type, str)
            or not data_type.strip()
            or not isinstance(boundaries, (list, tuple))
            or not boundaries
        ):
            return PartitionBuildSuggestion(False)

        operations: List[BaseExpression] = [
            SQLServerPartitionFunctionExpression(
                self,
                function,
                data_type,
                list(boundaries),
                range_direction=_get(
                    plan,
                    "range_direction",
                    "RIGHT",
                ),
            )
        ]
        scheme = self._suggestion_scheme(plan)
        if scheme is not None:
            if not self.supports_partition_scheme():  # type: ignore[attr-defined]
                return PartitionBuildSuggestion(False)
            scheme_expression = self._suggestion_scheme_expression(plan, function)
            if scheme_expression is None:
                return PartitionBuildSuggestion(False)
            operations.append(scheme_expression)

        keys = _get(plan, "keys")
        if keys:
            if not self.supports_partitioned_table_creation():  # type: ignore[attr-defined]
                return PartitionBuildSuggestion(False)
            key_nodes: List[BaseExpression] = []
            for key in keys:
                if isinstance(key, BaseExpression):
                    key_nodes.append(key)
                elif isinstance(key, str) and key.strip():
                    key_nodes.append(Column(self, key))
                else:
                    return PartitionBuildSuggestion(False)
            if not key_nodes:
                return PartitionBuildSuggestion(False)
            if scheme is None:
                return PartitionBuildSuggestion(False)
            operations.append(
                SQLServerPartitionByRangeClause(
                    self,
                    key_nodes,
                    scheme,
                    range_direction=_get(plan, "range_direction", "RIGHT"),
                )
            )
        return PartitionBuildSuggestion(tuple(operations))
