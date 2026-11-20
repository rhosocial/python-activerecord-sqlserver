# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/ddl/partition_syntax_fixtures.py
"""Fixture-driven matrix of SQL Server partition syntax families.

Each :class:`PartitionSyntaxCase` names one family of SQL Server's three-tier
partition model -- the ``RANGE LEFT``/``RANGE RIGHT`` function, the scheme
destinations, ``NEXT USED``, ``SPLIT``/``MERGE``/``SWITCH`` and the dependency
checked drops -- and carries the builders the offline matrix uses to exercise
it.

The cases do not repeat the exact assertions of
``test_partition_expressions.py``; they collect the families those files cover
into one parameterised table so a new syntax family is added in one place. No
server is needed: every builder returns a plan or an expression.

Maintenance decisions are no longer part of this matrix. The dialect's eight
``suggest_partition_*`` methods are covered separately in
``test_partition_suggestions.py``, and the catalogue side belongs to
introspection.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Optional, Sequence, Tuple

import pytest

from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression.partition import (
    SQLServerDropPartitionFunctionExpression,
    SQLServerDropPartitionSchemeExpression,
    SQLServerPartitionFunctionExpression,
    SQLServerPartitionFunctionMergeExpression,
    SQLServerPartitionFunctionSplitExpression,
    SQLServerPartitionSchemeExpression,
    SQLServerPartitionSchemeNextUsedExpression,
    SQLServerSwitchPartitionExpression,
)
from rhosocial.activerecord.backend.impl.sqlserver.partition import (
    SQLServerPartitionPlan,
)

#: Build a plan with no arguments, or refuse at construction when it asks for
#: something SQL Server cannot express.
PlanBuilder = Callable[[], SQLServerPartitionPlan]

#: Render one family's statements; the plan is ``None`` only for a case that
#: does not need one (``SWITCH`` names two tables instead).
DDLBuilder = Callable[[SQLServerDialect, Optional[SQLServerPartitionPlan]], Sequence[Any]]


@dataclass(frozen=True)
class PartitionSyntaxCase:
    """One SQL Server partition syntax family and how to exercise it.

    Attributes:
        name: Stable identifier used as the parameterised test id.
        description: One sentence saying which family this is.
        plan_builder: Builds the ``SQLServerPartitionPlan`` under test, if any.
        ddl_builder: Renders the family's DDL expressions from a dialect and
            the plan (``None`` when the family needs no DDL assertions).
        expected_fragments: Substrings required in the rendered DDL.
        forbidden_fragments: Substrings that must not appear in the DDL.
        expected_partition_count: Expected ``plan.partition_count``.
        expected_direction: Expected ``plan.range_direction.value``.
        expected_filegroups: Expected explicit ``plan.filegroups``.
        expected_next_filegroup: Expected ``plan.next_filegroup``.
        refuse_subpartition: The plan builder must raise
            ``UnsupportedFeatureError`` for a requested subpartitioning policy.
    """

    name: str
    description: str
    plan_builder: Optional[PlanBuilder] = None
    ddl_builder: Optional[DDLBuilder] = None
    expected_fragments: Tuple[str, ...] = ()
    forbidden_fragments: Tuple[str, ...] = ()
    expected_partition_count: Optional[int] = None
    expected_direction: Optional[str] = None
    expected_filegroups: Optional[Tuple[str, ...]] = None
    expected_next_filegroup: Optional[str] = None
    refuse_subpartition: bool = False


def _plan_builder(**overrides: Any) -> PlanBuilder:
    """Return a builder for a plan carrying *overrides*."""

    def build() -> SQLServerPartitionPlan:
        return SQLServerPartitionPlan(**overrides)

    return build


_BOUNDARIES = (date(2026, 1, 1), date(2026, 2, 1))
_THREE_BOUNDARIES = _BOUNDARIES + (date(2026, 3, 1),)
_SPLIT_BOUNDARY = date(2026, 3, 1)


def _function_ddl(
    dialect: SQLServerDialect, plan: Optional[SQLServerPartitionPlan]
) -> Sequence[Any]:
    """Render ``CREATE PARTITION FUNCTION`` from the plan."""
    return (
        SQLServerPartitionFunctionExpression(
            dialect,
            plan.function,
            plan.data_type,
            plan.boundaries,
            range_direction=plan.range_direction,
        ),
    )


def _scheme_ddl(dialect: SQLServerDialect, plan: Optional[SQLServerPartitionPlan]) -> Sequence[Any]:
    """Render ``CREATE PARTITION SCHEME`` from the plan's destinations."""
    return (
        SQLServerPartitionSchemeExpression(
            dialect,
            plan.scheme,
            plan.function,
            plan.filegroups,
            all_filegroup=plan.all_filegroup,
        ),
    )


