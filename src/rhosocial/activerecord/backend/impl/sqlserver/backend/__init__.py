# src/rhosocial/activerecord/backend/impl/sqlserver/backend/__init__.py
"""Sqlserver backend implementations.

Every backend keeps both classes in this package: the sync class in
``backend.py`` and the async class in ``async_backend.py``. So the sync class
is at ``impl.sqlserver.backend.backend`` and the async class at
``impl.sqlserver.backend.async_backend``.
"""

from .backend import SQLServerBackend
