# src/rhosocial/activerecord/backend/impl/sqlserver/expression/default_constraint.py
"""SQL Server named default-constraint action.

SQL Server attaches a column default as a *named* constraint rather than
through an ``ALTER COLUMN ... SET DEFAULT`` clause:

    ALTER TABLE [dbo].[T1]
        ADD CONSTRAINT [df_status] DEFAULT ('new') FOR [status]

Removing it is the ordinary ``DROP CONSTRAINT [df_status]`` (the drop-by-name
path this backend already renders). Core models ``SET DEFAULT`` as a column
alteration, a spelling T-SQL does not have, so the ADD half is
backend-proprietary and lives here; nothing is re-exported from core.

The value is a DDL literal: it is inlined (single quotes doubled) because DDL
carries no bind parameters. The constructor collects parameters only; the
formatter validates the column, the constraint name and the value shape.
"""

from typing import Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AlterTableAction,
)

if TYPE_CHECKING:  # pragma: no cover
    from ..dialect import SQLServerDialect

__all__ = ["SQLServerAddDefaultConstraintAction"]


class SQLServerAddDefaultConstraintAction(AlterTableAction):
    """``ALTER TABLE ... ADD CONSTRAINT <name> DEFAULT <value> FOR <column>``.

    Args:
        dialect: The dialect this action is bound to; ``None`` is accepted.
        column: The column the default applies to.
        value: A string value, rendered inline with its quotes doubled.
        constraint_name: Optional constraint name; SQL Server generates one
            when it is omitted.
    """

    def __init__(
        self,
        dialect: Optional["SQLServerDialect"],
        column: str,
        value: str,
        *,
        constraint_name: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.column = column
        self.value = value
        self.constraint_name = constraint_name

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this action."""
        return "format_add_default_constraint_action"