def _next_used_ddl(
    dialect: SQLServerDialect, plan: Optional[SQLServerPartitionPlan]
) -> Sequence[Any]:
    """Render ``ALTER PARTITION SCHEME ... NEXT USED``."""
    return (SQLServerPartitionSchemeNextUsedExpression(dialect, plan.scheme, plan.next_filegroup),)


def _split_ddl(dialect: SQLServerDialect, plan: Optional[SQLServerPartitionPlan]) -> Sequence[Any]:
    """Render ``SPLIT RANGE`` at a boundary the plan does not yet hold."""
    return (SQLServerPartitionFunctionSplitExpression(dialect, plan.function, _SPLIT_BOUNDARY),)


def _merge_ddl(dialect: SQLServerDialect, plan: Optional[SQLServerPartitionPlan]) -> Sequence[Any]:
    """Render ``MERGE RANGE`` at the plan's first boundary."""
    return (SQLServerPartitionFunctionMergeExpression(dialect, plan.function, plan.boundaries[0]),)


def _switch_ddl(dialect: SQLServerDialect, plan: Optional[SQLServerPartitionPlan]) -> Sequence[Any]:
    """Render a schema-qualified ``SWITCH PARTITION``."""
    return (
        SQLServerSwitchPartitionExpression(
            dialect,
            "logs",
            "logs_archive",
            source_partition=2,
            schema="dbo",
            target_schema="dbo",
        ),
    )


def _drops_ddl(dialect: SQLServerDialect, plan: Optional[SQLServerPartitionPlan]) -> Sequence[Any]:
    """Render the scheme drop before the function drop."""
    return (
        SQLServerDropPartitionSchemeExpression(dialect, plan.scheme),
        SQLServerDropPartitionFunctionExpression(dialect, plan.function),
    )


# ---------------------------------------------------------------------------
# The matrix
# ---------------------------------------------------------------------------

