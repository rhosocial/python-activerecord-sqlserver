# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/partition_scheme_change_suggestion.py
"""SQL Server's partition-scheme-change suggestion: an explicit refusal.

Table partitioning itself is native on SQL Server 2008+ and is an Enterprise
feature (Developer and Evaluation are licensed for the same feature set), so
there *are* partition functions, schemes and ``SWITCH`` statements to render.
Capability is not the question here: no chain of those nodes is a complete
scheme change.

Microsoft Learn, ``ALTER TABLE (Transact-SQL)`` / ``SWITCH`` (Arguments) states
that ``SWITCH`` "switches a block of data" by reassigning it to a target: the
target partition "must exist and it must be empty", and when switching to a
single table "the target table must already exist and it must be empty". The
same page's Remarks add: "you can't use this statement to change the way the
table itself is partitioned. To repartition a partitioned table, use
``ALTER PARTITION SCHEME`` and ``ALTER PARTITION FUNCTION``." In other words,
``SWITCH`` moves a partition's storage *out* of the source; it never copies it
back, and there is no in-place ``ALTER TABLE ... ON new_scheme``.

Changing a table's scheme therefore needs a data-preserving rebuild/migration
plan: build the destination table ON the new scheme, switch the staged data
back into the destination partition (an explicit SWITCH-back step), put the
destination in the live table's place, and only then drop the old scheme and
function -- which cannot be dropped while the live table still uses them. A
chain that only switches out and then drops the old objects would empty the
live table and break its dependencies; it is data-affecting and incomplete.

The point carries only declaration projections (names, boundaries, filegroups
and a stage-table *name*), with no evidence that the stage table exists, is
empty or is structurally identical, and no nodes to rebuild or rename the live
table. The suggestion contract cannot carry that plan, so a real change is
answered ``False`` -- the explicit "this backend cannot address it
automatically" state -- rather than an unsafe partial chain. An unchanged
projection answers ``None`` (no action).
"""
from __future__ import annotations

from ....suggestion import PartitionSchemeChangeSuggestion
from ._change_common import projection_params

__all__ = ["SQLServerPartitionSchemeChangeSuggestionMixin"]


class SQLServerPartitionSchemeChangeSuggestionMixin:
    """Refuse scheme changes the suggestion contract cannot carry safely."""

    def suggest_partition_scheme_change(
        self, point: PartitionSchemeChangeSuggestion
    ) -> PartitionSchemeChangeSuggestion:
        """Answer ``False`` for a change, ``None`` when nothing changed.

        The old/new projections are read only to distinguish "no action" from
        "unaddressable": a chain that switches data out of the live table
        without an explicit SWITCH-back would lose the table's data, so no
        combination of declaration fields can make one safe.
        """
        old_params = projection_params(point.old_partition)
        new_params = projection_params(point.new_partition)
        if old_params and old_params == new_params:
            return PartitionSchemeChangeSuggestion(operations=None)
        return PartitionSchemeChangeSuggestion(operations=False)
