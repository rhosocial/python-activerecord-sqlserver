# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/window.py
from .version_constants import SQL_SERVER_2012


class SQLServerWindowMixin:
    """SQL Server window function capability declarations."""

    def supports_window_functions(self) -> bool:
        """Window functions are supported since SQL Server 2005."""
        return True

    def supports_window_frame_clause(self) -> bool:
        """Window frame clauses are supported since SQL Server 2012."""
        return self.version >= SQL_SERVER_2012
