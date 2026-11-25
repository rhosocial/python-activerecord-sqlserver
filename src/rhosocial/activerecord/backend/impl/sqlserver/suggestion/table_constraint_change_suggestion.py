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
``TableConstraint`` node; the enriched point carries the live declarations, so
the backend reuses the one whose branch names the kind instead of guessing one
from the frozen projection. Only UNIQUE / PRIMARY KEY / FOREIGN KEY / CHECK are
spellable in T-SQL: an unknown branch, SQL Server's refused constraint traits
(``DEFERRABLE`` / ``INITIALLY`` / ``ENFORCED`` / ``NOT VALID``), or a point with
only a frozen projection answers ``False``. A point with no actual difference
between its two sides answers ``None`` (no action required).
"""
from __future__ import annotations

from ....expression.objects import Table
from ....expression.statements.ddl_alter import (
    AddTableConstraintAction,
    AlterTableStatement,
    DropTableConstraintAction,
)
from ....expression.statements.ddl_table import (
    ConstraintValidation,
    TableCheckConstraint,
    TableConstraint,
    TableForeignKeyConstraint,
    TablePrimaryKeyConstraint,
    TableUniqueConstraint,
)
from ....suggestion import TableConstraintChangeSuggestion
from ._change_common import fingerprint, live_by_name, named_values

__all__ = ["SQLServerTableConstraintChangeSuggestionMixin"]


def _spellable_constraint(dialect: object, constraint: object) -> bool:
    """Whether ``ALTER TABLE ... ADD CONSTRAINT`` can spell this live node.

    The accepted kinds are the four T-SQL table constraints. ``EXCLUDE`` and
    any unknown branch have no spelling, so they are refused rather than
    rendered into SQL the server rejects. The SQL-standard traits are refused
    by this dialect's renderer (Msg 102/156 on 2019); saying ``False`` here
    keeps the chain renderable, instead of returning actions that fail at
    ``to_sql()`` time.
    """
    branch = getattr(constraint, "branch", None)
    if not isinstance(
        branch,
        (
            TablePrimaryKeyConstraint,
            TableUniqueConstraint,
            TableCheckConstraint,
            TableForeignKeyConstraint,
        ),
    ):
        return False
    if not hasattr(dialect, branch.format_method):
        return False
    for trait in (
        "deferrable",
        "not_deferrable",
        "initially_deferred",
        "initially_immediate",
        "enforced",
        "not_enforced",
    ):
        if getattr(constraint, trait, False):
            return False
    if getattr(constraint, "validation", None) is ConstraintValidation.NOVALIDATE:
        return False
    return True


class SQLServerTableConstraintChangeSuggestionMixin:
    """Suggest one ALTER TABLE statement per changed table constraint."""

    def suggest_table_constraint_change(
        self, point: TableConstraintChangeSuggestion
    ) -> TableConstraintChangeSuggestion:
        """Drop the removed constraints, then add the live new ones, one per statement."""
        old = named_values(point.old_constraints)
        new = named_values(point.new_constraints)
        if old is None or new is None:
            return TableConstraintChangeSuggestion(operations=False)
        old_live = live_by_name(point.old_constraint_declarations, TableConstraint)
        new_live = live_by_name(point.new_constraint_declarations, TableConstraint)
        removed = [
            name
            for name, value in old.items()
            if name not in new
            or fingerprint(name, value, old_live) != fingerprint(name, new[name], new_live)
        ]
        added = [
            name
            for name, value in new.items()
            if name not in old
            or fingerprint(name, value, new_live) != fingerprint(name, old[name], old_live)
        ]
        if not removed and not added:
            return TableConstraintChangeSuggestion(operations=None)

        table_name = point.table_name
        if not isinstance(table_name, str) or not table_name.strip():
            return TableConstraintChangeSuggestion(operations=False)

        replacements = {}
        for name in added:
            constraint = new_live.get(name)
            if constraint is None and isinstance(new[name], TableConstraint):
                # A caller may pass the live node directly in new_constraints.
                constraint = new[name]
            if constraint is None or not _spellable_constraint(self, constraint):
                return TableConstraintChangeSuggestion(operations=False)
            replacements[name] = constraint

        table = Table(self, table_name)
        actions = [DropTableConstraintAction(self, name) for name in removed]
        actions.extend(AddTableConstraintAction(self, replacements[name]) for name in added)
        statements = tuple(
            AlterTableStatement(self, table, [action]) for action in actions
        )
        return TableConstraintChangeSuggestion(operations=statements)
