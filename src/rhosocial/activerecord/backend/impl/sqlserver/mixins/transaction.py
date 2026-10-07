# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/transaction.py
from typing import Any, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.transaction import (
        BeginTransactionExpression,
        SetTransactionExpression,
    )


class SQLServerTransactionMixin:
    """SQL Server transaction control capability declarations and formatting."""

    def supports_savepoint(self) -> bool:
        """SQL Server supports savepoints."""
        return True

    def supports_transaction_mode(self) -> bool:
        """SQL Server doesn't support READ ONLY transactions."""
        return False

    def supports_isolation_level_in_begin(self) -> bool:
        """SQL Server requires SET TRANSACTION ISOLATION LEVEL before BEGIN."""
        return False

    def supports_read_only_transaction(self) -> bool:
        """SQL Server doesn't support READ ONLY transactions."""
        return False

    def supports_deferrable_transaction(self) -> bool:
        """SQL Server doesn't support DEFERRABLE mode."""
        return False

    def supports_transaction_wait(self) -> bool:
        """SQL Server has no ``WAIT`` / ``NO WAIT`` transaction clause.

        Measured on 2019 / 2022 / 2025 (``{SQL Server}`` driver):
        ``BEGIN TRANSACTION WAIT`` is accepted, but the word is taken as the
        transaction *name* (``sys.dm_tran_active_transactions.name`` reads
        ``WAIT``; any control word behaves the same), ``BEGIN TRANSACTION
        NO WAIT`` is a syntax error, and ``SET TRANSACTION WAIT`` /
        ``SET TRANSACTION NO WAIT`` are syntax errors.  An explicitly requested
        spelling is refused by name rather than silently dropped.
        """
        return False

    def _transaction_wait_clause(self, expr: Any) -> str:
        """Consume the ``wait`` / ``no_wait`` pair for one transaction expression.

        Returns the spelling when the probe accepts it (so a subclass with a
        real lock-wait clause can render it), or refuses the requested spelling
        by name when the probe declines.  Never returns a spelling the probe
        did not approve.
        """
        params = expr.get_params()
        wait = params.get("wait")
        no_wait = params.get("no_wait")
        if not (wait or no_wait):
            return ""
        spelling = "WAIT" if wait else "NO WAIT"
        if not self.supports_transaction_wait():
            from rhosocial.activerecord.backend.dialect.exceptions import (
                UnsupportedFeatureError,
            )

            raise UnsupportedFeatureError(
                self.name,
                f"transaction {spelling}",
                f"{self.name} does not support the {spelling} transaction clause.",
            )
        return spelling

    def _refuse_deferrable_transaction(self, expr: Any) -> None:
        """Refuse an explicitly requested [NOT] DEFERRABLE transaction mode.

        SQL Server has no such mode (measured on 2019 / 2022 / 2025: the only
        ``BEGIN TRANSACTION`` spelling that parses is the transaction *name*,
        so ``BEGIN TRANSACTION DEFERRABLE`` names the transaction, and the
        ``NOT DEFERRABLE`` form is a syntax error). A requested spelling is
        refused by name rather than silently dropped.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import (
            UnsupportedFeatureError,
        )

        params = expr.get_params()
        if params.get("deferrable") or params.get("not_deferrable"):
            spelling = (
                "DEFERRABLE" if params.get("deferrable") else "NOT DEFERRABLE"
            )
            raise UnsupportedFeatureError(
                self.name,
                "DEFERRABLE transaction",
                f"{self.name} does not support the {spelling} transaction mode.",
            )

    def format_begin_transaction(
        self, expr: "BeginTransactionExpression"
    ) -> Tuple[str, tuple]:
        """Format BEGIN TRANSACTION for SQL Server."""
        from rhosocial.activerecord.backend.errors import UnsupportedTransactionModeError
        from rhosocial.activerecord.backend.transaction import TransactionMode

        self._refuse_deferrable_transaction(expr)
        wait_clause = self._transaction_wait_clause(expr)
        params = expr.get_params()
        mode = params.get("mode")

        if mode == TransactionMode.READ_ONLY:
            raise UnsupportedTransactionModeError(
                feature="READ ONLY transactions",
                backend="SQL Server",
                message="SQL Server does not support READ ONLY transactions."
            )

        if wait_clause:
            return f"BEGIN TRANSACTION {wait_clause}", ()
        return "BEGIN TRANSACTION", ()

    def format_set_transaction(self, expr: "SetTransactionExpression") -> Tuple[str, tuple]:
        """Format SET TRANSACTION for SQL Server.

        SQL Server requires SET TRANSACTION ISOLATION LEVEL before BEGIN TRANSACTION.
        """
        from rhosocial.activerecord.backend.errors import UnsupportedTransactionModeError
        from rhosocial.activerecord.backend.transaction import TransactionMode

        self._refuse_deferrable_transaction(expr)
        wait_clause = self._transaction_wait_clause(expr)
        params = expr.get_params()
        mode = params.get("mode")

        if mode == TransactionMode.READ_ONLY:
            raise UnsupportedTransactionModeError(
                feature="READ ONLY transactions",
                backend="SQL Server",
                message="SQL Server does not support READ ONLY transactions.",
            )

        options = []
        isolation_level = params.get("isolation_level")
        if isolation_level:
            level_name = self.get_isolation_level_name(isolation_level)
            options.append(f"ISOLATION LEVEL {level_name}")
        if wait_clause:
            options.append(wait_clause)
        if options:
            return f"SET TRANSACTION {' '.join(options)}", ()
        return "", ()
