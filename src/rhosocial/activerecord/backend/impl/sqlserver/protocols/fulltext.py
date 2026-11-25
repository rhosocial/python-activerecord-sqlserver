# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/fulltext.py
"""SQL Server full-text search capability contract.

The ``render_*`` half is the name-and-arguments convenience form; the
``format_*`` half is the per-node formatter every statement in
``expression.fulltext`` dispatches through.
"""

from typing import TYPE_CHECKING, List, Protocol, Tuple, Optional, runtime_checkable

if TYPE_CHECKING:
    from ..expression.fulltext import (
        SQLServerCreateFullTextCatalogStatement,
        SQLServerCreateFullTextIndexStatement,
        SQLServerDropFullTextCatalogStatement,
        SQLServerDropFullTextIndexStatement,
    )


@runtime_checkable
class SQLServerFullTextSearchSupport(Protocol):
    def supports_fulltext_catalog(self) -> bool: ...
    def render_create_full_text_catalog_statement(
        self, catalog_name: str, as_default: bool = False
    ) -> Tuple[str, tuple]: ...
    def format_create_full_text_catalog_statement(
        self, expr: "SQLServerCreateFullTextCatalogStatement"
    ) -> Tuple[str, tuple]: ...
    def format_drop_full_text_catalog_statement(
        self, expr: "SQLServerDropFullTextCatalogStatement"
    ) -> Tuple[str, tuple]: ...
    def render_create_full_text_index_statement(
        self,
        table: str,
        columns: List[str],
        key_index: str,
        catalog_name: str,
    ) -> Tuple[str, tuple]: ...
    def format_create_full_text_index_statement(
        self, expr: "SQLServerCreateFullTextIndexStatement"
    ) -> Tuple[str, tuple]: ...
    def format_drop_full_text_index_statement(
        self, expr: "SQLServerDropFullTextIndexStatement"
    ) -> Tuple[str, tuple]: ...
    def render_contains_predicate(self, column: str, search_string: str) -> Tuple[str, tuple]: ...
    def render_freetext_predicate(self, column: str, search_string: str) -> Tuple[str, tuple]: ...
    def render_containstable_function(
        self, table: str, column: str, search_string: str, top_n: Optional[int] = None
    ) -> Tuple[str, tuple]: ...
