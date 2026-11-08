# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_sqlserver_partition_maintenance.py
"""Unit tests for SQL Server partition planning and maintenance.

These run without a server: a fake maintenance object answers the catalogue
questions from canned rows and records the statements the real executor would
run. The catalogue SQL itself is asserted in
``test_sqlserver_partition.py``; this file is about decisions -- which
boundaries are missing, what a dry run would do, and why a drop is refused.
"""

import asyncio
from datetime import date, datetime

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.errors import DatabaseError
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.partition import (
    AsyncPartitionEnsurer,
    AsyncPartitionInventory,
    AsyncPartitionRetention,
    AsyncPartitionValidator,
    PartitionEnsurer,
    PartitionInventory,
    PartitionReport as CorePartitionReport,
    PartitionRetention,
    PartitionValidator,
)
from rhosocial.activerecord.backend.impl.sqlserver.partition import (
    AsyncSQLServerPartitionMaintenance,
    PartitionFunctionInfo,
    PartitionRangeInfo,
    PartitionReport,
    PartitionSchemeInfo,
    PartitionTableInfo,
    SQLServerPartitionMaintenance,
    SQLServerPartitionPlan,
)

DIALECT = SQLServerDialect((16, 0, 0))
OLD_DIALECT = SQLServerDialect((9, 0, 0))


def _plan(boundaries=(date(2026, 1, 1), date(2026, 2, 1)), **kwargs):
    return SQLServerPartitionPlan(
        function=kwargs.pop("function", "pf_logs"),
        data_type=kwargs.pop("data_type", "DATE"),
        boundaries=boundaries,
        **kwargs,
    )


class FakeMaintenance(SQLServerPartitionMaintenance):
    """A maintenance executor whose catalogue answers are supplied up front."""

    def __init__(
        self,
        *,
        dialect=DIALECT,
        functions=(),
        schemes=(),
        tables=(),
        ranges=(),
        exists=None,
    ):
        self.dialect = dialect
        self.functions = tuple(functions)
        self.schemes = tuple(schemes)
        self.tables = tuple(tables)
        self.ranges = tuple(ranges)
        self.exists = dict(exists or {})
        self.executed = []

    def _read_functions(self, function_name=None):
        return tuple(f for f in self.functions if function_name in (None, f.name))

    def _read_schemes(self, scheme_name=None, function_name=None):
        return tuple(
            s
            for s in self.schemes
            if scheme_name in (None, s.name)
            and function_name in (None, s.function)
        )

    def _read_tables(self, table_name=None, schema=None, scheme_name=None):
        return tuple(
            t
            for t in self.tables
            if table_name in (None, t.name)
            and schema in (None, t.schema)
            and scheme_name in (None, t.scheme)
        )

    def _read_ranges(self, table_name, schema=None):
        return tuple(r for r in self.ranges if r.table == table_name)

    def _read_boundary_exists(self, plan):
        return tuple(self.exists.get(boundary, False) for boundary in plan.boundaries)

    def _read_boundary_exists_for(self, plan, boundaries):
        return tuple(self.exists.get(boundary, False) for boundary in boundaries)

    def _execute(self, sql, params):
        self.executed.append(sql)


class FakeAsyncMaintenance(AsyncSQLServerPartitionMaintenance):
    """The async executor with the same canned answers as the sync fake."""

    def __init__(self, **kwargs):
        self.sync = FakeMaintenance(**kwargs)
        self.dialect = self.sync.dialect
        self.executed = self.sync.executed

    async def _read_functions(self, function_name=None):
        return self.sync._read_functions(function_name)

    async def _read_schemes(self, scheme_name=None, function_name=None):
        return self.sync._read_schemes(scheme_name, function_name)

    async def _read_tables(self, table_name=None, schema=None, scheme_name=None):
        return self.sync._read_tables(table_name, schema, scheme_name)

    async def _read_ranges(self, table_name, schema=None):
        return self.sync._read_ranges(table_name, schema)

    async def _read_boundary_exists(self, plan):
        return self.sync._read_boundary_exists(plan)

    async def _read_boundary_exists_for(self, plan, boundaries):
        return self.sync._read_boundary_exists_for(plan, boundaries)

    async def _execute(self, sql, params):
        self.sync._execute(sql, params)


