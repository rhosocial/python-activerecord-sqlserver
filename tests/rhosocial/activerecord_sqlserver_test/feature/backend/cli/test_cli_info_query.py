# tests/rhosocial/activerecord_sqlserver_test/feature/backend/cli/test_cli_info_query.py
"""Offline black-box tests for the ``info`` and ``query`` subcommands.

``info`` runs against its default offline dialect (explicit ``--version``),
a faked successful connection, and a failing connection fallback.
``query`` covers every SQL-source dispatch branch (positional / --file /
stdin / none), the sync/async split, result-shape branches and error exits
with a fake backend; no live server is required.
"""
import argparse
import json
import sys
from types import SimpleNamespace

import pytest

from rhosocial.activerecord.backend.errors import ConnectionError, QueryError
from rhosocial.activerecord.backend.dialect.protocols import ExplainSupport
from rhosocial.activerecord.backend.impl import sqlserver as backend_pkg
from rhosocial.activerecord.backend.impl.sqlserver.cli import info as info_mod
from rhosocial.activerecord.backend.impl.sqlserver.cli import query as query_mod
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    import os

    for key in list(os.environ):
        if key.startswith("SQLSERVER_"):
            monkeypatch.delenv(key, raising=False)


def make_args(create_parser, argv):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    create_parser(sub)
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# info subcommand
# ---------------------------------------------------------------------------


class TestInfoParserContract:
    def test_output_choices_table_json(self):
        assert make_args(info_mod.create_parser, ["info"]).output == "table"
        assert make_args(info_mod.create_parser, ["info", "-o", "json"]).output == "json"
        with pytest.raises(SystemExit):
            make_args(info_mod.create_parser, ["info", "-o", "csv"])

    def test_version_arg_and_verbose(self):
        args = make_args(info_mod.create_parser, ["info", "--version", "14.0.0", "-vv"])
        assert args.version == "14.0.0"
        assert args.verbose == 2

    def test_port_defaults_to_1433(self):
        assert make_args(info_mod.create_parser, ["info"]).port == 1433


class TestInfoOffline:
    def test_default_version_is_2022(self, capsys):
        info = info_mod.handle(make_args(info_mod.create_parser, ["info"]))
        assert info["database"]["version"] == "16.0.0"
        assert info["database"]["version_tuple"] == [16, 0, 0]
        assert info["database"]["connected"] is False
        payload = json.loads(capsys.readouterr().out)
        assert payload["database"] == info["database"]

    def test_explicit_version_flag(self, capsys):
        info = info_mod.handle(
            make_args(info_mod.create_parser, ["info", "--version", "14.0.7"])
        )
        assert info["database"]["version"] == "14.0.7"
        assert info["database"]["connected"] is False

    def test_json_contains_all_protocol_groups(self, capsys):
        info_mod.handle(make_args(info_mod.create_parser, ["info", "-o", "json"]))
        payload = json.loads(capsys.readouterr().out)
        expected_groups = {
            "Query Features", "JOIN Support", "Data Types", "DML Features",
            "Transaction & Locking", "Query Analysis", "DDL - Table", "DDL - View",
            "DDL - Schema & Index", "DDL - Sequence & Trigger", "String Matching",
            "SQL Server Native",
        }
        assert set(payload["protocols"]) == expected_groups

    def test_verbose_two_includes_method_details(self, capsys):
        info_mod.handle(make_args(info_mod.create_parser, ["info", "-vv", "-o", "json"]))
        payload = json.loads(capsys.readouterr().out)
        native = payload["protocols"]["SQL Server Native"]
        stats = next(iter(native.values()))
        assert "methods" in stats

    def test_verbose_one_omits_method_details(self, capsys):
        info_mod.handle(make_args(info_mod.create_parser, ["info", "-v", "-o", "json"]))
        payload = json.loads(capsys.readouterr().out)
        entry = payload["protocols"]["Query Features"]["WindowFunctionSupport"]
        assert set(entry) == {"supported", "total", "percentage"}

    def test_version_bits_differ_between_versions(self):
        old = info_mod.handle(
            make_args(info_mod.create_parser, ["info", "--version", "11.0.0", "-o", "json"])
        )
        new = info_mod.handle(
            make_args(info_mod.create_parser, ["info", "--version", "13.0.0", "-o", "json"])
        )
        old_json_support = old["protocols"]["Data Types"]["JSONSupport"]
        new_json_support = new["protocols"]["Data Types"]["JSONSupport"]
        assert old_json_support["supported"] < new_json_support["supported"]

    def test_parse_version_variants(self):
        assert info_mod.parse_version("16") == (16, 0, 0)
        assert info_mod.parse_version("15.2") == (15, 2, 0)
        assert info_mod.parse_version("16.0.4104") == (16, 0, 4104)


