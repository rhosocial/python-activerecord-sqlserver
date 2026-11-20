# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/ddl/test_partition_maintenance_offline.py
"""Offline mock-driven coverage for the SQL Server partition maintenance module.

The companion ``test_partition_maintenance.py`` drives the executors through
fake subclasses that override every I/O seam, so the module-level conversion
helpers and the real ``_fetch_rows`` / ``_read_*`` / ``_execute`` implementations
are never entered. This file closes that gap with pure mocks: a connectionless
real dialect renders the statements, a ``MagicMock``/``AsyncMock`` backend
answers ``execute``, and no driver, network or server is involved.

Both the sync and the native-async executors are covered; the async cases are
plain ``async def`` tests under the repository's ``asyncio_mode = auto``.
"""

from datetime import date, datetime, time, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.errors import DatabaseError

from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.partition.maintenance import (
    AsyncSQLServerPartitionMaintenance,
    SQLServerPartitionMaintenance,
    _as_int,
    _boundary_family,
    _boundary_parameter,
    _coerce_cutoff,
    _parse_catalogue_boundary,
    _range_bound,
    _SQLServerPartitionMaintenanceBase,
    _trim_iso_fraction,
)
from rhosocial.activerecord.backend.impl.sqlserver.partition.plan import (
    SQLServerPartitionPlan,
    _boundary_token,
)
from rhosocial.activerecord.backend.impl.sqlserver.partition.report import (
    PartitionFunctionInfo,
    PartitionOperation,
    PartitionRangeInfo,
    PartitionSchemeInfo,
    PartitionTableInfo,
)

DIALECT = SQLServerDialect(version=(16, 0, 0))


def _plan(boundaries=(date(2026, 1, 1), date(2026, 2, 1)), **kwargs):
    return SQLServerPartitionPlan(
        function=kwargs.pop("function", "pf_logs"),
        data_type=kwargs.pop("data_type", "DATE"),
        boundaries=boundaries,
        **kwargs,
    )


def _function(
    boundaries=("2026-01-01", "2026-02-01"), *, data_type="date", direction="RIGHT", count=None
):
    return PartitionFunctionInfo(
        name="pf_logs",
        data_type=data_type,
        range_direction=direction,
        boundary_values=tuple(boundaries),
        partition_count=len(boundaries) + 1 if count is None else count,
    )


def _scheme(name="ps_logs", *, function="pf_logs", filegroups=("PRIMARY",)):
    return PartitionSchemeInfo(name, function, tuple(filegroups))


def _table(name="logs", *, schema="dbo", scheme="ps_logs", function="pf_logs", count=3):
    return PartitionTableInfo(name, schema, scheme, function, "created_at", count)


def _range(number=1, *, table="logs", schema="dbo", low=None, high=None, rows=None, pages=None):
    return PartitionRangeInfo(
        table,
        schema,
        number,
        low,
        high,
        rows,
        None if pages is None else pages * 8192,
    )


def _backend(*, dialect=DIALECT, execute=None):
    backend = MagicMock()
    backend.dialect = dialect
    if execute is not None:
        backend.execute = execute
    return backend


def _base(*, dialect=DIALECT):
    return _SQLServerPartitionMaintenanceBase(_backend(dialect=dialect))


def _gate_dialect(**overrides):
    dialect = MagicMock()
    dialect.supports_table_partitioning.return_value = True
    dialect.supports_partition_function.return_value = True
    dialect.supports_partition_scheme.return_value = True
    dialect.supports_subpartitioning.return_value = False
    dialect.supports_split_partition.return_value = True
    dialect.supports_merge_partition.return_value = True
    for name, value in overrides.items():
        getattr(dialect, name).return_value = value
    return dialect


class TestAsInt:
    """Catalogue integers arrive as ints, strings or None."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [(None, None), (7, 7), (0, 0), ("12", 12), ("-3", -3), ("007", 7)],
    )
    def test_reads_int_like_values(self, value, expected):
        assert _as_int(value) == expected

    def test_rejects_non_numeric_text(self):
        with pytest.raises(ValueError):
            _as_int("n/a")


class TestBoundaryParameter:
    """Bind parameters must be spelled so every ODBC driver accepts them."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (datetime(2026, 1, 2, 3, 4, 5), "2026-01-02 03:04:05"),
            (date(2026, 1, 2), "2026-01-02"),
            (time(3, 4, 5), "03:04:05"),
            (Decimal("1.50"), "1.50"),
            (42, 42),
            ("text", "text"),
            (None, None),
        ],
    )
    def test_conversion(self, value, expected):
        assert _boundary_parameter(value) == expected


class TestBoundaryFamily:
    """Type spellings group by the comparison the server supports."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("date", "date"),
            ("DATE", "date"),
            ("datetime", "datetime"),
            ("datetime2", "datetime"),
            ("DATETIME2(3)", "datetime"),
            ("smalldatetime", "datetime"),
            ("datetimeoffset", "datetime"),
            ("DATETIMEOFFSET(7)", "datetime"),
            ("time", "time"),
            ("TIME(7)", "time"),
            ("tinyint", "int"),
            ("smallint", "int"),
            ("INT", "int"),
            ("bigint", "int"),
            ("decimal", "number"),
            ("DECIMAL(10, 2)", "number"),
            ("numeric(18, 0)", "number"),
            ("money", "number"),
            ("smallmoney", "number"),
            ("float", "number"),
            ("real", "number"),
            ("nvarchar(50)", "text"),
            ("varchar(max)", "text"),
            ("xml", "text"),
        ],
    )
    def test_family(self, value, expected):
        assert _boundary_family(value) == expected


class TestTrimIsoFraction:
    """Pre-3.11 parsers only accept six fractional digits."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("2026-01-01", "2026-01-01"),
            ("2026-01-01 00:00:00", "2026-01-01 00:00:00"),
            ("00:00:00.1", "00:00:00.1"),
            ("00:00:00.123456", "00:00:00.123456"),
            ("00:00:00.1234567", "00:00:00.123456"),
            ("00:00:00.123456789+00:00", "00:00:00.123456+00:00"),
            ("1.", "1."),
        ],
    )
    def test_trim(self, value, expected):
        assert _trim_iso_fraction(value) == expected