class ScriptedMaintenance(FakeMaintenance):
    """A fake executor that can fail or mutate its catalogue on a statement."""

    def __init__(self, *, fail_at=None, on_execute=None, **kwargs):
        super().__init__(**kwargs)
        self.fail_at = fail_at
        self.on_execute = on_execute
        self.attempts = 0

    def _execute(self, sql, params):
        if self.fail_at is not None and self.attempts == self.fail_at:
            self.attempts += 1
            raise DatabaseError("scripted failure")
        self.attempts += 1
        super()._execute(sql, params)
        if self.on_execute is not None:
            self.on_execute(self, sql, params)


class ScriptedAsyncMaintenance(FakeAsyncMaintenance):
    """The async executor over a scripted sync fake."""

    def __init__(self, sync):
        self.sync = sync
        self.dialect = sync.dialect
        self.executed = sync.executed


def _function_info(
    boundaries=("2026-01-01", "2026-02-01", "2026-03-01"),
    *,
    data_type="date",
):
    return [
        PartitionFunctionInfo(
            name="pf_logs",
            data_type=data_type,
            range_direction="RIGHT",
            boundary_values=tuple(boundaries),
            partition_count=len(boundaries) + 1,
        )
    ]


class TestSQLServerPartitionPlan:
    """Plan normalisation and explicit refusals."""

    def test_boundaries_are_sorted_and_counted(self):
        plan = _plan(boundaries=(date(2026, 2, 1), date(2026, 1, 1)))
        assert plan.boundaries == (date(2026, 1, 1), date(2026, 2, 1))
        assert plan.partition_count == 3

    def test_duplicate_boundaries_are_refused(self):
        with pytest.raises(ValueError, match="unique"):
            _plan(boundaries=(date(2026, 1, 1), date(2026, 1, 1)))

    def test_empty_boundaries_are_refused(self):
        with pytest.raises(ValueError, match="at least one"):
            _plan(boundaries=())

    def test_scheme_requires_one_destination_per_partition(self):
        with pytest.raises(ValueError, match="filegroups cannot serve"):
            _plan(scheme="ps_logs", filegroups=("PRIMARY", "fg1"))

    def test_all_filegroup_and_explicit_filegroups_are_exclusive(self):
        with pytest.raises(ValueError, match="mutually exclusive"):
            _plan(
                scheme="ps_logs",
                filegroups=("PRIMARY", "fg1", "fg2"),
                all_filegroup="PRIMARY",
            )

    def test_next_filegroup_defaults_to_the_last_explicit_destination(self):
        plan = _plan(
            scheme="ps_logs",
            filegroups=("PRIMARY", "fg1", "fg2"),
        )
        assert plan.next_filegroup == "fg2"

    def test_next_filegroup_defaults_to_all_filegroup(self):
        plan = _plan(scheme="ps_logs", all_filegroup="PRIMARY")
        assert plan.next_filegroup == "PRIMARY"

    def test_non_range_strategy_is_refused(self):
        with pytest.raises(UnsupportedFeatureError, match="HASH"):
            _plan(strategy="HASH")

    def test_subpartitioning_is_refused(self):
        with pytest.raises(UnsupportedFeatureError, match="subpartitioning"):
            _plan(subpartition_by="HASH")

    def test_invalid_data_type_is_refused(self):
        with pytest.raises(ValueError, match="invalid partition-function data type"):
            _plan(data_type="DATE; DROP TABLE x")

    def test_capability_gate_refuses_an_unsupported_version(self):
        maintenance = FakeMaintenance(dialect=OLD_DIALECT)
        with pytest.raises(UnsupportedFeatureError, match="table partitioning"):
            maintenance.ensure(_plan())