class TestInfoProtocolHelpers:
    @pytest.fixture
    def dialect(self):
        return SQLServerDialect((16, 0, 0))

    def test_get_protocol_support_methods_sorted(self):
        methods = info_mod.get_protocol_support_methods(ExplainSupport)
        assert methods == sorted(methods)
        assert "supports_explain_format" in methods

    def test_check_protocol_support_multi_arg_dict(self, dialect):
        results = info_mod.check_protocol_support(dialect, ExplainSupport)
        fmt = results["supports_explain_format"]
        assert fmt == {"supported": 2, "total": 2, "args": {"TEXT": True, "XML": True}}

    def test_calculate_protocol_stats_mixed_values(self):
        supported, total = info_mod._calculate_protocol_stats({"a": True, "b": False})
        assert (supported, total) == (1, 2)
        supported, total = info_mod._calculate_protocol_stats(
            {"fmt": {"supported": 3, "total": 5}}
        )
        assert (supported, total) == (3, 5)

    def test_status_style_boundaries(self):
        assert info_mod._get_status_style(100) == ("green", "[OK]")
        assert info_mod._get_status_style(50)[0] == "yellow"
        assert info_mod._get_status_style(10) == ("red", "[~]")
        assert info_mod._get_status_style(0) == ("red", "[X]")


class TestInfoConnectionBranches:
    def test_successful_connection_reports_server_version(self, monkeypatch, capsys):
        class ConnectedBackend:
            instances = []

            def __init__(self, connection_config=None):
                self.connection_config = connection_config
                self.disconnected = False
                type(self).instances.append(self)

            def connect(self):
                pass

            def introspect_and_adapt(self):
                pass

            def get_server_version(self):
                return (15, 0, 4202)

            def disconnect(self):
                self.disconnected = True

            @property
            def dialect(self):
                return SQLServerDialect((15, 0, 4202))

        monkeypatch.setattr(backend_pkg, "SQLServerBackend", ConnectedBackend)
        info = info_mod.handle(
            make_args(info_mod.create_parser, ["info", "--host", "srv1", "--database", "db"])
        )
        assert info["database"]["connected"] is True
        assert info["database"]["version"] == "15.0.4202"
        assert ConnectedBackend.instances[-1].disconnected is True

    def test_connection_failure_falls_back_to_default_dialect(self, monkeypatch):
        class RefusedBackend:
            def __init__(self, connection_config=None):
                pass

            def connect(self):
                raise ConnectionError("refused")

        monkeypatch.setattr(backend_pkg, "SQLServerBackend", RefusedBackend)
        info = info_mod.handle(
            make_args(info_mod.create_parser, ["info", "--database", "db"])
        )
        assert info["database"]["connected"] is False
        assert info["database"]["version"] == "16.0.0"  # default fallback


# ---------------------------------------------------------------------------
# query subcommand
# ---------------------------------------------------------------------------


class FakeQueryBackendBase:
    created = []
    instances = []
    executed = []
    connect_error = None
    execute_error = None
    result_factory = staticmethod(lambda sql: SimpleNamespace(data=[{"one": 1}], affected_rows=1, duration=0.01))

    def __init__(self, connection_config=None):
        self.connection_config = connection_config
        self._connection = object()
        self.disconnects = 0
        type(self).created.append(connection_config)
        type(self).instances.append(self)

    def connect(self):
        if self.connect_error is not None:
            raise self.connect_error

    def execute(self, sql):
        FakeQueryBackendBase.executed.append(sql)
        if self.execute_error is not None:
            raise self.execute_error
        return type(self).result_factory(sql)

    def disconnect(self):
        self.disconnects += 1


class FakeAsyncQueryBackend(FakeQueryBackendBase):
    async def connect(self):
        FakeQueryBackendBase.connect(self)

    async def execute(self, sql):
        return FakeQueryBackendBase.execute(self, sql)

    async def disconnect(self):
        self.disconnects += 1


def _tracking_class(base, name):
    return type(name, (base,), {"created": [], "instances": []})


@pytest.fixture(autouse=True)
def _reset_fake_state():
    FakeQueryBackendBase.executed = []


class TestQueryParserContract:
    def test_sql_positional_optional_with_file_flag(self):
        args = make_args(query_mod.create_parser, ["query", "-f", "q.sql"])
        assert args.sql is None and args.file == "q.sql"

    def test_log_level_default_info(self):
        assert make_args(query_mod.create_parser, ["query", "SELECT 1"]).log_level == "INFO"


