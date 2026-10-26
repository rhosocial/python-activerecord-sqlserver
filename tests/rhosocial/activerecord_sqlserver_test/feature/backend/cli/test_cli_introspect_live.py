# tests/rhosocial/activerecord_sqlserver_test/feature/backend/cli/test_cli_introspect_live.py
"""The ``introspect`` subcommand against a live SQL Server.

The offline suite in ``test_cli_introspect.py`` proves the dispatch -- which
introspector method answers which type -- with fakes. This proves the same
command works end to end against a real server, which is what the old
``get_tables``/``get_views``/``get_columns`` spelling could never do: those
methods exist nowhere in the backend, so against a live server every type
failed while the offline fakes happily answered them.

Runs on the first scenario only, like the other single-scenario live suites,
and points its probe objects through ``introspection_probe`` so the two live
suites see the same catalogue.
"""

import json

import pytest


from rhosocial.activerecord.backend.impl.sqlserver.__main__ import main

from tests.rhosocial.activerecord_sqlserver_test.feature.backend.introspection_probe import (
    PROBE_FUNCTION,
    PROBE_PROCEDURE,
    PROBE_SEQUENCE,
    PROBE_TABLE,
    PROBE_TRIGGER,
    create_probe_objects,
    drop_probe_objects,
)


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


@pytest.fixture
def probed_backend(sqlserver_backend_single):
    create_probe_objects(sqlserver_backend_single)
    yield sqlserver_backend_single
    drop_probe_objects(sqlserver_backend_single)


class TestIntrospectLiveCli:
    """``main(...)`` returns non-empty output for the types it advertises."""

    def test_tables(self, probed_backend, capsys):
        main(
            [
                "introspect",
                "tables",
                "-o",
                "json",
                *_connection_argv(probed_backend.config),
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, list) and payload
        names = [row["name"] for row in payload]
        assert PROBE_TABLE in names

    def test_views(self, probed_backend, capsys):
        main(
            [
                "introspect",
                "views",
                "-o",
                "json",
                *_connection_argv(probed_backend.config),
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, list) and payload
        assert all(row["name"] for row in payload)

    def test_columns(self, probed_backend, capsys):
        main(
            [
                "introspect",
                "columns",
                PROBE_TABLE,
                "-o",
                "json",
                *_connection_argv(probed_backend.config),
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, list) and payload
        assert "id" in [c["name"] for c in payload]

    def test_triggers(self, probed_backend, capsys):
        main(
            [
                "introspect",
                "triggers",
                "-o",
                "json",
                *_connection_argv(probed_backend.config),
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, list) and payload
        # The probe trigger, by name and by the table it fires on.
        names = [row.get("name") for row in payload]
        assert PROBE_TRIGGER in names
        row = [r for r in payload if r.get("name") == PROBE_TRIGGER][0]
        assert row.get("table_name") == PROBE_TABLE

    def test_schemas(self, probed_backend, capsys):
        main(
            [
                "introspect",
                "schemas",
                "-o",
                "json",
                *_connection_argv(probed_backend.config),
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, list) and payload
        assert any(row["name"] == "dbo" for row in payload)

    def test_procedures(self, probed_backend, capsys):
        main(
            [
                "introspect",
                "procedures",
                "-o",
                "json",
                *_connection_argv(probed_backend.config),
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, list) and payload
        assert any(row["name"] == PROBE_PROCEDURE for row in payload)

    def test_functions(self, probed_backend, capsys):
        main(
            [
                "introspect",
                "functions",
                "-o",
                "json",
                *_connection_argv(probed_backend.config),
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, list) and payload
        assert any(row["name"] == PROBE_FUNCTION for row in payload)

    def test_sequences(self, probed_backend, capsys):
        main(
            [
                "introspect",
                "sequences",
                "-o",
                "json",
                *_connection_argv(probed_backend.config),
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, list) and payload
        row = [r for r in payload if r["name"] == PROBE_SEQUENCE][0]
        # Decimal renders as text through the JSON provider; 5 and 2 are the
        # declared start and increment, so a wrong answer changes the text.
        assert row["start_value"] == "5"
        assert row["increment"] == "2"

    def test_database(self, probed_backend, capsys):
        main(
            [
                "introspect",
                "database",
                "-o",
                "json",
                *_connection_argv(probed_backend.config),
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload
        # ``get_database_info`` answers with the database's own name and the
        # version string the server reports (``15.0.4465`` and up).
        assert payload[0]["name"]
        assert payload[0]["version"].count(".") >= 2