class TestSQLServerPartitionCatalogueParsing:
    """Rows as the catalogue returns them become the report's value objects."""

    def test_functions_are_grouped_by_boundary(self):
        functions = FakeMaintenance._parse_functions(
            [
                {
                    "function_name": "pf",
                    "data_type": "date",
                    "boundary_value_on_right": 1,
                    "partition_count": 3,
                    "boundary_id": 1,
                    "boundary_value": "2026-01-01",
                },
                {
                    "function_name": "pf",
                    "data_type": "date",
                    "boundary_value_on_right": 1,
                    "partition_count": 3,
                    "boundary_id": 2,
                    "boundary_value": "2026-02-01",
                },
            ]
        )
        assert len(functions) == 1
        info = functions[0]
        assert info.name == "pf"
        assert info.range_direction == "RIGHT"
        assert info.boundary_values == ("2026-01-01", "2026-02-01")
        assert info.partition_count == 3

    def test_schemes_keep_destination_order(self):
        schemes = FakeMaintenance._parse_schemes(
            [
                {
                    "scheme_name": "ps",
                    "function_name": "pf",
                    "partition_count": 3,
                    "destination_id": 2,
                    "filegroup_name": "fg1",
                },
                {
                    "scheme_name": "ps",
                    "function_name": "pf",
                    "partition_count": 3,
                    "destination_id": 1,
                    "filegroup_name": "PRIMARY",
                },
            ]
        )
        assert len(schemes) == 1
        assert schemes[0].filegroups == ("fg1", "PRIMARY")
        assert schemes[0].destination_count == 2

    def test_tables_and_ranges_are_parsed(self):
        tables = FakeMaintenance._parse_tables(
            [
                {
                    "table_name": "logs",
                    "schema_name": "dbo",
                    "scheme_name": "ps",
                    "function_name": "pf",
                    "partition_column": "created_at",
                    "partition_count": 3,
                }
            ]
        )
        assert tables[0].partition_column == "created_at"

        ranges = FakeMaintenance._parse_ranges(
            [
                {
                    "table_name": "logs",
                    "schema_name": "dbo",
                    "partition_number": 2,
                    "row_count": 10,
                    "used_page_count": 2,
                    "low_boundary": "2026-01-01",
                    "high_boundary": "2026-02-01",
                }
            ]
        )
        assert ranges[0].data_bytes == 2 * 8192
        assert ranges[0].low_boundary == "2026-01-01"


