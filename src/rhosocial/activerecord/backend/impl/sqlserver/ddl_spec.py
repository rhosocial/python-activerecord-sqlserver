# src/rhosocial/activerecord/backend/impl/sqlserver/ddl_spec.py
"""SQL Server-specific DDL feature specs.

Plain declaration objects (no dialect at definition time) recognized by the
SQL Server dialect's ``build_spec`` via ``isinstance``. Only the SQL Server
dialect claims these specs; every other backend silently ignores them
(``build_spec`` returns ``None``).

SQL Server partitioning requires a pre-created partition scheme; the
partition spec therefore carries the scheme name, boundary direction, and
the boundary values used by the companion
``CREATE PARTITION FUNCTION`` / ``CREATE PARTITION SCHEME`` statements
(those are separate DDL statements, not part of ``CreateTableExpression``).
"""

from typing import Optional, Sequence, Union

from rhosocial.activerecord.backend.expression.statements.ddl_spec import (
    ColumnTypeSpec,
    PartitionSpec,
)


class SQLServerRangePartition(PartitionSpec):
    """SQL Server ``ON scheme(col)`` RANGE partitioning declaration.

    Args:
        column: the partitioning column.
        partition_scheme: name of the partition scheme to place the table on.
        boundaries: boundary values for the companion partition function
            (plain scalars; rendered inline by the partition-function DDL).
        right: ``True`` (default) selects ``RANGE RIGHT``; ``False`` selects
            ``RANGE LEFT``.

    Example::

        SQLServerRangePartition(
            column="created_at",
            partition_scheme="ps_orders",
            boundaries=["2026-01-01", "2027-01-01"],
        )
    """

    __slots__ = ("column", "partition_scheme", "boundaries", "right")

    def __init__(
        self,
        column: str,
        partition_scheme: str,
        boundaries: Optional[Sequence[Union[str, int, float]]] = None,
        *,
        right: bool = True,
    ):
        if not column:
            raise ValueError("SQLServerRangePartition requires a partition column")
        if not partition_scheme:
            raise ValueError("SQLServerRangePartition requires a partition scheme name")
        self.column = column
        self.partition_scheme = partition_scheme
        self.boundaries = list(boundaries) if boundaries is not None else []
        self.right = right


class SQLServerColumnstoreIndexSpec(ColumnTypeSpec):
    """Mark a table for a clustered columnstore index (SQL Server 2014+).

    SQL Server renders ``CREATE CLUSTERED COLUMNSTORE INDEX`` as a separate
    statement; this spec only records the intent on the table — the backend
    claims it to expose ``supports_columnstore_index`` capability-driven
    flows. Column-level placement is not applicable.
    """

    __slots__ = ()