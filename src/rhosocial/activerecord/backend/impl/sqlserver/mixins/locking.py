# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/locking.py
from typing import Tuple, TYPE_CHECKING

from .version_constants import SQL_SERVER_2019

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.query_parts import ForUpdateClause


class SQLServerLockingMixin:
    """SQL Server locking (table hints) capability and formatting."""

    def supports_for_update(self) -> bool:
        """SQL Server supports FOR UPDATE via table hints."""
        return True

    def supports_for_update_skip_locked(self) -> bool:
        """SQL Server 2019+ supports READPAST with UPDLOCK."""
        return self.version >= SQL_SERVER_2019

    def format_for_update_clause(self, clause: "ForUpdateClause") -> Tuple[str, tuple]:
        """Format FOR UPDATE for SQL Server using table hints.

        SQL Server does not support FOR UPDATE syntax. Instead, locking
        is achieved through table hints: WITH (UPDLOCK, ROWLOCK) etc.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
        from rhosocial.activerecord.backend.expression import LockStrength

        if clause.strength != LockStrength.UPDATE:
            raise UnsupportedFeatureError(
                self.name, f"{clause.strength.value} (unsupported lock strength)"
            )

        all_params: list = []

        sql_parts = ["WITH (UPDLOCK, ROWLOCK)"]

        if clause.skip_locked and self.supports_for_update_skip_locked():
            sql_parts[0] = "WITH (UPDLOCK, ROWLOCK, READPAST)"

        return " ".join(sql_parts), tuple(all_params)