class TestSQLServerPartitionEnsure:
    """``ensure`` creates, splits and reports without touching what exists."""

    def test_missing_function_is_created_with_its_scheme(self):
        maintenance = FakeMaintenance()
        report = maintenance.ensure(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"), dry_run=True
        )
        assert [op.action for op in report.operations] == [
            "create_function",
            "create_scheme",
        ]
        assert report.operations[0].sql == (
            "CREATE PARTITION FUNCTION [pf_logs] (DATE) AS RANGE RIGHT "
            "FOR VALUES ('2026-01-01', '2026-02-01')"
        )
        assert report.operations[1].sql == (
            "CREATE PARTITION SCHEME [ps_logs] AS PARTITION [pf_logs] "
            "ALL TO ([PRIMARY])"
        )
        assert maintenance.executed == []
        assert report.dry_run is True

    def test_real_ensure_executes_the_planned_statements(self):
        maintenance = FakeMaintenance()
        maintenance.ensure(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"), dry_run=False
        )
        assert len(maintenance.executed) == 2

    def test_existing_function_splits_only_missing_boundaries(self):
        maintenance = FakeMaintenance(
            functions=[
                PartitionFunctionInfo(
                    name="pf_logs",
                    data_type="date",
                    range_direction="RIGHT",
                    boundary_values=("2026-01-01",),
                    partition_count=2,
                )
            ],
            schemes=[
                PartitionSchemeInfo(
                    name="ps_logs", function="pf_logs", filegroups=("PRIMARY",)
                )
            ],
            exists={date(2026, 1, 1): True, date(2026, 2, 1): False},
        )
        report = maintenance.ensure(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"), dry_run=True
        )
        assert report.missing_boundaries == (date(2026, 2, 1),)
        assert [op.action for op in report.operations] == ["next_used", "split"]
        assert report.operations[0].sql == (
            "ALTER PARTITION SCHEME [ps_logs] NEXT USED [PRIMARY]"
        )
        assert report.operations[1].sql == (
            "ALTER PARTITION FUNCTION [pf_logs] () SPLIT RANGE ('2026-02-01')"
        )

    def test_idempotent_ensure_plans_nothing(self):
        maintenance = FakeMaintenance(
            functions=[
                PartitionFunctionInfo(
                    name="pf_logs",
                    data_type="date",
                    range_direction="RIGHT",
                    boundary_values=("2026-01-01", "2026-02-01"),
                    partition_count=3,
                )
            ],
            schemes=[
                PartitionSchemeInfo(
                    name="ps_logs", function="pf_logs", filegroups=("PRIMARY",)
                )
            ],
            exists={date(2026, 1, 1): True, date(2026, 2, 1): True},
        )
        report = maintenance.ensure(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"), dry_run=True
        )
        assert report.operations == ()

    def test_direction_mismatch_is_refused_rather_than_repaired(self):
        maintenance = FakeMaintenance(
            functions=[
                PartitionFunctionInfo(
                    name="pf_logs",
                    data_type="date",
                    range_direction="RIGHT",
                    boundary_values=(),
                    partition_count=1,
                )
            ]
        )
        with pytest.raises(ValueError, match="is RANGE RIGHT"):
            maintenance.ensure(
                _plan(range_direction="LEFT"), dry_run=True
            )

    def test_explicit_filegroups_need_the_function_to_match_already(self):
        maintenance = FakeMaintenance(
            functions=[
                PartitionFunctionInfo(
                    name="pf_logs",
                    data_type="date",
                    range_direction="RIGHT",
                    boundary_values=("2026-01-01",),
                    partition_count=2,
                )
            ],
            exists={date(2026, 1, 1): True, date(2026, 2, 1): False},
        )
        with pytest.raises(ValueError, match="explicit filegroups"):
            maintenance.ensure(
                _plan(
                    scheme="ps_logs",
                    filegroups=("PRIMARY", "fg1", "fg2"),
                ),
                dry_run=True,
            )

    def test_async_ensure_matches_the_sync_plan(self):
        kwargs = dict(
            functions=[
                PartitionFunctionInfo(
                    name="pf_logs",
                    data_type="date",
                    range_direction="RIGHT",
                    boundary_values=("2026-01-01",),
                    partition_count=2,
                )
            ],
            schemes=[
                PartitionSchemeInfo(
                    name="ps_logs", function="pf_logs", filegroups=("PRIMARY",)
                )
            ],
            exists={date(2026, 1, 1): True, date(2026, 2, 1): False},
        )
        plan = _plan(scheme="ps_logs", all_filegroup="PRIMARY")
        sync_report = FakeMaintenance(**kwargs).ensure(plan, dry_run=True)
        async_maintenance = FakeAsyncMaintenance(**kwargs)

        async def run():
            return await async_maintenance.ensure(plan, dry_run=True)

        import asyncio

        async_report = asyncio.run(run())
        assert async_report.operations == sync_report.operations


class TestSQLServerPartitionListAndValidate:
    """``list`` reports, and ``validate`` never repairs."""

    def test_list_reports_missing_boundaries_and_issues(self):
        maintenance = FakeMaintenance(
            functions=[
                PartitionFunctionInfo(
                    name="pf_logs",
                    data_type="date",
                    range_direction="RIGHT",
                    boundary_values=("2026-01-01",),
                    partition_count=2,
                )
            ],
            exists={date(2026, 1, 1): True, date(2026, 2, 1): False},
        )
        report = maintenance.list(_plan())
        assert report.missing_boundaries == (date(2026, 2, 1),)
        assert report.existing_boundaries == ("2026-01-01",)
        assert any("2 partitions" in issue for issue in report.issues)

    def test_list_reports_a_missing_function_with_every_boundary_missing(self):
        report = FakeMaintenance().list(_plan())
        assert report.missing_boundaries == (date(2026, 1, 1), date(2026, 2, 1))
        assert report.issues == ("partition function 'pf_logs' does not exist",)

    def test_validate_flags_a_table_on_the_wrong_scheme_and_holes(self):
        maintenance = FakeMaintenance(
            functions=[
                PartitionFunctionInfo(
                    name="pf_logs",
                    data_type="date",
                    range_direction="RIGHT",
                    boundary_values=("2026-01-01", "2026-02-01"),
                    partition_count=3,
                )
            ],
            schemes=[
                PartitionSchemeInfo(
                    name="ps_logs", function="pf_logs", filegroups=("PRIMARY",)
                )
            ],
            tables=[
                PartitionTableInfo(
                    name="logs",
                    schema="dbo",
                    scheme="ps_other",
                    function="pf_other",
                    partition_count=3,
                )
            ],
            ranges=[
                PartitionRangeInfo(table="logs", schema="dbo", partition_number=1),
                PartitionRangeInfo(table="logs", schema="dbo", partition_number=3),
            ],
            exists={date(2026, 1, 1): True, date(2026, 2, 1): True},
        )
        report = maintenance.validate(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"), table="logs"
        )
        assert any("built on 'ps_other'" in issue for issue in report.issues)
        assert any("uses function 'pf_other'" in issue for issue in report.issues)
        assert any("partitions are [1, 3]" in issue for issue in report.issues)
        assert report.operations == ()


