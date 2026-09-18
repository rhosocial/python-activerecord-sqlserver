# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/merge.py


class SQLServerMergeMixin:
    """SQL Server MERGE statement capability declaration."""

    def supports_merge_statement(self) -> bool:
        """SQL Server has native MERGE support since 2008."""
        return True
