# docs/examples/ar-migration/02_partition_lifecycle.py
"""Offline SQL Server partition LIFECYCLE suggestions -- no connection, no ctx.apply().

SQL Server has no ``ADD PARTITION`` and no ``DROP PARTITION``. A boundary is
added with SPLIT RANGE and removed with MERGE RANGE -- both move rows, so they
are data-affecting, not metadata-only. This script renders the real chains for
each lifecycle point. Every SQL line printed comes from ``expr.to_sql()[0]``;
the only non-SQL output is short status text for declined/no-op suggestions.

Run from the repository root:

    $env:PYTHONPATH = 'src'
    .venv3.14\\Scripts\\python.exe docs/examples/ar-migration/02_partition_lifecycle.py
"""

from datetime import date, datetime
from decimal import Decimal

from rhosocial.activerecord.backend.expression import Column
from rhosocial.activerecord.backend.expression.statements import PartitionByRangeClause
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

DIALECT = SQLServerDialect((16, 0, 0))

# A strategy is now a clause expression rather than an enum member.
RANGE = PartitionByRangeClause(DIALECT, [Column(DIALECT, "created_at")])


def render(suggestion):
    """Print one suggestion's chain. SQL text is read only from ``to_sql()``."""
    operations = suggestion.operations
    if operations is False:
        print("  operations is False (SQL Server has no such chain for this request)")
    elif operations is None:
        print("  operations is None (nothing to do)")
    else:
        for expr in operations:
            print(f"  {expr.to_sql()[0]}")


def base_plan(**overrides):
    """A DATE RANGE plan with a scheme, so NEXT USED can be shown on splits."""
    plan = {
        "function": "pf_logs",
        "data_type": "DATE",
        "boundaries": (date(2026, 1, 1), date(2026, 2, 1)),
        "scheme": "ps_logs",
        "all_filegroup": "PRIMARY",
    }
    plan.update(overrides)
    return plan


def scenario_add():
    """ADD a new boundary: NEXT USED on the scheme, then SPLIT RANGE (moves rows)."""
    print("== 1. ADD a boundary = NEXT USED + SPLIT RANGE (data-affecting) ==")
    plan = base_plan(boundary=date(2026, 3, 1))
    render(DIALECT.suggest_partition_add(RANGE, plan))


def scenario_split():
    """SPLIT an existing populated range at a mid-point: rows move to a new partition."""
    print("== 2. SPLIT an existing range = NEXT USED + SPLIT RANGE (data-affecting) ==")
    plan = base_plan(boundary=date(2026, 1, 15))
    render(DIALECT.suggest_partition_split(RANGE, plan))


def scenario_drop():
    """DROP a partition: MERGE RANGE, never DROP PARTITION (rows move out)."""
    print("== 3. DROP a partition = MERGE RANGE, not DROP PARTITION (data-affecting) ==")
    # With no explicit ``boundary``, DROP acts on the oldest boundary.
    render(DIALECT.suggest_partition_drop(RANGE, base_plan()))


def scenario_merge():
    """MERGE with an explicit boundary: the boundary itself is removed."""
    print("== 4. MERGE an explicit boundary = MERGE RANGE (data-affecting) ==")
    plan = base_plan(boundary=date(2026, 1, 1))
    render(DIALECT.suggest_partition_merge(RANGE, plan))


def scenario_retention():
    """RETENTION merges every boundary at or before the cutoff, in order."""
    print("== 5. RETENTION = one MERGE RANGE per boundary <= cutoff ==")
    plan = base_plan(
        boundaries=(date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)),
        cutoff=date(2026, 2, 1),
    )
    render(DIALECT.suggest_partition_retention(RANGE, plan))

    print("  -- numeric boundaries, cutoff given as text:")
    numeric = {
        "function": "pf_amount",
        "data_type": "DECIMAL(10, 2)",
        "boundaries": (Decimal("10.5"), Decimal("20.5"), Decimal("30.5")),
        "cutoff": "20.5",
    }
    render(DIALECT.suggest_partition_retention(RANGE, numeric))

    print("  -- DATETIME2 boundaries:")
    stamps = {
        "function": "pf_events",
        "data_type": "DATETIME2",
        "boundaries": (datetime(2026, 1, 1), datetime(2026, 3, 1)),
        "cutoff": datetime(2026, 2, 1),
    }
    render(DIALECT.suggest_partition_retention(RANGE, stamps))


def scenario_scaffolding():
    """Scaffolding teardown has a fixed order; in-place ALTER has no chain."""
    print("== 6. TABLE DROP = drop scheme, then function (no DROP TABLE) ==")
    render(DIALECT.suggest_partition_table_drop(RANGE, base_plan()))

    print("== 7. TABLE ALTER = False (no in-place mechanism) ==")
    render(DIALECT.suggest_partition_table_alter(RANGE, base_plan()))


def scenario_version_gate():
    """A (9, 0, 0) dialect withdraws every chain that mutates partitions."""
    print("== 8. version gate: SQLServerDialect((9, 0, 0)) declines ==")
    old = SQLServerDialect((9, 0, 0))
    plan = base_plan(boundary=date(2026, 3, 1), cutoff=date(2026, 2, 1))
    for name in ("build", "add", "drop", "split", "merge", "retention", "table_drop"):
        suggestion = getattr(old, f"suggest_partition_{name}")(RANGE, plan)
        print(f"  {name}: operations is {suggestion.operations}")


def main():
    print("SQL Server partition LIFECYCLE suggestions (offline, version 16.0.0)")
    scenario_add()
    scenario_split()
    scenario_drop()
    scenario_merge()
    scenario_retention()
    scenario_scaffolding()
    scenario_version_gate()


if __name__ == "__main__":
    main()
