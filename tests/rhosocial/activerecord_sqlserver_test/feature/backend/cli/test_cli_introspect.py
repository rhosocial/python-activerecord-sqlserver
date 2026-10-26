# tests/rhosocial/activerecord_sqlserver_test/feature/backend/cli/test_cli_introspect.py
"""Offline black-box tests for the ``introspect`` subcommand.

The fakes below implement the *real* introspector API -- ``list_tables``,
``list_views``, ``list_columns``, ... plus this backend's ``list_schemas``/
``list_procedures``/``list_functions``/``list_sequences``. That matters: the
command used to call ``get_tables``/``get_views``/``get_columns``, which exist
nowhere in the backend, so every type failed against a real backend while the
old fakes happily answered methods of those names. ``test_dispatch_contract``
closes that gap by checking every type against the real introspector classes,
with no fake in the way.
"""
import argparse
import json

import pytest

from rhosocial.activerecord.backend.errors import ConnectionError, QueryError
from rhosocial.activerecord.backend.impl.sqlserver.backend import async_backend as async_backend_mod
from rhosocial.activerecord.backend.impl.sqlserver.cli import introspect as introspect_mod
from rhosocial.activerecord.backend.impl.sqlserver.introspection import (
    AsyncSQLServerIntrospector,
    SyncSQLServerIntrospector,
)


class FakeTable:
    """The shape ``get_table_info`` returns, as far as the CLI reads it."""

    def __init__(self, name):
        self.name = name
        self.columns = [{"method": "columns"}]
        self.indexes = [{"method": "indexes"}]
        self.foreign_keys = [{"method": "foreign_keys"}]


class FakeIntrospector:
    """Fixed-data stand-in recording calls with their kwargs."""

    instances = []

    def __init__(self):
        self.calls = []
        type(self).instances.append(self)

    def _record(self, method, **kwargs):
        self.calls.append((method, kwargs))
        return [{"method": method, **kwargs}]

    def list_tables(self, schema=None, include_system=False):
        return self._record("list_tables", schema=schema, include_system=include_system)

    def list_views(self, schema=None, include_system=False):
        return self._record("list_views", schema=schema, include_system=include_system)

    def list_columns(self, table_name, schema=None):
        return self._record("list_columns", table_name=table_name, schema=schema)

    def list_indexes(self, table_name, schema=None):
        return self._record("list_indexes", table_name=table_name, schema=schema)

    def list_foreign_keys(self, table_name, schema=None):
        return self._record("list_foreign_keys", table_name=table_name, schema=schema)

    def list_triggers(self, table_name=None, schema=None):
        return self._record("list_triggers", table_name=table_name, schema=schema)

    def list_procedures(self, schema=None):
        return self._record("list_procedures", schema=schema)

    def list_functions(self, schema=None):
        return self._record("list_functions", schema=schema)

    def list_sequences(self, schema=None):
        return self._record("list_sequences", schema=schema)

    def list_schemas(self):
        return self._record("list_schemas")

    def get_database_info(self):
        return {"db_name": "db", "version": "16.0.4250.1"}

    def get_table_info(self, table_name, schema=None):
        self.calls.append(("get_table_info", {"table_name": table_name, "schema": schema}))
        return FakeTable(table_name)


class FakeMissingTableIntrospector(FakeIntrospector):
    def get_table_info(self, table_name, schema=None):
        self.calls.append(("get_table_info", {"table_name": table_name, "schema": schema}))
        return None


class FakeAsyncIntrospector(FakeIntrospector):
    """The same records, awaited."""

    async def list_tables(self, schema=None, include_system=False):
        return FakeIntrospector.list_tables(self, schema, include_system)

    async def list_schemas(self):
        return FakeIntrospector.list_schemas(self)

    async def list_triggers(self, table_name=None, schema=None):
        return FakeIntrospector.list_triggers(self, table_name, schema)

    async def get_database_info(self):
        return FakeIntrospector.get_database_info(self)

    async def get_table_info(self, table_name, schema=None):
        return FakeIntrospector.get_table_info(self, table_name, schema)