class TestSQLServerPartitionDropOrMerge:
    """SQL Server has no DROP PARTITION; the executor merges boundaries."""

    def test_dry_run_is_the_default_and_executes_nothing(self):
        maintenance = FakeMaintenance(
            functions=[
                PartitionFunctionInfo(
                    name="pf_logs",
                    data_type="date",
                    range_direction="RIGHT",
                    boundary_values=("2026-01-01", "2026-02-01"),
                    partition_count=3,
                )
            ],
            exists={date(2026, 1, 1): True},
        )
        report = maintenance.drop_or_merge(_plan(), [date(2026, 1, 1)])
        assert report.dry_run is True
        assert [op.action for op in report.operations] == ["merge"]
        assert report.operations[0].sql == (
            "ALTER PARTITION FUNCTION [pf_logs] () MERGE RANGE ('2026-01-01')"
        )
        assert maintenance.executed == []

    def test_real_merge_executes_the_statement(self):
        maintenance = FakeMaintenance(
            functions=[
                PartitionFunctionInfo(
                    name="pf_logs",
                    data_type="date",
                    range_direction="RIGHT",
                    boundary_values=("2026-01-01", "2026-02-01"),
                    partition_count=3,
                )
            ],
            exists={date(2026, 1, 1): True},
        )
        report = maintenance.drop_or_merge(
            _plan(), [date(2026, 1, 1)], dry_run=False
        )
        assert report.operations[0].action == "merge"
        assert maintenance.executed == [report.operations[0].sql]

    def test_absent_boundary_is_reported_not_merged(self):
        report = FakeMaintenance(
            functions=[
                PartitionFunctionInfo(
                    name="pf_logs",
                    data_type="date",
                    range_direction="RIGHT",
                    boundary_values=("2026-01-01",),
                    partition_count=2,
                )
            ]
        ).drop_or_merge(_plan(), [date(2026, 2, 1)])
        assert report.operations == ()
        assert any("is not present" in issue for issue in report.issues)

    def test_scaffolding_is_kept_when_a_table_uses_the_scheme(self):
        maintenance = FakeMaintenance(
            functions=[
                PartitionFunctionInfo(
                    name="pf_logs",
                    data_type="date",
                    range_direction="RIGHT",
                    boundary_values=(),
                    partition_count=1,
                )
            ],
            schemes=[
                PartitionSchemeInfo(
                    name="ps_logs", function="pf_logs", filegroups=("PRIMARY",)
                )
            ],
            tables=[
                PartitionTableInfo(
                    name="logs",
                    schema="dbo",
                    scheme="ps_logs",
                    function="pf_logs",
                    partition_count=1,
                )
            ],
        )
        report = maintenance.drop_or_merge(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"),
            dry_run=True,
            drop_scaffolding=True,
        )
        assert report.operations == ()
        assert any("used by 1 table" in issue for issue in report.issues)

    def test_unused_scaffolding_is_dropped_scheme_then_function(self):
        maintenance = FakeMaintenance(
            functions=[
                PartitionFunctionInfo(
                    name="pf_logs",
                    data_type="date",
                    range_direction="RIGHT",
                    boundary_values=("2026-01-01",),
                    partition_count=2,
                )
            ],
            schemes=[
                PartitionSchemeInfo(
                    name="ps_logs", function="pf_logs", filegroups=("PRIMARY",)
                )
            ],
            exists={date(2026, 1, 1): True},
        )
        report = maintenance.drop_or_merge(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"),
            [date(2026, 1, 1)],
            dry_run=True,
            drop_scaffolding=True,
        )
        actions = [op.action for op in report.operations]
        assert actions == ["merge", "drop_scheme", "drop_function"]
        assert report.operations[-2].sql == "DROP PARTITION SCHEME [ps_logs]"
        assert report.operations[-1].sql == "DROP PARTITION FUNCTION [pf_logs]"

    def test_one_unused_scheme_can_go_while_another_keeps_the_function(self):
        maintenance = FakeMaintenance(
            functions=[
                PartitionFunctionInfo(
                    name="pf_logs",
                    data_type="date",
                    range_direction="RIGHT",
                    boundary_values=(),
                    partition_count=1,
                )
            ],
            schemes=[
                PartitionSchemeInfo(
                    name="ps_unused", function="pf_logs", filegroups=("PRIMARY",)
                ),
                PartitionSchemeInfo(
                    name="ps_used", function="pf_logs", filegroups=("PRIMARY",)
                ),
            ],
            tables=[
                PartitionTableInfo(
                    name="logs",
                    schema="dbo",
                    scheme="ps_used",
                    function="pf_logs",
                    partition_count=1,
                )
            ],
        )
        report = maintenance.drop_or_merge(
            _plan(), dry_run=True, drop_scaffolding=True
        )
        assert [op.action for op in report.operations] == ["drop_scheme"]
        assert report.operations[0].name == "ps_unused"
        assert any("used by 1 table" in issue for issue in report.issues)
        assert any("still mapped by scheme" in issue for issue in report.issues)


