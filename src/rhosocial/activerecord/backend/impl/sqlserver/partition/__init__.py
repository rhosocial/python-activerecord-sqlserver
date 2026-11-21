# src/rhosocial/activerecord/backend/impl/sqlserver/partition/__init__.py
"""SQL Server partition planning.

SQL Server does not partition with ``PARTITION BY``. Its model is three
objects: a ``PARTITION FUNCTION`` that fixes the boundary values, a
``PARTITION SCHEME`` that maps each resulting partition to a filegroup, and a
table built ``ON <scheme>(<column>)``. Removing a partition is not a ``DROP``:
the boundary is merged away with ``MERGE RANGE``. There is no subpartitioning
at any version, and no ``PARTITION OF``.

This package now holds only the owner-agnostic layout description:

:mod:`plan`
    :class:`SQLServerPartitionPlan` -- the function, boundaries, direction and
    optional scheme, with no table name and no retention rule.

How to apply that layout is answered by the dialect's eight
``suggest_partition_*`` methods (see ``suggestion.partition``); how to
observe the catalogue is answered by the backend introspector. There is no
maintenance executor: a caller owns the table, the rows and the retention
decision, and executes the suggested expression chain itself.
"""

from .plan import SQLServerPartitionPlan

__all__ = [
    "SQLServerPartitionPlan",
]
