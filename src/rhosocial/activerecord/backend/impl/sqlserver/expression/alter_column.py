# src/rhosocial/activerecord/backend/impl/sqlserver/expression/alter_column.py
"""SQL Server-specific ALTER TABLE column actions.

SQL Server re-specifies the full column rather than applying the standard
``SET``/``DROP`` subclauses, so ``ALTER COLUMN`` carries attributes with no
generic equivalent:

* ``data_type`` — the new type for ``ALTER COLUMN col <type>``.
* ``collate`` — the ``COLLATE <name>`` clause.
* ``not_null`` — ``NULL`` / ``NOT NULL`` (``None`` = omit).
* ``sparse`` — the ``SPARSE`` storage clause.
* ``masked_function`` / ``drop_masked`` — dynamic data masking.

They live on ``SQLServerAlterColumn`` (deriving the generic ``AlterColumn``)
and are rendered by the SQL Server ``format_alter_column_action`` override.
SQL Server does **not** share them with any other backend.
"""

from typing import Any, Optional, Union, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.statements import (
    AlterColumn,
    ColumnAlterOperation,
)

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SQLServerAlterColumn",
]


class SQLServerAlterColumn(AlterColumn):
    """A SQL Server ``ALTER COLUMN`` action extending the generic one.

    Adds the SQL Server-only ``data_type``, ``collate``, ``not_null``,
    ``sparse``, ``masked_function`` and ``drop_masked`` fields.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        column_name: str,
        operation: Union[ColumnAlterOperation, str] = "SET DATA TYPE",
        *,
        new_value: Any = None,
        cascade: bool = False,
        data_type: Optional[str] = None,
        collate: Optional[str] = None,
        not_null: Optional[bool] = None,
        sparse: bool = False,
        masked_function: Optional[str] = None,
        drop_masked: bool = False,
    ):
        super().__init__(
            dialect,
            column_name,
            operation,
            new_value=new_value,
            cascade=cascade,
        )
        self.data_type = data_type
        self.collate = collate
        self.not_null = not_null
        self.sparse = sparse
        self.masked_function = masked_function
        self.drop_masked = drop_masked
