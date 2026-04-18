# src/rhosocial/activerecord/backend/impl/sqlserver/introspection/__init__.py
"""SQL Server schema introspection."""

from .introspector import SyncSQLServerIntrospector

__all__ = ["SyncSQLServerIntrospector"]
