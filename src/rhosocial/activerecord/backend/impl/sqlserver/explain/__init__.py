# src/rhosocial/activerecord/backend/impl/sqlserver/explain/__init__.py
"""SQL Server EXPLAIN result types."""

from .types import SQLServerExplainRow, SQLServerExplainResult

__all__ = ["SQLServerExplainRow", "SQLServerExplainResult"]
