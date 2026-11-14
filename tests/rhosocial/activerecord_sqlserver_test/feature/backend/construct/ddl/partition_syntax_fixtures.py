# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/ddl/partition_syntax_fixtures.py
"""Fixture-driven matrix of SQL Server partition syntax families.

Each :class:`PartitionSyntaxCase` names one family of SQL Server's three-tier
partition model -- the ``RANGE LEFT``/``RANGE RIGHT`` function, the scheme
destinations, ``NEXT USED``, ``SPLIT``/``MERGE``/``SWITCH``, the dependency
checked drops, and the maintenance executor's decisions -- and carries the
builders the offline matrix uses to exercise it.

The cases do not repeat the exact assertions of
``test_partition_expressions.py`` or ``test_partition_maintenance.py``;
they collect the families those files cover into one parameterised table so a
new syntax family is added in one place. No server is needed: every builder
returns a plan, an expression, or a maintenance report built from canned
catalogue rows.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Mapping, Optional, Sequence, Tuple

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
    PartitionFunctionInfo,
    PartitionRangeInfo,
    PartitionReport,
    PartitionSchemeInfo,
    PartitionTableInfo,
    SQLServerPartitionMaintenance,
    SQLServerPartitionPlan,
)

#: Build a plan with no arguments, or refuse at construction when it asks for
#: something SQL Server cannot express.
PlanBuilder = Callable[[], SQLServerPartitionPlan]

#: Render one family's statements; the plan is ``None`` only for a case that
#: does not need one (``SWITCH`` names two tables instead).
DDLBuilder = Callable[
    [SQLServerDialect, Optional[SQLServerPartitionPlan]], Sequence[Any]
]

#: Run a maintenance operation set and return its reports, keyed by operation.
MaintenanceBuilder = Callable[
    [SQLServerDialect], Mapping[str, PartitionReport]
]

#: Reserved for a live suite: set up the family against a server, then check
#: what only a server can answer. The offline matrix never calls either hook.
LiveHook = Callable[[Any, SQLServerPartitionPlan], Any]

_BOUNDARIES = (date(2026, 1, 1), date(2026, 2, 1))
_THREE_BOUNDARIES = _BOUNDARIES + (date(2026, 3, 1),)
_SPLIT_BOUNDARY = date(2026, 3, 1)


@dataclass(frozen=True)
class MaintenanceExpectation:
    """What one maintenance operation should decide.

    Attributes:
        operation: The report key the case's maintenance builder returns.
        actions: Expected ``PartitionOperation.action`` values, in order.
        missing_boundaries: Expected ``report.missing_boundaries``; ``None``
            skips the check.
        existing_boundaries: Expected ``report.existing_boundaries``; ``None``
            skips the check.
        issue_fragments: Substrings that must appear in at least one issue.
        sql_fragments: Substrings that must appear in at least one operation's
            rendered SQL.
        expect_dry_run: Expected ``report.dry_run``; ``None`` skips the check,
            because a read-only ``list``/``validate`` is neither a dry run nor
            an execution.
    """

    operation: str
    actions: Tuple[str, ...] = ()
    missing_boundaries: Optional[Tuple[Any, ...]] = None
    existing_boundaries: Optional[Tuple[str, ...]] = None
    issue_fragments: Tuple[str, ...] = ()
    sql_fragments: Tuple[str, ...] = ()
    expect_dry_run: Optional[bool] = None


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
        maintenance_builder: Runs the maintenance operations to inspect.
        maintenance_expectations: One expectation per operation the builder
            returns.
        live_setup: Optional live-suite setup hook (offline tests ignore it).
        live_check: Optional live-suite assertion hook (offline tests ignore it).
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
    maintenance_builder: Optional[MaintenanceBuilder] = None
    maintenance_expectations: Tuple[MaintenanceExpectation, ...] = ()
    live_setup: Optional[LiveHook] = None
    live_check: Optional[LiveHook] = None


def _plan_builder(**overrides: Any) -> PlanBuilder:
    """Return a builder for a plan carrying *overrides*."""

    def build() -> SQLServerPartitionPlan:
        return SQLServerPartitionPlan(**overrides)

    return build


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


def _scheme_ddl(
    dialect: SQLServerDialect, plan: Optional[SQLServerPartitionPlan]
) -> Sequence[Any]:
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
    return (
        SQLServerPartitionSchemeNextUsedExpression(
            dialect, plan.scheme, plan.next_filegroup
        ),
    )


def _split_ddl(
    dialect: SQLServerDialect, plan: Optional[SQLServerPartitionPlan]
) -> Sequence[Any]:
    """Render ``SPLIT RANGE`` at a boundary the plan does not yet hold."""
    return (
        SQLServerPartitionFunctionSplitExpression(
            dialect, plan.function, _SPLIT_BOUNDARY
        ),
    )


def _merge_ddl(
    dialect: SQLServerDialect, plan: Optional[SQLServerPartitionPlan]
) -> Sequence[Any]:
    """Render ``MERGE RANGE`` at the plan's first boundary."""
    return (
        SQLServerPartitionFunctionMergeExpression(
            dialect, plan.function, plan.boundaries[0]
        ),
    )


