# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/grouping.py


class SQLServerGroupingMixin:
    """SQL Server GROUP BY extension capability declarations."""

    def supports_rollup(self) -> bool:
        """ROLLUP is supported using WITH ROLLUP syntax."""
        return True

    def supports_cube(self) -> bool:
        """CUBE is supported using WITH CUBE syntax."""
        return True

    def supports_grouping_sets(self) -> bool:
        """GROUPING SETS is supported since SQL Server 2008."""
        return True
