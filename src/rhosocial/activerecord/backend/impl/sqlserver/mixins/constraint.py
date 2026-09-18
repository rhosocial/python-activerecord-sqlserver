# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/constraint.py


class SQLServerConstraintMixin:
    """SQL Server constraint capability declarations."""

    def supports_constraint_enforced(self) -> bool:
        """SQL Server does not support ENFORCED/NOT ENFORCED constraint control."""
        return False

    def supports_fk_match(self) -> bool:
        """SQL Server does not support MATCH {SIMPLE|PARTIAL|FULL}."""
        return False

    def supports_deferrable_constraint(self) -> bool:
        """SQL Server does not support DEFERRABLE constraints."""
        return False
