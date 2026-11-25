# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/partition_scheme_change_suggestion.py
"""SQL Server's partition-scheme-change suggestion.

Table partitioning is native on SQL Server 2008+ but an Enterprise feature
(Developer and Evaluation are licensed for the same feature set), so a chain is
returned only when ``partition_capability()`` answers ``NATIVE`` -- which this
dialect derives from ``supports_table_partitioning()`` and therefore from both
the 2008 version floor and the edition gate. Every other case answers ``False``.

There is no in-place ALTER of a partitioned table's scheme (the
``PartitionTableAlterSuggestion`` answer). A migration-time change is expressed
with the three-tier nodes SQL Server actually has: create the new partition
function, create the new scheme mapped to it, ``SWITCH`` the source partition
to the declared stage table, then drop the old scheme and function in
dependency order. Each node is one statement.

The core freezes a partition declaration to a clause-level projection naming a
scheme and a key column; it carries neither the new function's type/boundaries
nor a SWITCH target. A projection without those fields is answered ``False``
rather than inventing boundaries or a target table. A point whose old and new
projections are equal answers ``None`` (no action required).
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from ....dialect.partition_capability import PartitionCapability
from ....expression.bases import BaseExpression
from ....suggestion import PartitionSchemeChangeSuggestion
from ..expression.partition import (
    SQLServerDropPartitionFunctionExpression,
    SQLServerDropPartitionSchemeExpression,
    SQLServerPartitionFunctionExpression,
    SQLServerPartitionSchemeExpression,
    SQLServerSwitchPartitionExpression,
)
from ._change_common import projection_params

__all__ = ["SQLServerPartitionSchemeChangeSuggestionMixin"]

#: SQL Server 2008 (10.0) is the first release with partition functions/schemes.
_PARTITION_VERSION = (10, 0, 0)


def _name(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value.strip() else None


class SQLServerPartitionSchemeChangeSuggestionMixin:
    """Suggest a function -> scheme -> SWITCH -> old-scheme/function drop chain."""

    def suggest_partition_scheme_change(
        self, point: PartitionSchemeChangeSuggestion
    ) -> PartitionSchemeChangeSuggestion:
        """Return the native chain, or ``False`` when edition/grammar forbid it."""
        if self.partition_capability() is not PartitionCapability.NATIVE:
            return PartitionSchemeChangeSuggestion(operations=False)
        if not self.version_at_least(_PARTITION_VERSION):
            return PartitionSchemeChangeSuggestion(operations=False)

        old_params = projection_params(point.old_partition)
        new_params = projection_params(point.new_partition)
        if old_params and old_params == new_params:
            return PartitionSchemeChangeSuggestion(operations=None)

        chain = self._chain(point.table_name, old_params, new_params)
        if chain is None:
            return PartitionSchemeChangeSuggestion(operations=False)
        return PartitionSchemeChangeSuggestion(operations=chain)

    def _chain(
        self, table_name: Any, old: Any, new: Any
    ) -> Optional[Tuple[BaseExpression, ...]]:
        """Build the chain, or ``None`` when a required declaration is absent."""
        if not isinstance(table_name, str) or not table_name.strip():
            return None

        function = _name(new.get("function"))
        data_type = _name(new.get("data_type"))
        scheme = _name(new.get("scheme"))
        boundaries = new.get("boundaries")
        stage_table = _name(new.get("stage_table"))
        old_scheme = _name(old.get("scheme")) or _name(old.get("partition_scheme"))
        old_function = _name(old.get("function"))
        if not all((function, data_type, scheme, stage_table, old_scheme, old_function)):
            return None
        if not isinstance(boundaries, (list, tuple)) or not boundaries:
            return None

        filegroups = new.get("filegroups") or ()
        all_filegroup = _name(new.get("all_filegroup"))
        if not isinstance(filegroups, (list, tuple)) or (
            not filegroups and all_filegroup is None
        ):
            return None
        filegroups = list(filegroups)
        if any(not isinstance(filegroup, str) or not filegroup.strip() for filegroup in filegroups):
            return None

        range_direction = new.get("range_direction")
        if range_direction is None:
            range_direction = "RIGHT"
        source_partition = new.get("source_partition")
        target_partition = new.get("target_partition")
        if source_partition is not None and (
            not isinstance(source_partition, int) or isinstance(source_partition, bool)
        ):
            return None
        if target_partition is not None and (
            not isinstance(target_partition, int) or isinstance(target_partition, bool)
        ):
            return None

        operations: List[BaseExpression] = [
            SQLServerPartitionFunctionExpression(
                self,
                function,
                data_type,
                list(boundaries),
                range_direction=range_direction,
            ),
            SQLServerPartitionSchemeExpression(
                self,
                scheme,
                function,
                filegroups,
                all_filegroup=all_filegroup,
            ),
            SQLServerSwitchPartitionExpression(
                self,
                table_name,
                stage_table,
                source_partition=source_partition,
                target_partition=target_partition,
            ),
            SQLServerDropPartitionSchemeExpression(self, old_scheme),
            SQLServerDropPartitionFunctionExpression(self, old_function),
        ]
        return tuple(operations)
