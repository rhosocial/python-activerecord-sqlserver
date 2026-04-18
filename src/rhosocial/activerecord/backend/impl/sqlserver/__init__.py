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

from .backend import SQLServerBackend
from .config import SQLServerConnectionConfig
from .dialect import SQLServerDialect
from .transaction import SQLServerTransactionManager
from .adapters import (
    SQLServerUUIDAdapter,
    SQLServerDateTimeAdapter,
    SQLServerDateTimeOffsetAdapter,
    SQLServerDateAdapter,
    SQLServerTimeAdapter,
    SQLServerJSONAdapter,
    SQLServerXMLAdapter,
    SQLServerSpatialAdapter,
    SQLServerHierarchyIdAdapter,
)

from .explain import SQLServerExplainResult, SQLServerExplainRow


__all__ = [
    "SQLServerBackend",
    "SQLServerConnectionConfig",
    "SQLServerDialect",
    "SQLServerTransactionManager",
    "SQLServerUUIDAdapter",
    "SQLServerDateTimeAdapter",
    "SQLServerDateTimeOffsetAdapter",
    "SQLServerDateAdapter",
    "SQLServerTimeAdapter",
    "SQLServerJSONAdapter",
    "SQLServerXMLAdapter",
    "SQLServerSpatialAdapter",
    "SQLServerHierarchyIdAdapter",
    "SQLServerExplainResult",
    "SQLServerExplainRow",
]


def __getattr__(name: str):
    """Lazily load async components to avoid forcing aioodbc dependency.
    
    This allows users to import SQLServerBackend and other sync components without
    having aioodbc installed. Only when async components are actually accessed
    will aioodbc be required.
    
    Lazily loaded components:
    - AsyncSQLServerBackend: Async SQL Server backend implementation
    - AsyncSQLServerTransactionManager: Async transaction manager
    
    Raises:
        ImportError: If aioodbc is not installed when accessing async components.
        AttributeError: If the requested attribute doesn't exist.
    """
    _lazy_imports = {
        "AsyncSQLServerBackend": (".async_backend", "AsyncSQLServerBackend"),
        "AsyncSQLServerTransactionManager": (".async_transaction", "AsyncSQLServerTransactionManager"),
    }
    
    if name in _lazy_imports:
        module_path, class_name = _lazy_imports[name]
        try:
            import importlib
            module = importlib.import_module(module_path, __name__)
            return getattr(module, class_name)
        except ImportError as e:
            raise ImportError(
                f"{name} requires 'aioodbc' package. "
                f"Install it with: pip install rhosocial-activerecord-sqlserver[async] "
                f"or pip install aioodbc"
            ) from e
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
