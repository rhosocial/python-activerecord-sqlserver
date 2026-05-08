# src/rhosocial/activerecord/backend/impl/sqlserver/protocols.py
"""
SQL Server-specific protocols.

This module defines protocol classes for SQL Server-specific features
that extend the standard backend protocols.
"""

from typing import Dict, List, Optional, Protocol, Tuple, Any, Union

from rhosocial.activerecord.backend.dialect.protocols import (
    TableSupport,
    LockingSupport,
    JSONSupport,
)


class SQLServerIndexedViewSupport(Protocol):
    """Protocol for SQL Server indexed views."""

    def supports_indexed_view(self) -> bool:
        ...

    def format_create_indexed_view_statement(self, expr) -> Tuple[str, tuple]:
        ...


class SQLServerIdentitySupport(Protocol):
    """Protocol for IDENTITY column support."""

    def supports_identity_insert(self) -> bool:
        ...

    def format_set_identity_insert(self, table: str, on: bool) -> str:
        ...


class SQLServerTableHintSupport(Protocol):
    """Protocol for table hints."""

    def supports_table_hints(self) -> bool:
        ...

    def format_table_hint(self, hints: List[str]) -> str:
        ...


class SQLServerOutputSupport(Protocol):
    """Protocol for OUTPUT clause support."""

    def supports_output_clause(self) -> bool:
        ...

    def format_output_clause(self, columns: List[str], clause_type: str) -> Tuple[str, tuple]:
        ...


class SQLServerTableSupport(TableSupport, Protocol):
    """SQL Server-specific table support extending standard TableSupport."""

    def supports_select_into(self) -> bool:
        ...

    def supports_tablesample(self) -> bool:
        ...

    def format_select_into_statement(self, expr) -> Tuple[str, tuple]:
        ...


class SQLServerLockingSupport(LockingSupport, Protocol):
    """SQL Server-specific locking support with table hints."""

    def supports_readpast(self) -> bool:
        ...

    def format_table_hint_locking(self, hint_type: str) -> str:
        ...


class SQLServerJSONSupport(JSONSupport, Protocol):
    """SQL Server-specific JSON support with OPENJSON."""

    def format_openjson_expression(
        self,
        json_doc: str,
        path: Optional[str] = None,
        schema: Optional[Dict[str, str]] = None,
        alias: Optional[str] = None,
    ) -> Tuple[str, tuple]:
        ...


class SQLServerTemporalTableSupport(Protocol):
    """Protocol for SQL Server temporal table support (2016+)."""

    def supports_system_versioning(self) -> bool:
        ...

    def format_create_temporal_table_statement(self, expr) -> Tuple[str, tuple]:
        ...

    def format_temporal_period_definition(self, start_column: str, end_column: str) -> str:
        ...


class SQLServerSequenceSupport(Protocol):
    """Protocol for SQL Server SEQUENCE support (2012+)."""

    def supports_sequence_as_data_type(self) -> bool:
        ...

    def format_next_value_for(self, sequence_name: str) -> str:
        ...


class SQLServerFullTextSearchSupport(Protocol):
    """Protocol for SQL Server full-text search support."""

    def supports_fulltext_catalog(self) -> bool:
        ...

    def format_create_fulltext_catalog_statement(self, catalog_name: str) -> str:
        ...

    def format_contains_predicate(self, column: str, search_string: str) -> Tuple[str, tuple]:
        ...

    def format_freetext_predicate(self, column: str, search_string: str) -> Tuple[str, tuple]:
        ...

    def format_containstable_function(
        self, table: str, column: str, search_string: str, top_n: Optional[int] = None
    ) -> Tuple[str, tuple]:
        ...


class SQLServerTryCastSupport(Protocol):
    """Protocol for SQL Server TRY_CAST/TRY_CONVERT support (2012+)."""

    def supports_try_cast(self) -> bool:
        ...

    def supports_try_convert(self) -> bool:
        ...

    def format_try_cast_expression(self, expr_sql: str, target_type: str) -> Tuple[str, tuple]:
        ...

    def format_try_convert_expression(self, expr_sql: str, target_type: str, style: Optional[int] = None) -> Tuple[str, tuple]:
        ...


class SQLServerPaginationSupport(Protocol):
    """Protocol for SQL Server OFFSET FETCH pagination (2012+)."""

    def supports_offset_fetch(self) -> bool:
        ...

    def supports_order_by_in_subquery(self) -> bool:
        ...


class SQLServerMergeSupport(Protocol):
    """Protocol for SQL Server MERGE statement enhancements."""

    def supports_merge_output(self) -> bool:
        ...

    def supports_merge_holdlock(self) -> bool:
        ...

    def format_merge_output_clause(self, columns: List[str], action_type: Optional[str] = None) -> Tuple[str, tuple]:
        ...