# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/column_reorder_suggestion.py
"""SQL Server's column-reorder suggestion: an explicit refusal.

T-SQL's disk-based ``ALTER TABLE`` grammar has no column-position clause.
``ALTER COLUMN`` changes a column's type, nullability, collation, masking or
sparseness only; ``ADD`` appends the new column *after all existing columns*
(Microsoft Learn, ``ALTER TABLE (Transact-SQL)``, Arguments / ADD: "New columns
are added after all existing columns in the table being altered"). There is no
``FIRST`` / ``AFTER`` / ``POSITION`` form to target, so a reorder point has no
one-action statement chain this protocol can return.

A table rebuild could change the ordinal, but it moves every row and is exactly
the kind of data-affecting multi-step strategy a suggestion must not disguise
as a simple action. Every column-reorder point therefore answers ``False`` --
the explicit "this backend cannot address the reorder automatically" state --
for any old/new order, including a non-empty ``reordered_columns``.
"""
from __future__ import annotations

from ....suggestion import ColumnReorderSuggestion

__all__ = ["SQLServerColumnReorderSuggestionMixin"]


class SQLServerColumnReorderSuggestionMixin:
    """Answer SQL Server's lack of a column-position clause with ``False``."""

    def suggest_column_reorder(
        self, point: ColumnReorderSuggestion
    ) -> ColumnReorderSuggestion:
        """No native column-position clause: explicitly unsupported.

        The point's ``old_order`` / ``new_order`` and ``reordered_columns`` are
        deliberately not inspected: they describe *what* changed, but SQL
        Server offers no grammar to express the change, so the answer is the
        same for every reorder.
        """
        return ColumnReorderSuggestion(operations=False)
