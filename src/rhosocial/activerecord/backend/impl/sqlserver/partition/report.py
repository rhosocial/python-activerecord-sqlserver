# src/rhosocial/activerecord/backend/impl/sqlserver/partition/report.py
"""Value objects returned by SQL Server partition maintenance.

The objects keep the catalogue's own spelling -- the function's type name,
the scheme's filegroups, the boundary text the server rendered -- because a
value this package cannot parse is still information an operator needs.
"""

from dataclasses import dataclass
from typing import Any, Optional, Tuple

from rhosocial.activerecord.backend.partition import (
    PartitionOperation as CorePartitionOperation,
    PartitionReport as CorePartitionReport,
)

__all__ = [
    "PartitionFunctionInfo",
    "PartitionOperation",
    "PartitionRangeInfo",
    "PartitionReport",
    "PartitionSchemeInfo",
    "PartitionTableInfo",
]


@dataclass(frozen=True)
class PartitionFunctionInfo:
    """One partition function as the catalogue reports it.

    Attributes:
        name: Function name.
        data_type: The declared boundary type, e.g. ``date``.
        range_direction: ``LEFT`` or ``RIGHT``.
        boundary_values: Boundary text in boundary-id order, kept verbatim.
        partition_count: ``sys.partition_functions.fanout`` -- one more than
            the boundary count.
    """

    name: str
    data_type: str
    range_direction: str
    boundary_values: Tuple[str, ...] = ()
    partition_count: int = 0


@dataclass(frozen=True)
class PartitionSchemeInfo:
    """One partition scheme and its destinations.

    Attributes:
        name: Scheme name.
        function: The partition function the scheme maps.
        filegroups: Destination filegroup names in destination order.
        partition_count: The function's partition count at read time.
    """

    name: str
    function: str
    filegroups: Tuple[str, ...] = ()
    partition_count: int = 0

    @property
    def destination_count(self) -> int:
        """How many destinations the scheme currently declares."""
        return len(self.filegroups)


@dataclass(frozen=True)
class PartitionTableInfo:
    """One table built on a partition scheme.

    Attributes:
        name: Table name.
        schema: Schema the table lives in.
        scheme: Partition scheme the table is built on.
        function: Partition function behind that scheme.
        partition_column: The column named in ``ON scheme(column)``, when the
            catalogue could resolve it.
        partition_count: The function's partition count at read time.
    """

    name: str
    schema: Optional[str]
    scheme: str
    function: str
    partition_column: Optional[str] = None
    partition_count: int = 0


@dataclass(frozen=True)
class PartitionRangeInfo:
    """One partition of one table.

    Attributes:
        table: Table name.
        schema: Schema the table lives in.
        partition_number: SQL Server's partition number, from 1.
        low_boundary: Lower boundary text, or ``None`` for the first
            partition.
        high_boundary: Upper boundary text, or ``None`` for the last
            partition.
        row_count: ``sys.partitions.rows``.
        data_bytes: ``used_page_count`` multiplied by SQL Server's fixed 8 KiB
            page.
    """

    table: str
    schema: Optional[str]
    partition_number: int
    low_boundary: Optional[str] = None
    high_boundary: Optional[str] = None
    row_count: Optional[int] = None
    data_bytes: Optional[int] = None


# SQL Server's operation record is the core contract's record; the core field
# ``parent``/``level`` are optional because SQL Server has no tree.
PartitionOperation = CorePartitionOperation


@dataclass(frozen=True)
class PartitionReport(CorePartitionReport):
    """What the catalogue contains, and what an executor did or would do.

    SQL Server's report keeps the core envelope and adds the four catalogue
    collections its model has: functions, schemes, tables and per-partition
    ranges. ``target`` is the plan's function name (SQL Server always needs a
    function) or ``"(all)"`` for a catalogue-wide read.

    Attributes:
        function: The plan's function name, when the request named one.
        scheme: The plan's scheme name, when the request named one.
        functions: Every partition function the catalogue returned.
        schemes: Every partition scheme the catalogue returned.
        tables: Every partitioned table the catalogue returned.
        ranges: Per-partition rows for the requested table, when one was
            requested.
        missing_boundaries: Plan boundary values the function does not
            contain. Empty when the function itself is absent (all of the
            plan is missing, not just some boundaries).
        existing_boundaries: Boundary text the catalogue reported, in order.
    """

    function: Optional[str] = None
    scheme: Optional[str] = None
    functions: Tuple[PartitionFunctionInfo, ...] = ()
    schemes: Tuple[PartitionSchemeInfo, ...] = ()
    tables: Tuple[PartitionTableInfo, ...] = ()
    ranges: Tuple[PartitionRangeInfo, ...] = ()
    missing_boundaries: Tuple[Any, ...] = ()
    existing_boundaries: Tuple[str, ...] = ()

    def function_info(self, name: str) -> Optional[PartitionFunctionInfo]:
        """Return the named function, or ``None`` when it was not reported."""
        for info in self.functions:
            if info.name == name:
                return info
        return None

    def scheme_info(self, name: str) -> Optional[PartitionSchemeInfo]:
        """Return the named scheme, or ``None`` when it was not reported."""
        for info in self.schemes:
            if info.name == name:
                return info
        return None

    def table_info(self, name: str) -> Optional[PartitionTableInfo]:
        """Return the named table, or ``None`` when it was not reported."""
        for info in self.tables:
            if info.name == name:
                return info
        return None
