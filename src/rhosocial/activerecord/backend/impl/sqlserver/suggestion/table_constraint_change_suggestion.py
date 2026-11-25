# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/table_constraint_change_suggestion.py
"""SQL Server's table-constraint-change suggestion.

T-SQL's disk-based ``ALTER TABLE`` grammar carries both halves of a constraint
change: ``ADD { <table_constraint> }`` and ``DROP [CONSTRAINT] constraint_name``
(Microsoft Learn, ``ALTER TABLE (Transact-SQL)``). Neither is edition- or
version-gated, so the backend can return a real chain: one
``AlterTableStatement`` per action, old constraints dropped before new ones are
added so a changed definition can reuse its name.

The core freezes a declared constraint to ``("params", ...)`` pairs. That
projection carries the constraint's ``name`` but not the branch *class*: a
UNIQUE and a PRIMARY KEY both reduce to ``{"columns": ...}``. A DROP needs only
the name, which the projection does carry. An ADD needs a real
``TableConstraint`` node to reuse; when the point carries only the frozen
projection, rebuilding the branch would mean inventing a constraint kind, so
the answer is ``False`` rather than a guessed node. A point with no actual
difference between its two sides answers ``None`` (no action required).
"""
from __future__ import annotations

from ....expression.objects import Table
from ....expression.statements.ddl_alter import (
    AddTableConstraintAction,
    AlterTableStatement,
    DropTableConstraintAction,
)
from ....expression.statements.ddl_table import TableConstraint
from ....suggestion import TableConstraintChangeSuggestion
from ._change_common import projection_name, projection_node

__all__ = ["SQLServerTableConstraintChangeSuggestionMixin"]


class SQLServerTableConstraintChangeSuggestionMixin:
    """Suggest one ALTER TABLE statement per changed table constraint."""

    def suggest_table_constraint_change(
        self, point: TableConstraintChangeSuggestion
    ) -> TableConstraintChangeSuggestion:
        """Drop the removed constraints, then add the new ones, one per statement."""
        old = list(point.old_constraints or ())
        new = list(point.new_constraints or ())
        dropped = [projection for projection in old if projection not in new]
        added = [projection for projection in new if projection not in old]
        if not dropped and not added:
            return TableConstraintChangeSuggestion(operations=None)

        table_name = point.table_name
        if not isinstance(table_name, str) or not table_name.strip():
            return TableConstraintChangeSuggestion(operations=False)

        actions = []
        for projection in dropped:
            name = projection_name(projection)
            if name is None:
                # The frozen projection hides the constraint name as an opaque
                # repr; DROP CONSTRAINT needs a real name, so refuse.
                return TableConstraintChangeSuggestion(operations=False)
            actions.append(DropTableConstraintAction(self, name))
        for projection in added:
            constraint = projection_node(projection)
            if not isinstance(constraint, TableConstraint):
                # An ADD must reuse the caller's TableConstraint: the frozen
                # projection drops the branch class and cannot rebuild one.
                return TableConstraintChangeSuggestion(operations=False)
            actions.append(AddTableConstraintAction(self, constraint))

        table = Table(self, table_name)
        statements = tuple(
            AlterTableStatement(self, table, [action]) for action in actions
        )
        return TableConstraintChangeSuggestion(operations=statements)
