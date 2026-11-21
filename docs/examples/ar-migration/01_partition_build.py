# docs/examples/ar-migration/01_partition_build.py
"""Offline SQL Server partition BUILD suggestions -- no connection, no ctx.apply().

Shows the DDL this backend actually suggests at CREATE TABLE time. SQL Server
builds a partitioned table in three tiers: a partition FUNCTION fixes the
boundary values, a partition SCHEME maps them to filegroups, and the table is
created ON the scheme. Every SQL line printed here comes from
``expr.to_sql()[0]``; nothing is hand-written, and no database is contacted.

Run from the repository root:

    $env:PYTHONPATH = 'src'
    .venv3.14\\Scripts\\python.exe docs/examples/ar-migration/01_partition_build.py
"""

from datetime import date

from rhosocial.activerecord.backend.expression.statements import PartitionStrategy
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

# A modern server: the (10, 0, 0) partitioning gate is open. See script 02 and
# the README for what a (9, 0, 0) dialect does instead.
DIALECT = SQLServerDialect((16, 0, 0))


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


def scenario_function_and_scheme():
    """Two tiers: partition function + partition scheme (ALL TO one filegroup)."""
    print("== 1. RANGE RIGHT DATE function + scheme ==")
    plan = {
        "function": "pf_logs",
        "data_type": "DATE",
        "boundaries": (date(2026, 1, 1), date(2026, 2, 1)),
        "scheme": "ps_logs",
        "all_filegroup": "PRIMARY",
    }
    render(DIALECT.suggest_partition_build(PartitionStrategy.RANGE, plan))


def scenario_with_partition_key():
    """Three tiers: the optional ``keys`` field adds the table's ON clause."""
    print("== 2. add the table's ON key (three-tier chain) ==")
    plan = {
        "function": "pf_orders",
        "data_type": "DATE",
        "boundaries": (date(2026, 1, 1), date(2026, 2, 1)),
        "scheme": "ps_orders",
        "all_filegroup": "PRIMARY",
        "keys": ["created_at"],
    }
    render(DIALECT.suggest_partition_build(PartitionStrategy.RANGE, plan))


def scenario_range_left_with_filegroups():
    """RANGE LEFT and one explicit filegroup per partition (N boundaries = N+1)."""
    print("== 3. RANGE LEFT with INT boundaries and explicit filegroups ==")
    plan = {
        "function": "pf_amount",
        "data_type": "INT",
        "boundaries": (1, 2),
        "range_direction": "LEFT",
        "scheme": "ps_amount",
        "filegroups": ("FG_A", "FG_B", "FG_C"),
    }
    render(DIALECT.suggest_partition_build(PartitionStrategy.RANGE, plan))


def scenario_declines():
    """Tri-state: ``False`` for a non-RANGE strategy or an incomplete plan."""
    print("== 4. declined requests (no chain, printed as a status not SQL) ==")
    plan = {
        "function": "pf_logs",
        "data_type": "DATE",
        "boundaries": (date(2026, 1, 1), date(2026, 2, 1)),
        "scheme": "ps_logs",
        "all_filegroup": "PRIMARY",
    }
    print("  -- LIST strategy:")
    render(DIALECT.suggest_partition_build(PartitionStrategy.LIST, plan))
    print("  -- empty plan:")
    render(DIALECT.suggest_partition_build(PartitionStrategy.RANGE, {}))


def main():
    print("SQL Server partition BUILD suggestions (offline, version 16.0.0)")
    scenario_function_and_scheme()
    scenario_with_partition_key()
    scenario_range_left_with_filegroups()
    scenario_declines()


if __name__ == "__main__":
    main()