class TestSQLServerPartitionRetention:
    """Retention is derived from the catalogue, never guessed."""

    @staticmethod
    def _maintenance():
        boundaries = (date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1))
        return FakeMaintenance(
            functions=_function_info(("2026-01-01", "2026-02-01", "2026-03-01")),
            exists={boundary: True for boundary in boundaries},
        )

    def test_boundaries_at_or_before_the_cutoff_are_returned(self):
        maintenance = self._maintenance()
        plan = _plan()
        assert maintenance.retention_boundaries(plan, date(2026, 2, 1)) == (
            date(2026, 1, 1),
            date(2026, 2, 1),
        )
        assert maintenance.executed == []

    def test_nothing_before_the_first_boundary_is_returned(self):
        maintenance = self._maintenance()
        assert maintenance.retention_boundaries(_plan(), date(2025, 12, 31)) == ()

    def test_a_missing_function_has_nothing_to_retain(self):
        assert FakeMaintenance().retention_boundaries(_plan(), date(2026, 2, 1)) == ()

    def test_table_ranges_can_supply_the_upper_bounds(self):
        maintenance = FakeMaintenance(
            ranges=[
                PartitionRangeInfo(
                    table="logs", schema="dbo", partition_number=1
                ),
                PartitionRangeInfo(
                    table="logs",
                    schema="dbo",
                    partition_number=2,
                    low_boundary=None,
                    high_boundary="2026-01-01",
                ),
                PartitionRangeInfo(
                    table="logs",
                    schema="dbo",
                    partition_number=3,
                    low_boundary="2026-01-01",
                    high_boundary="2026-02-01",
                ),
            ]
        )
        assert maintenance.retention_boundaries(
            _plan(), date(2026, 2, 1), table="logs", schema="dbo"
        ) == (date(2026, 1, 1), date(2026, 2, 1))

    def test_datetime_boundaries_tolerate_seven_fractional_digits(self):
        maintenance = FakeMaintenance(
            functions=_function_info(
                ("2026-01-01T00:00:00.0000000", "2026-02-01T00:00:00.0000000"),
                data_type="datetime2",
            )
        )
        plan = _plan(
            boundaries=(datetime(2026, 1, 1), datetime(2026, 2, 1)),
            data_type="DATETIME2",
        )
        assert maintenance.retention_boundaries(plan, date(2026, 2, 1)) == (
            datetime(2026, 1, 1),
            datetime(2026, 2, 1),
        )

    def test_integer_boundaries_compare_as_integers(self):
        maintenance = FakeMaintenance(
            functions=_function_info(("100", "200"), data_type="int"),
            exists={100: True, 200: True},
        )
        plan = _plan(boundaries=(100, 200), data_type="INT")
        assert maintenance.retention_boundaries(plan, 150) == (100,)

    def test_drop_before_renders_only_by_default(self):
        maintenance = self._maintenance()
        report = maintenance.drop_before(_plan(), date(2026, 2, 1))
        assert report.dry_run is True
        assert [op.action for op in report.operations] == ["merge", "merge"]
        assert all("MERGE RANGE" in op.sql for op in report.operations)
        assert maintenance.executed == []
        assert report.errors == ()

    def test_drop_before_executes_when_asked(self):
        maintenance = self._maintenance()
        report = maintenance.drop_before(_plan(), date(2026, 2, 1), dry_run=False)
        assert [op.action for op in report.operations] == ["merge", "merge"]
        assert len(maintenance.executed) == 2

    def test_drop_before_can_drop_the_scaffolding_too(self):
        maintenance = self._maintenance()
        report = maintenance.drop_before(
            _plan(), date(2026, 2, 1), drop_scaffolding=True
        )
        assert [op.action for op in report.operations] == [
            "merge",
            "merge",
            "drop_function",
        ]

    def test_async_drop_before_matches_the_sync_plan(self):
        boundaries = (date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1))
        kwargs = dict(
            functions=_function_info(("2026-01-01", "2026-02-01", "2026-03-01")),
            exists={boundary: True for boundary in boundaries},
        )
        plan = _plan()
        sync_report = FakeMaintenance(**kwargs).drop_before(plan, date(2026, 2, 1))
        async_maintenance = FakeAsyncMaintenance(**kwargs)

        async def run():
            return await async_maintenance.drop_before(plan, date(2026, 2, 1))

        async_report = asyncio.run(run())
        assert async_report.operations == sync_report.operations
        assert async_report.dry_run is True


