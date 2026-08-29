# tests/rhosocial/activerecord_sqlserver_test/feature/backend/cli/test_cli_introspect.py
"""Offline black-box tests for the ``introspect`` subcommand.

All ``cli/introspect.py`` dispatch branches run against a fake backend whose
``introspector`` returns fixed data, so every type (including the SQL Server
specific ``procedures``/``functions``) is covered without a live server.
"""
import argparse
import json

import pytest

from rhosocial.activerecord.backend.errors import ConnectionError, QueryError
from rhosocial.activerecord.backend.impl import sqlserver as backend_pkg
from rhosocial.activerecord.backend.impl.sqlserver.cli import introspect as introspect_mod


class FakeIntrospector:
    """Fixed-data stand-in recording calls with their kwargs."""

    instances = []
    # When set, ``get_tables`` returns this instead of the default payload.
    tables_override = None

    def __init__(self):
        self.calls = []
        type(self).instances.append(self)

    def _record(self, method, **kwargs):
        self.calls.append((method, kwargs))
        return [{"method": method, **kwargs}]

    def get_tables(self, schema=None):
        if self.tables_override is not None:
            return self.tables_override
        return self._record("get_tables", schema=schema)

    def get_views(self, schema=None):
        return self._record("get_views", schema=schema)

    def get_columns(self, table, schema=None):
        return self._record("get_columns", table=table, schema=schema)

    def get_indexes(self, table, schema=None):
        return self._record("get_indexes", table=table, schema=schema)

    def get_foreign_keys(self, table, schema=None):
        return self._record("get_foreign_keys", table=table, schema=schema)

    def get_triggers(self, table=None, schema=None):
        if table == "explode":
            raise RuntimeError("trigger probe failed")
        return self._record("get_triggers", table=table, schema=schema)

    def get_constraints(self, table=None, schema=None):
        return self._record("get_constraints", table=table, schema=schema)

    def get_procedures(self, schema=None):
        return self._record("get_procedures", schema=schema)

    def get_functions(self, schema=None):
        return self._record("get_functions", schema=schema)

    def get_sequences(self, schema=None):
        return self._record("get_sequences", schema=schema)


class FakeBackendBase:
    created = []
    instances = []
    connect_error = None

    def __init__(self, connection_config=None):
        self.connection_config = connection_config
        self._connection = object()
        self.disconnects = 0
        self.introspector = FakeIntrospector()
        type(self).created.append(connection_config)
        type(self).instances.append(self)

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


def _tracking_class(base, name):
    return type(name, (base,), {"created": [], "instances": []})


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    import os

    for key in list(os.environ):
        if key.startswith("SQLSERVER_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def _patched(monkeypatch):
    """Patch sync backend construction and reset per-test recording state."""
    monkeypatch.setattr(
        introspect_mod, "SQLServerBackend", _tracking_class(FakeBackendBase, "FakeIntrospectBackend")
    )
    FakeIntrospector.instances = []
    FakeIntrospector.tables_override = None


def make_args(argv):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    introspect_mod.create_parser(sub)
    return parser.parse_args(argv)


class TestParserContract:
    def test_sqlserver_specific_types_accepted(self):
        assert make_args(["introspect", "procedures"]).type == "procedures"
        assert make_args(["introspect", "functions"]).type == "functions"

    def test_schema_defaults_to_dbo(self):
        args = make_args(["introspect", "tables"])
        assert args.schema == "dbo"
        assert make_args(["introspect", "tables", "--schema", "sales"]).schema == "sales"

    def test_name_optional_and_include_system_flag(self):
        args = make_args(["introspect", "columns", "users"])
        assert (args.type, args.name) == ("columns", "users")
        assert make_args(["introspect", "triggers"]).include_system is False

    def test_unknown_type_rejected(self):
        with pytest.raises(SystemExit):
            make_args(["introspect", "grants"])

    def test_missing_database_exits_before_backend_creation(self, capsys):
        with pytest.raises(SystemExit) as exc:
            introspect_mod.handle(make_args(["introspect", "tables"]))
        assert exc.value.code == 1
        assert "--database is required" in capsys.readouterr().err
        assert introspect_mod.SQLServerBackend.created == []


class TestHandleDispatch:
    @pytest.mark.parametrize(
        "argv",
        [
            ["tables"],
            ["views"],
            ["columns", "users"],
            ["indexes", "users"],
            ["foreign-keys", "users"],
            ["procedures"],
            ["functions"],
            ["sequences"],
        ],
    )
    def test_types_dispatch_and_render_json(self, argv, capsys):
        introspect_mod.handle(make_args(["introspect"] + argv + ["--database", "db"]))
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, list) and payload[0]["method"]

    def test_tables_receives_schema(self, capsys):
        introspect_mod.handle(
            make_args(["introspect", "tables", "--database", "db", "--schema", "sales"])
        )
        method, kwargs = FakeIntrospector.instances[-1].calls[-1]
        assert method == "get_tables"
        assert kwargs["schema"] == "sales"

    def test_table_detail_shows_columns_indexes_fks(self, capsys):
        introspect_mod.handle(make_args(["introspect", "table", "users", "--database", "db"]))
        inst = FakeIntrospector.instances[-1]
        methods = [m for m, _ in inst.calls]
        assert methods == ["get_columns", "get_indexes", "get_foreign_keys"]
        assert all(kwargs["table"] == "users" for _, kwargs in inst.calls)

    @pytest.mark.parametrize("kind", ["table", "columns", "indexes", "foreign-keys"])
    def test_missing_name_exits_for_table_scoped_types(self, kind, capsys):
        with pytest.raises(SystemExit) as exc:
            introspect_mod.handle(make_args(["introspect", kind, "--database", "db"]))
        assert exc.value.code == 1
        assert "Table name is required" in capsys.readouterr().err

    def test_triggers_with_table_name(self, capsys):
        introspect_mod.handle(
            make_args(["introspect", "triggers", "users", "--database", "db"])
        )
        method, kwargs = FakeIntrospector.instances[-1].calls[-1]
        assert method == "get_triggers"
        assert kwargs["table"] == "users"

    def test_triggers_without_name_iterates_all_tables(self):
        FakeIntrospector.tables_override = [
            type("T", (), {"name": "users"}),
            type("T", (), {"name": "orders"}),
        ]
        introspect_mod.handle(make_args(["introspect", "triggers", "--database", "db"]))
        trigger_calls = [
            k["table"] for m, k in FakeIntrospector.instances[-1].calls if m == "get_triggers"
        ]
        assert trigger_calls == ["users", "orders"]

    def test_triggers_iteration_swallows_per_table_errors(self):
        FakeIntrospector.tables_override = [
            type("T", (), {"name": "explode"}),
            type("T", (), {"name": "safe"}),
        ]
        introspect_mod.handle(make_args(["introspect", "triggers", "--database", "db"]))
        trigger_calls = [
            k["table"] for m, k in FakeIntrospector.instances[-1].calls if m == "get_triggers"
        ]
        assert trigger_calls == ["safe"]  # failure probing 'explode' is not fatal

    def test_database_without_name_lists_tables_and_schema(self, capsys):
        introspect_mod.handle(make_args(["introspect", "database", "--database", "db"]))
        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["schema"] == "dbo"
        assert payload[0]["tables"][0]["method"] == "get_tables"

    def test_database_with_name_shows_constraints(self, capsys):
        introspect_mod.handle(
            make_args(["introspect", "database", "users", "--database", "db"])
        )
        method, kwargs = FakeIntrospector.instances[-1].calls[-1]
        assert method == "get_constraints"
        assert kwargs["table"] == "users"


