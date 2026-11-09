# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_sqlserver_partition_live.py
"""Live tests for SQL Server partition DDL and maintenance.

These are skipped -- not passed -- when no scenario is configured or the
configured server cannot be reached, so a machine without the 2022 image does
not report a false success. The offline suites in
``test_sqlserver_partition.py`` and
``test_sqlserver_partition_maintenance.py`` cover the rendering and the
decisions; this file covers what only a server can answer: whether
``CREATE PARTITION FUNCTION`` / ``SCHEME`` / ``SPLIT`` / ``MERGE`` / ``SWITCH``
really work, and where rows land.

One scenario is used, like the other single-scenario live suites.
"""

import os
from datetime import date

import pytest

from providers.scenarios import get_enabled_scenarios, get_scenario

from rhosocial.activerecord.backend.impl.sqlserver.expression.partition import (
    SQLServerSwitchPartitionExpression,
)
from rhosocial.activerecord.backend.impl.sqlserver.partition import (
    SQLServerPartitionMaintenance,
    SQLServerPartitionPlan,
)

_SUFFIX = f"_{os.getpid()}"
_FUNCTION = f"pf_part{_SUFFIX}"
_SCHEME = f"ps_part{_SUFFIX}"
_TABLE = f"t_part{_SUFFIX}"
_STAGE = f"t_stage{_SUFFIX}"

_BOUNDARIES = (date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1))
_EXTRA = date(2026, 1, 15)


def _plan(boundaries=_BOUNDARIES):
    return SQLServerPartitionPlan(
        function=_FUNCTION,
        data_type="DATE",
        boundaries=boundaries,
        scheme=_SCHEME,
        all_filegroup="PRIMARY",
    )


def _cleanup(backend):
    """Remove the probe objects, children first, tolerating partial state."""
    for sql in (
        f"IF OBJECT_ID('dbo.{_STAGE}', 'U') IS NOT NULL DROP TABLE dbo.{_STAGE}",
        f"IF OBJECT_ID('dbo.{_TABLE}', 'U') IS NOT NULL DROP TABLE dbo.{_TABLE}",
        (
            f"IF EXISTS (SELECT 1 FROM sys.partition_schemes "
            f"WHERE name = '{_SCHEME}') DROP PARTITION SCHEME {_SCHEME}"
        ),
        (
            f"IF EXISTS (SELECT 1 FROM sys.partition_functions "
            f"WHERE name = '{_FUNCTION}') DROP PARTITION FUNCTION {_FUNCTION}"
        ),
    ):
        try:
            backend.execute(sql)
        except Exception:
            pass


@pytest.fixture(scope="function")
def partition_backend():
    """A backend against the first scenario for one test, or a skip when unavailable."""
    scenarios = get_enabled_scenarios()
    if not scenarios:
        pytest.skip("No SQL Server scenarios configured")
    scenario_name = next(iter(scenarios))
    backend_class, config = get_scenario(scenario_name)
    backend = backend_class(connection_config=config)
    try:
        backend.connect()
        backend.execute("SELECT 1")
    except Exception as exc:  # pragma: no cover - environment dependent
        try:
            backend.disconnect()
        except Exception:
            pass
        pytest.skip(f"SQL Server is unavailable: {exc}")
    _cleanup(backend)
    yield backend
    _cleanup(backend)
    backend.disconnect()


@pytest.fixture(scope="function")
def partition_fixture(partition_backend):
    """A real function, scheme and partitioned table with four partitions.

    Rebuilt for every test: the split and merge tests mutate the function, and
    xdist is free to run those on a different worker than the tests that expect
    the four-partition baseline.
    """
    maintenance = SQLServerPartitionMaintenance(partition_backend)
    plan = _plan()
    report = maintenance.ensure(plan)
    assert {op.action for op in report.operations} == {
        "create_function",
        "create_scheme",
    }
    partition_backend.execute(
        f"CREATE TABLE dbo.{_TABLE} ("
        "id INT NOT NULL, created_at DATE NOT NULL, "
        f"CONSTRAINT pk_{_TABLE} PRIMARY KEY (id, created_at)) "
        f"ON [{_SCHEME}] ([created_at])"
    )
    partition_backend.execute(
        f"CREATE TABLE dbo.{_STAGE} ("
        "id INT NOT NULL, created_at DATE NOT NULL, "
        f"CONSTRAINT pk_{_STAGE} PRIMARY KEY (id, created_at))"
    )
    partition_backend.execute(
        f"INSERT INTO dbo.{_TABLE} (id, created_at) VALUES "
        "(1, '2025-12-01'), (2, '2026-01-15'), "
        "(3, '2026-02-15'), (4, '2026-03-15')"
    )
    yield maintenance, plan
    _cleanup(partition_backend)