class TestParseCatalogueBoundary:
    """Catalogue text is read back into the declared type's Python value."""

    @pytest.mark.parametrize(
        ("data_type", "text", "expected"),
        [
            ("date", "2026-01-02T00:00:00", date(2026, 1, 2)),
            ("DATE", "2026-01-02", date(2026, 1, 2)),
            ("datetime", "2026-01-02 03:04:05", datetime(2026, 1, 2, 3, 4, 5)),
            ("datetime2", "2026-01-02T03:04:05.1234567", datetime(2026, 1, 2, 3, 4, 5, 123456)),
            ("datetimeoffset", "2026-01-02T03:04:05+08:00", datetime(2026, 1, 2, 3, 4, 5)),
            ("datetime", "2026-01-02T03:04:05Z", datetime(2026, 1, 2, 3, 4, 5)),
            ("time", "03:04:05", time(3, 4, 5)),
            ("int", "42", 42),
            ("bigint", "-7", -7),
            ("decimal", "1.50", Decimal("1.50")),
            ("money", "12.345", Decimal("12.345")),
            ("nvarchar(50)", "abc", "abc"),
        ],
    )
    def test_valid(self, data_type, text, expected):
        assert _parse_catalogue_boundary(data_type, text) == expected

    @pytest.mark.parametrize(
        ("data_type", "text"),
        [("date", "not-a-date"), ("int", "1.5"), ("decimal", "NaN!"), ("time", "25:00:00")],
    )
    def test_invalid_text_raises_value_error(self, data_type, text):
        with pytest.raises(ValueError, match="is not a valid"):
            _parse_catalogue_boundary(data_type, text)


class TestCoerceCutoff:
    """A caller's cutoff is coerced to the comparand for the function type."""

    @pytest.mark.parametrize(
        ("data_type", "value", "expected"),
        [
            ("date", datetime(2026, 1, 2, 23, 0), date(2026, 1, 2)),
            ("date", date(2026, 1, 2), date(2026, 1, 2)),
            ("date", "2026-01-02T00:00:00", date(2026, 1, 2)),
            ("datetime", date(2026, 1, 2), datetime(2026, 1, 2)),
            (
                "datetime",
                datetime(2026, 1, 2, 3, 4, 5, 123456),
                datetime(2026, 1, 2, 3, 4, 5, 123456),
            ),
            ("datetime", "2026-01-02T03:04:05.1234567Z", datetime(2026, 1, 2, 3, 4, 5, 123456)),
            (
                "datetime",
                datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc),
                datetime(2026, 1, 2, 3, 4),
            ),
            ("time", time(3, 4, 5), time(3, 4, 5)),
            ("time", "03:04:05.1234567", time(3, 4, 5, 123456)),
            ("int", "42", 42),
            ("int", 42, 42),
            ("decimal", "1.50", Decimal("1.50")),
            ("decimal", 1.5, Decimal("1.5")),
            ("nvarchar(50)", datetime(2026, 1, 2, 3, 4), "2026-01-02 03:04:00"),
            ("nvarchar(50)", date(2026, 1, 2), "2026-01-02"),
            ("nvarchar(50)", time(3, 4), "03:04:00"),
            ("nvarchar(50)", Decimal("1.50"), "1.50"),
            ("nvarchar(50)", 7, "7"),
        ],
    )
    def test_valid(self, data_type, value, expected):
        assert _coerce_cutoff(data_type, value) == expected

    @pytest.mark.parametrize(
        ("data_type", "value"),
        [("date", "not-a-date"), ("int", "x"), ("decimal", "oops"), ("time", "99:99")],
    )
    def test_invalid_cutoff_raises_value_error(self, data_type, value):
        with pytest.raises(ValueError, match="is not a valid"):
            _coerce_cutoff(data_type, value)


class TestRangeBound:
    """Low/high catalogue text joins into one display string."""

    @pytest.mark.parametrize(
        ("low", "high", "expected"),
        [
            (None, None, None),
            ("a", None, "a.."),
            (None, "b", "..b"),
            ("a", "b", "a..b"),
        ],
    )
    def test_join(self, low, high, expected):
        assert _range_bound(low, high) == expected


