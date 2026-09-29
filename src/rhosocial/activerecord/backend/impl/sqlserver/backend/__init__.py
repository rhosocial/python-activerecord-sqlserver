# src/rhosocial/activerecord/backend/impl/sqlserver/backend/__init__.py
"""Sqlserver backend implementations.

Every backend keeps both classes in this package: the sync class in
``backend.py`` and the async class in ``async_backend.py``. The async class is
re-exported here too, but resolved on first access, because it needs the
``aioodbc`` package that the ``rhosocial-activerecord-sqlserver[async]`` extra installs.
"""

from .backend import SQLServerBackend

__all__ = [
    "SQLServerBackend",
    "AsyncSQLServerBackend",
]


def __getattr__(name: str):
    """Resolve the async class on first access.

    Raises:
        ImportError: if aioodbc is missing, naming the extra that provides it.
        AttributeError: for any other name.
    """
    if name == "AsyncSQLServerBackend":
        try:
            from .async_backend import AsyncSQLServerBackend as backend
        except ImportError as e:
            raise ImportError(
                "AsyncSQLServerBackend requires the 'aioodbc' package. "
                "Install it with: pip install rhosocial-activerecord-sqlserver[async] or pip install aioodbc"
            ) from e
        return backend
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
