# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/cte.py


class SQLServerCTEMixin:
    """SQL Server CTE capability declarations."""

    def supports_basic_cte(self) -> bool:
        """Basic CTEs are supported in all modern SQL Server versions."""
        return True

    def supports_recursive_cte(self) -> bool:
        """Recursive CTEs are supported since SQL Server 2005."""
        return True

    def supports_unconditional_cte_order_by(self) -> bool:
        """SQL Server prohibits ORDER BY in CTEs unless TOP/OFFSET is present."""
        return False