class TestCatalogueParsing:
    """Row dictionaries become the report's immutable value objects."""

    def test_functions_group_rows_and_preserve_boundary_order(self):
        rows = [
            {
                "function_name": "pf",
                "data_type": "date",
                "boundary_value_on_right": "1",
                "partition_count": "3",
                "boundary_value": "2026-01-01",
            },
            {
                "function_name": "pf",
                "data_type": "date",
                "boundary_value_on_right": 1,
                "partition_count": 3,
                "boundary_value": "2026-02-01",
            },
            {
                "function_name": "pf",
                "data_type": "date",
                "boundary_value_on_right": 0,
                "partition_count": 3,
                "boundary_value": None,
            },
            {"function_name": None, "data_type": "date"},
        ]
        result = _SQLServerPartitionMaintenanceBase._parse_functions(rows)
        assert len(result) == 1
        assert result[0].range_direction == "RIGHT"
        assert result[0].boundary_values == ("2026-01-01", "2026-02-01")
        assert result[0].partition_count == 3

    def test_functions_default_to_left_and_zero(self):
        result = _SQLServerPartitionMaintenanceBase._parse_functions(
            [{"function_name": "pf", "boundary_value_on_right": 0}]
        )
        assert result[0].range_direction == "LEFT"
        assert result[0].data_type == ""
        assert result[0].partition_count == 0

    def test_schemes_skip_missing_names_and_empty_filegroups(self):
        rows = [
            {
                "scheme_name": "ps",
                "function_name": "pf",
                "partition_count": "3",
                "filegroup_name": "",
            },
            {
                "scheme_name": "ps",
                "function_name": "pf",
                "partition_count": 3,
                "filegroup_name": "fg1",
            },
            {"scheme_name": None, "function_name": "pf"},
        ]
        result = _SQLServerPartitionMaintenanceBase._parse_schemes(rows)
        assert len(result) == 1
        assert result[0].filegroups == ("fg1",)
        assert result[0].destination_count == 1

    def test_tables_deduplicate_by_schema_and_name(self):
        rows = [
            {
                "table_name": "logs",
                "schema_name": "dbo",
                "scheme_name": "ps",
                "function_name": "pf",
                "partition_count": "3",
                "partition_column": None,
            },
            {
                "table_name": "logs",
                "schema_name": "dbo",
                "scheme_name": "ps",
                "function_name": "pf",
                "partition_count": 3,
                "partition_column": "created_at",
            },
            {
                "table_name": "other",
                "schema_name": None,
                "scheme_name": None,
                "function_name": None,
                "partition_count": None,
            },
            {"table_name": None, "schema_name": "dbo"},
        ]
        result = _SQLServerPartitionMaintenanceBase._parse_tables(rows)
        assert len(result) == 2
        assert result[0].partition_column is None
        assert result[0].partition_count == 3
        assert result[1].schema is None
        assert result[1].scheme == ""
        assert result[1].function == ""

    def test_ranges_calculate_bytes_and_tolerate_nulls(self):
        rows = [
            {
                "table_name": "logs",
                "schema_name": "dbo",
                "partition_number": "2",
                "row_count": "10",
                "used_page_count": "3",
                "low_boundary": "a",
                "high_boundary": None,
            },
            {
                "table_name": "logs",
                "schema_name": None,
                "partition_number": None,
                "row_count": None,
                "used_page_count": None,
                "low_boundary": None,
                "high_boundary": None,
            },
        ]
        result = _SQLServerPartitionMaintenanceBase._parse_ranges(rows)
        assert result[0].data_bytes == 3 * 8192
        assert result[0].row_count == 10
        assert result[0].partition_number == 2
        assert result[1].partition_number == 0
        assert result[1].row_count is None
        assert result[1].data_bytes is None
        assert result[1].schema is None

    @pytest.mark.parametrize(
        ("functions", "name", "found"),
        [
            ((_function(),), "pf_logs", True),
            ((_function(),), "absent", False),
            ((), "pf_logs", False),
        ],
    )
    def test_find_function(self, functions, name, found):
        assert (
            _SQLServerPartitionMaintenanceBase._find_function(functions, name) is not None
        ) is found

    @pytest.mark.parametrize(
        ("name", "found"),
        [("ps_logs", True), ("absent", False), (None, False)],
    )
    def test_find_scheme(self, name, found):
        schemes = (_scheme(),)
        assert (_SQLServerPartitionMaintenanceBase._find_scheme(schemes, name) is not None) is found

    def test_core_partitions_map_ranges_to_the_core_contract(self):
        tables = (_table(),)
        ranges = (_range(1, high="a", rows=4, pages=1), _range(2, low="a"))
        result = _SQLServerPartitionMaintenanceBase._core_partitions(ranges, tables)
        assert len(result) == 2
        assert result[0].name == "logs_1"
        assert result[0].parent == "logs"
        assert result[0].level == 1
        assert result[0].method == "RANGE"
        assert result[0].bound == "..a"
        assert result[0].size_bytes == 8192
        assert result[0].extras["scheme"] == "ps_logs"
        assert result[0].extras["function"] == "pf_logs"
        assert result[1].bound == "a.."
        assert result[1].size_bytes is None

    def test_core_partitions_without_a_table_omit_engine_extras(self):
        result = _SQLServerPartitionMaintenanceBase._core_partitions((_range(),), ())
        assert "scheme" not in result[0].extras
        assert "function" not in result[0].extras
        assert result[0].extras["partition_number"] == 1


