# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/ddl/test_partition_suggestions.py
"""Offline contract tests for the 8 SQL Server partition suggestion methods.

No server is needed: the dialect's own formatters render each suggestion's
expression chain, so these tests verify both the tri-state shape and that the
returned nodes are real SQL Server expressions rather than hand-built SQL.
SQL Server's answers must stay faithful to its three-tier model: SPLIT RANGE
adds a boundary, MERGE RANGE removes one (there is no DROP PARTITION), and the
scaffolding drops happen in dependency order.
"""

import dataclasses
import importlib
import sys
from datetime import date, datetime
from decimal import Decimal

import pytest

from rhosocial.activerecord.backend.dialect.protocols import (
    PartitionAddSuggestionSupport,
    PartitionBuildSuggestionSupport,
    PartitionDropSuggestionSupport,
    PartitionMergeSuggestionSupport,
    PartitionRetentionSuggestionSupport,
    PartitionSplitSuggestionSupport,
    PartitionTableAlterSuggestionSupport,
    PartitionTableDropSuggestionSupport,
)
from rhosocial.activerecord.backend.expression import (
    PartitionAddSuggestion,
    PartitionBuildSuggestion,
    PartitionDropSuggestion,
    PartitionMergeSuggestion,
    PartitionRetentionSuggestion,
    PartitionSplitSuggestion,
    PartitionTableAlterSuggestion,
    PartitionTableDropSuggestion,
)
from rhosocial.activerecord.backend.expression.statements import PartitionStrategy
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression.partition import (
    SQLServerDropPartitionFunctionExpression,
    SQLServerDropPartitionSchemeExpression,
    SQLServerPartitionByRangeClause,
    SQLServerPartitionFunctionExpression,
    SQLServerPartitionFunctionMergeExpression,
    SQLServerPartitionFunctionSplitExpression,
    SQLServerPartitionSchemeExpression,
    SQLServerPartitionSchemeNextUsedExpression,
)
from rhosocial.activerecord.backend.impl.sqlserver.partition import SQLServerPartitionPlan

PROTOCOLS = (
    ("build", PartitionBuildSuggestionSupport, PartitionBuildSuggestion),
    ("table_drop", PartitionTableDropSuggestionSupport, PartitionTableDropSuggestion),
    ("table_alter", PartitionTableAlterSuggestionSupport, PartitionTableAlterSuggestion),
    ("add", PartitionAddSuggestionSupport, PartitionAddSuggestion),
    ("drop", PartitionDropSuggestionSupport, PartitionDropSuggestion),
    ("split", PartitionSplitSuggestionSupport, PartitionSplitSuggestion),
    ("merge", PartitionMergeSuggestionSupport, PartitionMergeSuggestion),
    ("retention", PartitionRetentionSuggestionSupport, PartitionRetentionSuggestion),
)


@pytest.fixture
def dialect():
    return SQLServerDialect((16, 0, 0))


def _plan(**overrides):
    values = {
        "function": "pf_logs",
        "data_type": "DATE",
        "boundaries": (date(2026, 1, 1), date(2026, 2, 1)),
        "scheme": "ps_logs",
        "all_filegroup": "PRIMARY",
    }
    values.update(overrides)
    return SQLServerPartitionPlan(**values)


def _sql(operations):
    return " ".join(expr.to_sql()[0] for expr in operations)


def test_dialect_satisfies_all_eight_protocols(dialect):
    for _name, protocol, _dataclass in PROTOCOLS:
        assert isinstance(dialect, protocol)


def test_suggestion_values_are_frozen_dataclasses(dialect):
    for name, _protocol, cls in PROTOCOLS:
        suggestion = getattr(dialect, f"suggest_partition_{name}")(PartitionStrategy.RANGE, None)
        assert isinstance(suggestion, cls)
        assert dataclasses.is_dataclass(suggestion)
        with pytest.raises(dataclasses.FrozenInstanceError):
            suggestion.operations = False