class FakeBackendBase:
    created = []
    instances = []
    connect_error = None
    introspector_class = FakeIntrospector

    def __init__(self, connection_config=None):
        self.connection_config = connection_config
        self._connection = object()
        self.disconnects = 0
        self.introspector = self.introspector_class()
        type(self).created.append(connection_config)
        type(self).instances.append(self)

    def connect(self):
        if self.connect_error is not None:
            raise self.connect_error

    def disconnect(self):
        self.disconnects += 1


class FakeAsyncBackendBase(FakeBackendBase):
    introspector_class = FakeAsyncIntrospector

    async def connect(self):
        FakeBackendBase.connect(self)

    async def disconnect(self):
        self.disconnects += 1


def _tracking_class(base, name, introspector_class=None):
    attrs = {"created": [], "instances": []}
    if introspector_class is not None:
        attrs["introspector_class"] = introspector_class
    return type(name, (base,), attrs)


def _json_documents(text):
    """Every standalone JSON document in *text*, in order.

    A table detail is rendered as three sections, each its own document, so
    the output is not one JSON array.
    """
    decoder = json.JSONDecoder()
    index, documents = 0, []
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        document, index = decoder.raw_decode(text, index)
        documents.append(document)
    return documents


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
        introspect_mod,
        "SQLServerBackend",
        _tracking_class(FakeBackendBase, "FakeIntrospectBackend"),
    )
    FakeIntrospector.instances = []


def make_args(argv):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    introspect_mod.create_parser(sub)
    return parser.parse_args(argv)


class TestParserContract:
    def test_sqlserver_specific_types_accepted(self):
        assert make_args(["introspect", "procedures"]).type == "procedures"
        assert make_args(["introspect", "functions"]).type == "functions"

    def test_schemas_type_accepted(self):
        assert make_args(["introspect", "schemas"]).type == "schemas"

    def test_schema_flag_is_not_offered(self):
        with pytest.raises(SystemExit):
            make_args(["introspect", "tables", "--schema", "sales"])

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


class TestDispatchContract:
    """Every advertised type resolves to a method the real backend has.

    No fake and no server: this is the regression guard for the command
    calling methods (``get_tables`` and friends) that never existed.
    """

    @pytest.mark.parametrize("kind", introspect_mod.INTROSPECT_TYPES)
    def test_type_maps_to_a_real_method_on_both_managers(self, kind):
        argv = ["introspect", kind]
        if kind in ("columns", "indexes", "foreign-keys"):
            argv.append("users")
        for method, _kwargs in introspect_mod._steps(make_args(argv)):
            assert hasattr(SyncSQLServerIntrospector, method), method
            assert hasattr(AsyncSQLServerIntrospector, method), method

    def test_database_takes_no_object_name(self):
        """``database`` answers the database's own facts, with or without a name.

        It used to accept a table name and render that table's columns,
        indexes and foreign keys -- the same three questions the aggregate
        ``table`` type answered. Both are gone; a name is now simply unused.
        """
        assert introspect_mod._steps(make_args(["introspect", "database"])) == [
            ("get_database_info", {})
        ]


