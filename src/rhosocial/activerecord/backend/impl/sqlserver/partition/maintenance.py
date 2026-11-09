# src/rhosocial/activerecord/backend/impl/sqlserver/partition/maintenance.py
"""SQL Server partition maintenance: plan in, catalogue out, DDL in order.

SQL Server's maintenance vocabulary differs from every other backend's. There
is no ``ADD``/``DROP PARTITION``: the boundary count *is* the partition count,
so a partition is added with ``SPLIT RANGE`` and removed with ``MERGE RANGE``.
``SWITCH`` moves a whole partition to another table without copying rows.

The executor is owner-agnostic. It knows a plan's function, boundaries,
direction and optional scheme; it knows nothing about which application owns
the table, which rows it keeps, or when it is allowed to delete them. Table
names are arguments to ``list`` and ``validate`` -- never defaults -- and no
retention policy is embedded: ``drop_or_merge`` merges exactly the boundaries
it is given, while ``drop_before`` reads the catalogue to choose them.

SQL Server's DDL is statement-scoped and auto-commits, so the executor does
not promise a transaction across several statements. It executes the planned
statements in order and reports each one's rendered SQL, so a failure can be
read as "these before, this one failed" rather than as a value that pretends
to be atomic.

Public surface is mirrored sync/async:

* :class:`SQLServerPartitionMaintenance`
* :class:`AsyncSQLServerPartitionMaintenance`

Both expose ``ensure``, ``list``, ``retention_boundaries``,
``drop_or_merge``, ``drop_before`` and ``validate``.
"""

from dataclasses import replace
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.errors import DatabaseError
from rhosocial.activerecord.backend.partition import PartitionInfo

from ..expression.partition import (
    SQLServerDropPartitionFunctionExpression,
    SQLServerDropPartitionSchemeExpression,
    SQLServerPartitionBoundaryQueryStatement,
    SQLServerPartitionFunctionExpression,
    SQLServerPartitionFunctionMergeExpression,
    SQLServerPartitionFunctionQueryStatement,
    SQLServerPartitionFunctionSplitExpression,
    SQLServerPartitionRangeQueryStatement,
    SQLServerPartitionSchemeExpression,
    SQLServerPartitionSchemeNextUsedExpression,
    SQLServerPartitionSchemeQueryStatement,
    SQLServerPartitionTableQueryStatement,
)
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
    "SQLServerPartitionMaintenance",
]

#: SQL Server's fixed page size; ``sys.partitions.used_page_count`` is pages.
_PAGE_BYTES = 8192


def _as_int(value: Any) -> Optional[int]:
    """Read a catalogue integer, tolerating the driver's string spelling."""
    if value is None:
        return None
    return int(value)


def _boundary_parameter(value: Any) -> Any:
    """Spell a boundary in a form every ODBC driver can bind.

    The legacy ``SQL Server`` ODBC driver has no ``SQLBindParameter`` support
    for ``date``/``time`` (it answers ``HYC00``), while Driver 18 binds them
    natively. The query casts the parameter to the function's type anyway,
    so an ISO string is accepted by both and asks the same question.
    """
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


#: Partition-function types grouped by the comparison they allow. The base
#: spelling is enough: ``DECIMAL(10, 2)`` compares like ``DECIMAL`` and
#: ``NVARCHAR(50)`` like text.
_INT_TYPES = frozenset({"tinyint", "smallint", "int", "bigint"})
_NUMBER_TYPES = frozenset({"decimal", "numeric", "money", "smallmoney", "float", "real"})
_DATETIME_TYPES = frozenset({"datetime", "datetime2", "smalldatetime", "datetimeoffset"})


def _boundary_family(data_type: str) -> str:
    """Group a partition-function type into the comparison it supports."""
    base = data_type.split("(", 1)[0].strip().lower()
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
    digits = text[dot + 1:end]
    if len(digits) <= 6:
        return text
    return f"{text[:dot + 1]}{digits[:6]}{text[end:]}"


def _parse_catalogue_boundary(data_type: str, text: str) -> Any:
    """Read one catalogue boundary as the Python value its type names.

    The catalogue query renders every boundary as text so all ODBC drivers can
    fetch it. Retention still has to compare those values, so the text is read
    back into the function's declared family. A ``datetimeoffset`` boundary is
    compared by wall-clock time: retention is a date decision, and an offset
    that the caller did not supply has no better meaning here.
    """
    family = _boundary_family(data_type)
    try:
        if family == "date":
            return date.fromisoformat(text[:10])
        if family == "datetime":
            normalized = _trim_iso_fraction(text).replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            return parsed.replace(tzinfo=None) if parsed.tzinfo is not None else parsed
        if family == "time":
            return time.fromisoformat(_trim_iso_fraction(text).replace("Z", "+00:00"))
        if family == "int":
            return int(text)
        if family == "number":
            return Decimal(text)
        return text
    except (ValueError, ArithmeticError) as exc:
        raise ValueError(
            f"catalogue boundary {text!r} is not a valid {data_type} value"
        ) from exc


def _coerce_cutoff(data_type: str, value: Any) -> Any:
    """Read *value* as the comparand for a function of *data_type*."""
    family = _boundary_family(data_type)
    try:
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
                normalized = _trim_iso_fraction(str(value)).replace("Z", "+00:00")
                parsed = datetime.fromisoformat(normalized)
            return parsed.replace(tzinfo=None) if parsed.tzinfo is not None else parsed
        if family == "time":
            if isinstance(value, time):
                return value
            return time.fromisoformat(
                _trim_iso_fraction(str(value)).replace("Z", "+00:00")
            )
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
    except (ValueError, TypeError, ArithmeticError) as exc:
        raise ValueError(f"cutoff {value!r} is not a valid {data_type} value") from exc


def _range_bound(low: Optional[str], high: Optional[str]) -> Optional[str]:
    """Join a partition's catalogue bounds into one display string."""
    if low is None and high is None:
        return None
    left = "" if low is None else low
    right = "" if high is None else high
    return f"{left}..{right}"


