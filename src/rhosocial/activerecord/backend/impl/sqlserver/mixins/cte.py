# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/cte.py


class SQLServerCTEMixin:
    """SQL Server CTE capability declarations."""

    def supports_basic_cte(self) -> bool:
        """Basic CTEs are supported in all modern SQL Server versions."""
        return True

    def supports_recursive_cte(self) -> bool:
        """Recursive CTEs are supported since SQL Server 2005."""
        return True

    def supports_materialized_cte(self) -> bool:
        """SQL Server has no ``AS [NOT] MATERIALIZED`` CTE hint.

        Measured on 2019 / 2022 / 2025 (``{SQL Server}`` driver):
        ``WITH c AS (...)`` is accepted, while ``AS MATERIALIZED`` and
        ``AS NOT MATERIALIZED`` are syntax errors near ``MATERIALIZED`` /
        ``NOT``.  An explicitly requested hint is refused by name rather than
        rendered, so the declaration is never silently bypassed.
        """
        return False

    def supports_unconditional_cte_order_by(self) -> bool:
        """SQL Server prohibits ORDER BY in CTEs unless TOP/OFFSET is present."""
        return False
