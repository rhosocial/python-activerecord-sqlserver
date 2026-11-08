# src/rhosocial/activerecord/backend/impl/sqlserver/partition/plan.py
"""The owner-agnostic description of a SQL Server partition layout.

A plan names the partition function, the boundary values and the optional
partition scheme. It carries no table name, no column name and no retention
rule: those belong to the application that owns the data, exactly as they do
for the other backends' partition helpers.

SQL Server has one strategy -- RANGE, with either side of a boundary owning
the value -- and no subpartitioning at any version. The two fields that could
ask for another strategy are present so the refusal is explicit at construction
rather than a conventional promise not to pass them.
"""

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Optional, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

from ..expression.partition import (
    SQLServerPartitionRangeDirection,
    _as_range_direction,
    validate_partition_data_type,
)

__all__ = ["SQLServerPartitionPlan"]


def _boundary_token(value: Any) -> Tuple[str, str]:
    """A comparable token for one boundary value.

    The token is used only to find duplicates inside one plan, never to read
    the catalogue: boundary comparison against the server is done by the
    server, with the value cast to the function's declared type.
    """
    if isinstance(value, bool):
        return "bool", "1" if value else "0"
    if isinstance(value, int):
        return "int", str(value)
    if isinstance(value, (float, Decimal)):
        return "number", format(value, "f")
    if isinstance(value, datetime):
        return "datetime", value.isoformat(sep=" ")
    if isinstance(value, date):
        return "date", value.isoformat()
    if isinstance(value, time):
        return "time", value.isoformat()
    if isinstance(value, str):
        return "str", value
    raise ValueError(
        f"unsupported partition boundary {value!r}; use a number, string or "
        f"date/time value"
    )


@dataclass(frozen=True)
class SQLServerPartitionPlan:
    """A partition function, its boundaries and an optional scheme.

    Attributes:
        function: Partition function name, optionally schema-qualified with
            dots. It is a name the caller owns; the library has no default.
        data_type: The boundary column's declared type, e.g. ``DATE``,
            ``INT`` or ``NVARCHAR(50)``.
        boundaries: Boundary values in ascending order. ``N`` boundaries
            describe ``N + 1`` partitions; the plan sorts them and refuses
            duplicates.
        range_direction: ``RIGHT`` (the default in SQL Server: the boundary
            value belongs to the partition on its right) or ``LEFT``.
        scheme: Partition scheme name, or ``None`` when the caller only wants
            the function managed.
        filegroups: Explicit destinations for the scheme, one per partition.
            Mutually exclusive with ``all_filegroup``; when given,
            ``len(filegroups)`` must equal ``len(boundaries) + 1``.
        all_filegroup: A single filegroup for every partition. Mutually
            exclusive with ``filegroups``.
        next_filegroup: The filegroup a ``SPLIT RANGE`` consumes. Defaults to
            the last explicit filegroup, or to ``all_filegroup``; it is
            recorded here so the executor can emit ``NEXT USED`` before each
            split instead of relying on the scheme's current state.
        strategy: Always ``"RANGE"``. Present so a non-RANGE request is
            refused explicitly rather than silently interpreted as RANGE.
        subpartition_by: Always ``None``. SQL Server has no subpartitioning;
            any value is refused with :class:`UnsupportedFeatureError`.

    Example:
        >>> plan = SQLServerPartitionPlan(
        ...     function="pf_logs",
        ...     data_type="DATE",
        ...     boundaries=(date(2026, 1, 1), date(2026, 2, 1)),
        ...     scheme="ps_logs",
        ...     all_filegroup="PRIMARY",
        ... )
    """

    function: str
    data_type: str
    boundaries: Tuple[Any, ...]
    range_direction: SQLServerPartitionRangeDirection = (
        SQLServerPartitionRangeDirection.RIGHT
    )
    scheme: Optional[str] = None
    filegroups: Tuple[str, ...] = ()
    all_filegroup: Optional[str] = None
    next_filegroup: Optional[str] = None
    strategy: str = "RANGE"
    subpartition_by: Optional[str] = None

    def __post_init__(self) -> None:
        """Normalise and validate the plan.

        Raises:
            ValueError: A name is empty, a type is not a plain SQL type, the
                boundaries are empty, duplicated, or mutually incomparable, or
                the scheme/filegroup combination is inconsistent.
            UnsupportedFeatureError: ``strategy`` is not RANGE, or a
                subpartitioning policy was requested.
        """
        if not isinstance(self.function, str) or not self.function.strip():
            raise ValueError("function must be a non-empty string")
        data_type = validate_partition_data_type(self.data_type)

        if not isinstance(self.strategy, str) or self.strategy.strip().upper() != "RANGE":
            raise UnsupportedFeatureError(
                "SQL Server",
                f"{self.strategy!r} partitioning",
                "SQL Server supports RANGE partitioning only.",
            )
        if self.subpartition_by is not None:
            raise UnsupportedFeatureError(
                "SQL Server",
                f"subpartitioning by {self.subpartition_by!r}",
                "SQL Server has no subpartitioning; use one RANGE level.",
            )

        values = tuple(self.boundaries)
        if not values:
            raise ValueError("boundaries must contain at least one value")
        tokens = [_boundary_token(value) for value in values]
        if len(set(tokens)) != len(tokens):
            raise ValueError("boundaries must be unique")
        try:
            sorted_values = tuple(sorted(values))
        except TypeError as exc:
            raise ValueError("boundaries must be mutually comparable") from exc

        direction = _as_range_direction(self.range_direction)

        scheme = self.scheme
        if scheme is not None and (not isinstance(scheme, str) or not scheme.strip()):
            raise ValueError("scheme must be a non-empty string or None")
        filegroups = tuple(self.filegroups)
        if scheme is None:
            if filegroups or self.all_filegroup is not None or self.next_filegroup is not None:
                raise ValueError(
                    "filegroups, all_filegroup and next_filegroup require a scheme"
                )
        else:
            if not filegroups and self.all_filegroup is None:
                raise ValueError(
                    "a scheme needs either explicit filegroups or all_filegroup"
                )
            if filegroups and self.all_filegroup is not None:
                raise ValueError(
                    "filegroups and all_filegroup are mutually exclusive"
                )
            if filegroups and len(filegroups) != len(sorted_values) + 1:
                raise ValueError(
                    f"{len(filegroups)} filegroups cannot serve "
                    f"{len(sorted_values) + 1} partitions; pass one filegroup "
                    f"per partition"
                )
            next_filegroup = self.next_filegroup
            if next_filegroup is None:
                next_filegroup = filegroups[-1] if filegroups else self.all_filegroup
            elif filegroups and next_filegroup not in filegroups:
                raise ValueError(
                    f"next_filegroup {next_filegroup!r} is not one of the plan's "
                    f"filegroups"
                )
            elif self.all_filegroup is not None and next_filegroup != self.all_filegroup:
                raise ValueError(
                    f"next_filegroup {next_filegroup!r} must equal "
                    f"all_filegroup {self.all_filegroup!r}"
                )
            object.__setattr__(self, "next_filegroup", next_filegroup)

        object.__setattr__(self, "data_type", data_type)
        object.__setattr__(self, "boundaries", sorted_values)
        object.__setattr__(self, "range_direction", direction)
        object.__setattr__(self, "filegroups", filegroups)

    @property
    def partition_count(self) -> int:
        """How many partitions the plan describes."""
        return len(self.boundaries) + 1