class _SQLServerPartitionMaintenanceBase:
    """Catalogue parsing, planning and rendering shared by both executors.

    The two executors implement only the I/O seams (``_read_functions``,
    ``_read_schemes``, ``_read_tables``, ``_read_ranges``,
    ``_read_boundary_exists``, ``_execute``). Every decision -- what is
    missing, what a dry run would do, which issue a validation found -- lives
    here once, so sync and async cannot drift apart.
    """

    def __init__(self, backend: Any) -> None:
        self.backend = backend
        self.dialect = backend.dialect

    # --------------------------------------------------------------- I/O
    def _read_functions(
        self, function_name: Optional[str] = None
    ) -> Tuple[PartitionFunctionInfo, ...]:
        raise NotImplementedError

    def _read_schemes(
        self,
        scheme_name: Optional[str] = None,
        function_name: Optional[str] = None,
    ) -> Tuple[PartitionSchemeInfo, ...]:
        raise NotImplementedError

    def _read_tables(
        self,
        table_name: Optional[str] = None,
        schema: Optional[str] = None,
        scheme_name: Optional[str] = None,
    ) -> Tuple[PartitionTableInfo, ...]:
        raise NotImplementedError

    def _read_ranges(
        self, table_name: str, schema: Optional[str] = None
    ) -> Tuple[PartitionRangeInfo, ...]:
        raise NotImplementedError

    def _read_boundary_exists(
        self, plan: SQLServerPartitionPlan
    ) -> Tuple[bool, ...]:
        raise NotImplementedError

    def _execute(self, sql: str, params: Tuple[Any, ...]) -> None:
        raise NotImplementedError

    # ------------------------------------------------------------- parsing
    @staticmethod
    def _parse_functions(rows: Sequence[Any]) -> Tuple[PartitionFunctionInfo, ...]:
        grouped: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            name = row.get("function_name")
            if not name:
                continue
            bucket = grouped.setdefault(
                name,
                {
                    "data_type": str(row.get("data_type") or ""),
                    "direction": (
                        "RIGHT"
                        if _as_int(row.get("boundary_value_on_right")) == 1
                        else "LEFT"
                    ),
                    "partition_count": _as_int(row.get("partition_count")) or 0,
                    "boundaries": [],
                },
            )
            if row.get("boundary_value") is not None:
                bucket["boundaries"].append(str(row["boundary_value"]))
        return tuple(
            PartitionFunctionInfo(
                name=name,
                data_type=bucket["data_type"],
                range_direction=bucket["direction"],
                boundary_values=tuple(bucket["boundaries"]),
                partition_count=bucket["partition_count"],
            )
            for name, bucket in grouped.items()
        )

    @staticmethod
    def _parse_schemes(rows: Sequence[Any]) -> Tuple[PartitionSchemeInfo, ...]:
        grouped: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            name = row.get("scheme_name")
            if not name:
                continue
            bucket = grouped.setdefault(
                name,
                {
                    "function": str(row.get("function_name") or ""),
                    "partition_count": _as_int(row.get("partition_count")) or 0,
                    "filegroups": [],
                },
            )
            if row.get("filegroup_name"):
                bucket["filegroups"].append(str(row["filegroup_name"]))
        return tuple(
            PartitionSchemeInfo(
                name=name,
                function=bucket["function"],
                filegroups=tuple(bucket["filegroups"]),
                partition_count=bucket["partition_count"],
            )
            for name, bucket in grouped.items()
        )

    @staticmethod
    def _parse_tables(rows: Sequence[Any]) -> Tuple[PartitionTableInfo, ...]:
        tables = []
        seen = set()
        for row in rows:
            name = row.get("table_name")
            if not name:
                continue
            schema = row.get("schema_name")
            key = (schema, name)
            if key in seen:
                continue
            seen.add(key)
            tables.append(
                PartitionTableInfo(
                    name=str(name),
                    schema=None if schema is None else str(schema),
                    scheme=str(row.get("scheme_name") or ""),
                    function=str(row.get("function_name") or ""),
                    partition_column=(
                        None
                        if row.get("partition_column") is None
                        else str(row["partition_column"])
                    ),
                    partition_count=_as_int(row.get("partition_count")) or 0,
                )
            )
        return tuple(tables)

    @staticmethod
    def _parse_ranges(rows: Sequence[Any]) -> Tuple[PartitionRangeInfo, ...]:
        return tuple(
            PartitionRangeInfo(
                table=str(row.get("table_name") or ""),
                schema=(
                    None
                    if row.get("schema_name") is None
                    else str(row["schema_name"])
                ),
                partition_number=_as_int(row.get("partition_number")) or 0,
                low_boundary=(
                    None
                    if row.get("low_boundary") is None
                    else str(row["low_boundary"])
                ),
                high_boundary=(
                    None
                    if row.get("high_boundary") is None
                    else str(row["high_boundary"])
                ),
                row_count=_as_int(row.get("row_count")),
                data_bytes=(
                    None
                    if row.get("used_page_count") is None
                    else _as_int(row["used_page_count"]) * _PAGE_BYTES
                ),
            )
            for row in rows
        )

    # ------------------------------------------------------------- planning
    @staticmethod
    def _find_function(
        functions: Sequence[PartitionFunctionInfo], name: str
    ) -> Optional[PartitionFunctionInfo]:
        for info in functions:
            if info.name == name:
                return info
        return None

    @staticmethod
    def _find_scheme(
        schemes: Sequence[PartitionSchemeInfo], name: Optional[str]
    ) -> Optional[PartitionSchemeInfo]:
        if name is None:
            return None
        for info in schemes:
            if info.name == name:
                return info
        return None

    def _plan_ensure(
        self,
        plan: SQLServerPartitionPlan,
        functions: Sequence[PartitionFunctionInfo],
        schemes: Sequence[PartitionSchemeInfo],
        exists: Sequence[bool],
    ) -> Tuple[
        Tuple[Any, ...],
        List[Tuple[PartitionOperation, Tuple[Any, ...]]],
        List[str],
    ]:
        """Decide what ``ensure`` would do; no I/O happens here."""
        planned: List[Tuple[PartitionOperation, Tuple[Any, ...]]] = []
        issues: List[str] = []
        info = self._find_function(functions, plan.function)

        def add(action: str, name: str, statement: Any) -> None:
            sql, params = statement.to_sql()
            planned.append((PartitionOperation(action=action, name=name, sql=sql), params))

        if info is None:
            add(
                "create_function",
                plan.function,
                SQLServerPartitionFunctionExpression(
                    self.dialect,
                    plan.function,
                    plan.data_type,
                    list(plan.boundaries),
                    range_direction=plan.range_direction,
                ),
            )
            if plan.scheme:
                add(
                    "create_scheme",
                    plan.scheme,
                    SQLServerPartitionSchemeExpression(
                        self.dialect,
                        plan.scheme,
                        plan.function,
                        list(plan.filegroups),
                        all_filegroup=plan.all_filegroup,
                    ),
                )
            return (), planned, issues

        if info.range_direction != plan.range_direction.value:
            raise ValueError(
                f"partition function {plan.function!r} is RANGE "
                f"{info.range_direction}; the plan asks for RANGE "
                f"{plan.range_direction.value}. Dropping and recreating the "
                f"function would move every row; do it explicitly instead."
            )
        if info.data_type.upper() != plan.data_type.upper():
            raise ValueError(
                f"partition function {plan.function!r} partitions on "
                f"{info.data_type}, but the plan declares {plan.data_type}. "
                f"Change the plan's data_type or recreate the function."
            )

        missing = tuple(
            boundary
            for boundary, present in zip(plan.boundaries, exists)
            if not present
        )

        if plan.scheme:
            scheme_info = self._find_scheme(schemes, plan.scheme)
            if scheme_info is None:
                if (
                    plan.filegroups
                    and info.partition_count != plan.partition_count
                ):
                    raise ValueError(
                        f"partition function {plan.function!r} currently has "
                        f"{info.partition_count} partitions, but the plan "
                        f"provides {len(plan.filegroups)} explicit filegroups "
                        f"for {plan.partition_count}. Create the scheme with "
                        f"all_filegroup, or bring the boundary count into step "
                        f"before supplying explicit destinations."
                    )
                add(
                    "create_scheme",
                    plan.scheme,
                    SQLServerPartitionSchemeExpression(
                        self.dialect,
                        plan.scheme,
                        plan.function,
                        list(plan.filegroups),
                        all_filegroup=plan.all_filegroup,
                    ),
                )
                scheme_info = PartitionSchemeInfo(
                    name=plan.scheme,
                    function=plan.function,
                    filegroups=tuple(plan.filegroups),
                    partition_count=info.partition_count,
                )
            else:
                if scheme_info.function != plan.function:
                    raise ValueError(
                        f"partition scheme {plan.scheme!r} maps function "
                        f"{scheme_info.function!r}, not {plan.function!r}."
                    )
                # A scheme may declare one extra destination for NEXT USED --
                # ALL TO does exactly that -- so only a shortfall is a
                # partition that has nowhere to live.
                if scheme_info.destination_count < info.partition_count:
                    issues.append(
                        f"scheme {plan.scheme!r} declares "
                        f"{scheme_info.destination_count} destinations for "
                        f"{info.partition_count} partitions"
                    )

        for boundary in missing:
            if plan.scheme and plan.next_filegroup:
                add(
                    "next_used",
                    plan.next_filegroup,
                    SQLServerPartitionSchemeNextUsedExpression(
                        self.dialect, plan.scheme, plan.next_filegroup
                    ),
                )
            add(
                "split",
                str(boundary),
                SQLServerPartitionFunctionSplitExpression(
                    self.dialect, plan.function, boundary
                ),
            )
        return missing, planned, issues

    def _plan_list(
        self,
        plan: Optional[SQLServerPartitionPlan],
        functions: Sequence[PartitionFunctionInfo],
        schemes: Sequence[PartitionSchemeInfo],
        tables: Sequence[PartitionTableInfo],
        ranges: Sequence[PartitionRangeInfo],
        exists: Sequence[bool] = (),
    ) -> PartitionReport:
        """Build the reporting half of ``list``; no I/O happens here."""
        issues: List[str] = []
        missing: Tuple[Any, ...] = ()
        existing: Tuple[str, ...] = ()

        if plan is not None:
            info = self._find_function(functions, plan.function)
            if info is None:
                issues.append(f"partition function {plan.function!r} does not exist")
                missing = tuple(plan.boundaries)
            else:
                existing = info.boundary_values
                missing = tuple(
                    boundary
                    for boundary, present in zip(plan.boundaries, exists)
                    if not present
                )
                if info.range_direction != plan.range_direction.value:
                    issues.append(
                        f"partition function {plan.function!r} is RANGE "
                        f"{info.range_direction}, not RANGE "
                        f"{plan.range_direction.value}"
                    )
                if info.data_type.upper() != plan.data_type.upper():
                    issues.append(
                        f"partition function {plan.function!r} partitions on "
                        f"{info.data_type}, not {plan.data_type}"
                    )
                if info.partition_count != plan.partition_count:
                    issues.append(
                        f"partition function {plan.function!r} has "
                        f"{info.partition_count} partitions, but the plan "
                        f"describes {plan.partition_count}"
                    )
                if plan.scheme:
                    scheme_info = self._find_scheme(schemes, plan.scheme)
                    if scheme_info is None:
                        issues.append(
                            f"partition scheme {plan.scheme!r} does not exist"
                        )
                    else:
                        if scheme_info.function != plan.function:
                            issues.append(
                                f"partition scheme {plan.scheme!r} maps "
                                f"{scheme_info.function!r}, not "
                                f"{plan.function!r}"
                            )
                        if scheme_info.destination_count < info.partition_count:
                            issues.append(
                                f"scheme {plan.scheme!r} declares "
                                f"{scheme_info.destination_count} destinations "
                                f"for {info.partition_count} partitions"
                            )

        return PartitionReport(
            target=plan.function if plan is not None else "(all)",
            function=None if plan is None else plan.function,
            scheme=None if plan is None else plan.scheme,
            functions=tuple(functions),
            schemes=tuple(schemes),
            tables=tuple(tables),
            partitions=self._core_partitions(ranges, tables),
            ranges=tuple(ranges),
            missing_boundaries=missing,
            existing_boundaries=existing,
            issues=tuple(issues),
        )

    def _plan_validate(
        self,
        report: PartitionReport,
        plan: SQLServerPartitionPlan,
        table: Optional[str],
    ) -> Tuple[str, ...]:
        """Add the table-level checks ``validate`` makes to *report*."""
        issues = list(report.issues)
        info = report.function_info(plan.function)
        if table is not None:
            table_info = report.table_info(table)
            if table_info is None:
                issues.append(
                    f"table {table!r} is not partitioned or does not exist"
                )
            else:
                if plan.scheme and table_info.scheme != plan.scheme:
                    issues.append(
                        f"table {table!r} is built on {table_info.scheme!r}, "
                        f"not {plan.scheme!r}"
                    )
                if table_info.function != plan.function:
                    issues.append(
                        f"table {table!r} uses function "
                        f"{table_info.function!r}, not {plan.function!r}"
                    )
                if (
                    info is not None
                    and table_info.partition_count != info.partition_count
                ):
                    issues.append(
                        f"table {table!r} reports "
                        f"{table_info.partition_count} partitions, but function "
                        f"{plan.function!r} has {info.partition_count}"
                    )
                if info is not None:
                    expected = set(range(1, info.partition_count + 1))
                    observed = {row.partition_number for row in report.ranges}
                    if observed != expected:
                        issues.append(
                            f"table {table!r} partitions are "
                            f"{sorted(observed)}, expected {sorted(expected)}"
                        )
        return tuple(issues)

    def _plan_drop(
        self,
        plan: SQLServerPartitionPlan,
        functions: Sequence[PartitionFunctionInfo],
        schemes: Sequence[PartitionSchemeInfo],
        tables: Sequence[PartitionTableInfo],
        requested: Sequence[Any],
        exists: Sequence[bool],
        drop_scaffolding: bool,
    ) -> List[Tuple[PartitionOperation, Tuple[Any, ...]]]:
        """Decide what ``drop_or_merge`` would do; catalogue is read."""
        planned: List[Tuple[PartitionOperation, Tuple[Any, ...]]] = []

        def add(action: str, name: str, statement: Any) -> None:
            sql, params = statement.to_sql()
            planned.append((PartitionOperation(action=action, name=name, sql=sql), params))

        info = self._find_function(functions, plan.function)
        if info is None:
            return planned

        for boundary, present in zip(requested, exists):
            if not present:
                continue
            add(
                "merge",
                str(boundary),
                SQLServerPartitionFunctionMergeExpression(
                    self.dialect, plan.function, boundary
                ),
            )

        if not drop_scaffolding:
            return planned

        # A scheme can be dropped only when no table is built on it; the
        # function can be dropped only when no scheme maps it. Both checks
        # read the catalogue before any statement runs, so a dry run and a
        # real run agree on which drops are safe.
        candidate_schemes = [
            scheme
            for scheme in schemes
            if scheme.function == plan.function
            and (plan.scheme is None or scheme.name == plan.scheme)
        ]
        dropped_schemes: List[str] = []
        for scheme in candidate_schemes:
            users = [t for t in tables if t.scheme == scheme.name]
            if users:
                continue
            add(
                "drop_scheme",
                scheme.name,
                SQLServerDropPartitionSchemeExpression(self.dialect, scheme.name),
            )
            dropped_schemes.append(scheme.name)

        remaining_schemes = [
            scheme
            for scheme in schemes
            if scheme.function == plan.function
            and scheme.name not in dropped_schemes
        ]
        if remaining_schemes:
            return planned
        add(
            "drop_function",
            plan.function,
            SQLServerDropPartitionFunctionExpression(self.dialect, plan.function),
        )
        return planned

    # ------------------------------------------------------------- reporting
    @staticmethod
    def _core_partitions(
        ranges: Sequence[PartitionRangeInfo],
        tables: Sequence[PartitionTableInfo],
    ) -> Tuple[PartitionInfo, ...]:
        """Map the engine's per-partition rows into the core contract."""
        by_table = {(table.schema, table.name): table for table in tables}
        rows = []
        for row in ranges:
            table = by_table.get((row.schema, row.table))
            extras: Dict[str, Any] = {
                "partition_number": row.partition_number,
                "table": row.table,
            }
            if table is not None:
                extras["scheme"] = table.scheme
                extras["function"] = table.function
            rows.append(
                PartitionInfo(
                    name=f"{row.table}_{row.partition_number}",
                    parent=row.table,
                    level=1,
                    method="RANGE",
                    bound=_range_bound(row.low_boundary, row.high_boundary),
                    schema=row.schema,
                    row_count=row.row_count,
                    size_bytes=row.data_bytes,
                    extras=extras,
                )
            )
        return tuple(rows)

    @staticmethod
    def _report(
        plan: Optional[SQLServerPartitionPlan],
        functions: Sequence[PartitionFunctionInfo],
        schemes: Sequence[PartitionSchemeInfo],
        tables: Sequence[PartitionTableInfo],
        ranges: Sequence[PartitionRangeInfo],
        missing: Sequence[Any],
        existing: Sequence[str],
        issues: Sequence[str],
        planned: Sequence[Tuple[PartitionOperation, Tuple[Any, ...]]],
        dry_run: bool,
    ) -> PartitionReport:
        return PartitionReport(
            target=plan.function if plan is not None else "(all)",
            function=None if plan is None else plan.function,
            scheme=None if plan is None else plan.scheme,
            functions=tuple(functions),
            schemes=tuple(schemes),
            tables=tuple(tables),
            partitions=_SQLServerPartitionMaintenanceBase._core_partitions(
                ranges, tables
            ),
            ranges=tuple(ranges),
            missing_boundaries=tuple(missing),
            existing_boundaries=tuple(existing),
            issues=tuple(issues),
            operations=tuple(operation for operation, _ in planned),
            dry_run=dry_run,
        )

    def _run(
        self,
        planned: Sequence[Tuple[PartitionOperation, Tuple[Any, ...]]],
        dry_run: bool,
    ) -> Tuple[Tuple[str, ...], int]:
        """Execute the planned statements, stopping at the first error.

        Returns:
            ``(errors, completed)``: the failure text (empty when nothing
            failed) and how many statements ran successfully. SQL Server's
            DDL auto-commits, so a failure is reported rather than rolled back.
        """
        if dry_run:
            return (), 0
        completed = 0
        for operation, params in planned:
            try:
                self._execute(operation.sql, params)
            except DatabaseError as exc:
                return (
                    f"{operation.action} {operation.name!r} failed: {exc}",
                ), completed
            completed += 1
        return (), completed

    # -------------------------------------------------------------- gates
    def _require_support(self, plan: SQLServerPartitionPlan) -> None:
        if not self.dialect.supports_table_partitioning():
            raise UnsupportedFeatureError(
                "SQL Server",
                "table partitioning",
                "Partitioning requires SQL Server 2008 or later.",
            )
        if not self.dialect.supports_partition_function():
            raise UnsupportedFeatureError(
                "SQL Server", "partition functions", "Requires SQL Server 2008+."
            )
        if plan.scheme and not self.dialect.supports_partition_scheme():
            raise UnsupportedFeatureError(
                "SQL Server", "partition schemes", "Requires SQL Server 2008+."
            )
        if self.dialect.supports_subpartitioning():
            raise UnsupportedFeatureError(
                "SQL Server",
                "subpartitioning",
                "This backend must not claim subpartitioning.",
            )
        if not self.dialect.supports_split_partition():
            raise UnsupportedFeatureError(
                "SQL Server", "SPLIT RANGE", "Requires SQL Server 2008+."
            )

    def _require_merge(self) -> None:
        if not self.dialect.supports_table_partitioning():
            raise UnsupportedFeatureError(
                "SQL Server", "table partitioning", "Requires SQL Server 2008+."
            )
        if not self.dialect.supports_merge_partition():
            raise UnsupportedFeatureError(
                "SQL Server", "MERGE RANGE", "Requires SQL Server 2008+."
            )
        if self.dialect.supports_subpartitioning():
            raise UnsupportedFeatureError(
                "SQL Server",
                "subpartitioning",
                "This backend must not claim subpartitioning.",
            )


