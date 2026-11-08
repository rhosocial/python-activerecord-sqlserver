# src/rhosocial/activerecord/backend/impl/sqlserver/partition/__init__.py
"""SQL Server partition planning and maintenance.

SQL Server does not partition with ``PARTITION BY``. Its model is three
objects: a ``PARTITION FUNCTION`` that fixes the boundary values, a
``PARTITION SCHEME`` that maps each resulting partition to a filegroup, and a
table built ``ON <scheme>(<column>)``. Removing a partition is not a ``DROP``:
the boundary is merged away with ``MERGE RANGE``. There is no subpartitioning
at any version, and no ``PARTITION OF``.

This package holds the backend-level objects and executor for that model:

:mod:`plan`
    :class:`SQLServerPartitionPlan` -- the function, boundaries, direction and
    optional scheme, with no table name and no retention rule.
:mod:`report`
    Value objects describing what the catalogue answered and what an executor
    did (or would do under a dry run).
:mod:`maintenance`
    :class:`SQLServerPartitionMaintenance` and
    :class:`AsyncSQLServerPartitionMaintenance`, each with ``ensure``, ``list``,
    ``retention_boundaries``, ``drop_or_merge``, ``drop_before`` and
    ``validate``.

Table names are arguments, never defaults: the application owns which table
is partitioned and which rows it keeps.
"""

from .maintenance import AsyncSQLServerPartitionMaintenance, SQLServerPartitionMaintenance
from .plan import SQLServerPartitionPlan
from .report import (
    PartitionFunctionInfo,
    PartitionOperation,
    PartitionRangeInfo,
    PartitionReport,
    PartitionSchemeInfo,
    PartitionTableInfo,
)

__all__ = [
    "AsyncSQLServerPartitionMaintenance",
    "PartitionFunctionInfo",
    "PartitionOperation",
    "PartitionRangeInfo",
    "PartitionReport",
    "PartitionSchemeInfo",
    "PartitionTableInfo",
    "SQLServerPartitionMaintenance",
    "SQLServerPartitionPlan",
]
