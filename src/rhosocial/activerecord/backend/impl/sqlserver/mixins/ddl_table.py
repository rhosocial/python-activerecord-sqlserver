# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/table.py
from typing import Tuple, TYPE_CHECKING

from .version_constants import SQL_SERVER_2016

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import (
        CreateTableExpression,
        DropTableExpression,
        AlterTableExpression,
        ColumnDefinition,
        TableConstraint,
        IndexDefinition,
    )


class SQLServerTableMixin:
    """SQL Server table DDL capability declarations."""

    def supports_if_exists_table(self) -> bool:
        """SQL Server supports DROP TABLE IF EXISTS (2016+)."""
        return self.version >= SQL_SERVER_2016

    def supports_drop_table_cascade(self) -> bool:
        """SQL Server does not support CASCADE for DROP TABLE."""
        return False

    def supports_drop_table_restrict(self) -> bool:
        """SQL Server does not support RESTRICT for DROP TABLE."""
        return False

    def supports_multi_action_alter_table(self) -> bool:
        """SQL Server requires one action per ALTER TABLE statement."""
        return False

    def supports_add_column(self) -> bool:
        """SQL Server supports ALTER TABLE ADD COLUMN."""
        return True

    def supports_table_partitioning(self) -> bool:
        """SQL Server supports table partitioning."""
        return True