def _switch_ddl(
    dialect: SQLServerDialect, plan: Optional[SQLServerPartitionPlan]
) -> Sequence[Any]:
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


def _drops_ddl(
    dialect: SQLServerDialect, plan: Optional[SQLServerPartitionPlan]
) -> Sequence[Any]:
    """Render the scheme drop before the function drop."""
    return (
        SQLServerDropPartitionSchemeExpression(dialect, plan.scheme),
        SQLServerDropPartitionFunctionExpression(dialect, plan.function),
    )


# ---------------------------------------------------------------------------
# Canned catalogue rows for the maintenance families
# ---------------------------------------------------------------------------


def _canned_function() -> PartitionFunctionInfo:
    """A function with two boundaries, so it has three partitions."""
    return PartitionFunctionInfo(
        name="pf_logs",
        data_type="date",
        range_direction="RIGHT",
        boundary_values=("2026-01-01", "2026-02-01"),
        partition_count=3,
    )


def _canned_scheme() -> PartitionSchemeInfo:
    """The scheme mapping the canned function, with a spare destination."""
    return PartitionSchemeInfo(
        name="ps_logs",
        function="pf_logs",
        filegroups=("PRIMARY", "PRIMARY", "PRIMARY", "PRIMARY"),
        partition_count=3,
    )


def _canned_table() -> PartitionTableInfo:
    """One table built on the canned scheme."""
    return PartitionTableInfo(
        name="logs",
        schema="dbo",
        scheme="ps_logs",
        function="pf_logs",
        partition_column="created_at",
        partition_count=3,
    )


def _canned_ranges() -> Tuple[PartitionRangeInfo, ...]:
    """The three partitions the canned table occupies."""
    return tuple(
        PartitionRangeInfo(table="logs", schema="dbo", partition_number=number)
        for number in (1, 2, 3)
    )


def _two_partition_plan() -> SQLServerPartitionPlan:
    """A plan with two boundaries and ``ALL TO [PRIMARY]``."""
    return SQLServerPartitionPlan(
        function="pf_logs",
        data_type="DATE",
        boundaries=_BOUNDARIES,
        scheme="ps_logs",
        all_filegroup="PRIMARY",
    )


def _three_partition_plan() -> SQLServerPartitionPlan:
    """A plan adding one boundary to :func:`_two_partition_plan`."""
    return SQLServerPartitionPlan(
        function="pf_logs",
        data_type="DATE",
        boundaries=_THREE_BOUNDARIES,
        scheme="ps_logs",
        all_filegroup="PRIMARY",
    )


