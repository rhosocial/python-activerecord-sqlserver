# tests/rhosocial/activerecord_sqlserver_test/feature/backend/execute/cli/test_cli_live.py
"""Real-database CLI integration tests for the SQL Server backend.

The offline suite under ``feature/backend/construct/cli`` proves command
dispatch with fakes; this module drives ``main()`` against the very server the
backend fixtures connect to. ``introspect`` is already covered end to end by
``test_cli_introspect_live.py``; here we cover the remaining database-backed
commands: ``info``, ``query`` and ``status``.

Every assertion below reads the CLI's own JSON output after ``main()`` opened
a real connection -- there are no mocks. The ``sqlserver_backend_single``
fixture skips when no scenario/server is available, so these cases only truly
run where a live SQL Server is present (CI).
"""

import json

from rhosocial.activerecord.backend.impl.sqlserver.__main__ import main


def _connection_argv(config):
    """Connection flags for the scenario the fixture connected with."""
    return [
        "--host",
        config.host,
        "--port",
        str(config.port),
        "--database",
        config.database,
        "--user",
        config.username,
        "--password",
        config.password or "",
        "--driver",
        config.driver,
    ]


class TestInfoLiveCli:
    """``info -o json`` -- with ``--database``, it introspects the live server."""

    def test_info_reports_the_connected_server(self, sqlserver_backend_single, capsys):
        main(["info", "-o", "json", *_connection_argv(sqlserver_backend_single.config)])
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, dict)
        assert payload["database"]["type"] == "sqlserver"
        assert payload["database"]["version"]
        assert isinstance(payload["protocols"], dict) and payload["protocols"]
        # ``--database`` sends info down its connect-and-introspect path; a
        # mocked/faked run would leave this False, so it marks the live path.
        assert payload["database"]["connected"] is True


class TestQueryLiveCli:
    """``query -o json`` executes SQL on the live server."""

    def test_query_select_one(self, sqlserver_backend_single, capsys):
        main(
            [
                "query",
                "SELECT 1 AS n",
                "-o",
                "json",
                *_connection_argv(sqlserver_backend_single.config),
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, list) and len(payload) == 1
        assert payload[0]["n"] == 1


class TestStatusLiveCli:
    """``status`` answers both the overview and a single category from the server."""

    def test_status_all(self, sqlserver_backend_single, capsys):
        main(["status", "all", "-o", "json", *_connection_argv(sqlserver_backend_single.config)])
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, dict) and payload
        assert payload["server_version"]
        assert payload["server_vendor"]
        assert "configuration" in payload

    def test_status_config(self, sqlserver_backend_single, capsys):
        main(["status", "config", "-o", "json", *_connection_argv(sqlserver_backend_single.config)])
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, list) and payload
        assert all(row["name"] for row in payload)
