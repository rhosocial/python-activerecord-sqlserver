# src/rhosocial/activerecord/backend/impl/sqlserver/protocols.py
"""
SQL Server-specific protocols.

This module defines protocol classes for SQL Server-specific features
that extend the standard backend protocols.
"""

from typing import Protocol, Tuple


class SQLServerIndexedViewSupport(Protocol):
    """Protocol for SQL Server indexed views."""
    
    def supports_indexed_view(self) -> bool:
        """Whether indexed views are supported."""
        ...
    
    def format_create_indexed_view_statement(self, expr) -> Tuple[str, tuple]:
        """Format CREATE INDEXED VIEW statement."""
        ...


class SQLServerIdentitySupport(Protocol):
    """Protocol for IDENTITY column support."""
    
    def supports_identity_insert(self) -> bool:
        """Whether SET IDENTITY_INSERT is supported."""
        ...
    
    def format_set_identity_insert(self, table: str, on: bool) -> str:
        """Format SET IDENTITY_INSERT statement."""
        ...


class SQLServerTableHintSupport(Protocol):
    """Protocol for table hints."""
    
    def supports_table_hints(self) -> bool:
        """Whether table hints are supported."""
        ...
    
    def format_table_hint(self, hints) -> str:
        """Format table hint clause."""
        ...


class SQLServerOutputSupport(Protocol):
    """Protocol for OUTPUT clause support."""
    
    def supports_output_clause(self) -> bool:
        """Whether OUTPUT clause is supported."""
        ...
    
    def format_output_clause(self, columns, clause_type: str) -> Tuple[str, tuple]:
        """Format OUTPUT clause for INSERT/UPDATE/DELETE."""
        ...
