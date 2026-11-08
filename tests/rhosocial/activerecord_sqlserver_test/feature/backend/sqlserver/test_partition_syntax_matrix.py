# tests/rhosocial/activerecord_sqlserver_test/feature/backend/sqlserver/test_partition_syntax_matrix.py
"""Offline matrix over SQL Server's partition syntax families.

Every test is parameterised by ``partition_syntax_case`` from
``partition_syntax_fixtures.py``. The matrix asserts the four things a family
can be wrong about without a server: the plan's normalised count, direction
and destinations; the rendered DDL's required and forbidden fragments; the
explicit refusal of subpartitioning; and the maintenance executor's decisions
against canned catalogue rows.

No connection is opened. The ``sqlserver_dialect`` fixture is the existing
offline fixture from ``feature/backend/conftest.py``.
"""

from typing import Optional

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.partition import (
    SQLServerPartitionPlan,
)

from partition_syntax_fixtures import (  # noqa: F401 - registers the fixture
    CASES,
    PartitionSyntaxCase,
    partition_syntax_case,
)


def _plan_for(
    case: PartitionSyntaxCase,
) -> Optional[SQLServerPartitionPlan]:
    """Build the case's plan, or ``None`` when the family needs no plan."""
    if case.plan_builder is None:
        return None
    return case.plan_builder()


class TestPartitionSyntaxMatrix:
    """The matrix itself is a table, so its ids must be stable and unique."""

    def test_case_ids_are_unique(self):
        names = [case.name for case in CASES]
        assert len(names) == len(set(names))

    def test_every_case_has_a_description(self):
        assert all(case.description.strip() for case in CASES)


class TestPartitionSyntaxPlan:
    """Plan normalisation: partition count, direction and destinations."""

    def test_count_direction_and_filegroups(
        self, partition_syntax_case  # noqa: F811 - pytest fixture
    ):
        case = partition_syntax_case
        if case.refuse_subpartition:
            return
        plan = _plan_for(case)
        if plan is None:
            return
        if case.expected_partition_count is not None:
            assert plan.partition_count == case.expected_partition_count, (
                f"{case.name}: expected {case.expected_partition_count} "
                f"partitions, got {plan.partition_count}"
            )
        if case.expected_direction is not None:
            assert plan.range_direction.value == case.expected_direction, (
                f"{case.name}: expected RANGE {case.expected_direction}, "
                f"got RANGE {plan.range_direction.value}"
            )
        if case.expected_filegroups is not None:
            assert plan.filegroups == case.expected_filegroups, (
                f"{case.name}: expected filegroups "
                f"{case.expected_filegroups!r}, got {plan.filegroups!r}"
            )
        if case.expected_next_filegroup is not None:
            assert plan.next_filegroup == case.expected_next_filegroup, (
                f"{case.name}: expected NEXT USED "
                f"{case.expected_next_filegroup!r}, got "
                f"{plan.next_filegroup!r}"
            )

    def test_subpartitioning_is_refused(
        self, partition_syntax_case  # noqa: F811 - pytest fixture
    ):
        case = partition_syntax_case
        if not case.refuse_subpartition:
            return
        with pytest.raises(UnsupportedFeatureError, match="subpartitioning"):
            case.plan_builder()


class TestPartitionSyntaxDDL:
    """Rendered statements carry the required spelling and nothing else."""

    def test_required_and_forbidden_fragments(
        self,
        partition_syntax_case,  # noqa: F811 - pytest fixture
        sqlserver_dialect: SQLServerDialect,
    ):
        case = partition_syntax_case
        if case.ddl_builder is None:
            return
        plan = _plan_for(case)
        rendered = []
        for statement in case.ddl_builder(sqlserver_dialect, plan):
            sql, params = statement.to_sql()
            assert params == (), (
                f"{case.name}: partition DDL binds no parameters, got {params!r}"
            )
            rendered.append(sql)
        for fragment in case.expected_fragments:
            assert any(fragment in sql for sql in rendered), (
                f"{case.name}: expected {fragment!r} in {rendered!r}"
            )
        for fragment in case.forbidden_fragments:
            assert all(fragment not in sql for sql in rendered), (
                f"{case.name}: forbidden {fragment!r} appeared in {rendered!r}"
            )


class TestPartitionSyntaxMaintenance:
    """Maintenance decisions run against canned catalogue rows."""

    def test_planning_decisions(
        self,
        partition_syntax_case,  # noqa: F811 - pytest fixture
        sqlserver_dialect: SQLServerDialect,
    ):
        case = partition_syntax_case
        if case.maintenance_builder is None:
            return
        reports = case.maintenance_builder(sqlserver_dialect)
        assert set(reports) == {
            expectation.operation for expectation in case.maintenance_expectations
        }, f"{case.name}: unexpected maintenance report keys {sorted(reports)}"
        for expectation in case.maintenance_expectations:
            report = reports[expectation.operation]
            if expectation.expect_dry_run is not None:
                assert report.dry_run is expectation.expect_dry_run, (
                    f"{case.name}/{expectation.operation}: expected dry_run="
                    f"{expectation.expect_dry_run}, got {report.dry_run}"
                )
            assert [op.action for op in report.operations] == list(
                expectation.actions
            ), (
                f"{case.name}/{expectation.operation}: expected actions "
                f"{list(expectation.actions)!r}, got "
                f"{[op.action for op in report.operations]!r}"
            )
            if expectation.missing_boundaries is not None:
                assert report.missing_boundaries == (
                    expectation.missing_boundaries
                ), (
                    f"{case.name}/{expectation.operation}: expected missing "
                    f"boundaries {expectation.missing_boundaries!r}, got "
                    f"{report.missing_boundaries!r}"
                )
            if expectation.existing_boundaries is not None:
                assert report.existing_boundaries == (
                    expectation.existing_boundaries
                ), (
                    f"{case.name}/{expectation.operation}: expected existing "
                    f"boundaries {expectation.existing_boundaries!r}, got "
                    f"{report.existing_boundaries!r}"
                )
            for fragment in expectation.issue_fragments:
                assert any(fragment in issue for issue in report.issues), (
                    f"{case.name}/{expectation.operation}: expected an issue "
                    f"containing {fragment!r}, got {report.issues!r}"
                )
            for fragment in expectation.sql_fragments:
                assert any(fragment in op.sql for op in report.operations), (
                    f"{case.name}/{expectation.operation}: expected "
                    f"{fragment!r} in {[op.sql for op in report.operations]!r}"
                )
