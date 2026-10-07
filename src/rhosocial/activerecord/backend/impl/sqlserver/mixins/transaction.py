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
        params = expr.get_params()
        mode = params.get("mode")

        if mode == TransactionMode.READ_ONLY:
            raise UnsupportedTransactionModeError(
                feature="READ ONLY transactions",
                backend="SQL Server",
                message="SQL Server does not support READ ONLY transactions."
            )

        return "BEGIN TRANSACTION", ()

    def format_set_transaction(self, expr: "SetTransactionExpression") -> Tuple[str, tuple]:
        """Format SET TRANSACTION for SQL Server.

        SQL Server requires SET TRANSACTION ISOLATION LEVEL before BEGIN TRANSACTION.
        """
        from rhosocial.activerecord.backend.errors import UnsupportedTransactionModeError
        from rhosocial.activerecord.backend.transaction import TransactionMode

        self._refuse_deferrable_transaction(expr)
        params = expr.get_params()
        mode = params.get("mode")

        if mode == TransactionMode.READ_ONLY:
            raise UnsupportedTransactionModeError(
                feature="READ ONLY transactions",
                backend="SQL Server",
                message="SQL Server does not support READ ONLY transactions.",
            )

        isolation_level = params.get("isolation_level")
        if isolation_level:
            level_name = self.get_isolation_level_name(isolation_level)
            return f"SET TRANSACTION ISOLATION LEVEL {level_name}", ()

        return "", ()
