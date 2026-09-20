# src/rhosocial/activerecord/backend/impl/sqlserver/expression/table_options.py
"""SQL Server-specific CREATE TABLE options.

SQL Server adds table-level options that have no generic equivalent:

* ``MEMORY_OPTIMIZED=ON`` — memory-optimized (in-memory) table.
* ``DURABILITY=SCHEMA_ONLY|SCHEMA_AND_DATA`` — durability of a
  memory-optimized table.

These live on ``SQLServerCreateTableOptions`` (deriving the generic
``CreateTableOptions``) and are rendered by the SQL Server
``format_create_table_statement`` override.
"""

from typing import Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.statements import CreateTableOptions

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SQLServerCreateTableOptions",
]


class SQLServerCreateTableOptions(CreateTableOptions):
    """A SQL Server CREATE TABLE options declaration extending the generic one.

    Adds the SQL Server-only ``memory_optimized`` / ``durability`` options.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        *,
        or_replace: bool = False,
        comment: Optional[str] = None,
        memory_optimized: bool = False,
        durability: Optional[str] = None,
    ):
        super().__init__(dialect, or_replace=or_replace, comment=comment)
        self.memory_optimized = memory_optimized
        self.durability = durability
