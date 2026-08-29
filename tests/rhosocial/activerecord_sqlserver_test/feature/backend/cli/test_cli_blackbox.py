# tests/rhosocial/activerecord_test/feature/backend/cli/test_cli_blackbox.py
"""Black-box CLI tests for the SQL Server backend.

Live server scenarios (127.0.0.1:11433-11435) may be unavailable in the
current environment; live cases skip via a reachability guard while static
cases (command surface, info) always run.
"""

import io
import json
import socket
from contextlib import redirect_stderr, redirect_stdout

import pytest

from rhosocial.activerecord.backend.impl.sqlserver.__main__ import main
from providers.scenarios import get_scenario_raw

COMMANDS = [
    "info", "query", "introspect", "status",
    "named-expression", "named-procedure", "named-procedure-graph",
    "named-migration", "named-connection",
]


@pytest.fixture(scope="module")
def conn_args():
    backend_cls, config = get_scenario_raw("sqlserver_2025")
    _s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _s.settimeout(2)
    try:
        _s.connect((config.host, int(config.port)))
    except OSError:
        pytest.skip(f"Scenario server unreachable: {config.host}:{config.port}")
    finally:
        _s.close()
    args = [
        "--host", config.host,
        "--port", str(config.port),
        "--database", config.database,
        "--user", config.username,
        "--password", config.password,
    ]
    if getattr(config, "driver", None):
        args += ["--driver", config.driver]
    return args


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    exc = None
    with redirect_stdout(out), redirect_stderr(err):
        try:
            main(argv)
        except SystemExit as e:
            exc = e
    return out.getvalue(), err.getvalue(), exc


class TestCommandSurface:
    """Static: always run, no server needed."""

    def test_help_lists_all_commands(self):
        out, _, _ = run_cli(["--help"])
        for cmd in COMMANDS:
            assert cmd in out

    def test_missing_command_errors(self):
        _, _, exc = run_cli([])
        assert exc is not None and exc.code == 1

    def test_help_shows_unified_args(self):
        out, _, _ = run_cli(["query", "--help"])
        assert "--user" in out
        assert "--username" in out
        assert "--ssl" in out
        assert "--async" in out
        assert "--named-connection" in out
        assert "--conn-param" in out


class TestInfo:
    """Static: info needs no server."""

    def test_info(self):
        out, _, exc = run_cli(["info"])
        assert exc is None
        assert "SQL Server" in out or "sqlserver" in out or "sql server" in out.lower()


class TestQuery:
    """Live: requires the scenario server."""

    def test_query_json(self, conn_args):
        out, err, exc = run_cli(["query"] + conn_args + ["SELECT 1 AS one", "-o", "json"])
        assert exc is None, f"stderr: {err}\nstdout: {out}"
        assert json.loads(out) == [{"one": 1}]

    def test_query_async(self, conn_args):
        out, _, exc = run_cli(["query"] + conn_args + ["SELECT 1 AS one", "-o", "json", "--async"])
        assert exc is None
        assert json.loads(out) == [{"one": 1}]


class TestStatus:
    """Live: requires the scenario server."""

    def test_status(self, conn_args):
        out, err, exc = run_cli(["status"] + conn_args + ["-o", "json"])
        assert exc is None, f"stderr: {err}\nstdout: {out}"
        assert json.loads(out)