class TestPlanning:
    """Pure planning helpers make every decision before any statement runs."""

    def test_ensure_with_missing_function_creates_function_and_scheme(self):
        plan = _plan(scheme="ps_logs", all_filegroup="PRIMARY")
        missing, planned, issues = _base()._plan_ensure(plan, (), (), ())
        assert missing == ()
        assert issues == []
        assert [op.action for op, _ in planned] == ["create_function", "create_scheme"]
        assert "CREATE PARTITION FUNCTION" in planned[0][0].sql

    def test_ensure_without_scheme_creates_only_the_function(self):
        planned = _base()._plan_ensure(_plan(), (), (), ())[1]
        assert [op.action for op, _ in planned] == ["create_function"]

    def test_ensure_splits_only_missing_boundaries_without_a_scheme(self):
        plan = _plan()
        missing, planned, _ = _base()._plan_ensure(plan, (_function(),), (), (True, False))
        assert missing == (date(2026, 2, 1),)
        assert [op.action for op, _ in planned] == ["split"]
        assert "SPLIT RANGE" in planned[0][0].sql

    def test_ensure_emits_next_used_before_each_split(self):
        plan = _plan(scheme="ps_logs", all_filegroup="PRIMARY")
        _, planned, _ = _base()._plan_ensure(plan, (_function(),), (_scheme(),), (True, False))
        assert [op.action for op, _ in planned] == ["next_used", "split"]

    def test_ensure_is_idempotent_when_all_boundaries_exist(self):
        _, planned, issues = _base()._plan_ensure(_plan(), (_function(),), (), (True, True))
        assert planned == []
        assert issues == []

    @pytest.mark.parametrize(
        ("functions", "kwargs", "match"),
        [
            ((_function(direction="LEFT"),), {}, "is RANGE LEFT"),
            ((_function(data_type="int"),), {}, "partitions on int"),
        ],
    )
    def test_ensure_refuses_drift_in_direction_or_type(self, functions, kwargs, match):
        with pytest.raises(ValueError, match=match):
            _base()._plan_ensure(_plan(**kwargs), functions, (), (False, False))

    def test_ensure_refuses_explicit_filegroups_on_a_mismatched_function(self):
        plan = _plan(scheme="ps_logs", filegroups=("fg0", "fg1", "fg2"))
        with pytest.raises(ValueError, match="explicit filegroups"):
            _base()._plan_ensure(plan, (_function(count=7),), (), (False, False))

    def test_ensure_creates_a_missing_scheme_on_an_existing_function(self):
        _, planned, _ = _base()._plan_ensure(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"), (_function(),), (), (True, True)
        )
        assert [op.action for op, _ in planned] == ["create_scheme"]

    def test_ensure_refuses_a_scheme_mapped_to_another_function(self):
        with pytest.raises(ValueError, match="maps function"):
            _base()._plan_ensure(
                _plan(scheme="ps_logs", all_filegroup="PRIMARY"),
                (_function(),),
                (_scheme(function="pf_other"),),
                (False, False),
            )

    def test_ensure_continues_when_the_scheme_has_enough_destinations(self):
        _, planned, issues = _base()._plan_ensure(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"),
            (_function(),),
            (_scheme(filegroups=("fg0", "fg1", "fg2", "fg3")),),
            (True, False),
        )
        assert [op.action for op, _ in planned] == ["next_used", "split"]
        assert not any("destinations" in issue for issue in issues)

    def test_ensure_reports_a_short_scheme_as_an_issue(self):
        _, _, issues = _base()._plan_ensure(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"),
            (_function(),),
            (_scheme(filegroups=("PRIMARY",)),),
            (True, True),
        )
        assert any("1 destinations for 3 partitions" in issue for issue in issues)

    def test_list_without_a_plan_reports_everything(self):
        report = _base()._plan_list(None, (_function(),), (_scheme(),), (_table(),), (_range(),))
        assert report.target == "(all)"
        assert report.function is None
        assert report.issues == ()
        assert len(report.functions) == 1
        assert len(report.partitions) == 1

    def test_list_reports_a_missing_function_and_all_boundaries(self):
        report = _base()._plan_list(_plan(), (), (), (), ())
        assert report.missing_boundaries == (date(2026, 1, 1), date(2026, 2, 1))
        assert report.issues == ("partition function 'pf_logs' does not exist",)

    def test_list_reports_direction_type_count_and_scheme_issues(self):
        plan = _plan(scheme="ps_logs", all_filegroup="PRIMARY")
        report = _base()._plan_list(
            plan,
            (_function(data_type="int", direction="LEFT", count=9),),
            (_scheme(function="pf_other", filegroups=("PRIMARY",)),),
            (),
            (),
            (True, True),
        )
        assert report.existing_boundaries == ("2026-01-01", "2026-02-01")
        assert any("RANGE LEFT" in issue for issue in report.issues)
        assert any("partitions on int" in issue for issue in report.issues)
        assert any("9 partitions" in issue for issue in report.issues)
        assert any("maps 'pf_other'" in issue for issue in report.issues)
        assert any("1 destinations" in issue for issue in report.issues)

    def test_list_has_no_scheme_issue_when_destinations_are_enough(self):
        report = _base()._plan_list(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"),
            (_function(),),
            (_scheme(filegroups=("fg0", "fg1", "fg2", "fg3")),),
            (),
            (),
            (True, True),
        )
        assert not any("destinations" in issue for issue in report.issues)

    def test_list_reports_a_missing_scheme(self):
        report = _base()._plan_list(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"),
            (_function(),),
            (),
            (),
            (),
            (True, True),
        )
        assert any("scheme 'ps_logs' does not exist" in issue for issue in report.issues)

    def test_drop_merges_only_present_boundaries(self):
        planned = _base()._plan_drop(
            _plan(),
            (_function(),),
            (),
            (),
            (date(2026, 1, 1), date(2026, 2, 1)),
            (True, False),
            False,
        )
        assert [op.action for op, _ in planned] == ["merge"]
        assert planned[0][0].name == "2026-01-01"
        assert "MERGE RANGE" in planned[0][0].sql

    def test_drop_is_empty_for_an_unknown_function(self):
        assert _base()._plan_drop(_plan(), (), (), (), (), (), True) == []

    def test_drop_without_scaffolding_stops_after_merges(self):
        planned = _base()._plan_drop(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"),
            (_function(),),
            (_scheme(),),
            (),
            (),
            (),
            False,
        )
        assert all(op.action == "merge" for op, _ in planned)

    def test_drop_removes_unused_scheme_then_function(self):
        planned = _base()._plan_drop(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"),
            (_function(),),
            (_scheme(),),
            (),
            (),
            (),
            True,
        )
        assert [op.action for op, _ in planned] == ["drop_scheme", "drop_function"]
        assert planned[0][0].sql == "DROP PARTITION SCHEME [ps_logs]"
        assert planned[1][0].sql == "DROP PARTITION FUNCTION [pf_logs]"

    def test_drop_keeps_the_function_when_a_table_uses_the_scheme(self):
        planned = _base()._plan_drop(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"),
            (_function(),),
            (_scheme(),),
            (_table(),),
            (),
            (),
            True,
        )
        assert [op.action for op, _ in planned] == []

    def test_drop_keeps_the_function_when_another_scheme_remains(self):
        schemes = (_scheme("ps_one"), _scheme("ps_two"))
        planned = _base()._plan_drop(
            _plan(), (_function(),), schemes, (_table(scheme="ps_two"),), (), (), True
        )
        assert [op.action for op, _ in planned] == ["drop_scheme"]
        assert planned[0][0].name == "ps_one"

    def test_report_carries_operations_and_dry_run(self):
        op = PartitionOperation(action="split", name="x", sql="SQL")
        report = _SQLServerPartitionMaintenanceBase._report(
            _plan(), (), (), (), (), (), (), (), [(op, ("p",))], True
        )
        assert report.target == "pf_logs"
        assert report.operations == (op,)
        assert report.dry_run is True

    def test_validate_adds_table_level_findings(self):
        report = _base()._plan_list(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"),
            (_function(),),
            (_scheme(),),
            (_table(scheme="ps_other", function="pf_other", count=9),),
            (_range(1), _range(3)),
            (True, True),
        )
        issues = _base()._plan_validate(
            report, _plan(scheme="ps_logs", all_filegroup="PRIMARY"), "logs"
        )
        assert any("built on 'ps_other'" in issue for issue in issues)
        assert any("uses function 'pf_other'" in issue for issue in issues)
        assert any("9 partitions" in issue for issue in issues)
        assert any("partitions are [1, 3]" in issue for issue in issues)

    def test_validate_a_consistent_table_adds_nothing(self):
        plan = _plan(scheme="ps_logs", all_filegroup="PRIMARY")
        report = _base()._plan_list(
            plan,
            (_function(),),
            (_scheme(filegroups=("fg0", "fg1", "fg2", "fg3")),),
            (_table(),),
            (_range(1), _range(2), _range(3)),
            (True, True),
        )
        assert _base()._plan_validate(report, plan, "logs") == ()

    def test_validate_reports_a_missing_table(self):
        report = _base()._plan_list(_plan(), (_function(),), (), (), (), (True, True))
        issues = _base()._plan_validate(report, _plan(), "absent")
        assert any("is not partitioned or does not exist" in issue for issue in issues)

    def test_validate_without_a_table_adds_nothing(self):
        report = _base()._plan_list(_plan(), (_function(),), (), (), (), (True, True))
        assert _base()._plan_validate(report, _plan(), None) == report.issues


