# src/rhosocial/activerecord/backend/impl/sqlserver/functions/schema.py
"""
SQL Server schema resolution functions.

Provides a SQL expression factory for asking the server which namespace an
unqualified reference resolves against.

Follows the expression-dialect separation architecture:
- First parameter is always the dialect instance
- Returns an Expression object (FunctionCall)
- Does not concatenate SQL strings directly
"""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.expression import core

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


def current_schema(dialect: "SQLDialectBase") -> "core.FunctionCall":
    """Create a function call for the current schema.

    Returns the default schema name for the current user -- the schema an
    unqualified reference resolves against. Never NULL: SQL Server always has a
    default schema, defaulting to dbo.

    Usage:
        - current_schema(dialect)

    Args:
        dialect: The SQL dialect instance

    Returns:
        A FunctionCall instance that evaluates to the current schema name
    """
    return core.FunctionCall(dialect, "SCHEMA_NAME")
