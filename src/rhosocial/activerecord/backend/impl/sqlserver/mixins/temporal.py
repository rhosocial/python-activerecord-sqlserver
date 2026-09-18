# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/temporal.py
from .version_constants import SQL_SERVER_2016


class SQLServerTemporalMixin:
    """SQL Server temporal table capability declaration."""

    def supports_temporal_tables(self) -> bool:
        """SQL Server 2016+ supports temporal tables."""
        return self.version >= SQL_SERVER_2016