class TestSQLServerPartitionErrors:
    """A non-transactional engine reports failures instead of pretending."""

    def test_a_failed_statement_is_recorded_and_later_ones_stop(self):
        maintenance = ScriptedMaintenance(fail_at=1)
        report = maintenance.ensure(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"), dry_run=False
        )
        assert len(report.errors) == 1
        assert report.errors[0].startswith("create_scheme")
        assert "scripted failure" in report.errors[0]
        assert [op.action for op in report.operations] == ["create_function"]
        assert len(maintenance.executed) == 1

    def test_completed_merges_stay_visible_after_a_failure(self):
        maintenance = ScriptedMaintenance(
            functions=_function_info(("2026-01-01", "2026-02-01")),
            exists={date(2026, 1, 1): True, date(2026, 2, 1): True},
            fail_at=1,
        )
        report = maintenance.drop_or_merge(
            _plan(), [date(2026, 1, 1), date(2026, 2, 1)], dry_run=False
        )
        assert [op.action for op in report.operations] == ["merge"]
        assert report.operations[0].name == str(date(2026, 1, 1))
        assert len(report.errors) == 1
        assert report.errors[0].startswith("merge ")
        assert len(maintenance.executed) == 1

    def test_async_failure_is_recorded_without_later_statements(self):
        maintenance = ScriptedAsyncMaintenance(ScriptedMaintenance(fail_at=0))

        async def run():
            return await maintenance.ensure(
                _plan(scheme="ps_logs", all_filegroup="PRIMARY"), dry_run=False
            )

        report = asyncio.run(run())
        assert len(report.errors) == 1
        assert report.errors[0].startswith("create_function")
        assert report.operations == ()


