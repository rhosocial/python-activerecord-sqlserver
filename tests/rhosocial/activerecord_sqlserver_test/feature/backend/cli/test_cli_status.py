# tests/rhosocial/activerecord_sqlserver_test/feature/backend/cli/test_cli_status.py
"""Offline black-box tests for the ``status`` subcommand.

``cli/status.py`` exposes ``create_parser(subparsers) + handle(args)``. The
SQLServerBackend construction point and the SQL Server status introspectors
are monkeypatched with minimal fakes so no live server is required.
"""
import argparse
import json

import pytest

from rhosocial.activerecord.backend.errors import ConnectionError, QueryError
from rhosocial.activerecord.backend.impl.sqlserver.cli import status as status_mod
from rhosocial.activerecord.backend.impl import sqlserver as backend_pkg

STATUS_INTROSPECTOR_MODULE = (
    "rhosocial.activerecord.backend.impl.sqlserver.introspection.status_introspector"
)
BACKEND_PACKAGE = "rhosocial.activerecord.backend.impl.sqlserver"


def _tracking_class(base, name):
    """Create a fresh subclass with per-class construction tracking."""
    cls = type(name, (base,), {"created": [], "instances": [], "__init__": base._tracked_init})
    return cls


class FakeBackendBase:
    """Minimal backend lifecycle: fixed connect/disconnect + captured config."""

    created = []
    instances = []

    def _tracked_init(self, connection_config=None):
        self.connection_config = connection_config
        self._connection = object()  # truthy so the handler's finally disconnects
        self.disconnects = 0
        type(self).created.append(connection_config)
        type(self).instances.append(self)

    connect_error = None

    def connect(self):
        if self.connect_error is not None:
            raise self.connect_error

    def disconnect(self):
        self.disconnects += 1

    def introspect_and_adapt(self):
        pass


class FakeAsyncBackendBase(FakeBackendBase):
    async def connect(self):
        FakeBackendBase.connect(self)

    async def disconnect(self):
        self.disconnects += 1

    async def introspect_and_adapt(self):
        pass


class RecordingIntrospector:
    """Fixed-data introspector stand-in recording dispatched method names."""

    instances = []

    def __init__(self, backend):
        self.backend = backend
        self.calls = []
        type(self).instances.append(self)

    def get_overview(self):
        self.calls.append("get_overview")
        return {
            "server_version": "16.0.0",
            "server_vendor": "Microsoft",
            "configuration": [],
            "databases": [{"name": "master", "size_bytes": 1024}],
        }

    def list_configuration(self, category=None):
        self.calls.append("list_configuration")
        return [{"name": "max server memory", "value": 2147483648, "category": str(category)}]

    def list_performance_metrics(self):
        self.calls.append("list_performance_metrics")
        return [{"name": "batch requests/sec", "value": 120}]

    def get_connection_info(self):
        self.calls.append("get_connection_info")
        return {"user": "sa", "database": "master"}

    def get_storage_info(self):
        self.calls.append("get_storage_info")
        return {"size_bytes": 2048}

    def list_databases(self):
        self.calls.append("list_databases")
        return [{"name": "master", "size_bytes": 1024}, {"name": "tempdb", "size_bytes": None}]

    def list_users(self):
        self.calls.append("list_users")
        return [{"name": "dbo"}]