class _FakeMaintenance(SQLServerPartitionMaintenance):
    """A maintenance executor whose catalogue answers are supplied up front.

    It overrides only the I/O seams, so every decision under test runs the
    same code path as the real executor while ``_execute`` records statements
    instead of running them.
    """

    def __init__(
        self,
        *,
        dialect: SQLServerDialect,
        functions: Sequence[PartitionFunctionInfo] = (),
        schemes: Sequence[PartitionSchemeInfo] = (),
        tables: Sequence[PartitionTableInfo] = (),
        ranges: Sequence[PartitionRangeInfo] = (),
        exists: Optional[Mapping[Any, bool]] = None,
    ) -> None:
        self.dialect = dialect
        self.functions = tuple(functions)
        self.schemes = tuple(schemes)
        self.tables = tuple(tables)
        self.ranges = tuple(ranges)
        self.exists = dict(exists or {})
        self.executed = []

    def _read_functions(
        self, function_name: Optional[str] = None
    ) -> Tuple[PartitionFunctionInfo, ...]:
        return tuple(
            f for f in self.functions if function_name in (None, f.name)
        )

    def _read_schemes(
        self,
        scheme_name: Optional[str] = None,
        function_name: Optional[str] = None,
    ) -> Tuple[PartitionSchemeInfo, ...]:
        return tuple(
            s
            for s in self.schemes
            if scheme_name in (None, s.name)
            and function_name in (None, s.function)
        )

    def _read_tables(
        self,
        table_name: Optional[str] = None,
        schema: Optional[str] = None,
        scheme_name: Optional[str] = None,
    ) -> Tuple[PartitionTableInfo, ...]:
        return tuple(
            t
            for t in self.tables
            if table_name in (None, t.name)
            and schema in (None, t.schema)
            and scheme_name in (None, t.scheme)
        )

    def _read_ranges(
        self, table_name: str, schema: Optional[str] = None
    ) -> Tuple[PartitionRangeInfo, ...]:
        return tuple(r for r in self.ranges if r.table == table_name)

    def _read_boundary_exists(
        self, plan: SQLServerPartitionPlan
    ) -> Tuple[bool, ...]:
        return tuple(self.exists.get(boundary, False) for boundary in plan.boundaries)

    def _read_boundary_exists_for(
        self, plan: SQLServerPartitionPlan, boundaries: Sequence[Any]
    ) -> Tuple[bool, ...]:
        return tuple(self.exists.get(boundary, False) for boundary in boundaries)

    def _execute(self, sql: str, params: Tuple[Any, ...]) -> None:
        self.executed.append(sql)


def _drop_maintenance(dialect: SQLServerDialect) -> Mapping[str, PartitionReport]:
    """Plan the two dependency-checked drop outcomes.

    The unused scheme is dropped before the function; the used scheme keeps
    both because the catalogue reports a table built on it.
    """
    function = _canned_function()
    scheme = _canned_scheme()
    table = _canned_table()
    plan = _two_partition_plan()
    unused = _FakeMaintenance(
        dialect=dialect, functions=(function,), schemes=(scheme,)
    )
    used = _FakeMaintenance(
        dialect=dialect,
        functions=(function,),
        schemes=(scheme,),
        tables=(table,),
    )
    return {
        "drop_unused": unused.drop_or_merge(
            plan, [], dry_run=True, drop_scaffolding=True
        ),
        "drop_refused": used.drop_or_merge(
            plan, [], dry_run=True, drop_scaffolding=True
        ),
    }


def _all_maintenance_operations(
    dialect: SQLServerDialect,
) -> Mapping[str, PartitionReport]:
    """Run ``ensure``, ``list``, ``drop_or_merge`` and ``validate`` once."""
    function = _canned_function()
    scheme = _canned_scheme()
    table = _canned_table()
    ranges = _canned_ranges()
    plan_two = _two_partition_plan()
    plan_three = _three_partition_plan()
    ensure_fake = _FakeMaintenance(
        dialect=dialect,
        functions=(function,),
        schemes=(scheme,),
        exists={
            date(2026, 1, 1): True,
            date(2026, 2, 1): True,
            date(2026, 3, 1): False,
        },
    )
    report_fake = _FakeMaintenance(
        dialect=dialect,
        functions=(function,),
        schemes=(scheme,),
        tables=(table,),
        ranges=ranges,
        exists={date(2026, 1, 1): True, date(2026, 2, 1): True},
    )
    return {
        "ensure": ensure_fake.ensure(plan_three, dry_run=True),
        "list": report_fake.list(plan_two),
        "drop_or_merge": report_fake.drop_or_merge(
            plan_two, [date(2026, 1, 1)], dry_run=True, drop_scaffolding=True
        ),
        "validate": report_fake.validate(plan_two, table="logs", schema="dbo"),
    }


def _live_ensure(
    backend: Any, plan: SQLServerPartitionPlan
) -> PartitionReport:
    """Reserved for a live suite: create the planned scaffolding."""
    return SQLServerPartitionMaintenance(backend).ensure(plan)


def _live_function_count_matches(
    backend: Any, plan: SQLServerPartitionPlan
) -> bool:
    """Reserved for a live suite: the function now has the planned fanout."""
    report = SQLServerPartitionMaintenance(backend).list(plan)
    info = report.function_info(plan.function)
    return info is not None and info.partition_count == plan.partition_count


# ---------------------------------------------------------------------------
# The matrix
# ---------------------------------------------------------------------------

