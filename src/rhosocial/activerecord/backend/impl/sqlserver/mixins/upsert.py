# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/upsert.py


class SQLServerUpsertMixin:
    """SQL Server upsert capability declarations."""

    def supports_upsert(self) -> bool:
        """SQL Server uses MERGE for upsert operations."""
        return True

    def get_upsert_syntax_type(self) -> str:
        """Return 'MERGE' for SQL Server."""
        return "MERGE"
