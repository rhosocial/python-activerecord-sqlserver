# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/index.py
from .version_constants import SQL_SERVER_2016


class SQLServerIndexMixin:
    """SQL Server index capability declarations."""

    def supports_index_if_exists(self) -> bool:
        """SQL Server supports DROP INDEX IF EXISTS (2016+)."""
        return self.version >= SQL_SERVER_2016

    def supports_partial_index(self) -> bool:
        """SQL Server supports filtered indexes (WHERE clause)."""
        return True

    def supports_functional_index(self) -> bool:
        """SQL Server supports indexes on computed columns."""
        return True

    def supports_concurrent_index(self) -> bool:
        """SQL Server supports ONLINE index creation (Enterprise edition)."""
        return True

    def supports_fulltext_index(self) -> bool:
        """SQL Server supports FULLTEXT indexes."""
        return True
