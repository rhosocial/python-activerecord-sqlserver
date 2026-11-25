# src/rhosocial/activerecord/backend/impl/sqlserver/expression/rename.py
"""SQL Server object rename through ``sp_rename``.

T-SQL has no ``ALTER TABLE ... RENAME COLUMN`` and no ``ALTER TABLE ... RENAME
TO``. Both renames are the ``sp_rename`` stored procedure:

    EXEC sp_rename N'[dbo].[T1].[old_col]', N'new_col', N'COLUMN'
    EXEC sp_rename N'[dbo].[T1]', N'T2', N'OBJECT'

That is a procedure call rather than a DDL clause, which is why this backend
answers ``supports_rename_column`` / ``supports_rename_table`` with ``False``
(core's action vocabulary spells the clauses this server does not have) and
models the real mechanism as this proprietary statement instead. Nothing here
is re-exported from core.

The constructor collects parameters only; the formatter owns the object-kind
vocabulary, the name checks and every refusal.
"""

from typing import Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from ..dialect import SQLServerDialect

__all__ = ["SQLServerRenameObjectStatement"]

#: The object kinds Microsoft documents for ``sp_rename``'s third argument.
RENAME_OBJECT_KINDS = ("COLUMN", "OBJECT", "INDEX", "USERDATATYPE", "STATISTICS")


class SQLServerRenameObjectStatement(BaseExpression):
    """``EXEC sp_rename N'<old>', N'<new>', N'<kind>'``.

    Args:
        dialect: The dialect this statement is bound to; ``None`` is accepted
            and the tree can be rendered later through ``to_sql(dialect)``.
        old_name: The object's current address. ``sp_rename`` wants the full
            dotted address for a column (``schema.table.column``) and just
            ``schema.table`` for a table.
        new_name: The new leaf name (not a dotted address).
        kind: ``"COLUMN"`` / ``"OBJECT"`` (and the other documented kinds).
            The formatter validates the word.
    """

    def __init__(
        self,
        dialect: Optional["SQLServerDialect"],
        old_name: str,
        new_name: str,
        kind: str = "OBJECT",
    ):
        super().__init__(dialect)
        self.old_name = old_name
        self.new_name = new_name
        self.kind = kind

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this statement."""
        return "format_rename_object_statement"