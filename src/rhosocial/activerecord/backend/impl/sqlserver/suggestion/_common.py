# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/_common.py
"""Shared helpers and the common base for SQL Server's partition suggestion mixins.

The eight ``suggest_partition_*`` mixins are split one-per-file, but they all
read the same opaque ``plan`` shape and build their expression chains from the
same nodes. The plan readers and boundary-comparison helpers live here so there
is a single source for how SQL Server interprets a suggestion plan; each mixin
keeps only its own ``suggest_partition_<x>()`` method and the imports that
method needs.

Boundary-comparison helpers are kept here rather than imported from the retired
maintenance module: with the maintenance protocol gone, this is the single
source for how SQL Server performs each partition operation.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Optional

from ..expression.partition import (
    SQLServerPartitionSchemeExpression,
    SQLServerPartitionSchemeNextUsedExpression,
)

__all__ = ["SQLServerPartitionSuggestionBase"]

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


def _word(strategy: Any) -> str:
    """Normalise a strategy clause, member or spelling to an upper-case word.

    A strategy now arrives as a ``PartitionByClause`` node whose fixed word is
    carried in ``.word``/``.method``. The enum and plain-string spellings are
    still read so callers using the previous form keep working.
    """
    value = getattr(strategy, "word", None)
    if value is None:
        value = getattr(strategy, "method", None)
    if value is None:
        value = getattr(strategy, "value", strategy)
    return str(value).strip().upper()


def _is_range(strategy: Any) -> bool:
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


class SQLServerPartitionSuggestionBase:
    """Plan readers shared by all eight SQL Server partition suggestion mixins."""

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
