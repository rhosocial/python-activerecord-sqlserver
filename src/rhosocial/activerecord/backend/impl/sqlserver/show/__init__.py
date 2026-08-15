# src/rhosocial/activerecord/backend/impl/sqlserver/show/__init__.py
"""
SQL Server SHOW functionality module.

SQL Server has no ``SHOW ...`` statements. This package provides the
SQL Server equivalents by querying system catalogs and parsing results
into the same typed dataclasses used across backend implementations.

Usage:
    from rhosocial.activerecord.backend.impl.sqlserver.show.functionality import (
        SQLServerShowFunctionality,
    )

    show = SQLServerShowFunctionality(backend)
"""

from .functionality import SQLServerShowFunctionality

__all__ = [
    "SQLServerShowFunctionality",
]