class TestHandleDispatch:
    @pytest.mark.parametrize(
        ("argv", "method"),
        [
            (["tables"], "list_tables"),
            (["views"], "list_views"),
            (["columns", "users"], "list_columns"),
            (["indexes", "users"], "list_indexes"),
            (["foreign-keys", "users"], "list_foreign_keys"),
            (["triggers"], "list_triggers"),
            (["procedures"], "list_procedures"),
            (["functions"], "list_functions"),
            (["sequences"], "list_sequences"),
            (["schemas"], "list_schemas"),
        ],
    )
    def test_types_dispatch_and_render_json(self, argv, method, capsys):
        introspect_mod.handle(make_args(["introspect"] + argv + ["--database", "db"]))
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, list)
        assert payload[0]["method"] == method

    def test_tables_receives_include_system_and_no_schema(self, capsys):
        introspect_mod.handle(
            make_args(["introspect", "tables", "--database", "db", "--include-system"])
        )
        method, kwargs = FakeIntrospector.instances[-1].calls[-1]
        assert method == "list_tables"
        assert kwargs == {"schema": None, "include_system": True}

    def test_schemas_take_no_scope_argument(self):
        introspect_mod.handle(make_args(["introspect", "schemas", "--database", "db"]))
        method, kwargs = FakeIntrospector.instances[-1].calls[-1]
        assert (method, kwargs) == ("list_schemas", {})


    @pytest.mark.parametrize("kind", ["columns", "indexes", "foreign-keys"])
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
        assert method == "list_triggers"
        assert kwargs["table_name"] == "users"

    def test_triggers_without_name_asks_once_for_all(self):
        introspect_mod.handle(make_args(["introspect", "triggers", "--database", "db"]))
        calls = FakeIntrospector.instances[-1].calls
        assert calls == [
            ("list_triggers", {"table_name": None, "schema": None}),
        ]

    def test_database_without_name_reports_database_info(self, capsys):
        introspect_mod.handle(make_args(["introspect", "database", "--database", "db"]))
        payload = json.loads(capsys.readouterr().out)
        assert payload == [{"db_name": "db", "version": "16.0.4250.1"}]

    def test_database_with_a_name_is_not_a_table_detail(self, capsys):
        """A name must not smuggle the aggregate back in.

        ``database users`` used to answer the same three-part table detail as
        ``table users``; both are gone, so the name changes nothing.
        """
        introspect_mod.handle(
            make_args(["introspect", "database", "users", "--database", "db"])
        )
        method, _kwargs = FakeIntrospector.instances[-1].calls[-1]
        assert method == "get_database_info"


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
        [
            (ConnectionError("refused"), None),
            (None, QueryError("syntax")),
            (None, RuntimeError("boom")),
        ],
    )
    def test_error_paths_exit_nonzero(self, monkeypatch, backend_error, introspector_exc):
        cls = _tracking_class(FakeBackendBase, "ErrBackend")
        if introspector_exc is not None:

            class Exploding(FakeIntrospector):
                def list_tables(self, schema=None, include_system=False):
                    raise introspector_exc

            cls.introspector_class = Exploding
        else:
            cls.connect_error = backend_error
        monkeypatch.setattr(introspect_mod, "SQLServerBackend", cls)
        with pytest.raises(SystemExit) as exc:
            introspect_mod.handle(make_args(["introspect", "tables", "--database", "db"]))
        assert exc.value.code != 0


class TestHandleAsync:
    def test_async_tables_dispatch(self, monkeypatch, capsys):
        monkeypatch.setattr(
            async_backend_mod,
            "AsyncSQLServerBackend",
            _tracking_class(FakeAsyncBackendBase, "AsyncFake"),
            raising=False,
        )
        introspect_mod.handle(
            make_args(["introspect", "tables", "--database", "db", "-o", "json", "--async"])
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["method"] == "list_tables"

    def test_async_schemas_dispatch(self, monkeypatch, capsys):
        monkeypatch.setattr(
            async_backend_mod,
            "AsyncSQLServerBackend",
            _tracking_class(FakeAsyncBackendBase, "AsyncSchemasFake"),
            raising=False,
        )
        introspect_mod.handle(
            make_args(["introspect", "schemas", "--database", "db", "-o", "json", "--async"])
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["method"] == "list_schemas"

    def test_async_connection_error_exits_nonzero(self, monkeypatch):
        cls = _tracking_class(FakeAsyncBackendBase, "AsyncErr")
        cls.connect_error = ConnectionError("refused")
        monkeypatch.setattr(async_backend_mod, "AsyncSQLServerBackend", cls, raising=False)
        with pytest.raises(SystemExit) as exc:
            introspect_mod.handle(
                make_args(["introspect", "tables", "--database", "db", "--async"])
            )
        assert exc.value.code != 0