class TestQuerySqlSourceDispatch:
    def test_invalid_log_level_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid log level"):
            query_mod.handle(
                make_args(query_mod.create_parser, ["query", "--log-level", "LOUD", "SELECT 1"])
            )

    def test_no_sql_anywhere_exits_nonzero(self, monkeypatch, capsys):
        class TtyStdin:
            def isatty(self):
                return True

        monkeypatch.setattr(sys, "stdin", TtyStdin())
        with pytest.raises(SystemExit) as exc:
            query_mod.handle(make_args(query_mod.create_parser, ["query", "--database", "db"]))
        assert exc.value.code == 1
        assert "No SQL query provided" in capsys.readouterr().err

    def test_positional_sql_executed(self, tmp_path, monkeypatch, capsys):
        cls = _tracking_class(FakeQueryBackendBase, "QPos")
        monkeypatch.setattr(query_mod, "SQLServerBackend", cls)
        query_mod.handle(
            make_args(query_mod.create_parser, ["query", "--database", "db", "SELECT 1 AS one"])
        )
        assert FakeQueryBackendBase.executed == ["SELECT 1 AS one"]
        assert json.loads(capsys.readouterr().out) == [{"one": 1}]

    def test_positional_sql_takes_precedence_over_file(self, tmp_path, monkeypatch):
        cls = _tracking_class(FakeQueryBackendBase, "QPrecedence")
        monkeypatch.setattr(query_mod, "SQLServerBackend", cls)
        sql_file = tmp_path / "from_file.sql"
        sql_file.write_text("SELECT 'file'", encoding="utf-8")
        query_mod.handle(
            make_args(
                query_mod.create_parser,
                ["query", "--database", "db", "SELECT 'positional'", "-f", str(sql_file)],
            )
        )
        assert FakeQueryBackendBase.executed == ["SELECT 'positional'"]

    def test_file_source_executed(self, tmp_path, monkeypatch):
        cls = _tracking_class(FakeQueryBackendBase, "QFile")
        monkeypatch.setattr(query_mod, "SQLServerBackend", cls)
        sql_file = tmp_path / "q.sql"
        sql_file.write_text("SELECT TOP 1 name FROM sys.objects", encoding="utf-8")
        query_mod.handle(
            make_args(query_mod.create_parser, ["query", "--database", "db", "-f", str(sql_file)])
        )
        assert FakeQueryBackendBase.executed == ["SELECT TOP 1 name FROM sys.objects"]

    def test_missing_file_exits_nonzero(self, monkeypatch, caplog, tmp_path):
        monkeypatch.setattr(query_mod, "SQLServerBackend", _tracking_class(FakeQueryBackendBase, "QMiss"))
        with pytest.raises(SystemExit) as exc:
            query_mod.handle(
                make_args(query_mod.create_parser, ["query", "--database", "db", "-f", str(tmp_path / "nope.sql")])
            )
        assert exc.value.code == 1
        assert any("File not found" in r.message for r in caplog.records)

    def test_stdin_source_executed(self, monkeypatch):
        class PipeStdin:
            def isatty(self):
                return False

            def read(self):
                return "SELECT COUNT(*) FROM sys.tables"

        monkeypatch.setattr(sys, "stdin", PipeStdin())
        monkeypatch.setattr(query_mod, "SQLServerBackend", _tracking_class(FakeQueryBackendBase, "QStdin"))
        query_mod.handle(make_args(query_mod.create_parser, ["query", "--database", "db"]))
        assert FakeQueryBackendBase.executed == ["SELECT COUNT(*) FROM sys.tables"]

    def test_empty_stdin_exits_nonzero(self, monkeypatch, capsys):
        class EmptyStdin:
            def isatty(self):
                return False

            def read(self):
                return ""

        monkeypatch.setattr(sys, "stdin", EmptyStdin())
        monkeypatch.setattr(query_mod, "SQLServerBackend", _tracking_class(FakeQueryBackendBase, "QEmpty"))
        with pytest.raises(SystemExit) as exc:
            query_mod.handle(make_args(query_mod.create_parser, ["query", "--database", "db"]))
        assert exc.value.code == 1
        assert "No SQL query provided" in capsys.readouterr().err

    def test_multiple_statements_rejected(self, monkeypatch, caplog):
        class TtyStdin:
            def isatty(self):
                return True

        monkeypatch.setattr(sys, "stdin", TtyStdin())
        monkeypatch.setattr(query_mod, "SQLServerBackend", _tracking_class(FakeQueryBackendBase, "QMulti"))
        with pytest.raises(SystemExit) as exc:
            query_mod.handle(
                make_args(query_mod.create_parser, ["query", "--database", "db", "SELECT 1; SELECT 2"])
            )
        assert exc.value.code == 1
        assert any("Multiple SQL statements" in r.message for r in caplog.records)

    def test_trailing_semicolon_single_statement_allowed(self, monkeypatch):
        monkeypatch.setattr(query_mod, "SQLServerBackend", _tracking_class(FakeQueryBackendBase, "QTerm"))
        query_mod.handle(
            make_args(query_mod.create_parser, ["query", "--database", "db", "SELECT 1;"])
        )
        assert FakeQueryBackendBase.executed == ["SELECT 1;"]


