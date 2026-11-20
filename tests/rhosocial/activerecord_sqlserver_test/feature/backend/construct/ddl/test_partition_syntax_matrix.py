# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/ddl/test_partition_syntax_matrix.py
"""Offline matrix over SQL Server's partition syntax families.

Every test is parameterised by ``partition_syntax_case`` from
``partition_syntax_fixtures.py``. The matrix asserts the things a family can be
wrong about without a server: the plan's normalised count, direction and
destinations; the rendered DDL's required and forbidden fragments; and the
explicit refusal of subpartitioning. Suggestion values are covered in
``test_partition_suggestions.py``.

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

    def test_subpartitioning_is_refused(self, partition_syntax_case):  # noqa: F811 - pytest fixture
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
            assert params == (), f"{case.name}: partition DDL binds no parameters, got {params!r}"
            rendered.append(sql)
        for fragment in case.expected_fragments:
            assert any(
                fragment in sql for sql in rendered
            ), f"{case.name}: expected {fragment!r} in {rendered!r}"
        for fragment in case.forbidden_fragments:
            assert all(
                fragment not in sql for sql in rendered
            ), f"{case.name}: forbidden {fragment!r} appeared in {rendered!r}"