class TestRunnerAndGates:
    """Execution stops at the first error; capability gates are explicit."""

    def _planned(self):
        op1 = PartitionOperation(action="first", name="a", sql="SQL1")
        op2 = PartitionOperation(action="second", name="b", sql="SQL2")
        return [(op1, ()), (op2, ())]

    def test_dry_run_executes_nothing(self):
        maintenance = SQLServerPartitionMaintenance(_backend())
        maintenance._execute = MagicMock()
        assert maintenance._run(self._planned(), True) == ((), 0)
        maintenance._execute.assert_not_called()

    def test_real_run_executes_every_statement(self):
        maintenance = SQLServerPartitionMaintenance(_backend())
        maintenance._execute = MagicMock()
        assert maintenance._run(self._planned(), False) == ((), 2)
        assert maintenance._execute.call_count == 2

    def test_first_error_stops_later_statements(self):
        maintenance = SQLServerPartitionMaintenance(_backend())
        maintenance._execute = MagicMock(side_effect=[None, DatabaseError("boom")])
        errors, completed = maintenance._run(self._planned(), False)
        assert completed == 1
        assert errors == ("second 'b' failed: boom",)

    @pytest.mark.parametrize(
        ("flag", "value", "match"),
        [
            ("supports_table_partitioning", False, "table partitioning"),
            ("supports_partition_function", False, "partition functions"),
            ("supports_partition_scheme", False, "partition schemes"),
            ("supports_subpartitioning", True, "subpartitioning"),
            ("supports_split_partition", False, "SPLIT RANGE"),
        ],
    )
    def test_require_support_refuses_when_a_gate_fails(self, flag, value, match):
        base = _base(dialect=_gate_dialect(**{flag: value}))
        with pytest.raises(UnsupportedFeatureError, match=match):
            base._require_support(_plan(scheme="ps_logs", all_filegroup="PRIMARY"))

    def test_require_support_accepts_a_capable_dialect(self):
        _base(dialect=_gate_dialect())._require_support(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY")
        )

    @pytest.mark.parametrize(
        ("flag", "value", "match"),
        [
            ("supports_table_partitioning", False, "table partitioning"),
            ("supports_merge_partition", False, "MERGE RANGE"),
            ("supports_subpartitioning", True, "subpartitioning"),
        ],
    )
    def test_require_merge_refuses_when_a_gate_fails(self, flag, value, match):
        base = _base(dialect=_gate_dialect(**{flag: value}))
        with pytest.raises(UnsupportedFeatureError, match=match):
            base._require_merge()

    def test_require_merge_accepts_a_capable_dialect(self):
        _base(dialect=_gate_dialect())._require_merge()


