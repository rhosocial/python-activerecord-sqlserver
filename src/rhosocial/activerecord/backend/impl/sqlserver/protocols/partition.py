# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/partition.py
"""SQL Server table partitioning protocol.

SQL Server supports table partitioning via partition functions and
partition schemes (Enterprise Edition). This protocol extends the
generic PartitionSupport contract with SQL Server-specific capabilities.

Version Requirements:
- SQL Server 2012+ (partitioning via columnstore indexes)
- SQL Server 2008+ (basic partitioning)
"""

from typing import Protocol, Sequence, Tuple, runtime_checkable, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.protocols import PartitionSupport

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.impl.sqlserver.expression.partition import (
        SQLServerPartitionFunctionExpression,
        SQLServerPartitionSchemeExpression,
    )


@runtime_checkable
class SQLServerPartitionSupport(PartitionSupport, Protocol):
    """SQL Server table partitioning protocol.

    SQL Server supports RANGE partitioning only, using a three-tier model:
    partition function → partition scheme → ON clause in CREATE TABLE.
    """

    def supports_range_right_partitioning(self) -> bool:
        """Whether RANGE RIGHT partitioning is supported."""
        ...

    def supports_range_left_partitioning(self) -> bool:
        """Whether RANGE LEFT partitioning is supported."""
        ...

    def supports_partition_function(self) -> bool:
        """Whether CREATE PARTITION FUNCTION is supported."""
        ...

    def supports_partition_scheme(self) -> bool:
        """Whether CREATE PARTITION SCHEME is supported."""
        ...

    def supports_switch_partition(self) -> bool:
        """Whether ALTER TABLE ... SWITCH PARTITION is supported."""
        ...

    def supports_split_partition(self) -> bool:
        """Whether ALTER PARTITION FUNCTION ... SPLIT RANGE is supported."""
        ...

    def supports_merge_partition(self) -> bool:
        """Whether ALTER PARTITION FUNCTION ... MERGE RANGE is supported."""
        ...

    def format_sqlserver_partition_function(self, expr: "SQLServerPartitionFunctionExpression") -> Tuple[str, tuple]:
        """Format CREATE PARTITION FUNCTION statement."""
        ...

    def format_sqlserver_partition_scheme(self, expr: "SQLServerPartitionSchemeExpression") -> Tuple[str, tuple]:
        """Format CREATE PARTITION SCHEME statement."""
        ...
