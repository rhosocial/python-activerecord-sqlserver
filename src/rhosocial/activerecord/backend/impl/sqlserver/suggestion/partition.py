# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/partition.py
"""SQLServerPartitionSuggestionMixin -- real answers for the 8 partition suggestions.

The eight ``suggest_partition_*`` methods turn a caller-supplied ``plan`` into
ordered chains of SQL Server's own expression nodes from
``...expression.partition``. Nothing here renders SQL: the dialect formatters
own the spelling exactly as they do for every other statement in this backend.

SQL Server has three tiers -- a partition FUNCTION fixes the boundaries, a
partition SCHEME maps them to filegroups, and the table is built ``ON`` the
scheme -- and only one strategy, RANGE (LEFT or RIGHT). There is no
``ADD PARTITION`` or ``DROP PARTITION``: a boundary is added with ``SPLIT RANGE``
and removed with ``MERGE RANGE``, both of which move rows. Removal, split and
retention therefore honestly suggest ``MERGE RANGE`` / ``SPLIT RANGE`` rather
than a metadata-only drop.

The protocol keeps ``plan`` opaque, so this mixin reads a small documented set
of fields from either a mapping or an object with attributes (a
:class:`~..partition.plan.SQLServerPartitionPlan` works as-is):

* ``function``, ``data_type``, ``boundaries``, ``range_direction`` -- function;
* ``scheme``, ``filegroups``, ``all_filegroup``, ``next_filegroup`` -- scheme;
* ``keys`` -- optional column names/expressions for the table's ``ON`` tier;
* ``boundary`` -- the boundary a single ADD/DROP/SPLIT/MERGE acts on (falls
  back to the newest boundary for add/split and the oldest for drop/merge);
* ``cutoff`` -- inclusive retention upper bound (RANGE only).

Boundary-comparison helpers are kept here rather than imported from the retired
maintenance module: with the maintenance protocol gone, this mixin is the
single source for how SQL Server performs each partition operation.

Tri-state result: a tuple of expressions when a real chain exists, ``False``
when SQL Server has no such mechanism for the strategy/plan, ``None`` when
nothing needs doing. The capability probes on ``SQLServerPartitionMixin`` gate
every mutating chain, so a dialect that withdraws a feature answers ``False``
rather than emitting SQL the server would reject.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, List, Optional, Sequence, TYPE_CHECKING

from ....expression import Column
from ....suggestion import (
    PartitionAddSuggestion,
    PartitionBuildSuggestion,
    PartitionDropSuggestion,
    PartitionMergeSuggestion,
    PartitionRetentionSuggestion,
    PartitionSplitSuggestion,
    PartitionTableAlterSuggestion,
    PartitionTableDropSuggestion,
)
from ....expression.bases import BaseExpression
from ..expression.partition import (
    SQLServerDropPartitionFunctionExpression,
    SQLServerDropPartitionSchemeExpression,
    SQLServerPartitionByRangeClause,
    SQLServerPartitionFunctionExpression,
    SQLServerPartitionFunctionMergeExpression,
    SQLServerPartitionFunctionSplitExpression,
    SQLServerPartitionSchemeExpression,
    SQLServerPartitionSchemeNextUsedExpression,
)

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.statements import PartitionStrategy

__all__ = ["SQLServerPartitionSuggestionMixin"]

# SQL Server's partition-function types grouped by the comparison they allow.
# The base spelling is enough: DECIMAL(10, 2) compares like DECIMAL and
# NVARCHAR(50) like text.
_INT_TYPES = frozenset({"tinyint", "smallint", "int", "bigint"})
_NUMBER_TYPES = frozenset({"decimal", "numeric", "money", "smallmoney", "float", "real"})
_DATETIME_TYPES = frozenset({"datetime", "datetime2", "smalldatetime", "datetimeoffset"})


def _get(plan: Any, name: str, default: Any = None) -> Any:
    """Read one field from a mapping-shaped or attribute-shaped plan."""
    if plan is None:
        return default
    if isinstance(plan, Mapping):
        return plan.get(name, default)
    return getattr(plan, name, default)


def _word(strategy: "PartitionStrategy") -> str:
    """Normalise a strategy member or its spelling to an upper-case word."""
    value = getattr(strategy, "value", strategy)
    return str(value).strip().upper()


def _is_range(strategy: "PartitionStrategy") -> bool:
    return _word(strategy) == "RANGE"


def _boundary_family(data_type: Any) -> str:
    """Group a partition-function type into the comparison it supports."""
    base = str(data_type).split("(", 1)[0].strip().lower()
    if base == "date":
        return "date"
    if base in _DATETIME_TYPES:
        return "datetime"
    if base == "time":
        return "time"
    if base in _INT_TYPES:
        return "int"
    if base in _NUMBER_TYPES:
        return "number"
    return "text"


def _trim_iso_fraction(text: str) -> str:
    """Keep at most six fractional digits, as pre-3.11 parsers require."""
    dot = text.find(".")
    if dot < 0:
        return text
    end = dot + 1
    while end < len(text) and text[end].isdigit():
        end += 1
    digits = text[dot + 1 : end]
    if len(digits) <= 6:
        return text
    return f"{text[:dot + 1]}{digits[:6]}{text[end:]}"


def _coerce_boundary(data_type: Any, value: Any) -> Any:
    """Read *value* as the comparand for a function of *data_type*.

    The catalogue reads boundaries back as text, but a plan carries native
    values. Both spellings are accepted here so retention can compare the two.
    A ``datetimeoffset`` is compared by wall-clock time: retention is a date
    decision and an offset the caller did not supply has no better meaning.
    """
    family = _boundary_family(data_type)
    if family == "date":
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])
    if family == "datetime":
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, date):
            parsed = datetime.combine(value, time.min)
        else:
            parsed = datetime.fromisoformat(_trim_iso_fraction(str(value)).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=None) if parsed.tzinfo is not None else parsed
    if family == "time":
        if isinstance(value, time):
            return value
        return time.fromisoformat(_trim_iso_fraction(str(value)).replace("Z", "+00:00"))
    if family == "int":
        return int(value)
    if family == "number":
        return Decimal(str(value))
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


class SQLServerPartitionSuggestionMixin:
    """Suggest SQL Server's real DDL action chains for partition lifecycle points."""

    # -- shared helpers --------------------------------------------------

    def _suggestion_function(self, plan: Any) -> Optional[str]:
        function = _get(plan, "function")
        if not isinstance(function, str) or not function.strip():
            return None
        return function

    def _suggestion_scheme(self, plan: Any) -> Optional[str]:
        scheme = _get(plan, "scheme")
        if not isinstance(scheme, str) or not scheme.strip():
            return None
        return scheme

    def _suggestion_scheme_expression(
        self, plan: Any, function: str
    ) -> Optional[SQLServerPartitionSchemeExpression]:
        scheme = self._suggestion_scheme(plan)
        if scheme is None:
            return None
        filegroups = _get(plan, "filegroups") or ()
        all_filegroup = _get(plan, "all_filegroup")
        if not filegroups and not all_filegroup:
            return None
        return SQLServerPartitionSchemeExpression(
            self,
            scheme,
            function,
            list(filegroups),
            all_filegroup=all_filegroup,
        )

    def _suggestion_boundary(self, plan: Any, *, newest: bool) -> Any:
        boundary = _get(plan, "boundary")
        if boundary is not None:
            return boundary
        boundaries = _get(plan, "boundaries") or ()
        if isinstance(boundaries, (list, tuple)) and boundaries:
            return boundaries[-1] if newest else boundaries[0]
        return None

    def _suggestion_next_used(
        self, plan: Any, scheme: Optional[str]
    ) -> Optional[SQLServerPartitionSchemeNextUsedExpression]:
        """The ``NEXT USED`` a SPLIT consumes, when the plan names a scheme."""
        if scheme is None:
            return None
        filegroup = _get(plan, "next_filegroup")
        if filegroup is None:
            filegroups = _get(plan, "filegroups") or ()
            if isinstance(filegroups, (list, tuple)) and filegroups:
                filegroup = filegroups[-1]
            else:
                filegroup = _get(plan, "all_filegroup")
        if not isinstance(filegroup, str) or not filegroup.strip():
            return None
        return SQLServerPartitionSchemeNextUsedExpression(self, scheme, filegroup)

    # -- 1. build --------------------------------------------------------

    def suggest_partition_build(
        self,
        strategy: "PartitionStrategy",
        plan: object,
    ) -> PartitionBuildSuggestion:
        """Suggest the function -> scheme -> ON chain for CREATE TABLE time."""
        if not _is_range(strategy):
            return PartitionBuildSuggestion(False)
        if not self.supports_partition_function():  # type: ignore[attr-defined]
            return PartitionBuildSuggestion(False)
        function = self._suggestion_function(plan)
        data_type = _get(plan, "data_type")
        boundaries = _get(plan, "boundaries")
        if (
            function is None
            or not isinstance(data_type, str)
            or not data_type.strip()
            or not isinstance(boundaries, (list, tuple))
            or not boundaries
        ):
            return PartitionBuildSuggestion(False)

        operations: List[BaseExpression] = [
            SQLServerPartitionFunctionExpression(
                self,
                function,
                data_type,
                list(boundaries),
                range_direction=_get(
                    plan,
                    "range_direction",
                    "RIGHT",
                ),
            )
        ]
        scheme = self._suggestion_scheme(plan)
        if scheme is not None:
            if not self.supports_partition_scheme():  # type: ignore[attr-defined]
                return PartitionBuildSuggestion(False)
            scheme_expression = self._suggestion_scheme_expression(plan, function)
            if scheme_expression is None:
                return PartitionBuildSuggestion(False)
            operations.append(scheme_expression)

        keys = _get(plan, "keys")
        if keys:
            if not self.supports_partitioned_table_creation():  # type: ignore[attr-defined]
                return PartitionBuildSuggestion(False)
            key_nodes: List[BaseExpression] = []
            for key in keys:
                if isinstance(key, BaseExpression):
                    key_nodes.append(key)
                elif isinstance(key, str) and key.strip():
                    key_nodes.append(Column(self, key))
                else:
                    return PartitionBuildSuggestion(False)
            if not key_nodes:
                return PartitionBuildSuggestion(False)
            if scheme is None:
                return PartitionBuildSuggestion(False)
            operations.append(
                SQLServerPartitionByRangeClause(
                    self,
                    key_nodes,
                    scheme,
                    range_direction=_get(plan, "range_direction", "RIGHT"),
                )
            )
        return PartitionBuildSuggestion(tuple(operations))

    # -- 2. table_drop ---------------------------------------------------

    def suggest_partition_table_drop(
        self,
        strategy: "PartitionStrategy",
        plan: object,
    ) -> PartitionTableDropSuggestion:
        """Suggest dropping the scaffolding: scheme first, then function.

        SQL Server refuses to drop a partition function while a scheme maps it,
        so the order is part of the answer. No ``DROP TABLE`` is suggested:
        dropping the scheme while a table is built on it is refused too, and
        moving every row out would be a data-affecting decision the caller owns.
        """
        if not _is_range(strategy):
            return PartitionTableDropSuggestion(False)
        if not self.supports_partition_function():  # type: ignore[attr-defined]
            return PartitionTableDropSuggestion(False)
        function = self._suggestion_function(plan)
        if function is None:
            return PartitionTableDropSuggestion(False)

        operations: List[BaseExpression] = []
        scheme = self._suggestion_scheme(plan)
        if scheme is not None:
            if not self.supports_partition_scheme():  # type: ignore[attr-defined]
                return PartitionTableDropSuggestion(False)
            operations.append(SQLServerDropPartitionSchemeExpression(self, scheme))
        operations.append(SQLServerDropPartitionFunctionExpression(self, function))
        return PartitionTableDropSuggestion(tuple(operations))

    # -- 3. table_alter --------------------------------------------------

    def suggest_partition_table_alter(
        self,
        strategy: "PartitionStrategy",
        plan: object,
    ) -> PartitionTableAlterSuggestion:
        """SQL Server has no in-place ALTER of a partitioned table's scheme.

        Changing a function's type or direction means dropping and recreating
        the scaffolding, which moves every row; the maintenance executor
        refused that and asked the caller to do it explicitly. There is no
        honest expression chain here, so the answer is ``False``.
        """
        return PartitionTableAlterSuggestion(False)

    # -- 4. add ----------------------------------------------------------

    def suggest_partition_add(
        self,
        strategy: "PartitionStrategy",
        plan: object,
    ) -> PartitionAddSuggestion:
        """Suggest NEXT USED + SPLIT RANGE: SQL Server's way to add a partition."""
        if not _is_range(strategy):
            return PartitionAddSuggestion(False)
        if not self.supports_split_partition():  # type: ignore[attr-defined]
            return PartitionAddSuggestion(False)
        function = self._suggestion_function(plan)
        boundary = self._suggestion_boundary(plan, newest=True)
        if function is None or boundary is None:
            return PartitionAddSuggestion(False)

        operations: List[BaseExpression] = []
        next_used = self._suggestion_next_used(plan, self._suggestion_scheme(plan))
        if next_used is not None:
            operations.append(next_used)
        operations.append(SQLServerPartitionFunctionSplitExpression(self, function, boundary))
        return PartitionAddSuggestion(tuple(operations))

    # -- 5. drop ---------------------------------------------------------

    def suggest_partition_drop(
        self,
        strategy: "PartitionStrategy",
        plan: object,
    ) -> PartitionDropSuggestion:
        """Suggest MERGE RANGE: SQL Server has no DROP PARTITION."""
        if not _is_range(strategy):
            return PartitionDropSuggestion(False)
        if not self.supports_merge_partition():  # type: ignore[attr-defined]
            return PartitionDropSuggestion(False)
        function = self._suggestion_function(plan)
        boundary = self._suggestion_boundary(plan, newest=False)
        if function is None:
            return PartitionDropSuggestion(False)
        if boundary is None:
            return PartitionDropSuggestion(None)
        return PartitionDropSuggestion(
            (SQLServerPartitionFunctionMergeExpression(self, function, boundary),)
        )

    # -- 6. split --------------------------------------------------------

    def suggest_partition_split(
        self,
        strategy: "PartitionStrategy",
        plan: object,
    ) -> PartitionSplitSuggestion:
        """Suggest NEXT USED + SPLIT RANGE (a data-affecting operation)."""
        if not _is_range(strategy):
            return PartitionSplitSuggestion(False)
        if not self.supports_split_partition():  # type: ignore[attr-defined]
            return PartitionSplitSuggestion(False)
        function = self._suggestion_function(plan)
        boundary = self._suggestion_boundary(plan, newest=True)
        if function is None or boundary is None:
            return PartitionSplitSuggestion(False)

        operations: List[BaseExpression] = []
        next_used = self._suggestion_next_used(plan, self._suggestion_scheme(plan))
        if next_used is not None:
            operations.append(next_used)
        operations.append(SQLServerPartitionFunctionSplitExpression(self, function, boundary))
        return PartitionSplitSuggestion(tuple(operations))

    # -- 7. merge --------------------------------------------------------

    def suggest_partition_merge(
        self,
        strategy: "PartitionStrategy",
        plan: object,
    ) -> PartitionMergeSuggestion:
        """Suggest MERGE RANGE (a data-affecting operation)."""
        if not _is_range(strategy):
            return PartitionMergeSuggestion(False)
        if not self.supports_merge_partition():  # type: ignore[attr-defined]
            return PartitionMergeSuggestion(False)
        function = self._suggestion_function(plan)
        boundary = self._suggestion_boundary(plan, newest=False)
        if function is None or boundary is None:
            return PartitionMergeSuggestion(False)
        return PartitionMergeSuggestion(
            (SQLServerPartitionFunctionMergeExpression(self, function, boundary),)
        )

    # -- 8. retention ----------------------------------------------------

    def suggest_partition_retention(
        self,
        strategy: "PartitionStrategy",
        plan: object,
    ) -> PartitionRetentionSuggestion:
        """Suggest one MERGE RANGE per boundary at or before the cutoff.

        SQL Server's function boundary is the upper bound of the partition on
        its left in both RANGE LEFT and RANGE RIGHT, so a boundary qualifies
        when it is less than or equal to the cutoff. Removal is a MERGE, never
        a DROP PARTITION, and moving rows is inherent to the operation.
        """
        if not _is_range(strategy):
            return PartitionRetentionSuggestion(False)
        if not self.supports_merge_partition():  # type: ignore[attr-defined]
            return PartitionRetentionSuggestion(False)
        function = self._suggestion_function(plan)
        data_type = _get(plan, "data_type")
        boundaries = _get(plan, "boundaries")
        cutoff = _get(plan, "cutoff")
        if (
            function is None
            or not isinstance(data_type, str)
            or not data_type.strip()
            or not isinstance(boundaries, (list, tuple))
            or cutoff is None
        ):
            return PartitionRetentionSuggestion(False)

        try:
            threshold = _coerce_boundary(data_type, cutoff)
            candidates: List[Any] = [
                boundary
                for boundary in boundaries
                if _coerce_boundary(data_type, boundary) <= threshold
            ]
        except (TypeError, ValueError, ArithmeticError):
            return PartitionRetentionSuggestion(False)

        if not candidates:
            return PartitionRetentionSuggestion(None)
        operations: Sequence[SQLServerPartitionFunctionMergeExpression] = tuple(
            SQLServerPartitionFunctionMergeExpression(self, function, boundary)
            for boundary in candidates
        )
        return PartitionRetentionSuggestion(tuple(operations))