class TestQueryResultBranches:
    def test_result_without_data_writes_empty_json_array(self, monkeypatch, capsys):
        cls = _tracking_class(FakeQueryBackendBase, "QNoData")

        def no_data_result(sql):
            return SimpleNamespace(data=[], affected_rows=3, duration=0.02)

        cls.result_factory = staticmethod(no_data_result)
        monkeypatch.setattr(query_mod, "SQLServerBackend", cls)
        query_mod.handle(make_args(query_mod.create_parser, ["query", "--database", "db", "UPDATE t SET x=1"]))
        assert json.loads(capsys.readouterr().out) == []

    def test_none_result_object_handled(self, monkeypatch, capsys):
        cls = _tracking_class(FakeQueryBackendBase, "QNone")
        cls.result_factory = staticmethod(lambda sql: None)
        monkeypatch.setattr(query_mod, "SQLServerBackend", cls)
        query_mod.handle(make_args(query_mod.create_parser, ["query", "--database", "db", "USE master"]))
        assert capsys.readouterr().out == ""  # only logger output, nothing on stdout

    def test_disconnect_called_in_finally(self, monkeypatch):
        cls = _tracking_class(FakeQueryBackendBase, "QDisc")
        monkeypatch.setattr(query_mod, "SQLServerBackend", cls)
        query_mod.handle(make_args(query_mod.create_parser, ["query", "--database", "db", "SELECT 1"]))
        assert cls.instances[-1].disconnects >= 1

    def test_connection_config_resolved_from_args(self, monkeypatch):
        cls = _tracking_class(FakeQueryBackendBase, "QCfg")
        monkeypatch.setattr(query_mod, "SQLServerBackend", cls)
        argv = [
            "query", "--host", "h1", "--port", "1444", "--database", "db",
            "--username", "alice", "--encrypt",
        ]
        query_mod.handle(make_args(query_mod.create_parser, argv + ["SELECT 1"]))
        config = cls.created[-1]
        assert config.host == "h1" and config.port == 1444 and config.database == "db"
        assert config.username == "alice"


class TestQueryErrors:
    @pytest.mark.parametrize(
        ("connect_error", "execute_error"),
        [(ConnectionError("login failed"), None), (None, QueryError("invalid column")), (None, RuntimeError("boom"))],
    )
    def test_error_paths_exit_nonzero(self, monkeypatch, connect_error, execute_error):
        cls = _tracking_class(FakeQueryBackendBase, "QErr")
        cls.connect_error = connect_error
        cls.execute_error = execute_error
        monkeypatch.setattr(query_mod, "SQLServerBackend", cls)
        with pytest.raises(SystemExit) as exc:
            query_mod.handle(
                make_args(query_mod.create_parser, ["query", "--database", "db", "SELECT 1"])
            )
        assert exc.value.code != 0


class TestQueryAsync:
    def test_async_dispatch_executes_query(self, monkeypatch, capsys):
        cls = _tracking_class(FakeAsyncQueryBackend, "QAsync")
        monkeypatch.setattr(backend_pkg, "AsyncSQLServerBackend", cls, raising=False)
        query_mod.handle(
            make_args(
                query_mod.create_parser,
                ["query", "--database", "db", "SELECT 1 AS one", "-o", "json", "--async"],
            )
        )
        assert FakeQueryBackendBase.executed == ["SELECT 1 AS one"]
        assert json.loads(capsys.readouterr().out) == [{"one": 1}]

    @pytest.mark.parametrize(
        ("connect_error", "execute_error"),
        [(ConnectionError("refused"), None), (None, QueryError("timeout"))],
    )
    def test_async_errors_exit_nonzero(self, monkeypatch, connect_error, execute_error):
        cls = _tracking_class(FakeAsyncQueryBackend, "QAsyncErr")
        cls.connect_error = connect_error
        cls.execute_error = execute_error
        monkeypatch.setattr(backend_pkg, "AsyncSQLServerBackend", cls, raising=False)
        with pytest.raises(SystemExit) as exc:
            query_mod.handle(
                make_args(query_mod.create_parser, ["query", "--database", "db", "SELECT 1", "--async"])
            )
        assert exc.value.code != 0
