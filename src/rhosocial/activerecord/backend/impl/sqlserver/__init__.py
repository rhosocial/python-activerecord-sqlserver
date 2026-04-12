# src/rhosocial/activerecord/backend/impl/sqlserver/__init__.py
"""
SQL Server backend implementation for the Python ORM.

This module provides:
- SQL Server synchronous backend with connection management and query execution
- SQL Server asynchronous backend with async/await support
- SQL Server-specific connection configuration
- Type mapping and value conversion
- Transaction management with savepoint support (sync and async)
- SQL Server dialect and expression handling

Architecture:
- SQLServerBackend: Synchronous implementation using pyodbc
- AsyncSQLServerBackend: Asynchronous implementation using async pyodbc
- Independent from ORM frameworks - uses only native drivers
"""

__all__ = []