class TestSQLServerPartitionPostState:
    """A real run reports the catalogue it left behind, not the one it read."""

    def test_ensure_reports_the_boundaries_it_created(self):
        boundary = date(2026, 2, 1)

        def on_execute(maintenance, sql, params):
            if "SPLIT RANGE" in sql:
                maintenance.functions = tuple(
                    _function_info(("2026-01-01", "2026-02-01"))
                )
                maintenance.exists[boundary] = True

        maintenance = ScriptedMaintenance(
            functions=_function_info(("2026-01-01",)),
            schemes=[
                PartitionSchemeInfo(
                    name="ps_logs", function="pf_logs", filegroups=("PRIMARY",)
                )
            ],
            exists={date(2026, 1, 1): True, boundary: False},
            on_execute=on_execute,
        )
        report = maintenance.ensure(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"), dry_run=False
        )
        assert report.missing_boundaries == ()
        assert report.existing_boundaries == ("2026-01-01", "2026-02-01")

    def test_dry_run_keeps_the_pre_execution_snapshot(self):
        maintenance = ScriptedMaintenance(
            functions=_function_info(("2026-01-01",)),
            schemes=[
                PartitionSchemeInfo(
                    name="ps_logs", function="pf_logs", filegroups=("PRIMARY",)
                )
            ],
            exists={date(2026, 1, 1): True, date(2026, 2, 1): False},
        )
        report = maintenance.ensure(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"), dry_run=True
        )
        assert report.missing_boundaries == (date(2026, 2, 1),)
        assert report.existing_boundaries == ("2026-01-01",)
        assert report.dry_run is True


class TestSQLServerPartitionCoreMapping:
    """The engine rows are also exposed as core ``PartitionInfo`` rows."""

    def test_ranges_become_core_partition_rows(self):
        maintenance = FakeMaintenance(
            functions=_function_info(("2026-01-01", "2026-02-01")),
            schemes=[
                PartitionSchemeInfo(
                    name="ps_logs", function="pf_logs", filegroups=("PRIMARY",)
                )
            ],
            tables=[
                PartitionTableInfo(
                    name="logs",
                    schema="dbo",
                    scheme="ps_logs",
                    function="pf_logs",
                    partition_count=3,
                )
            ],
            ranges=[
                PartitionRangeInfo(
                    table="logs",
                    schema="dbo",
                    partition_number=1,
                    high_boundary="2026-01-01",
                    row_count=4,
                    data_bytes=8192,
                ),
                PartitionRangeInfo(
                    table="logs",
                    schema="dbo",
                    partition_number=2,
                    low_boundary="2026-01-01",
                    high_boundary="2026-02-01",
                ),
                PartitionRangeInfo(
                    table="logs",
                    schema="dbo",
                    partition_number=3,
                    low_boundary="2026-02-01",
                ),
            ],
            exists={date(2026, 1, 1): True, date(2026, 2, 1): True},
        )
        report = maintenance.list(
            _plan(scheme="ps_logs", all_filegroup="PRIMARY"),
            table="logs",
            schema="dbo",
        )
        assert [row.partition_number for row in report.ranges] == [1, 2, 3]
        assert len(report.partitions) == 3
        first, second, third = report.partitions
        assert first.name == "logs_1"
        assert first.parent == "logs"
        assert first.level == 1
        assert first.method == "RANGE"
        assert first.bound == "..2026-01-01"
        assert second.bound == "2026-01-01..2026-02-01"
        assert third.bound == "2026-02-01.."
        assert first.schema == "dbo"
        assert first.row_count == 4
        assert first.size_bytes == 8192
        assert first.extras["partition_number"] == 1
        assert first.extras["scheme"] == "ps_logs"
        assert first.extras["function"] == "pf_logs"


def test_report_is_the_core_contract_envelope():
    report = PartitionReport(target="pf_logs")

    assert isinstance(report, CorePartitionReport)
    assert report.function is None
    assert report.dry_run is False


def test_the_sync_executor_offers_inventory_ensure_validation_and_retention():
    executor = FakeMaintenance()

    assert isinstance(executor, PartitionInventory)
    assert isinstance(executor, PartitionEnsurer)
    assert isinstance(executor, PartitionValidator)
    assert isinstance(executor, PartitionRetention)


def test_the_async_executor_offers_inventory_ensure_validation_and_retention():
    executor = FakeAsyncMaintenance()

    assert isinstance(executor, AsyncPartitionInventory)
    assert isinstance(executor, AsyncPartitionEnsurer)
    assert isinstance(executor, AsyncPartitionValidator)
    assert isinstance(executor, AsyncPartitionRetention)
