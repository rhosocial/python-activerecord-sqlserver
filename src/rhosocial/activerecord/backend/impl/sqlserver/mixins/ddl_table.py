# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/ddl_table.py
from .version_constants import SQL_SERVER_2016


class SQLServerTableMixin:
    """SQL Server table DDL capability declarations."""

    def supports_truncate(self) -> bool:
        """SQL Server supports ``TRUNCATE TABLE``.

        Measured accepted on 2019 / 2022 / 2025 (``{SQL Server}`` driver) and
        the table is emptied; the modifier pair (``CASCADE`` / ``RESTRICT``) is
        refused by the formatter, not by this master probe.
        """
        return True

    def supports_if_exists_table(self) -> bool:
        """SQL Server supports DROP TABLE IF EXISTS (2016+)."""
        return self.version_at_least(SQL_SERVER_2016)

    def supports_drop_table_cascade(self) -> bool:
        """SQL Server does not support CASCADE for DROP TABLE."""
        return False

    def supports_drop_table_restrict(self) -> bool:
        """SQL Server does not support RESTRICT for DROP TABLE."""
        return False

    def supports_rename_table(self) -> bool:
        """SQL Server has no ``ALTER TABLE ... RENAME TO`` clause.

        The engine renames a table with the ``sp_rename`` stored procedure
        (``EXEC sp_rename 'old', 'new'``). That is a procedure call, not an
        ``ALTER TABLE`` action, so it cannot be expressed as the fragment a
        :class:`RenameTableAction` contributes to ``ALTER TABLE <table>``.
        Answering ``False`` makes core's ``format_rename_table_action``
        raise ``UnsupportedFeatureError`` instead of emitting the invalid
        T-SQL ``ALTER TABLE ... RENAME TO ...``.
        """
        return False

    def supports_rename_column(self) -> bool:
        """SQL Server has no ``ALTER TABLE ... RENAME COLUMN ... TO`` clause.

        A column rename is likewise an ``sp_rename`` call
        (``EXEC sp_rename 'dbo.t.old', 'new', 'COLUMN'``), not an
        ``ALTER TABLE`` action, so it does not fit the one-action-fragment
        contract either. ``False`` makes core's
        ``format_rename_column_action`` refuse rather than emit invalid
        ``RENAME COLUMN`` T-SQL.
        """
        return False

    def supports_add_column(self) -> bool:
        """SQL Server supports ALTER TABLE ADD COLUMN."""
        return True

    def supports_table_partitioning(self) -> bool:
        """SQL Server supports table partitioning."""
        return True