class TestHandleLifecycleAndConfig:
    def test_connection_config_resolved_from_args(self):
        introspect_mod.handle(
            make_args(
                ["introspect", "tables", "--host", "srv9", "--port", "1500", "--database", "db"]
            )
        )
        config = introspect_mod.SQLServerBackend.created[-1]
        assert config.host == "srv9"
        assert config.port == 1500
        assert config.database == "db"

    def test_disconnect_called_in_finally(self):
        introspect_mod.handle(make_args(["introspect", "views", "--database", "db"]))
        assert introspect_mod.SQLServerBackend.instances[-1].disconnects >= 1


class TestHandleErrors:
    @pytest.mark.parametrize(
        ("backend_error", "introspector_exc"),
        [(ConnectionError("refused"), None), (None, QueryError("syntax")), (None, RuntimeError("boom"))],
    )
    def test_error_paths_exit_nonzero(self, monkeypatch, backend_error, introspector_exc):
        cls = _tracking_class(FakeBackendBase, "ErrBackend")
        if introspector_exc is not None:

            class Exploding(FakeIntrospector):
                def get_tables(self, schema=None):
                    raise introspector_exc

            orig_init = cls.__init__

            def init_with_exploding(self, connection_config=None):
                orig_init(self, connection_config=connection_config)
                self.introspector = Exploding()

            cls.__init__ = init_with_exploding
        else:
            cls.connect_error = backend_error
        monkeypatch.setattr(introspect_mod, "SQLServerBackend", cls)
        with pytest.raises(SystemExit) as exc:
            introspect_mod.handle(make_args(["introspect", "tables", "--database", "db"]))
        assert exc.value.code != 0


class TestHandleAsync:
    def test_async_tables_dispatch(self, monkeypatch, capsys):
        monkeypatch.setattr(
            backend_pkg,
            "AsyncSQLServerBackend",
            _tracking_class(FakeAsyncBackendBase, "AsyncFake"),
            raising=False,
        )
        introspect_mod.handle(
            make_args(["introspect", "tables", "--database", "db", "-o", "json", "--async"])
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["method"] == "get_tables"

    def test_async_connection_error_exits_nonzero(self, monkeypatch):
        cls = _tracking_class(FakeAsyncBackendBase, "AsyncErr")
        cls.connect_error = ConnectionError("refused")
        monkeypatch.setattr(backend_pkg, "AsyncSQLServerBackend", cls, raising=False)
        with pytest.raises(SystemExit) as exc:
            introspect_mod.handle(
                make_args(["introspect", "tables", "--database", "db", "--async"])
            )
        assert exc.value.code != 0