class SQLServerPartitionMaintenance(_SQLServerPartitionMaintenanceBase):
    """Synchronous SQL Server partition maintenance.

    Example:
        >>> maintenance = SQLServerPartitionMaintenance(backend)
        >>> report = maintenance.ensure(plan)
        >>> dry = maintenance.drop_or_merge(plan, [date(2026, 1, 1)])
    """

    def _fetch_rows(self, statement: Any) -> Sequence[Any]:
        sql, params = statement.to_sql()
        result = self.backend.execute(sql, params)
        return result.data or []

    def _read_functions(
        self, function_name: Optional[str] = None
    ) -> Tuple[PartitionFunctionInfo, ...]:
        return self._parse_functions(
            self._fetch_rows(
                SQLServerPartitionFunctionQueryStatement(
                    self.dialect, function_name=function_name
                )
            )
        )

    def _read_schemes(
        self,
        scheme_name: Optional[str] = None,
        function_name: Optional[str] = None,
    ) -> Tuple[PartitionSchemeInfo, ...]:
        return self._parse_schemes(
            self._fetch_rows(
                SQLServerPartitionSchemeQueryStatement(
                    self.dialect,
                    scheme_name=scheme_name,
                    function_name=function_name,
                )
            )
        )

    def _read_tables(
        self,
        table_name: Optional[str] = None,
        schema: Optional[str] = None,
        scheme_name: Optional[str] = None,
    ) -> Tuple[PartitionTableInfo, ...]:
        return self._parse_tables(
            self._fetch_rows(
                SQLServerPartitionTableQueryStatement(
                    self.dialect,
                    table_name=table_name,
                    schema=schema,
                    scheme_name=scheme_name,
                )
            )
        )

    def _read_ranges(
        self, table_name: str, schema: Optional[str] = None
    ) -> Tuple[PartitionRangeInfo, ...]:
        return self._parse_ranges(
            self._fetch_rows(
                SQLServerPartitionRangeQueryStatement(
                    self.dialect, table_name=table_name, schema=schema
                )
            )
        )

    def _read_boundary_exists(
        self, plan: SQLServerPartitionPlan
    ) -> Tuple[bool, ...]:
        exists = []
        for boundary in plan.boundaries:
            rows = self._fetch_rows(
                SQLServerPartitionBoundaryQueryStatement(
                    self.dialect,
                    function_name=plan.function,
                    data_type=plan.data_type,
                    boundary_value=_boundary_parameter(boundary),
                )
            )
            exists.append(bool(rows and _as_int(rows[0].get("boundary_exists"))))
        return tuple(exists)

    def _execute(self, sql: str, params: Tuple[Any, ...]) -> None:
        self.backend.execute(sql, params)

    def ensure(
        self, plan: SQLServerPartitionPlan, *, dry_run: bool = False
    ) -> PartitionReport:
        """Create what is missing and split absent boundaries.

        The function is created with the plan's full boundary list when it
        does not exist; when it does, only boundaries the server does not
        already hold are split in. A scheme is created on demand. Existing
        objects are never altered: a direction or type mismatch raises
        ``ValueError`` rather than being repaired behind the caller's back.

        Args:
            plan: The function, boundaries and optional scheme to ensure.
            dry_run: Build the statement list without executing it.

        Returns:
            A report whose ``operations`` are the statements run (or would be
            run), and whose ``issues`` are inconsistencies found while
            planning.
        """
        self._require_support(plan)
        functions = self._read_functions(plan.function)
        exists = self._read_boundary_exists(plan)
        schemes = self._read_schemes(plan.scheme, plan.function) if plan.scheme else ()
        missing, planned, issues = self._plan_ensure(plan, functions, schemes, exists)
        existing = ()
        info = self._find_function(functions, plan.function)
        if info is not None:
            existing = info.boundary_values
        report = self._report(
            plan, functions, schemes, (), (), missing, existing, issues, planned, dry_run
        )
        errors, completed = self._run(planned, dry_run)
        if dry_run:
            return report
        post = self.list(plan)
        return replace(
            post,
            operations=tuple(operation for operation, _ in planned[:completed]),
            issues=tuple(dict.fromkeys((*issues, *post.issues))),
            errors=errors,
            dry_run=False,
        )

    def list(
        self,
        plan: Optional[SQLServerPartitionPlan] = None,
        *,
        table: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> PartitionReport:
        """Read the catalogue and report the tree around a plan or table.

        Args:
            plan: When given, narrows to its function and scheme and reports
                its missing boundaries.
            table: When given, also returns that table's per-partition rows.
            schema: Schema the requested table lives in.
        """
        function_name = None if plan is None else plan.function
        scheme_name = None if plan is None else plan.scheme
        functions = self._read_functions(function_name)
        schemes = self._read_schemes(scheme_name, function_name) if plan else ()
        tables = self._read_tables(
            table, schema, None if (plan is None or table) else plan.scheme
        )
        ranges = self._read_ranges(table, schema) if table else ()
        exists = self._read_boundary_exists(plan) if plan is not None else ()
        return self._plan_list(plan, functions, schemes, tables, ranges, exists)

    def retention_boundaries(
        self,
        plan: SQLServerPartitionPlan,
        cutoff: Any,
        *,
        table: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> Tuple[Any, ...]:
        """Return the boundaries a retention cut would merge away.

        SQL Server's function boundary is the upper bound of the partition on
        its left, whichever RANGE direction the function declares, so a
        boundary qualifies when it is less than or equal to *cutoff*.

        Args:
            plan: Plan naming the function and its boundary type.
            cutoff: The oldest value to keep.
            table: When given, read the table's partition ranges instead of
                the function's boundary list.
            schema: Schema the table lives in.

        Returns:
            Boundary values, in ascending order, whose partition lies wholly
            before or on *cutoff*. Nothing is executed.
        """
        function = self._find_function(
            self._read_functions(plan.function), plan.function
        )
        if table is not None:
            texts = tuple(
                row.high_boundary
                for row in self._read_ranges(table, schema)
                if row.high_boundary is not None
            )
        elif function is not None:
            texts = function.boundary_values
        else:
            return ()
        cutoff_value = _coerce_cutoff(plan.data_type, cutoff)
        values = tuple(
            _parse_catalogue_boundary(plan.data_type, text) for text in texts
        )
        return tuple(value for value in values if value <= cutoff_value)

    def drop_before(
        self,
        plan: SQLServerPartitionPlan,
        cutoff: Any,
        *,
        dry_run: bool = True,
        drop_scaffolding: bool = False,
    ) -> PartitionReport:
        """Merge the partitions a retention cut puts at or before *cutoff*.

        The boundaries are computed from the catalogue by
        :meth:`retention_boundaries` and handed to :meth:`drop_or_merge`.
        SQL Server cannot drop a partition, so this is a ``MERGE RANGE``
        operation, not a metadata-only drop.

        Args:
            plan: The plan whose function is acted on.
            cutoff: The oldest value to keep.
            dry_run: Render the statements without executing them (the
                default).
            drop_scaffolding: Also drop the scheme and function when unused.
        """
        boundaries = self.retention_boundaries(plan, cutoff)
        return self.drop_or_merge(
            plan,
            boundaries,
            dry_run=dry_run,
            drop_scaffolding=drop_scaffolding,
        )

    def drop_or_merge(
        self,
        plan: SQLServerPartitionPlan,
        boundaries: Optional[Sequence[Any]] = None,
        *,
        dry_run: bool = True,
        drop_scaffolding: bool = False,
    ) -> PartitionReport:
        """Merge boundaries away, or drop the function and scheme behind them.

        SQL Server has no ``DROP PARTITION``; a boundary is removed with
        ``MERGE RANGE``, which folds its rows into the partition on the left.
        ``boundaries`` names exactly what to merge -- there is no retention
        policy here, and no "before date" shorthand. When omitted, the plan's
        own boundaries are merged, collapsing the function to one partition.

        ``drop_scaffolding`` drops the scheme and then the function, but only
        when the catalogue shows no table built on either. A table using the
        scheme keeps both, and the report says why.

        Args:
            plan: The plan whose function and scheme are acted on.
            boundaries: Boundary values to merge; defaults to the plan's.
            dry_run: Leave the statements unexecuted (the default).
            drop_scaffolding: Also drop the scheme and function when unused.
        """
        self._require_merge()
        requested = tuple(plan.boundaries if boundaries is None else boundaries)
        functions = self._read_functions(plan.function)
        schemes = self._read_schemes(function_name=plan.function)
        tables = self._read_tables()
        exists = self._read_boundary_exists_for(plan, requested)
        planned = self._plan_drop(
            plan,
            functions,
            schemes,
            tables,
            requested,
            exists,
            drop_scaffolding,
        )

        issues = []
        info = self._find_function(functions, plan.function)
        if info is None:
            issues.append(f"partition function {plan.function!r} does not exist")
        for boundary, present in zip(requested, exists):
            if not present:
                issues.append(
                    f"boundary {boundary!r} is not present in "
                    f"{plan.function!r}; nothing to merge"
                )
        if drop_scaffolding:
            for scheme in schemes:
                if scheme.function != plan.function:
                    continue
                if plan.scheme is not None and scheme.name != plan.scheme:
                    continue
                users = [t for t in tables if t.scheme == scheme.name]
                if users:
                    issues.append(
                        f"scheme {scheme.name!r} is used by "
                        f"{len(users)} table(s); it cannot be dropped"
                    )
            dropped = {
                operation.name
                for operation, _ in planned
                if operation.action == "drop_scheme"
            }
            remaining = [
                scheme
                for scheme in schemes
                if scheme.function == plan.function and scheme.name not in dropped
            ]
            if remaining:
                issues.append(
                    f"partition function {plan.function!r} is still mapped by "
                    f"scheme(s) {[s.name for s in remaining]}; it cannot be dropped"
                )
        report = self._report(
            plan, functions, schemes, tables, (), (), (), issues, planned, dry_run
        )
        errors, completed = self._run(planned, dry_run)
        if dry_run:
            return report
        post = self.list(plan)
        return replace(
            post,
            operations=tuple(operation for operation, _ in planned[:completed]),
            issues=tuple(dict.fromkeys((*issues, *post.issues))),
            errors=errors,
            dry_run=False,
        )

    def validate(
        self,
        plan: SQLServerPartitionPlan,
        *,
        table: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> PartitionReport:
        """Report gaps, mismatches and partition-number holes; repair nothing.

        Args:
            plan: The plan to validate against the catalogue.
            table: Optionally also check that this table is on the plan's
                scheme, uses its function, and has one row per partition.
            schema: Schema the table lives in.
        """
        report = self.list(plan, table=table, schema=schema)
        issues = self._plan_validate(report, plan, table)
        return replace(report, issues=issues)

    def _read_boundary_exists_for(
        self, plan: SQLServerPartitionPlan, boundaries: Sequence[Any]
    ) -> Tuple[bool, ...]:
        exists = []
        for boundary in boundaries:
            rows = self._fetch_rows(
                SQLServerPartitionBoundaryQueryStatement(
                    self.dialect,
                    function_name=plan.function,
                    data_type=plan.data_type,
                    boundary_value=_boundary_parameter(boundary),
                )
            )
            exists.append(bool(rows and _as_int(rows[0].get("boundary_exists"))))
        return tuple(exists)


class AsyncSQLServerPartitionMaintenance(_SQLServerPartitionMaintenanceBase):
    """Asynchronous SQL Server partition maintenance.

    Mirrors :class:`SQLServerPartitionMaintenance` method for method; only
    the I/O seams await.
    """

    async def _fetch_rows(self, statement: Any) -> Sequence[Any]:
        sql, params = statement.to_sql()
        result = await self.backend.execute(sql, params)
        return result.data or []

    async def _read_functions(
        self, function_name: Optional[str] = None
    ) -> Tuple[PartitionFunctionInfo, ...]:
        return self._parse_functions(
            await self._fetch_rows(
                SQLServerPartitionFunctionQueryStatement(
                    self.dialect, function_name=function_name
                )
            )
        )

    async def _read_schemes(
        self,
        scheme_name: Optional[str] = None,
        function_name: Optional[str] = None,
    ) -> Tuple[PartitionSchemeInfo, ...]:
        return self._parse_schemes(
            await self._fetch_rows(
                SQLServerPartitionSchemeQueryStatement(
                    self.dialect,
                    scheme_name=scheme_name,
                    function_name=function_name,
                )
            )
        )

    async def _read_tables(
        self,
        table_name: Optional[str] = None,
        schema: Optional[str] = None,
        scheme_name: Optional[str] = None,
    ) -> Tuple[PartitionTableInfo, ...]:
        return self._parse_tables(
            await self._fetch_rows(
                SQLServerPartitionTableQueryStatement(
                    self.dialect,
                    table_name=table_name,
                    schema=schema,
                    scheme_name=scheme_name,
                )
            )
        )

    async def _read_ranges(
        self, table_name: str, schema: Optional[str] = None
    ) -> Tuple[PartitionRangeInfo, ...]:
        return self._parse_ranges(
            await self._fetch_rows(
                SQLServerPartitionRangeQueryStatement(
                    self.dialect, table_name=table_name, schema=schema
                )
            )
        )

    async def _read_boundary_exists(
        self, plan: SQLServerPartitionPlan
    ) -> Tuple[bool, ...]:
        exists = []
        for boundary in plan.boundaries:
            rows = await self._fetch_rows(
                SQLServerPartitionBoundaryQueryStatement(
                    self.dialect,
                    function_name=plan.function,
                    data_type=plan.data_type,
                    boundary_value=_boundary_parameter(boundary),
                )
            )
            exists.append(bool(rows and _as_int(rows[0].get("boundary_exists"))))
        return tuple(exists)

    async def _read_boundary_exists_for(
        self, plan: SQLServerPartitionPlan, boundaries: Sequence[Any]
    ) -> Tuple[bool, ...]:
        exists = []
        for boundary in boundaries:
            rows = await self._fetch_rows(
                SQLServerPartitionBoundaryQueryStatement(
                    self.dialect,
                    function_name=plan.function,
                    data_type=plan.data_type,
                    boundary_value=_boundary_parameter(boundary),
                )
            )
            exists.append(bool(rows and _as_int(rows[0].get("boundary_exists"))))
        return tuple(exists)

    async def _execute(self, sql: str, params: Tuple[Any, ...]) -> None:
        await self.backend.execute(sql, params)

    async def _run(
        self,
        planned: Sequence[Tuple[PartitionOperation, Tuple[Any, ...]]],
        dry_run: bool,
    ) -> Tuple[Tuple[str, ...], int]:
        """Execute the planned statements asynchronously, stopping at the first error.

        Returns:
            ``(errors, completed)``: the failure text (empty when nothing
            failed) and how many statements ran successfully.
        """
        if dry_run:
            return (), 0
        completed = 0
        for operation, params in planned:
            try:
                await self._execute(operation.sql, params)
            except DatabaseError as exc:
                return (
                    f"{operation.action} {operation.name!r} failed: {exc}",
                ), completed
            completed += 1
        return (), completed

    async def ensure(
        self, plan: SQLServerPartitionPlan, *, dry_run: bool = False
    ) -> PartitionReport:
        """Create what is missing and split absent boundaries asynchronously.

        The function is created with the plan's full boundary list when it
        does not exist; when it does, only boundaries the server does not
        already hold are split in. A scheme is created on demand. Existing
        objects are never altered: a direction or type mismatch raises
        ``ValueError`` rather than being repaired behind the caller's back.

        Args:
            plan: The function, boundaries and optional scheme to ensure.
            dry_run: Build the statement list without executing it.

        Returns:
            A report whose ``operations`` are the statements run (or would be
            run), and whose ``issues`` are inconsistencies found while
            planning.
        """
        self._require_support(plan)
        functions = await self._read_functions(plan.function)
        exists = await self._read_boundary_exists(plan)
        schemes = (
            await self._read_schemes(plan.scheme, plan.function) if plan.scheme else ()
        )
        missing, planned, issues = self._plan_ensure(plan, functions, schemes, exists)
        existing = ()
        info = self._find_function(functions, plan.function)
        if info is not None:
            existing = info.boundary_values
        report = self._report(
            plan, functions, schemes, (), (), missing, existing, issues, planned, dry_run
        )
        errors, completed = await self._run(planned, dry_run)
        if dry_run:
            return report
        post = await self.list(plan)
        return replace(
            post,
            operations=tuple(operation for operation, _ in planned[:completed]),
            issues=tuple(dict.fromkeys((*issues, *post.issues))),
            errors=errors,
            dry_run=False,
        )

    async def list(
        self,
        plan: Optional[SQLServerPartitionPlan] = None,
        *,
        table: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> PartitionReport:
        """Read the catalogue and report the tree asynchronously.

        Args:
            plan: When given, narrows to its function and scheme and reports
                its missing boundaries.
            table: When given, also returns that table's per-partition rows.
            schema: Schema the requested table lives in.
        """
        function_name = None if plan is None else plan.function
        scheme_name = None if plan is None else plan.scheme
        functions = await self._read_functions(function_name)
        schemes = (
            await self._read_schemes(scheme_name, function_name) if plan else ()
        )
        tables = await self._read_tables(
            table, schema, None if (plan is None or table) else plan.scheme
        )
        ranges = await self._read_ranges(table, schema) if table else ()
        exists = await self._read_boundary_exists(plan) if plan is not None else ()
        return self._plan_list(plan, functions, schemes, tables, ranges, exists)

    async def retention_boundaries(
        self,
        plan: SQLServerPartitionPlan,
        cutoff: Any,
        *,
        table: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> Tuple[Any, ...]:
        """Return the boundaries a retention cut would merge away asynchronously.

        SQL Server's function boundary is the upper bound of the partition on
        its left, whichever RANGE direction the function declares, so a
        boundary qualifies when it is less than or equal to *cutoff*.

        Args:
            plan: Plan naming the function and its boundary type.
            cutoff: The oldest value to keep.
            table: When given, read the table's partition ranges instead of
                the function's boundary list.
            schema: Schema the table lives in.

        Returns:
            Boundary values, in ascending order, whose partition lies wholly
            before or on *cutoff*. Nothing is executed.
        """
        function = self._find_function(
            await self._read_functions(plan.function), plan.function
        )
        if table is not None:
            texts = tuple(
                row.high_boundary
                for row in await self._read_ranges(table, schema)
                if row.high_boundary is not None
            )
        elif function is not None:
            texts = function.boundary_values
        else:
            return ()
        cutoff_value = _coerce_cutoff(plan.data_type, cutoff)
        values = tuple(
            _parse_catalogue_boundary(plan.data_type, text) for text in texts
        )
        return tuple(value for value in values if value <= cutoff_value)

    async def drop_before(
        self,
        plan: SQLServerPartitionPlan,
        cutoff: Any,
        *,
        dry_run: bool = True,
        drop_scaffolding: bool = False,
    ) -> PartitionReport:
        """Merge the partitions at or before *cutoff* asynchronously.

        The boundaries are computed from the catalogue by
        :meth:`retention_boundaries` and handed to :meth:`drop_or_merge`.
        SQL Server cannot drop a partition, so this is a ``MERGE RANGE``
        operation, not a metadata-only drop.

        Args:
            plan: The plan whose function is acted on.
            cutoff: The oldest value to keep.
            dry_run: Render the statements without executing them (the
                default).
            drop_scaffolding: Also drop the scheme and function when unused.
        """
        boundaries = await self.retention_boundaries(plan, cutoff)
        return await self.drop_or_merge(
            plan,
            boundaries,
            dry_run=dry_run,
            drop_scaffolding=drop_scaffolding,
        )

    async def drop_or_merge(
        self,
        plan: SQLServerPartitionPlan,
        boundaries: Optional[Sequence[Any]] = None,
        *,
        dry_run: bool = True,
        drop_scaffolding: bool = False,
    ) -> PartitionReport:
        """Merge boundaries away, or drop the unused scaffolding, asynchronously.

        SQL Server has no ``DROP PARTITION``; a boundary is removed with
        ``MERGE RANGE``, which folds its rows into the partition on the left.
        ``boundaries`` names exactly what to merge -- there is no retention
        policy here, and no "before date" shorthand. When omitted, the plan's
        own boundaries are merged, collapsing the function to one partition.

        ``drop_scaffolding`` drops the scheme and then the function, but only
        when the catalogue shows no table built on either. A table using the
        scheme keeps both, and the report says why.

        Args:
            plan: The plan whose function and scheme are acted on.
            boundaries: Boundary values to merge; defaults to the plan's.
            dry_run: Leave the statements unexecuted (the default).
            drop_scaffolding: Also drop the scheme and function when unused.
        """
        self._require_merge()
        requested = tuple(plan.boundaries if boundaries is None else boundaries)
        functions = await self._read_functions(plan.function)
        schemes = await self._read_schemes(function_name=plan.function)
        tables = await self._read_tables()
        exists = await self._read_boundary_exists_for(plan, requested)
        planned = self._plan_drop(
            plan,
            functions,
            schemes,
            tables,
            requested,
            exists,
            drop_scaffolding,
        )

        issues = []
        info = self._find_function(functions, plan.function)
        if info is None:
            issues.append(f"partition function {plan.function!r} does not exist")
        for boundary, present in zip(requested, exists):
            if not present:
                issues.append(
                    f"boundary {boundary!r} is not present in "
                    f"{plan.function!r}; nothing to merge"
                )
        if drop_scaffolding:
            for scheme in schemes:
                if scheme.function != plan.function:
                    continue
                if plan.scheme is not None and scheme.name != plan.scheme:
                    continue
                users = [t for t in tables if t.scheme == scheme.name]
                if users:
                    issues.append(
                        f"scheme {scheme.name!r} is used by "
                        f"{len(users)} table(s); it cannot be dropped"
                    )
            dropped = {
                operation.name
                for operation, _ in planned
                if operation.action == "drop_scheme"
            }
            remaining = [
                scheme
                for scheme in schemes
                if scheme.function == plan.function and scheme.name not in dropped
            ]
            if remaining:
                issues.append(
                    f"partition function {plan.function!r} is still mapped by "
                    f"scheme(s) {[s.name for s in remaining]}; it cannot be dropped"
                )
        report = self._report(
            plan, functions, schemes, tables, (), (), (), issues, planned, dry_run
        )
        errors, completed = await self._run(planned, dry_run)
        if dry_run:
            return report
        post = await self.list(plan)
        return replace(
            post,
            operations=tuple(operation for operation, _ in planned[:completed]),
            issues=tuple(dict.fromkeys((*issues, *post.issues))),
            errors=errors,
            dry_run=False,
        )

    async def validate(
        self,
        plan: SQLServerPartitionPlan,
        *,
        table: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> PartitionReport:
        """Report gaps, mismatches and partition-number holes asynchronously.

        Nothing is repaired.

        Args:
            plan: The plan to validate against the catalogue.
            table: Optionally also check that this table is on the plan's
                scheme, uses its function, and has one row per partition.
            schema: Schema the table lives in.
        """
        report = await self.list(plan, table=table, schema=schema)
        issues = self._plan_validate(report, plan, table)
        return replace(report, issues=issues)