def test_build_returns_three_tier_chain(dialect):
    plan = _plan()
    suggestion = dialect.suggest_partition_build(PartitionStrategy.RANGE, plan)
    assert len(suggestion.operations) == 2
    assert isinstance(suggestion.operations[0], SQLServerPartitionFunctionExpression)
    assert isinstance(suggestion.operations[1], SQLServerPartitionSchemeExpression)
    sql = _sql(suggestion.operations)
    assert "CREATE PARTITION FUNCTION [pf_logs] (DATE) AS RANGE RIGHT" in sql
    assert "CREATE PARTITION SCHEME [ps_logs] AS PARTITION [pf_logs] ALL TO ([PRIMARY])" in sql

    with_keys = dialect.suggest_partition_build(
        PartitionStrategy.RANGE,
        {**plan.__dict__, "keys": ["created_at"]},
    )
    assert len(with_keys.operations) == 3
    assert isinstance(with_keys.operations[2], SQLServerPartitionByRangeClause)
    assert "ON [ps_logs] ([created_at])" in _sql(with_keys.operations)

    left = dialect.suggest_partition_build(
        PartitionStrategy.RANGE,
        {"function": "pf", "data_type": "INT", "boundaries": (1, 2), "range_direction": "LEFT"},
    )
    assert "AS RANGE LEFT FOR VALUES (1, 2)" in _sql(left.operations)


def test_build_declines_unsupported_strategies_and_incomplete_plans(dialect):
    for strategy in (PartitionStrategy.LIST, PartitionStrategy.HASH, "SPATIAL"):
        assert dialect.suggest_partition_build(strategy, _plan()).operations is False
    assert dialect.suggest_partition_build(PartitionStrategy.RANGE, {}).operations is False
    assert (
        dialect.suggest_partition_build(
            PartitionStrategy.RANGE, {"function": "pf", "data_type": "DATE", "boundaries": ()}
        ).operations
        is False
    )


def test_table_drop_drops_scheme_then_function(dialect):
    suggestion = dialect.suggest_partition_table_drop(PartitionStrategy.RANGE, _plan())
    assert isinstance(suggestion.operations[0], SQLServerDropPartitionSchemeExpression)
    assert isinstance(suggestion.operations[1], SQLServerDropPartitionFunctionExpression)
    sql = _sql(suggestion.operations)
    assert sql == "DROP PARTITION SCHEME [ps_logs] DROP PARTITION FUNCTION [pf_logs]"
    assert "DROP TABLE" not in sql
    assert dialect.suggest_partition_table_drop(PartitionStrategy.RANGE, {}).operations is False


def test_table_alter_has_no_in_place_mechanism(dialect):
    for strategy in PartitionStrategy:
        assert dialect.suggest_partition_table_alter(strategy, _plan()).operations is False


def test_add_is_next_used_then_split_range(dialect):
    plan = {**_plan().__dict__, "boundary": date(2026, 3, 1)}
    suggestion = dialect.suggest_partition_add(PartitionStrategy.RANGE, plan)
    assert isinstance(suggestion.operations[0], SQLServerPartitionSchemeNextUsedExpression)
    assert isinstance(suggestion.operations[1], SQLServerPartitionFunctionSplitExpression)
    sql = _sql(suggestion.operations)
    assert "ALTER PARTITION SCHEME [ps_logs] NEXT USED [PRIMARY]" in sql
    assert "ALTER PARTITION FUNCTION [pf_logs] () SPLIT RANGE ('2026-03-01')" in sql
    assert "ADD PARTITION" not in sql
    assert dialect.suggest_partition_add(PartitionStrategy.HASH, plan).operations is False
    assert dialect.suggest_partition_add(PartitionStrategy.RANGE, {}).operations is False


def test_drop_is_merge_range_not_drop_partition(dialect):
    suggestion = dialect.suggest_partition_drop(PartitionStrategy.RANGE, _plan())
    assert isinstance(suggestion.operations[0], SQLServerPartitionFunctionMergeExpression)
    sql = _sql(suggestion.operations)
    assert "ALTER PARTITION FUNCTION [pf_logs] () MERGE RANGE ('2026-01-01')" in sql
    assert "DROP PARTITION" not in sql
    assert (
        dialect.suggest_partition_drop(PartitionStrategy.RANGE, {"function": "pf"}).operations
        is None
    )
    assert dialect.suggest_partition_drop(PartitionStrategy.LIST, _plan()).operations is False


def test_split_is_next_used_then_split_range(dialect):
    plan = {**_plan().__dict__, "boundary": date(2026, 1, 15)}
    suggestion = dialect.suggest_partition_split(PartitionStrategy.RANGE, plan)
    assert isinstance(suggestion.operations[0], SQLServerPartitionSchemeNextUsedExpression)
    assert isinstance(suggestion.operations[1], SQLServerPartitionFunctionSplitExpression)
    assert "SPLIT RANGE ('2026-01-15')" in _sql(suggestion.operations)
    assert dialect.suggest_partition_split(PartitionStrategy.HASH, plan).operations is False