class TestSyncSeams:
    """The real sync I/O seams issue catalogue questions through backend.execute."""

    def test_fetch_rows_returns_data_or_empty(self):
        backend = _backend(execute=MagicMock(return_value=SimpleNamespace(data=[{"x": 1}])))
        statement = MagicMock()
        statement.to_sql.return_value = ("SELECT 1", ())
        assert SQLServerPartitionMaintenance(backend)._fetch_rows(statement) == [{"x": 1}]
        backend.execute.assert_called_once_with("SELECT 1", ())

    def test_fetch_rows_tolerates_null_data(self):
        backend = _backend(execute=MagicMock(return_value=SimpleNamespace(data=None)))
        statement = MagicMock()
        statement.to_sql.return_value = ("SELECT 1", ())
        assert SQLServerPartitionMaintenance(backend)._fetch_rows(statement) == []

    def test_read_functions_uses_the_catalogue_statement(self):
        backend = _backend(
            execute=MagicMock(
                return_value=SimpleNamespace(
                    data=[
                        {"function_name": "pf", "data_type": "date", "boundary_value_on_right": 1}
                    ]
                )
            )
        )
        result = SQLServerPartitionMaintenance(backend)._read_functions("pf")
        assert result[0].name == "pf"
        sql, _ = backend.execute.call_args.args
        assert "sys.partition_functions" in sql

    def test_read_schemes_uses_the_catalogue_statement(self):
        backend = _backend(
            execute=MagicMock(
                return_value=SimpleNamespace(
                    data=[{"scheme_name": "ps", "function_name": "pf", "filegroup_name": "PRIMARY"}]
                )
            )
        )
        result = SQLServerPartitionMaintenance(backend)._read_schemes("ps", "pf")
        assert result[0].filegroups == ("PRIMARY",)
        assert "sys.partition_schemes" in backend.execute.call_args.args[0]

    def test_read_tables_uses_the_catalogue_statement(self):
        backend = _backend(
            execute=MagicMock(
                return_value=SimpleNamespace(
                    data=[{"table_name": "logs", "schema_name": "dbo", "scheme_name": "ps"}]
                )
            )
        )
        result = SQLServerPartitionMaintenance(backend)._read_tables("logs", "dbo")
        assert result[0].name == "logs"
        assert "sys.tables" in backend.execute.call_args.args[0]

    def test_read_ranges_uses_the_catalogue_statement(self):
        backend = _backend(
            execute=MagicMock(
                return_value=SimpleNamespace(
                    data=[{"table_name": "logs", "partition_number": 1, "used_page_count": 2}]
                )
            )
        )
        result = SQLServerPartitionMaintenance(backend)._read_ranges("logs", "dbo")
        assert result[0].data_bytes == 2 * 8192
        assert "boundary_text" in backend.execute.call_args.args[0]

    def test_read_boundary_exists_checks_each_boundary(self):
        backend = _backend(
            execute=MagicMock(
                side_effect=[
                    SimpleNamespace(data=[{"boundary_exists": 1}]),
                    SimpleNamespace(data=[{"boundary_exists": 0}]),
                    SimpleNamespace(data=[]),
                ]
            )
        )
        plan = _plan(boundaries=(date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)))
        assert SQLServerPartitionMaintenance(backend)._read_boundary_exists(plan) == (
            True,
            False,
            False,
        )
        assert backend.execute.call_count == 3

    def test_read_boundary_exists_for_checks_the_requested_boundaries(self):
        backend = _backend(
            execute=MagicMock(return_value=SimpleNamespace(data=[{"boundary_exists": 1}]))
        )
        result = SQLServerPartitionMaintenance(backend)._read_boundary_exists_for(
            _plan(), (date(2026, 1, 1),)
        )
        assert result == (True,)
        sql, params = backend.execute.call_args.args
        assert "CAST" in sql
        assert date(2026, 1, 1).isoformat() in params

    def test_execute_delegates_to_the_backend(self):
        backend = _backend(execute=MagicMock())
        SQLServerPartitionMaintenance(backend)._execute("DDL", (1,))
        backend.execute.assert_called_once_with("DDL", (1,))


class TestSyncPublicMethods:
    """Public methods behave the same with MagicMock seams as with fake ones."""

    def _maintenance(self, **kwargs):
        maintenance = SQLServerPartitionMaintenance(_backend())
        maintenance._read_functions = MagicMock(return_value=kwargs.get("functions", ()))
        maintenance._read_schemes = MagicMock(return_value=kwargs.get("schemes", ()))
        maintenance._read_tables = MagicMock(return_value=kwargs.get("tables", ()))
        maintenance._read_ranges = MagicMock(return_value=kwargs.get("ranges", ()))
        maintenance._read_boundary_exists = MagicMock(return_value=kwargs.get("exists", ()))
        maintenance._read_boundary_exists_for = MagicMock(return_value=kwargs.get("exists", ()))
        maintenance._execute = MagicMock()
        return maintenance

    def test_ensure_dry_run_plans_the_function(self):
        maintenance = self._maintenance()
        report = maintenance.ensure(_plan(), dry_run=True)
        assert [op.action for op in report.operations] == ["create_function"]
        maintenance._execute.assert_not_called()

    def test_ensure_real_run_reports_the_post_state(self):
        maintenance = self._maintenance()
        report = maintenance.ensure(_plan(), dry_run=False)
        assert report.dry_run is False
        assert [op.action for op in report.operations] == ["create_function"]
        maintenance._execute.assert_called_once()

    def test_retention_boundaries_from_function(self):
        maintenance = self._maintenance(functions=(_function(),))
        assert maintenance.retention_boundaries(_plan(), date(2026, 1, 15)) == (date(2026, 1, 1),)

    def test_retention_boundaries_from_table_ranges(self):
        maintenance = self._maintenance(
            ranges=(_range(1, high="2026-01-01"), _range(2, high="2026-02-01"))
        )
        assert maintenance.retention_boundaries(_plan(), date(2026, 1, 15), table="logs") == (
            date(2026, 1, 1),
        )

    def test_retention_boundaries_with_no_catalogue_is_empty(self):
        assert self._maintenance().retention_boundaries(_plan(), date(2026, 1, 15)) == ()

    def test_drop_before_defaults_to_a_dry_run(self):
        maintenance = self._maintenance(functions=(_function(),), exists=(True, False))
        report = maintenance.drop_before(_plan(), date(2026, 1, 15))
        assert report.dry_run is True
        assert [op.action for op in report.operations] == ["merge"]
        maintenance._execute.assert_not_called()

    def test_drop_or_merge_real_run_executes(self):
        maintenance = self._maintenance(functions=(_function(),), exists=(True, False))
        report = maintenance.drop_or_merge(_plan(), (date(2026, 1, 1),), dry_run=False)
        assert report.dry_run is False
        assert [op.action for op in report.operations] == ["merge"]
        maintenance._execute.assert_called_once()

    def test_validate_uses_the_mocked_seams(self):
        maintenance = self._maintenance(functions=(_function(),))
        report = maintenance.validate(_plan(), table="logs")
        assert any("does not exist" in issue for issue in report.issues)

    def test_drop_or_merge_reports_a_missing_function(self):
        maintenance = self._maintenance()
        report = maintenance.drop_or_merge(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"),
            (),
            dry_run=True,
            drop_scaffolding=True,
        )
        assert any("does not exist" in issue for issue in report.issues)
        assert report.operations == ()

    def test_drop_or_merge_reports_a_scheme_used_by_a_table(self):
        maintenance = self._maintenance(
            functions=(_function(),), schemes=(_scheme(),), tables=(_table(),)
        )
        report = maintenance.drop_or_merge(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"),
            (),
            dry_run=True,
            drop_scaffolding=True,
        )
        assert any("used by 1 table" in issue for issue in report.issues)
        assert any("still mapped by scheme" in issue for issue in report.issues)

    def test_drop_or_merge_ignores_unrelated_schemes(self):
        maintenance = self._maintenance(
            functions=(_function(),),
            schemes=(_scheme("ps_other", function="pf_other"), _scheme("ps_another")),
        )
        report = maintenance.drop_or_merge(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"),
            (),
            dry_run=True,
            drop_scaffolding=True,
        )
        assert report.operations == ()
        assert not any("used by" in issue for issue in report.issues)