def _partition_of(backend, created_at: date) -> int:
    # Bind an ISO string rather than a ``date``: the legacy ``SQL Server``
    # ODBC driver has no SQLBindParameter support for ``date`` (HYC00), while
    # the implicit conversion from the string is accepted by every version.
    row = backend.execute(
        "SELECT $PARTITION."
        f"{_FUNCTION}(?) AS partition_number",
        (created_at.isoformat(),),
    ).data
    return int(row[0]["partition_number"])


class TestSQLServerPartitionLive:
    """What the server confirms about SQL Server's function/scheme model."""

    def test_ensure_created_a_function_and_scheme(self, partition_backend, partition_fixture):
        maintenance, plan = partition_fixture
        report = maintenance.list(plan)
        info = report.function_info(_FUNCTION)
        assert info is not None
        assert info.range_direction == "RIGHT"
        assert info.partition_count == 4
        assert len(info.boundary_values) == 3
        scheme = report.scheme_info(_SCHEME)
        assert scheme is not None
        assert scheme.function == _FUNCTION
        assert scheme.destination_count >= 1
        assert maintenance.validate(plan).issues == ()

    def test_rows_land_in_the_expected_partitions(self, partition_backend, partition_fixture):
        assert _partition_of(partition_backend, date(2025, 12, 1)) == 1
        assert _partition_of(partition_backend, date(2026, 1, 15)) == 2
        assert _partition_of(partition_backend, date(2026, 2, 15)) == 3
        assert _partition_of(partition_backend, date(2026, 3, 15)) == 4

    def test_list_reports_the_table_and_each_partition(self, partition_backend, partition_fixture):
        maintenance, plan = partition_fixture
        report = maintenance.list(plan, table=_TABLE, schema="dbo")
        table = report.table_info(_TABLE)
        assert table is not None
        assert table.scheme == _SCHEME
        assert table.partition_column == "created_at"
        assert [row.partition_number for row in report.ranges] == [1, 2, 3, 4]
        assert report.ranges[0].low_boundary is None
        assert report.ranges[-1].high_boundary is None
        assert sum(row.row_count or 0 for row in report.ranges) == 4
        assert maintenance.validate(plan, table=_TABLE, schema="dbo").issues == ()

    def test_split_adds_a_partition(self, partition_backend, partition_fixture):
        maintenance, _ = partition_fixture
        split_plan = _plan(_BOUNDARIES + (_EXTRA,))
        report = maintenance.ensure(split_plan)
        actions = [op.action for op in report.operations]
        assert actions == ["next_used", "split"]
        info = maintenance.list(split_plan).function_info(_FUNCTION)
        assert info is not None and info.partition_count == 5
        assert _partition_of(partition_backend, _EXTRA) == 3

    def test_merge_removes_the_partition_without_dropping_it(
        self, partition_backend, partition_fixture
    ):
        maintenance, _ = partition_fixture
        # The split is this test's precondition, not another test's side effect:
        # xdist may run the split test on a different worker.
        maintenance.ensure(_plan(_BOUNDARIES + (_EXTRA,)))
        report = maintenance.drop_or_merge(
            _plan(_BOUNDARIES + (_EXTRA,)), [_EXTRA], dry_run=False
        )
        assert [op.action for op in report.operations] == ["merge"]
        info = maintenance.list(_plan()).function_info(_FUNCTION)
        assert info is not None and info.partition_count == 4
        assert _partition_of(partition_backend, date(2026, 1, 15)) == 2

    def test_switch_moves_a_partition_to_another_table(self, partition_backend, partition_fixture):
        maintenance, plan = partition_fixture
        switch = SQLServerSwitchPartitionExpression(
            partition_backend.dialect,
            _TABLE,
            _STAGE,
            source_partition=1,
            schema="dbo",
            target_schema="dbo",
        )
        partition_backend.execute(*switch.to_sql())
        before = partition_backend.execute(
            f"SELECT COUNT(*) AS c FROM dbo.{_TABLE} WHERE created_at = '2025-12-01'"
        ).data[0]["c"]
        moved = partition_backend.execute(
            f"SELECT id FROM dbo.{_STAGE}"
        ).data
        assert before == 0
        assert [row["id"] for row in moved] == [1]
        assert maintenance.validate(plan, table=_TABLE, schema="dbo").issues == ()

    def test_scaffolding_is_refused_while_the_table_uses_it(
        self, partition_backend, partition_fixture
    ):
        maintenance, plan = partition_fixture
        report = maintenance.drop_or_merge(
            plan, dry_run=True, drop_scaffolding=True
        )
        assert all(op.action != "drop_function" for op in report.operations)
        assert any("used by" in issue for issue in report.issues)

    def test_drop_before_renders_the_live_retention_boundaries(
        self, partition_fixture
    ):
        maintenance, plan = partition_fixture
        boundaries = maintenance.retention_boundaries(plan, date(2026, 2, 1))
        report = maintenance.drop_before(plan, date(2026, 2, 1))
        assert report.dry_run is True
        assert report.errors == ()
        assert [op.action for op in report.operations] == ["merge"] * len(
            boundaries
        )