class AsyncRecordingIntrospector(RecordingIntrospector):
    async def get_overview(self):
        return super().get_overview()

    async def list_configuration(self, category=None):
        return super().list_configuration(category)

    async def list_performance_metrics(self):
        return super().list_performance_metrics()

    async def get_connection_info(self):
        return super().get_connection_info()

    async def get_storage_info(self):
        return super().get_storage_info()

    async def list_databases(self):
        return super().list_databases()

    async def list_users(self):
        return super().list_users()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove SQLSERVER_* env vars so parser defaults are deterministic."""
    import os

    for key in list(os.environ):
        if key.startswith("SQLSERVER_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def fake_backend_cls():
    return _tracking_class(FakeBackendBase, "FakeStatusBackend")


@pytest.fixture
def fake_async_backend_cls():
    return _tracking_class(FakeAsyncBackendBase, "FakeStatusAsyncBackend")


def make_args(argv):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    status_mod.create_parser(sub)
    return parser.parse_args(argv)


class TestParserContract:
    def test_port_defaults_to_1433(self):
        assert make_args(["status"]).port == 1433

    def test_driver_default_is_odbc_18(self):
        assert make_args(["status"]).driver == "ODBC Driver 18 for SQL Server"

    def test_encrypt_flag_default_and_override(self):
        assert make_args(["status"]).encrypt is False
        assert make_args(["status", "--encrypt"]).encrypt is True
        assert make_args(["status", "--no-encrypt"]).encrypt is False

    def test_encrypt_flags_are_mutually_exclusive(self):
        with pytest.raises(SystemExit):
            make_args(["status", "--encrypt", "--no-encrypt"])

    def test_trust_server_certificate_defaults_true(self):
        assert make_args(["status"]).trust_server_certificate is True
        assert (
            make_args(["status", "--no-trust-server-certificate"]).trust_server_certificate
            is False
        )

    def test_output_choices_and_default(self):
        assert make_args(["status", "-o", "csv"]).output == "csv"
        assert make_args(["status"]).output == "table"
        with pytest.raises(SystemExit):
            make_args(["status", "-o", "yaml"])

    def test_type_choices_accept_known_reject_unknown(self):
        assert make_args(["status", "storage"]).type == "storage"
        with pytest.raises(SystemExit):
            make_args(["status", "bogus"])

    def test_verbose_counts_and_rich_ascii_flag(self):
        args = make_args(["status", "-vv", "--rich-ascii"])
        assert args.verbose == 2
        assert args.rich_ascii is True


class TestHandleGuards:
    def test_missing_database_exits_before_backend_creation(
        self, fake_backend_cls, monkeypatch, capsys
    ):
        monkeypatch.setattr(status_mod, "SQLServerBackend", fake_backend_cls)
        with pytest.raises(SystemExit) as exc:
            status_mod.handle(make_args(["status"]))
        assert exc.value.code == 1
        assert "--database is required" in capsys.readouterr().err
        assert fake_backend_cls.created == []


class TestHandleSyncDispatch:
    @pytest.mark.parametrize(
        ("status_type", "method"),
        [
            ("config", "list_configuration"),
            ("performance", "list_performance_metrics"),
            ("connections", "get_connection_info"),
            ("storage", "get_storage_info"),
            ("databases", "list_databases"),
            ("users", "list_users"),
        ],
    )
    def test_type_dispatches_to_introspector_method(
        self, fake_backend_cls, monkeypatch, capsys, status_type, method
    ):
        monkeypatch.setattr(
            f"{STATUS_INTROSPECTOR_MODULE}.SyncSQLServerStatusIntrospector", RecordingIntrospector
        )
        monkeypatch.setattr(status_mod, "SQLServerBackend", fake_backend_cls)
        RecordingIntrospector.instances = []
        status_mod.handle(make_args(["status", status_type, "--database", "db", "-o", "json"]))
        json.loads(capsys.readouterr().out)  # well-formed JSON emitted
        assert method in RecordingIntrospector.instances[-1].calls

    def test_overview_dispatch_and_json_payload(self, fake_backend_cls, monkeypatch, capsys):
        monkeypatch.setattr(
            f"{STATUS_INTROSPECTOR_MODULE}.SyncSQLServerStatusIntrospector", RecordingIntrospector
        )
        monkeypatch.setattr(status_mod, "SQLServerBackend", fake_backend_cls)
        RecordingIntrospector.instances = []
        status_mod.handle(make_args(["status", "all", "--database", "db"]))
        payload = json.loads(capsys.readouterr().out)
        assert payload["server_version"] == "16.0.0"
        assert payload["server_vendor"] == "Microsoft"
        assert "get_overview" in RecordingIntrospector.instances[-1].calls

    @pytest.mark.parametrize("fmt", ["csv", "tsv"])
    def test_csv_tsv_fall_back_to_json_for_overview(
        self, fake_backend_cls, monkeypatch, capsys, fmt
    ):
        monkeypatch.setattr(
            f"{STATUS_INTROSPECTOR_MODULE}.SyncSQLServerStatusIntrospector", RecordingIntrospector
        )
        monkeypatch.setattr(status_mod, "SQLServerBackend", fake_backend_cls)
        status_mod.handle(make_args(["status", "all", "--database", "db", "-o", fmt]))
        payload = json.loads(capsys.readouterr().out)
        assert payload["server_version"] == "16.0.0"

    def test_table_format_without_rich_renders_json(
        self, fake_backend_cls, monkeypatch, capsys
    ):
        assert status_mod.RICH_AVAILABLE is False  # rich not installed in this env
        monkeypatch.setattr(
            f"{STATUS_INTROSPECTOR_MODULE}.SyncSQLServerStatusIntrospector", RecordingIntrospector
        )
        monkeypatch.setattr(status_mod, "SQLServerBackend", fake_backend_cls)
        status_mod.handle(
            make_args(["status", "databases", "--database", "db", "-o", "table"])
        )
        payload = json.loads(capsys.readouterr().out)
        assert {row["name"] for row in payload} == {"master", "tempdb"}

    def test_config_csv_output_writes_header_row(
        self, fake_backend_cls, monkeypatch, capsys
    ):
        monkeypatch.setattr(
            f"{STATUS_INTROSPECTOR_MODULE}.SyncSQLServerStatusIntrospector", RecordingIntrospector
        )
        monkeypatch.setattr(status_mod, "SQLServerBackend", fake_backend_cls)
        status_mod.handle(make_args(["status", "config", "--database", "db", "-o", "csv"]))
        first_line = capsys.readouterr().out.splitlines()[0]
        assert first_line == "name,value,category"

    def test_disconnect_called_in_finally(self, fake_backend_cls, monkeypatch, capsys):
        monkeypatch.setattr(
            f"{STATUS_INTROSPECTOR_MODULE}.SyncSQLServerStatusIntrospector", RecordingIntrospector
        )
        monkeypatch.setattr(status_mod, "SQLServerBackend", fake_backend_cls)
        status_mod.handle(make_args(["status", "users", "--database", "db"]))
        assert fake_backend_cls.instances[-1].disconnects >= 1

    def test_connection_config_resolved_from_args(self, fake_backend_cls, monkeypatch, capsys):
        monkeypatch.setattr(
            f"{STATUS_INTROSPECTOR_MODULE}.SyncSQLServerStatusIntrospector", RecordingIntrospector
        )
        monkeypatch.setattr(status_mod, "SQLServerBackend", fake_backend_cls)
        argv = [
            "status", "users", "--host", "srv1", "--port", "1444", "--database", "db",
            "--user", "bob", "--password", "pw", "--driver", "ODBC Driver 17 for SQL Server",
        ]
        status_mod.handle(make_args(argv))
        config = fake_backend_cls.created[-1]
        assert (config.host, config.port, config.database) == ("srv1", 1444, "db")
        assert (config.username, config.password) == ("bob", "pw")
        assert config.driver == "ODBC Driver 17 for SQL Server"

    def test_ssl_disabled_disables_encrypt(self, fake_backend_cls, monkeypatch):
        monkeypatch.setattr(
            f"{STATUS_INTROSPECTOR_MODULE}.SyncSQLServerStatusIntrospector", RecordingIntrospector
        )
        monkeypatch.setattr(status_mod, "SQLServerBackend", fake_backend_cls)
        status_mod.handle(
            make_args(["status", "users", "--database", "db", "--ssl", "disabled"])
        )
        config = fake_backend_cls.created[-1]
        assert config.encrypt is False
        assert config.trust_server_certificate is True

    def test_ssl_verify_full_requires_cert_check(self, fake_backend_cls, monkeypatch):
        monkeypatch.setattr(
            f"{STATUS_INTROSPECTOR_MODULE}.SyncSQLServerStatusIntrospector", RecordingIntrospector
        )
        monkeypatch.setattr(status_mod, "SQLServerBackend", fake_backend_cls)
        status_mod.handle(
            make_args(["status", "users", "--database", "db", "--ssl", "verify-full"])
        )
        config = fake_backend_cls.created[-1]
        assert config.encrypt is True
        assert config.trust_server_certificate is False

    def test_trusted_connection_passthrough(self, fake_backend_cls, monkeypatch):
        monkeypatch.setattr(
            f"{STATUS_INTROSPECTOR_MODULE}.SyncSQLServerStatusIntrospector", RecordingIntrospector
        )
        monkeypatch.setattr(status_mod, "SQLServerBackend", fake_backend_cls)
        status_mod.handle(
            make_args(["status", "users", "--database", "db", "--trusted-connection"])
        )
        assert fake_backend_cls.created[-1].trusted_connection is True


class TestHandleErrors:
    def _run_with(self, fake_backend_cls, monkeypatch, backend_error=None, introspector_exc=None):
        if backend_error is not None:
            backend_cls = _tracking_class(FakeBackendBase, "ErrBackend")
            backend_cls.connect_error = backend_error
            monkeypatch.setattr(status_mod, "SQLServerBackend", backend_cls)
        else:
            monkeypatch.setattr(status_mod, "SQLServerBackend", fake_backend_cls)
        if introspector_exc is not None:

            class ExplodingIntrospector(RecordingIntrospector):
                def get_overview(self):
                    raise introspector_exc

            monkeypatch.setattr(
                f"{STATUS_INTROSPECTOR_MODULE}.SyncSQLServerStatusIntrospector",
                ExplodingIntrospector,
            )
        else:
            monkeypatch.setattr(
                f"{STATUS_INTROSPECTOR_MODULE}.SyncSQLServerStatusIntrospector",
                RecordingIntrospector,
            )
        with pytest.raises(SystemExit) as exc:
            status_mod.handle(make_args(["status", "all", "--database", "db", "-o", "json"]))
        return exc.value.code

    def test_connection_error_exits_nonzero(self, fake_backend_cls, monkeypatch):
        code = self._run_with(fake_backend_cls, monkeypatch, backend_error=ConnectionError("no route"))
        assert code != 0

    def test_query_error_exits_nonzero(self, fake_backend_cls, monkeypatch):
        code = self._run_with(fake_backend_cls, monkeypatch, introspector_exc=QueryError("bad query"))
        assert code != 0

    def test_unexpected_error_exits_nonzero_with_stderr(
        self, fake_backend_cls, monkeypatch, capsys
    ):
        code = self._run_with(fake_backend_cls, monkeypatch, introspector_exc=RuntimeError("boom"))
        assert code != 0
        assert "Error during status retrieval" in capsys.readouterr().err


class TestHandleAsync:
    def test_async_overview_dispatch(self, fake_async_backend_cls, monkeypatch, capsys):
        monkeypatch.setattr(
            f"{STATUS_INTROSPECTOR_MODULE}.AsyncSQLServerStatusIntrospector",
            AsyncRecordingIntrospector,
        )
        monkeypatch.setattr(backend_pkg, "AsyncSQLServerBackend", fake_async_backend_cls, raising=False)
        status_mod.handle(
            make_args(["status", "all", "--database", "db", "-o", "json", "--async"])
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload["server_vendor"] == "Microsoft"

    def test_async_connection_error_exits_nonzero(self, fake_async_backend_cls, monkeypatch):
        fake_async_backend_cls.connect_error = ConnectionError("refused")
        monkeypatch.setattr(backend_pkg, "AsyncSQLServerBackend", fake_async_backend_cls, raising=False)
        with pytest.raises(SystemExit) as exc:
            status_mod.handle(make_args(["status", "all", "--database", "db", "--async"]))
        assert exc.value.code == 1

    def test_async_query_error_exits_nonzero(self, fake_async_backend_cls, monkeypatch):
        class ExplodingAsync(AsyncRecordingIntrospector):
            async def get_overview(self):
                raise QueryError("timeout")

        monkeypatch.setattr(
            f"{STATUS_INTROSPECTOR_MODULE}.AsyncSQLServerStatusIntrospector", ExplodingAsync
        )
        monkeypatch.setattr(backend_pkg, "AsyncSQLServerBackend", fake_async_backend_cls, raising=False)
        with pytest.raises(SystemExit) as exc:
            status_mod.handle(make_args(["status", "all", "--database", "db", "--async"]))
        assert exc.value.code == 1
