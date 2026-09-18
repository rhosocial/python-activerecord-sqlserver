# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/set_type.py
"""SQL Server SET type protocol.

SQL Server has no MySQL-style SET column type; comma-separated values are
stored in VARCHAR columns. The formatters accept the corresponding
expression nodes and read their state off ``expr.<attr>``.
"""

from typing import Protocol, Tuple, runtime_checkable


@runtime_checkable
class SQLServerSetTypeSupport(Protocol):
    """SQL Server SET type approximation protocol."""

    def supports_set_type(self) -> bool:
        """Whether the MySQL-style SET type is supported (always False)."""
        ...

    def format_set_literal(self, expr) -> Tuple[str, tuple]:
        """Format a :class:`SQLServerSetLiteralExpression` node."""
        ...

    def format_find_in_set(self, expr) -> Tuple[str, tuple]:
        """Format a :class:`SQLServerFindInSetExpression` node."""
        ...

    def format_set_contains(self, expr) -> Tuple[str, tuple]:
        """Format a :class:`SQLServerSetContainsExpression` node."""
        ...
