# src/rhosocial/activerecord/backend/impl/sqlserver/expression/column.py
"""SQL Server-specific column definition expressions.

SQL Server extends the standard column definition with per-column attributes
that have no generic equivalent:

* ``SPARSE`` — optimized storage for columns with many NULLs.
* ``ROWGUIDCOL`` — marks a ``uniqueidentifier`` column as the row GUID column.

These live on ``SQLServerColumnDefinition`` (deriving the generic
``ColumnDefinition``) and are rendered by the SQL Server
``format_column_definition`` override. They are declared through
``SQLServerColumnOptions`` (deriving the generic ``ColumnOptions``).
"""

from typing import Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.statements import ColumnDefinition
from rhosocial.activerecord.base import ColumnOptions

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SQLServerColumnDefinition",
    "SQLServerColumnOptions",
]


class SQLServerColumnDefinition(ColumnDefinition):
    """A SQL Server column definition extending the generic one.

    Adds the SQL Server-only ``sparse`` and ``rowguidcol`` attributes.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        data_type,
        constraints=None,
        comment: Optional[str] = None,
        generated_expression=None,
        attributes=None,
        *,
        sparse: Optional[bool] = None,
        rowguidcol: Optional[bool] = None,
    ):
        super().__init__(
            dialect,
            name,
            data_type,
            constraints=constraints,
            comment=comment,
            generated_expression=generated_expression,
            attributes=attributes,
        )
        self.sparse = sparse
        self.rowguidcol = rowguidcol


class SQLServerColumnOptions(ColumnOptions):
    """SQL Server per-column options declaration."""

    def __init__(
        self,
        *,
        sparse: Optional[bool] = None,
        rowguidcol: Optional[bool] = None,
    ):
        super().__init__()
        self.sparse = sparse
        self.rowguidcol = rowguidcol

    def column_definition_class(self):
        """Build a ``SQLServerColumnDefinition`` for these options."""
        return SQLServerColumnDefinition

    def apply_to(self, column) -> None:
        """Transfer the SQL Server-only fields onto the column definition."""
        if not isinstance(column, SQLServerColumnDefinition):
            raise TypeError(
                "SQLServerColumnOptions.apply_to requires a SQLServerColumnDefinition, "
                f"got {type(column).__name__}"
            )
        column.sparse = self.sparse
        column.rowguidcol = self.rowguidcol
