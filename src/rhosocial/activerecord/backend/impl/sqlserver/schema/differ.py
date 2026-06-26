# src/rhosocial/activerecord/backend/impl/sqlserver/schema/differ.py
"""SQL Server schema differ — column ordinal position matters."""

from rhosocial.activerecord.backend.schema.differ import SchemaDiffer


class SQLServerSchemaDiffer(SchemaDiffer):
    """SQL Server schema differ.

    SQL Server column order matters: ALTER TABLE ADD appends columns
    (unless using WITH VALUES or specific constraints).
    """

    def _columns_equivalent(self, old_col, new_col) -> bool:
        if not super()._columns_equivalent(old_col, new_col):
            return False
        return old_col.ordinal_position == new_col.ordinal_position