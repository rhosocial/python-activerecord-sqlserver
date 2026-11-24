# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/create_table_layout_suggestion.py
"""SQLServerCreateTableLayoutSuggestionMixin -- SQL Server's CREATE TABLE layout.

SQL Server renders neither inline indexes nor inline comments in ``CREATE TABLE``;
the core capability probes therefore stay at their ``False`` defaults here, and
the layout is always "split". The two flags are read from the dialect instead of
being hardcoded so the answer cannot drift from the switches that gate rendering.
"""

from rhosocial.activerecord.backend.suggestion.definitions import (
    CreateTableLayoutSuggestion,
)
from rhosocial.activerecord.backend.suggestion.protocols import (
    CreateTableLayoutSuggestionSupport,
)


class SQLServerCreateTableLayoutSuggestionMixin(CreateTableLayoutSuggestionSupport):
    """Report the CREATE TABLE layout SQL Server renders: no inlining."""

    def suggest_create_table_layout(self) -> CreateTableLayoutSuggestion:
        inline_index = self.supports_inline_index()
        inline_comment = self.supports_table_comment()
        return CreateTableLayoutSuggestion(
            strategy="single" if inline_index and inline_comment else "split",
            inline_index=inline_index,
            inline_comment=inline_comment,
            state="actions",
        )


__all__ = ["SQLServerCreateTableLayoutSuggestionMixin"]
