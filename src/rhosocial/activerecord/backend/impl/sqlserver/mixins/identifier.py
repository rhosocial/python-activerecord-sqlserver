# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/identifier.py


class SQLServerIdentifierMixin:
    """SQL Server identifier formatting (square brackets)."""

    def format_identifier(self, identifier: str, need_quote: bool = True) -> str:
        """
        Format identifier using SQL Server's brackets.

        SQL Server uses square brackets [] for identifiers, escaping
        internal brackets by doubling them.

        Args:
            identifier: Raw identifier string
            need_quote: Whether to quote the identifier (default True)

        Returns:
            Quoted identifier with escaped internal brackets, or raw identifier if need_quote is False
        """
        if not need_quote:
            if self.is_reserved_word(identifier):
                import warnings
                from rhosocial.activerecord.backend.warnings import IdentifierQuotingWarning
                warnings.warn(
                    f"Identifier '{identifier}' is a reserved word in {self.name} "
                    f"and may cause SQL errors without quoting.",
                    IdentifierQuotingWarning,
                    stacklevel=2,
                )
            return identifier
        escaped = identifier.replace("]", "]]")
        return f"[{escaped}]"