CASES: Tuple[PartitionSyntaxCase, ...] = (
    PartitionSyntaxCase(
        name="range_right",
        description="RANGE RIGHT owns the boundary value and is the default.",
        plan_builder=_plan_builder(
            function="pf_logs", data_type="DATE", boundaries=_BOUNDARIES
        ),
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
        live_setup=_live_ensure,
        live_check=_live_function_count_matches,
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
        live_setup=_live_ensure,
        live_check=_live_function_count_matches,
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
            "CREATE PARTITION SCHEME [ps_logs] AS PARTITION [pf_logs] "
            "ALL TO ([PRIMARY])",
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
        expected_fragments=(
            "ALTER PARTITION SCHEME [ps_logs] NEXT USED [fg2]",
        ),
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
        expected_fragments=(
            "FOR VALUES ('2026-01-01', '2026-02-01', '2026-03-01')",
        ),
        forbidden_fragments=("RANGE LEFT",),
        expected_partition_count=4,
        expected_direction="RIGHT",
        live_setup=_live_ensure,
        live_check=_live_function_count_matches,
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
        plan_builder=_plan_builder(
            function="pf_logs", data_type="DATE", boundaries=_BOUNDARIES
        ),
        ddl_builder=_split_ddl,
        expected_fragments=(
            "ALTER PARTITION FUNCTION [pf_logs] () SPLIT RANGE ('2026-03-01')",
        ),
        forbidden_fragments=("MERGE RANGE", "DROP PARTITION"),
        expected_partition_count=3,
        expected_direction="RIGHT",
        live_setup=_live_ensure,
        live_check=_live_function_count_matches,
    ),
    PartitionSyntaxCase(
        name="merge",
        description="MERGE RANGE removes one boundary without dropping a table.",
        plan_builder=_plan_builder(
            function="pf_logs", data_type="DATE", boundaries=_BOUNDARIES
        ),
        ddl_builder=_merge_ddl,
        expected_fragments=(
            "ALTER PARTITION FUNCTION [pf_logs] () MERGE RANGE ('2026-01-01')",
        ),
        forbidden_fragments=("SPLIT RANGE", "DROP PARTITION"),
        expected_partition_count=3,
        expected_direction="RIGHT",
        live_setup=_live_ensure,
        live_check=_live_function_count_matches,
    ),
    PartitionSyntaxCase(
        name="switch",
        description="SWITCH PARTITION moves storage to another table.",
        ddl_builder=_switch_ddl,
        expected_fragments=(
            "ALTER TABLE [dbo].[logs] SWITCH PARTITION 2 TO [dbo].[logs_archive]",
        ),
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
        maintenance_builder=_drop_maintenance,
        maintenance_expectations=(
            MaintenanceExpectation(
                operation="drop_unused",
                actions=("drop_scheme", "drop_function"),
                sql_fragments=(
                    "DROP PARTITION SCHEME [ps_logs]",
                    "DROP PARTITION FUNCTION [pf_logs]",
                ),
                expect_dry_run=True,
            ),
            MaintenanceExpectation(
                operation="drop_refused",
                actions=(),
                issue_fragments=("used by 1 table(s)",),
                sql_fragments=(),
                expect_dry_run=True,
            ),
        ),
    ),
    PartitionSyntaxCase(
        name="maintenance_ensure_list_drop_merge_validate",
        description="The four decisions run against canned catalogue rows.",
        plan_builder=_two_partition_plan,
        maintenance_builder=_all_maintenance_operations,
        maintenance_expectations=(
            MaintenanceExpectation(
                operation="ensure",
                actions=("next_used", "split"),
                missing_boundaries=(date(2026, 3, 1),),
                existing_boundaries=("2026-01-01", "2026-02-01"),
                sql_fragments=(
                    "ALTER PARTITION SCHEME [ps_logs] NEXT USED [PRIMARY]",
                    "SPLIT RANGE ('2026-03-01')",
                ),
                expect_dry_run=True,
            ),
            MaintenanceExpectation(
                operation="list",
                actions=(),
                missing_boundaries=(),
                existing_boundaries=("2026-01-01", "2026-02-01"),
            ),
            MaintenanceExpectation(
                operation="drop_or_merge",
                actions=("merge",),
                issue_fragments=("used by 1 table(s)",),
                sql_fragments=("MERGE RANGE ('2026-01-01')",),
                expect_dry_run=True,
            ),
            MaintenanceExpectation(
                operation="validate",
                actions=(),
                missing_boundaries=(),
            ),
        ),
    ),
)


@pytest.fixture(
    params=CASES,
    ids=[case.name for case in CASES],
)
def partition_syntax_case(request: pytest.FixtureRequest) -> PartitionSyntaxCase:
    """Yield one declared syntax family at a time, identified by its name."""
    return request.param