CASES: Tuple[PartitionSyntaxCase, ...] = (
    PartitionSyntaxCase(
        name="range_right",
        description="RANGE RIGHT owns the boundary value and is the default.",
        plan_builder=_plan_builder(function="pf_logs", data_type="DATE", boundaries=_BOUNDARIES),
        ddl_builder=_function_ddl,
        expected_fragments=(
            "CREATE PARTITION FUNCTION [pf_logs] (DATE)",
            "AS RANGE RIGHT FOR VALUES",
            "'2026-01-01'",
            "'2026-02-01'",
        ),
        forbidden_fragments=("RANGE LEFT", "CREATE PARTITION SCHEME"),
        expected_partition_count=3,
        expected_direction="RIGHT",
    ),
    PartitionSyntaxCase(
        name="range_left",
        description="RANGE LEFT owns the boundary value on its left side.",
        plan_builder=_plan_builder(
            function="pf_events",
            data_type="INT",
            boundaries=(100, 200),
            range_direction="LEFT",
        ),
        ddl_builder=_function_ddl,
        expected_fragments=(
            "CREATE PARTITION FUNCTION [pf_events] (INT)",
            "AS RANGE LEFT FOR VALUES (100, 200)",
        ),
        forbidden_fragments=("RANGE RIGHT",),
        expected_partition_count=3,
        expected_direction="LEFT",
    ),
    PartitionSyntaxCase(
        name="scheme_all_primary",
        description="A scheme may send every partition ALL TO one filegroup.",
        plan_builder=_plan_builder(
            function="pf_logs",
            data_type="DATE",
            boundaries=_BOUNDARIES,
            scheme="ps_logs",
            all_filegroup="PRIMARY",
        ),
        ddl_builder=_scheme_ddl,
        expected_fragments=(
            "CREATE PARTITION SCHEME [ps_logs] AS PARTITION [pf_logs] " "ALL TO ([PRIMARY])",
        ),
        forbidden_fragments=("TO ([PRIMARY],",),
        expected_partition_count=3,
        expected_direction="RIGHT",
        expected_filegroups=(),
        expected_next_filegroup="PRIMARY",
    ),
    PartitionSyntaxCase(
        name="scheme_filegroups",
        description="A scheme may name one destination per partition.",
        plan_builder=_plan_builder(
            function="pf_logs",
            data_type="DATE",
            boundaries=_BOUNDARIES,
            scheme="ps_logs",
            filegroups=("PRIMARY", "fg1", "fg2"),
        ),
        ddl_builder=_scheme_ddl,
        expected_fragments=("TO ([PRIMARY], [fg1], [fg2])",),
        forbidden_fragments=("ALL TO",),
        expected_partition_count=3,
        expected_direction="RIGHT",
        expected_filegroups=("PRIMARY", "fg1", "fg2"),
        expected_next_filegroup="fg2",
    ),
    PartitionSyntaxCase(
        name="next_used",
        description="NEXT USED marks the filegroup a later SPLIT consumes.",
        plan_builder=_plan_builder(
            function="pf_logs",
            data_type="DATE",
            boundaries=_BOUNDARIES,
            scheme="ps_logs",
            filegroups=("PRIMARY", "fg1", "fg2"),
        ),
        ddl_builder=_next_used_ddl,
        expected_fragments=("ALTER PARTITION SCHEME [ps_logs] NEXT USED [fg2]",),
        forbidden_fragments=("SPLIT RANGE",),
        expected_partition_count=3,
        expected_direction="RIGHT",
        expected_filegroups=("PRIMARY", "fg1", "fg2"),
        expected_next_filegroup="fg2",
    ),
    PartitionSyntaxCase(
        name="multi_boundary",
        description="N boundaries describe N + 1 partitions.",
        plan_builder=_plan_builder(
            function="pf_logs", data_type="DATE", boundaries=_THREE_BOUNDARIES
        ),
        ddl_builder=_function_ddl,
        expected_fragments=("FOR VALUES ('2026-01-01', '2026-02-01', '2026-03-01')",),
        forbidden_fragments=("RANGE LEFT",),
        expected_partition_count=4,
        expected_direction="RIGHT",
    ),
    PartitionSyntaxCase(
        name="no_subpartition_refused",
        description="SQL Server has no subpartitioning at any version.",
        plan_builder=_plan_builder(
            function="pf_logs",
            data_type="DATE",
            boundaries=_BOUNDARIES,
            subpartition_by="HASH",
        ),
        refuse_subpartition=True,
    ),
    PartitionSyntaxCase(
        name="split",
        description="SPLIT RANGE adds one boundary, and therefore one partition.",
        plan_builder=_plan_builder(function="pf_logs", data_type="DATE", boundaries=_BOUNDARIES),
        ddl_builder=_split_ddl,
        expected_fragments=("ALTER PARTITION FUNCTION [pf_logs] () SPLIT RANGE ('2026-03-01')",),
        forbidden_fragments=("MERGE RANGE", "DROP PARTITION"),
        expected_partition_count=3,
        expected_direction="RIGHT",
    ),
    PartitionSyntaxCase(
        name="merge",
        description="MERGE RANGE removes one boundary without dropping a table.",
        plan_builder=_plan_builder(function="pf_logs", data_type="DATE", boundaries=_BOUNDARIES),
        ddl_builder=_merge_ddl,
        expected_fragments=("ALTER PARTITION FUNCTION [pf_logs] () MERGE RANGE ('2026-01-01')",),
        forbidden_fragments=("SPLIT RANGE", "DROP PARTITION"),
        expected_partition_count=3,
        expected_direction="RIGHT",
    ),
    PartitionSyntaxCase(
        name="switch",
        description="SWITCH PARTITION moves storage to another table.",
        ddl_builder=_switch_ddl,
        expected_fragments=("ALTER TABLE [dbo].[logs] SWITCH PARTITION 2 TO [dbo].[logs_archive]",),
        forbidden_fragments=("SPLIT RANGE", "MERGE RANGE", "DROP TABLE"),
    ),
    PartitionSyntaxCase(
        name="drop_function_scheme",
        description="Drops are dependency-checked and have no IF EXISTS spelling.",
        plan_builder=_plan_builder(
            function="pf_logs",
            data_type="DATE",
            boundaries=_BOUNDARIES,
            scheme="ps_logs",
            all_filegroup="PRIMARY",
        ),
        ddl_builder=_drops_ddl,
        expected_fragments=(
            "DROP PARTITION SCHEME [ps_logs]",
            "DROP PARTITION FUNCTION [pf_logs]",
        ),
        forbidden_fragments=("IF EXISTS", "CASCADE"),
        expected_partition_count=3,
        expected_direction="RIGHT",
    ),
)


@pytest.fixture(
    params=CASES,
    ids=[case.name for case in CASES],
)
def partition_syntax_case(request: pytest.FixtureRequest) -> PartitionSyntaxCase:
    """Yield one declared syntax family at a time, identified by its name."""
    return request.param
