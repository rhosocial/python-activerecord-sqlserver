# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/locking.py
from typing import Tuple, TYPE_CHECKING

from .version_constants import SQL_SERVER_2019

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.query_parts import ForUpdateClause
    from ..expression.locking import SQLServerTableHintClause


class SQLServerLockingMixin:
    """SQL Server locking (table hints) capability and formatting."""

    def supports_for_update(self) -> bool:
        """SQL Server supports FOR UPDATE via table hints."""
        return True

    def supports_for_update_skip_locked(self) -> bool:
        """SQL Server 2019+ supports READPAST with UPDLOCK."""
        return self.version_at_least(SQL_SERVER_2019)

    def format_for_update_clause(self, expr: "ForUpdateClause") -> Tuple[str, tuple]:
        """Format FOR UPDATE for SQL Server using table hints.

        SQL Server does not support FOR UPDATE syntax. Instead, locking
        is achieved through table hints: WITH (UPDLOCK, ROWLOCK) etc.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
        from rhosocial.activerecord.backend.expression import LockStrength

        if expr.strength != LockStrength.UPDATE:
            # The phrase, not the artifact word: a refusal names what SQL would
            # have said, and the artifact word is a serialization detail that
            # means nothing to whoever reads the error.
            raise UnsupportedFeatureError(
                self.name, f"{expr.strength.phrase} (unsupported lock strength)"
            )

        all_params: list = []

        sql_parts = ["WITH (UPDLOCK, ROWLOCK)"]

        if expr.skip_locked and self.supports_for_update_skip_locked():
            sql_parts[0] = "WITH (UPDLOCK, ROWLOCK, READPAST)"

        return " ".join(sql_parts), tuple(all_params)

    def format_sqlserver_table_hint_clause(
        self, expr: "SQLServerTableHintClause"
    ) -> Tuple[str, tuple]:
        """Format a ``WITH (hint, ...)`` table hint clause.

        The clause holds hint *values* -- each is a word, not a node -- so the
        formatter reads ``name`` off each one rather than asking it to render
        itself.

        An empty clause renders as the empty string: the clause is a suffix on a
        table reference, and "no hints" means there is nothing to append.
        """
        if not expr.hints:
            return "", ()
        return f"WITH ({', '.join(hint.name for hint in expr.hints)})", ()
