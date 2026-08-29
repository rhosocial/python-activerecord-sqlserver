# tests/providers/pooling.py
"""Database pooling helpers for the SQL Server test providers.

Under parallel (pytest-xdist) runs with a positive pool size the providers
reuse a per-worker pooled database ``{database}_{index}`` on the scenario's SQL
Server instance instead of the shared scenario ``database`` schema, so scenario
variants of the same test can run concurrently on different workers without
conflicting. The pool name prefix is derived from the scenario's configured
``database`` (the YAML ``database`` field), so e.g. ``database: master``
produces pooled databases ``master_0``, ``master_1``, ... Serial runs (no
``-n``) keep the previous behaviour: the provider connects to the scenario's
configured ``database``.

The scenario name selects the server (host/port); the pool index selects the
database name. The two are deliberately unrelated.
"""

import pyodbc
from dataclasses import replace

from rhosocial.activerecord.testsuite.core.pool import (
    pooled_database_name,
    register_base_database,
    register_pool_reset_handler,
)

from .scenarios import SCENARIO_MAP, get_scenario_raw

# Derive each scenario's pooled-database base name from its configured
# ``database`` (YAML ``database`` field). Registered at import time so any
# caller of pooled_database_name() / resolve_database_name() resolves names
# consistent with the scenario configuration.
for _scenario_name, _scenario_config in SCENARIO_MAP.items():
    register_base_database(_scenario_name, _scenario_config["database"])


def resolve_database_name(scenario_name: str):
    """
    Return the pooled database name (e.g. ``master_3``) used by a test for
    the given scenario, or ``None`` when pooling is inactive (callers then fall
    back to the scenario's configured database).
    """
    return pooled_database_name(scenario_name)


def _escape_literal(name: str) -> str:
    """Escape a SQL Server string literal (single quotes doubled)."""
    return name.replace("'", "''")


def _escape_bracket(name: str) -> str:
    """Escape a SQL Server identifier for use inside square brackets."""
    return name.replace("]", "]]")


def _connect_admin(config) -> pyodbc.Connection:
    """Connect to the ``master`` maintenance database of the scenario's server."""
    admin_config = replace(config, database="master")
    return pyodbc.connect(
        admin_config.build_connection_string(),
        autocommit=True,
        timeout=config.timeout or 10,
    )


def _reset_sqlserver_database(scenario_name: str, db_name: str) -> None:
    """Ensure the pooled database exists and is empty on the scenario's server.

    Connects to ``master`` on the server selected by ``scenario_name``, drops
    the pooled ``db_name`` database if it exists (forcing existing connections
    closed) and recreates it empty, so the test starts from a clean state.
    Errors are swallowed: a failed reset must not hide the underlying test
    failure.
    """
    if scenario_name not in SCENARIO_MAP:
        return
    _, config = get_scenario_raw(scenario_name)
    try:
        conn = _connect_admin(config)
        try:
            with conn.cursor() as cursor:
                db_escaped = _escape_bracket(db_name)
                cursor.execute(
                    f"SELECT COUNT(*) FROM sys.databases "
                    f"WHERE name = N'{_escape_literal(db_name)}'"
                )
                if not cursor.fetchone()[0]:
                    cursor.execute(f"CREATE DATABASE [{db_escaped}]")
                    cursor.execute(
                        f"ALTER DATABASE [{db_escaped}] "
                        "SET READ_COMMITTED_SNAPSHOT ON"
                    )
                    return
                cursor.execute(
                    f"SELECT COUNT(*) FROM [{db_escaped}].sys.tables "
                    f"WHERE is_ms_shipped = 0"
                )
                if not cursor.fetchone()[0]:
                    return
                cursor.execute(
                    f"ALTER DATABASE [{db_escaped}] "
                    "SET SINGLE_USER WITH ROLLBACK IMMEDIATE"
                )
                cursor.execute(f"DROP DATABASE [{db_escaped}]")
                cursor.execute(f"CREATE DATABASE [{db_escaped}]")
                cursor.execute(
                    f"ALTER DATABASE [{db_escaped}] "
                    "SET READ_COMMITTED_SNAPSHOT ON"
                )
        finally:
            conn.close()
    except Exception:
        pass


register_pool_reset_handler(_reset_sqlserver_database)
