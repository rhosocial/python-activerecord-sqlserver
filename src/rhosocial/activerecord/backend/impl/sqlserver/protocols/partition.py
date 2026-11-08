# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/partition.py
"""SQL Server table partitioning protocol.

SQL Server supports table partitioning via partition functions and
partition schemes (Enterprise Edition). This protocol extends the
generic PartitionSupport contract with SQL Server-specific capabilities.

Version Requirements:
- SQL Server 2012+ (partitioning via columnstore indexes)
- SQL Server 2008+ (basic partitioning)
"""

from typing import Protocol, Tuple, runtime_checkable, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.protocols import PartitionSupport

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.impl.sqlserver.expression.partition import (
        SQLServerDropPartitionFunctionExpression,
        SQLServerDropPartitionSchemeExpression,
        SQLServerPartitionFunctionExpression,
        SQLServerPartitionFunctionMergeExpression,
        SQLServerPartitionFunctionSplitExpression,
        SQLServerPartitionSchemeExpression,
        SQLServerPartitionSchemeNextUsedExpression,
        SQLServerSwitchPartitionExpression,
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

    def format_partition_function_expression(self, expr: "SQLServerPartitionFunctionExpression") -> Tuple[str, tuple]:
        """Format CREATE PARTITION FUNCTION statement."""
        ...

    def format_partition_scheme_expression(self, expr: "SQLServerPartitionSchemeExpression") -> Tuple[str, tuple]:
        """Format CREATE PARTITION SCHEME statement."""
        ...

    def format_partition_function_split_expression(
        self, expr: "SQLServerPartitionFunctionSplitExpression"
    ) -> Tuple[str, tuple]:
        """Format ``ALTER PARTITION FUNCTION ... SPLIT RANGE``."""
        ...

    def format_partition_function_merge_expression(
        self, expr: "SQLServerPartitionFunctionMergeExpression"
    ) -> Tuple[str, tuple]:
        """Format ``ALTER PARTITION FUNCTION ... MERGE RANGE``."""
        ...

    def format_partition_scheme_next_used_expression(
        self, expr: "SQLServerPartitionSchemeNextUsedExpression"
    ) -> Tuple[str, tuple]:
        """Format ``ALTER PARTITION SCHEME ... NEXT USED``."""
        ...

    def format_switch_partition_expression(
        self, expr: "SQLServerSwitchPartitionExpression"
    ) -> Tuple[str, tuple]:
        """Format ``ALTER TABLE ... SWITCH [PARTITION n] TO``."""
        ...

    def format_drop_partition_function_expression(
        self, expr: "SQLServerDropPartitionFunctionExpression"
    ) -> Tuple[str, tuple]:
        """Format ``DROP PARTITION FUNCTION``."""
        ...

    def format_drop_partition_scheme_expression(
        self, expr: "SQLServerDropPartitionSchemeExpression"
    ) -> Tuple[str, tuple]:
        """Format ``DROP PARTITION SCHEME``."""
        ...
