# tests/support/sqlserver.py
"""The SQL Server backend's test scenarios.

The scenario file holds server connection parameters only; the logical database
name comes from the test directory and is injected here.  SQL Server is a
server backend, so a scenario maps to one database on one instance.

Maintenance work (dropping and creating databases, server-level checks) runs on
the ``master`` database every SQL Server instance ships with, because a
connection cannot drop the database it is currently using.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

from rhosocial.activerecord.backend.impl.sqlserver.backend import (
    AsyncSQLServerBackend,
    SQLServerBackend,
)
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig

CONFIG_PATH = Path(
    os.environ.get("SQLSERVER_SCENARIOS_CONFIG_PATH")
    or Path(__file__).resolve().parents[1] / "config" / "sqlserver_scenarios.yaml"
)

# The scenario file describes a server, never a database: the logical name is
# derived from the test directory.  A ``database`` key, if present, is dropped.
SERVER_ONLY_KEYS = ("database",)

# The database every SQL Server instance has, used for server-level connections.
MAINTENANCE_DATABASE = "master"

DDL_OPTIONS = ExecutionOptions(stmt_type=StatementType.DDL)
DQL_OPTIONS = ExecutionOptions(stmt_type=StatementType.DQL)


def _load_scenarios(path: Path = CONFIG_PATH) -> Dict[str, Dict[str, Any]]:
    """Load one server-parameter dict per scenario from the YAML file."""
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    entries = data.get("scenarios")
    if not entries:
        raise ValueError(f"{path} defines no scenarios")
    return {
        name: {key: value for key, value in entry.items() if key not in SERVER_ONLY_KEYS}
        for name, entry in entries.items()
    }


SCENARIO_MAP = _load_scenarios()
SCENARIOS = tuple(SCENARIO_MAP)


def _identifier(name: str) -> str:
    """Quote a SQL Server identifier (database names come from the testsuite)."""
    return "[" + name.replace("]", "]]") + "]"


@dataclass(frozen=True)
class SQLServerScenario:
    """One SQL Server test scenario: an instance plus the backend classes."""

    name: str
    server: Dict[str, Any]
    backend_class: Any = SQLServerBackend
    async_backend_class: Any = AsyncSQLServerBackend
    maintenance_database: str = "master"

    def make_config(self, database: str) -> SQLServerConnectionConfig:
        """Return the connection configuration for this database on this instance."""
        return SQLServerConnectionConfig(**self.server, database=database)

    def reset_database(self, database: str) -> None:
        """Drop and recreate ``database`` on this scenario's instance.

        ``READ_COMMITTED_SNAPSHOT`` is turned on as part of the creation: the
        concurrency tests read while another connection writes, and statement
        snapshots are what keep those readers from blocking (or deadlocking)
        each other.  The CI workflow used to pre-enable the option on its single
        ``test_db``; every directory now owns a database of its own, so it is
        enabled here, while the database is still free of other connections.
        """
        backend = self.backend_class(
            connection_config=SQLServerConnectionConfig(
                **self.server, database=MAINTENANCE_DATABASE
            )
        )
        backend.connect()
        try:
            identifier = _identifier(database)
            exists = bool(
                backend.execute(
                    "SELECT name FROM sys.databases WHERE name = ?",
                    (database,),
                    options=DQL_OPTIONS,
                ).data
            )
            if exists:
                # A leftover database may still have connections attached; the
                # single-user switch evicts them so the drop cannot block.
                backend.execute(
                    f"ALTER DATABASE {identifier} SET SINGLE_USER WITH ROLLBACK IMMEDIATE",
                    (),
                    options=DDL_OPTIONS,
                )
            backend.execute(
                f"DROP DATABASE IF EXISTS {identifier}",
                (),
                options=DDL_OPTIONS,
            )
            backend.execute(
                f"CREATE DATABASE {identifier}",
                (),
                options=DDL_OPTIONS,
            )
            backend.execute(
                f"ALTER DATABASE {identifier} SET READ_COMMITTED_SNAPSHOT ON",
                (),
                options=DDL_OPTIONS,
            )
        finally:
            backend.disconnect()


def scenario(name: str) -> SQLServerScenario:
    """Return the scenario called ``name``."""
    try:
        server = SCENARIO_MAP[name]
    except KeyError:
        raise KeyError(f"Unknown SQL Server scenario: {name}") from None
    return SQLServerScenario(name, server)


def get_enabled_scenarios():
    """Return the scenarios this backend enables, as a name -> server map."""
    return {name: dict(server) for name, server in SCENARIO_MAP.items()}


def get_scenario(name: str):
    """Return ``(backend_class, config)`` for a benchmark database."""
    current = scenario(name)
    current.reset_database("test_benchmark")
    return current.backend_class, current.make_config("test_benchmark")


def get_scenario_raw(name: str):
    """Return ``(backend_class, config)`` for a server-level connection.

    Falls back to the first configured scenario when CI enables only one.
    """
    resolved = name if name in SCENARIO_MAP else next(iter(SCENARIO_MAP), None)
    if resolved is None:
        raise KeyError("No %s scenario configured" % name)
    current = scenario(resolved)
    return current.backend_class, current.make_config(MAINTENANCE_DATABASE)