class TestAsyncSeams:
    """The native async seams await the backend's AsyncMock execute."""

    async def test_fetch_rows_returns_data_or_empty(self):
        backend = _backend(execute=AsyncMock(return_value=SimpleNamespace(data=[{"x": 1}])))
        statement = MagicMock()
        statement.to_sql.return_value = ("SELECT 1", ())
        maintenance = AsyncSQLServerPartitionMaintenance(backend)
        assert await maintenance._fetch_rows(statement) == [{"x": 1}]
        backend.execute.assert_awaited_once_with("SELECT 1", ())

    async def test_read_functions(self):
        backend = _backend(
            execute=AsyncMock(
                return_value=SimpleNamespace(
                    data=[{"function_name": "pf", "data_type": "int", "boundary_value_on_right": 1}]
                )
            )
        )
        result = await AsyncSQLServerPartitionMaintenance(backend)._read_functions("pf")
        assert result[0].range_direction == "RIGHT"

    async def test_read_schemes(self):
        backend = _backend(
            execute=AsyncMock(
                return_value=SimpleNamespace(
                    data=[{"scheme_name": "ps", "function_name": "pf", "filegroup_name": "fg1"}]
                )
            )
        )
        result = await AsyncSQLServerPartitionMaintenance(backend)._read_schemes()
        assert result[0].filegroups == ("fg1",)

    async def test_read_tables(self):
        backend = _backend(
            execute=AsyncMock(
                return_value=SimpleNamespace(
                    data=[{"table_name": "logs", "schema_name": "dbo", "scheme_name": "ps"}]
                )
            )
        )
        result = await AsyncSQLServerPartitionMaintenance(backend)._read_tables("logs")
        assert result[0].scheme == "ps"

    async def test_read_ranges(self):
        backend = _backend(
            execute=AsyncMock(
                return_value=SimpleNamespace(
                    data=[{"table_name": "logs", "partition_number": "1", "used_page_count": "4"}]
                )
            )
        )
        result = await AsyncSQLServerPartitionMaintenance(backend)._read_ranges("logs")
        assert result[0].data_bytes == 4 * 8192

    async def test_read_boundary_exists(self):
        backend = _backend(
            execute=AsyncMock(
                side_effect=[
                    SimpleNamespace(data=[{"boundary_exists": 1}]),
                    SimpleNamespace(data=[]),
                ]
            )
        )
        plan = _plan(boundaries=(date(2026, 1, 1), date(2026, 2, 1)))
        assert await AsyncSQLServerPartitionMaintenance(backend)._read_boundary_exists(plan) == (
            True,
            False,
        )

    async def test_read_boundary_exists_for(self):
        backend = _backend(
            execute=AsyncMock(return_value=SimpleNamespace(data=[{"boundary_exists": 1}]))
        )
        result = await AsyncSQLServerPartitionMaintenance(backend)._read_boundary_exists_for(
            _plan(), (10,)
        )
        assert result == (True,)

    async def test_execute_delegates_to_the_backend(self):
        backend = _backend(execute=AsyncMock())
        await AsyncSQLServerPartitionMaintenance(backend)._execute("DDL", ())
        backend.execute.assert_awaited_once_with("DDL", ())

    async def test_async_run_stops_at_the_first_error(self):
        maintenance = AsyncSQLServerPartitionMaintenance(_backend())
        first = PartitionOperation(action="first", name="a", sql="SQL1")
        second = PartitionOperation(action="second", name="b", sql="SQL2")
        maintenance._execute = AsyncMock(side_effect=[None, DatabaseError("boom")])
        errors, completed = await maintenance._run([(first, ()), (second, ())], False)
        assert completed == 1
        assert errors == ("second 'b' failed: boom",)

    async def test_async_run_dry_run_is_a_no_op(self):
        maintenance = AsyncSQLServerPartitionMaintenance(_backend())
        maintenance._execute = AsyncMock()
        op = PartitionOperation(action="first", name="a", sql="SQL1")
        assert await maintenance._run([(op, ())], True) == ((), 0)
        maintenance._execute.assert_not_awaited()


