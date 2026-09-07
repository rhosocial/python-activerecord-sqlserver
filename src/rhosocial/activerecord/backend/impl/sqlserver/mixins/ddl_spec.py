# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/ddl_spec.py
"""SQL Server ``build_spec`` implementation (DDL feature-spec claiming).

Composed into ``SQLServerDialect``. Claims the SQL Server-specific Specs
defined in ``..ddl_spec`` via ``isinstance`` and translates them into the
SQL Server expression layer. All other Specs fall through to the generic
``DDLSpecBuildingMixin`` base translation.
"""

from typing import Any, Optional

from rhosocial.activerecord.backend.dialect.mixins.ddl_spec import DDLSpecBuildingMixin
from rhosocial.activerecord.backend.expression import Column
from rhosocial.activerecord.backend.expression.statements.ddl_spec import DDLSpec

from ..ddl_spec import SQLServerRangePartition
from ..expression.partition import (
    SQLServerPartitionByRangeClause,
    SQLServerPartitionRangeDirection,
)


class SQLServerDDLSpecMixin(DDLSpecBuildingMixin):
    """SQL Server-specific ``build_spec`` claiming and translation."""

    def build_spec(self, spec: "DDLSpec") -> Optional[Any]:
        """Claim SQL Server Specs; otherwise defer to the generic build."""
        if isinstance(spec, SQLServerRangePartition):
            return self._build_sqlserver_range_partition(spec)
        return super().build_spec(spec)

    def _build_sqlserver_range_partition(self, spec: "SQLServerRangePartition"):
        """Translate a RANGE partition Spec to ``SQLServerPartitionByRangeClause``.

        SQL Server only supports RANGE partitioning. The companion
        ``CREATE PARTITION FUNCTION`` / ``CREATE PARTITION SCHEME`` statements
        are separate DDL built from ``spec.boundaries`` by the caller.
        """
        direction = (
            SQLServerPartitionRangeDirection.RIGHT
            if spec.right
            else SQLServerPartitionRangeDirection.LEFT
        )
        return SQLServerPartitionByRangeClause(
            self,
            keys=[Column(self, spec.column)],
            partition_scheme=spec.partition_scheme,
            range_direction=direction,
            dialect_options={"partition_scheme": spec.partition_scheme},
        )