def test_merge_is_merge_range(dialect):
    suggestion = dialect.suggest_partition_merge(PartitionStrategy.RANGE, _plan())
    assert isinstance(suggestion.operations[0], SQLServerPartitionFunctionMergeExpression)
    assert "MERGE RANGE ('2026-01-01')" in _sql(suggestion.operations)
    assert (
        dialect.suggest_partition_merge(PartitionStrategy.RANGE, {"function": "pf"}).operations
        is False
    )


def test_retention_merges_boundaries_at_or_before_cutoff(dialect):
    plan = {
        "function": "pf_logs",
        "data_type": "DATE",
        "boundaries": (date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)),
        "cutoff": date(2026, 2, 1),
    }
    suggestion = dialect.suggest_partition_retention(PartitionStrategy.RANGE, plan)
    assert len(suggestion.operations) == 2
    assert all(
        isinstance(operation, SQLServerPartitionFunctionMergeExpression)
        for operation in suggestion.operations
    )
    sql = _sql(suggestion.operations)
    assert "MERGE RANGE ('2026-01-01')" in sql
    assert "MERGE RANGE ('2026-02-01')" in sql
    assert "MERGE RANGE ('2026-03-01')" not in sql
    assert "DROP PARTITION" not in sql

    nothing = dialect.suggest_partition_retention(
        PartitionStrategy.RANGE, {**plan, "cutoff": date(2025, 12, 31)}
    )
    assert nothing.operations is None
    assert (
        dialect.suggest_partition_retention(
            PartitionStrategy.RANGE, {k: v for k, v in plan.items() if k != "cutoff"}
        ).operations
        is False
    )
    assert dialect.suggest_partition_retention(PartitionStrategy.LIST, plan).operations is False


def test_retention_handles_numeric_and_datetime_boundaries(dialect):
    numeric = dialect.suggest_partition_retention(
        PartitionStrategy.RANGE,
        {
            "function": "pf_amount",
            "data_type": "DECIMAL(10, 2)",
            "boundaries": (Decimal("10.5"), Decimal("20.5"), Decimal("30.5")),
            "cutoff": "20.5",
        },
    )
    assert len(numeric.operations) == 2

    stamp = dialect.suggest_partition_retention(
        PartitionStrategy.RANGE,
        {
            "function": "pf_events",
            "data_type": "DATETIME2",
            "boundaries": (datetime(2026, 1, 1), datetime(2026, 3, 1)),
            "cutoff": datetime(2026, 2, 1),
        },
    )
    assert len(stamp.operations) == 1
    assert "MERGE RANGE ('2026-01-01 00:00:00')" in _sql(stamp.operations)


def test_old_version_declines_mutating_chains():
    old = SQLServerDialect((9, 0, 0))
    for name in ("add", "drop", "split", "merge", "retention"):
        suggestion = getattr(old, f"suggest_partition_{name}")(PartitionStrategy.RANGE, _plan())
        assert suggestion.operations is False


def test_suggestion_mixin_imports_with_maintenance_blocked(monkeypatch):
    """The suggestion module must not import a maintenance/report module.

    Blocking those names in ``sys.modules`` while (re)importing the module and
    exercising every method proves the mixin is self-contained. This holds
    both before and after the maintenance protocol is retired.
    """
    for suffix in ("partition.maintenance", "partition.report"):
        name = f"rhosocial.activerecord.backend.impl.sqlserver.{suffix}"
        monkeypatch.setitem(sys.modules, name, None)
    module_name = "rhosocial.activerecord.backend.impl.sqlserver.mixins.partition_suggestion"
    monkeypatch.delitem(sys.modules, module_name, raising=False)
    module = importlib.import_module(module_name)

    # Call the freshly imported mixin's methods unbound on a real dialect, so
    # the expression nodes get a valid dialect for rendering.
    dialect = SQLServerDialect((16, 0, 0))
    plan = {**_plan().__dict__, "boundary": date(2026, 3, 1), "cutoff": date(2026, 2, 1)}
    for name, _protocol, cls in PROTOCOLS:
        method = getattr(module.SQLServerPartitionSuggestionMixin, f"suggest_partition_{name}")
        suggestion = method(dialect, PartitionStrategy.RANGE, plan)
        assert isinstance(suggestion, cls)
        assert dataclasses.is_dataclass(suggestion)