class TestAsyncPublicMethods:
    """The async public surface mirrors the sync one with AsyncMock seams."""

    def _maintenance(self, **kwargs):
        maintenance = AsyncSQLServerPartitionMaintenance(_backend())
        maintenance._read_functions = AsyncMock(return_value=kwargs.get("functions", ()))
        maintenance._read_schemes = AsyncMock(return_value=kwargs.get("schemes", ()))
        maintenance._read_tables = AsyncMock(return_value=kwargs.get("tables", ()))
        maintenance._read_ranges = AsyncMock(return_value=kwargs.get("ranges", ()))
        maintenance._read_boundary_exists = AsyncMock(return_value=kwargs.get("exists", ()))
        maintenance._read_boundary_exists_for = AsyncMock(return_value=kwargs.get("exists", ()))
        maintenance._execute = AsyncMock()
        return maintenance

    async def test_ensure_dry_run(self):
        maintenance = self._maintenance()
        report = await maintenance.ensure(_plan(), dry_run=True)
        assert [op.action for op in report.operations] == ["create_function"]
        maintenance._execute.assert_not_awaited()

    async def test_ensure_real_run(self):
        maintenance = self._maintenance()
        report = await maintenance.ensure(_plan(), dry_run=False)
        assert report.dry_run is False
        maintenance._execute.assert_awaited_once()

    async def test_list_without_a_plan(self):
        report = await self._maintenance().list()
        assert report.target == "(all)"
        assert report.issues == ()

    async def test_retention_boundaries(self):
        maintenance = self._maintenance(functions=(_function(),))
        assert await maintenance.retention_boundaries(_plan(), date(2026, 1, 15)) == (
            date(2026, 1, 1),
        )

    async def test_retention_boundaries_from_table(self):
        maintenance = self._maintenance(ranges=(_range(high="2026-01-01"),))
        assert await maintenance.retention_boundaries(_plan(), date(2026, 1, 15), table="logs") == (
            date(2026, 1, 1),
        )

    async def test_retention_boundaries_without_a_catalogue_is_empty(self):
        assert await self._maintenance().retention_boundaries(_plan(), date(2026, 1, 15)) == ()

    async def test_drop_before(self):
        maintenance = self._maintenance(functions=(_function(),), exists=(True, False))
        report = await maintenance.drop_before(_plan(), date(2026, 1, 15))
        assert report.dry_run is True
        assert [op.action for op in report.operations] == ["merge"]

    async def test_drop_or_merge_real_run(self):
        maintenance = self._maintenance(functions=(_function(),), exists=(True, False))
        report = await maintenance.drop_or_merge(_plan(), (date(2026, 1, 1),), dry_run=False)
        assert [op.action for op in report.operations] == ["merge"]
        maintenance._execute.assert_awaited_once()

    async def test_validate(self):
        maintenance = self._maintenance(functions=(_function(),))
        report = await maintenance.validate(_plan())
        assert report.issues == ()

    async def test_drop_or_merge_reports_a_missing_function(self):
        maintenance = self._maintenance()
        report = await maintenance.drop_or_merge(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"),
            (),
            dry_run=True,
            drop_scaffolding=True,
        )
        assert any("does not exist" in issue for issue in report.issues)
        assert report.operations == ()

    async def test_drop_or_merge_reports_scaffolding_issues(self):
        maintenance = self._maintenance(
            functions=(_function(),), schemes=(_scheme(),), tables=(_table(),)
        )
        report = await maintenance.drop_or_merge(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"),
            (),
            dry_run=True,
            drop_scaffolding=True,
        )
        assert any("used by 1 table" in issue for issue in report.issues)
        assert any("still mapped by scheme" in issue for issue in report.issues)

    async def test_drop_or_merge_ignores_unrelated_schemes(self):
        maintenance = self._maintenance(
            functions=(_function(),),
            schemes=(_scheme("ps_other", function="pf_other"), _scheme("ps_another")),
        )
        report = await maintenance.drop_or_merge(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"),
            (),
            dry_run=True,
            drop_scaffolding=True,
        )
        assert report.operations == ()
        assert not any("used by" in issue for issue in report.issues)


class TestPlanBoundaryTokens:
    """Plan boundary tokens are only for spotting duplicates inside one plan."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (True, ("bool", "1")),
            (False, ("bool", "0")),
            (7, ("int", "7")),
            (1.5, ("number", "1.500000")),
            (Decimal("2.50"), ("number", "2.50")),
            (datetime(2026, 1, 2, 3, 4), ("datetime", "2026-01-02 03:04:00")),
            (date(2026, 1, 2), ("date", "2026-01-02")),
            (time(3, 4), ("time", "03:04:00")),
            ("abc", ("str", "abc")),
        ],
    )
    def test_token(self, value, expected):
        assert _boundary_token(value) == expected

    def test_unsupported_value_is_refused(self):
        with pytest.raises(ValueError, match="unsupported partition boundary"):
            _boundary_token(object())

    def test_bool_and_int_one_produce_distinct_tokens(self):
        assert _boundary_token(True) != _boundary_token(1)

    def test_direction_is_normalised_from_a_lowercase_word(self):
        assert _plan(range_direction="left").range_direction.value == "LEFT"

    def test_incomparable_boundaries_are_refused(self):
        with pytest.raises(ValueError, match="mutually comparable"):
            _plan(boundaries=(1, "two"))

    def test_filegroups_require_a_scheme(self):
        with pytest.raises(ValueError, match="require a scheme"):
            _plan(filegroups=("fg1",))

    def test_next_filegroup_must_be_one_of_the_filegroups(self):
        with pytest.raises(ValueError, match="not one of the plan's filegroups"):
            _plan(scheme="ps", filegroups=("fg0", "fg1", "fg2"), next_filegroup="fgX")

    def test_next_filegroup_must_equal_all_filegroup(self):
        with pytest.raises(ValueError, match="must equal all_filegroup"):
            _plan(scheme="ps", all_filegroup="PRIMARY", next_filegroup="fgX")

    def test_empty_function_name_is_refused(self):
        with pytest.raises(ValueError, match="non-empty string"):
            _plan(function="  ")

    def test_blank_scheme_name_is_refused(self):
        with pytest.raises(ValueError, match="non-empty string"):
            _plan(scheme="  ", all_filegroup="PRIMARY")

    def test_a_scheme_needs_a_destination(self):
        with pytest.raises(ValueError, match="needs either explicit filegroups"):
            _plan(scheme="ps_logs")
