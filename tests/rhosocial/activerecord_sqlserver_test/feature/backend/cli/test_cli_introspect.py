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
    SQLServerIntrospector,
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

    def list_extended_properties(
        self,
        major_id=None,
        *,
        table_name=None,
        minor_id=None,
        class_name="OBJECT_OR_COLUMN",
        schema=None,
    ):
        return self._record("list_extended_properties", table_name=table_name, schema=schema)

    def get_view_info(self, view_name, schema=None):
        self.calls.append(("get_view_info", {"view_name": view_name, "schema": schema}))
        return {"name": view_name, "definition": "CREATE VIEW v AS SELECT 1"}

    def table_exists(self, table_name, schema=None):
        self.calls.append(("table_exists", {"table_name": table_name, "schema": schema}))
        return True

    def get_database_info(self):
        return {"db_name": "db", "version": "16.0.4250.1"}

    # ---- the nine families shared with the MySQL and PostgreSQL CLIs ----
    # Each records the call the way the families above do, so a branch that
    # names the wrong method, or drops an argument, shows up as a wrong
    # recorded call rather than as a plausible listing.

    def list_unused_indexes(self, schema=None):
        return self._record("list_unused_indexes", schema=schema)

    def list_table_usage_stats(self, schema=None):
        return self._record("list_table_usage_stats", schema=schema)

    def list_runtime_metrics(self, schema=None):
        return self._record("list_runtime_metrics", schema=schema)

    def list_index_usage_stats(self, schema=None):
        return self._record("list_index_usage_stats", schema=schema)

    def list_object_dependencies(self, object_name=None, schema=None):
        return self._record(
            "list_object_dependencies", object_name=object_name, schema=schema
        )

    def get_ddl_statement(self, object_name, schema=None):
        self.calls.append(
            ("get_ddl_statement", {"object_name": object_name, "schema": schema})
        )
        return {
            "schema": "dbo",
            "object_type": "TABLE",
            "object_name": object_name,
            "ddl": "CREATE TABLE [users] ([id] int)",
            "native": False,
        }

    def list_column_data_profiles(self, table_name, schema=None):
        return self._record("list_column_data_profiles", table_name=table_name, schema=schema)

    def sample_column_values(self, table_name, column_name, limit=100, schema=None):
        return self._record(
            "sample_column_values",
            table_name=table_name,
            column_name=column_name,
            limit=limit,
            schema=schema,
        )

    def estimate_join_coverage(
        self, left_table, left_column, right_table, right_column, schema=None
    ):
        self.calls.append(
            (
                "estimate_join_coverage",
                {
                    "left_table": left_table,
                    "left_column": left_column,
                    "right_table": right_table,
                    "right_column": right_column,
                    "schema": schema,
                },
            )
        )
        return {
            "left_table": left_table,
            "left_column": left_column,
            "right_table": right_table,
            "right_column": right_column,
            "left_coverage": 1.0,
            "right_coverage": 0.5,
        }

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

    async def list_extended_properties(
        self,
        major_id=None,
        *,
        table_name=None,
        minor_id=None,
        class_name="OBJECT_OR_COLUMN",
        schema=None,
    ):
        return FakeIntrospector.list_extended_properties(
            self,
            major_id,
            table_name=table_name,
            minor_id=minor_id,
            class_name=class_name,
            schema=schema,
        )

    async def get_view_info(self, view_name, schema=None):
        return FakeIntrospector.get_view_info(self, view_name, schema)

    async def table_exists(self, table_name, schema=None):
        return FakeIntrospector.table_exists(self, table_name, schema)

    async def get_database_info(self):
        return FakeIntrospector.get_database_info(self)

    async def get_table_info(self, table_name, schema=None):
        return FakeIntrospector.get_table_info(self, table_name, schema)

    async def list_unused_indexes(self, schema=None):
        return FakeIntrospector.list_unused_indexes(self, schema)

    async def list_table_usage_stats(self, schema=None):
        return FakeIntrospector.list_table_usage_stats(self, schema)

    async def list_runtime_metrics(self, schema=None):
        return FakeIntrospector.list_runtime_metrics(self, schema)

    async def list_index_usage_stats(self, schema=None):
        return FakeIntrospector.list_index_usage_stats(self, schema)

    async def list_object_dependencies(self, object_name=None, schema=None):
        return FakeIntrospector.list_object_dependencies(self, object_name, schema)

    async def get_ddl_statement(self, object_name, schema=None):
        return FakeIntrospector.get_ddl_statement(self, object_name, schema)

    async def list_column_data_profiles(self, table_name, schema=None):
        return FakeIntrospector.list_column_data_profiles(self, table_name, schema)

    async def sample_column_values(self, table_name, column_name, limit=100, schema=None):
        return FakeIntrospector.sample_column_values(
            self, table_name, column_name, limit, schema
        )

    async def estimate_join_coverage(
        self, left_table, left_column, right_table, right_column, schema=None
    ):
        return FakeIntrospector.estimate_join_coverage(
            self, left_table, left_column, right_table, right_column, schema
        )


class FakeBackendBase:
    created = []
    instances = []
    connect_error = None
    introspector_class = FakeIntrospector

    def __init__(self, connection_config=None):
        self.connection_config = connection_config
        self._connection = object()
        self.disconnects = 0
        self.adaptations = 0
        self.introspector = self.introspector_class()
        type(self).created.append(connection_config)
        type(self).instances.append(self)

    def connect(self):
        if self.connect_error is not None:
            raise self.connect_error

    def introspect_and_adapt(self):
        # The command must ask the server what it is talking to before the
        # first question; the capability gates and version rendering need it.
        self.adaptations += 1

    def disconnect(self):
        self.disconnects += 1


class FakeAsyncBackendBase(FakeBackendBase):
    introspector_class = FakeAsyncIntrospector

    async def connect(self):
        FakeBackendBase.connect(self)

    async def introspect_and_adapt(self):
        FakeBackendBase.introspect_and_adapt(self)

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
        if kind in ("columns", "indexes", "foreign-keys", "extended-properties",
                    "ddl", "column-profiles", "value-samples"):
            argv.append("users")
        if kind == "value-samples":
            argv += ["--column", "status"]
        if kind == "join-coverage":
            argv += ["--left-table", "orders", "--left-column", "customer_id",
                     "--right-table", "customers", "--right-column", "id"]
        for method, _kwargs in introspect_mod._steps(make_args(argv)):
            assert hasattr(SQLServerIntrospector, method), method
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
            (["extended-properties", "users"], "list_extended_properties"),
            (["triggers"], "list_triggers"),
            (["procedures"], "list_procedures"),
            (["functions"], "list_functions"),
            (["sequences"], "list_sequences"),
            (["schemas"], "list_schemas"),
            # The nine families shared with the MySQL and PostgreSQL CLIs.
            # ``table-stats`` and ``ddl`` are refused by the dialect's own
            # answer, so their rows below are what the branch *would* ask:
            # the capability gate stops a real run before that, and the
            # dedicated test file asserts both halves.
            (["unused-indexes"], "list_unused_indexes"),
            (["table-stats"], "list_table_usage_stats"),
            (["runtime"], "list_runtime_metrics"),
            (["index-stats"], "list_index_usage_stats"),
            (["dependencies"], "list_object_dependencies"),
            (["dependencies", "orders"], "list_object_dependencies"),
            (["column-profiles", "orders"], "list_column_data_profiles"),
            (
                ["value-samples", "orders", "--column", "status"],
                "sample_column_values",
            ),
            (
                [
                    "join-coverage",
                    "--left-table", "orders",
                    "--left-column", "customer_id",
                    "--right-table", "customers",
                    "--right-column", "id",
                ],
                "estimate_join_coverage",
            ),
        ],
    )
    def test_types_dispatch_and_render_json(self, argv, method, capsys):
        if method == "estimate_join_coverage":
            # The coverage answer is a record of its own, not the ``_record``
            # shape the other families return; the four names it carries are
            # asserted by the test beside this one.
            pytest.skip("asserted by test_join_coverage_receives_the_four_names")
        introspect_mod.handle(make_args(["introspect"] + argv + ["--database", "db"]))
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, list)
        assert payload[0]["method"] == method

    def test_ddl_prints_the_engine_text_and_keeps_the_native_flag(self, capsys):
        """A DDL text is a block, so the table format prints it as one; the
        machine formats keep the record, ``native`` included."""
        introspect_mod.handle(
            make_args(["introspect", "ddl", "users", "--database", "db", "-o", "json"])
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["object_name"] == "users"
        assert payload[0]["ddl"] == "CREATE TABLE [users] ([id] int)"
        assert payload[0]["native"] is False

    def test_join_coverage_receives_the_four_names(self, capsys):
        introspect_mod.handle(
            make_args([
                "introspect", "join-coverage",
                "--left-table", "orders",
                "--left-column", "customer_id",
                "--right-table", "customers",
                "--right-column", "id",
                "--database", "db",
            ])
        )
        method, kwargs = FakeIntrospector.instances[-1].calls[-1]
        assert method == "estimate_join_coverage"
        assert kwargs == {
            "left_table": "orders",
            "left_column": "customer_id",
            "right_table": "customers",
            "right_column": "id",
            "schema": None,
        }
        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["left_coverage"] == 1.0
        assert payload[0]["right_coverage"] == 0.5

    def test_a_coverage_the_server_cannot_measure_is_an_error(self, monkeypatch, capsys):
        """``None`` is "not measured", which is not a zero-overlap answer."""

        class UnmeasurableIntrospector(FakeIntrospector):
            def estimate_join_coverage(self, *args, **kwargs):
                return None

        monkeypatch.setattr(
            introspect_mod,
            "SQLServerBackend",
            _tracking_class(
                FakeBackendBase, "UnmeasurableBackend", UnmeasurableIntrospector
            ),
        )
        with pytest.raises(SystemExit) as exc:
            introspect_mod.handle(
                make_args([
                    "introspect", "join-coverage",
                    "--left-table", "orders",
                    "--left-column", "customer_id",
                    "--right-table", "customers",
                    "--right-column", "id",
                    "--database", "db",
                ])
            )
        assert exc.value.code == 1
        assert "could not measure" in capsys.readouterr().err

    def test_tables_receives_include_system_and_no_schema(self, capsys):
        introspect_mod.handle(
            make_args(["introspect", "tables", "--database", "db", "--include-system"])
        )
        method, kwargs = FakeIntrospector.instances[-1].calls[-1]
        assert method == "list_tables"
        assert kwargs == {"schema": None, "include_system": True}

    def test_the_backend_is_adapted_before_the_first_question(self):
        introspect_mod.handle(
            make_args(["introspect", "tables", "--database", "db"])
        )
        # The capability gates and version rendering need the handshake's
        # version; the command must ask for it rather than hope something did.
        assert introspect_mod.SQLServerBackend.instances[-1].adaptations == 1

    def test_schemas_take_no_scope_argument(self):
        introspect_mod.handle(make_args(["introspect", "schemas", "--database", "db"]))
        method, kwargs = FakeIntrospector.instances[-1].calls[-1]
        assert (method, kwargs) == ("list_schemas", {})


    @pytest.mark.parametrize(
        "kind", ["columns", "indexes", "foreign-keys", "extended-properties"]
    )
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

    def test_views_without_a_name_lists(self):
        introspect_mod.handle(make_args(["introspect", "views", "--database", "db"]))
        method, kwargs = FakeIntrospector.instances[-1].calls[-1]
        assert (method, kwargs) == ("list_views", {"schema": None, "include_system": False})

    def test_views_with_a_name_asks_the_single_view(self, capsys):
        """A name is the single-view question, not a filter over the list."""
        introspect_mod.handle(
            make_args(["introspect", "views", "active_users", "--database", "db"])
        )
        method, kwargs = FakeIntrospector.instances[-1].calls[-1]
        assert (method, kwargs) == ("get_view_info", {"view_name": "active_users", "schema": None})
        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["definition"]

    def test_a_view_that_is_not_there_exits_one(self, monkeypatch, capsys):
        class MissingViewIntrospector(FakeIntrospector):
            def get_view_info(self, view_name, schema=None):
                return None

        monkeypatch.setattr(
            introspect_mod,
            "SQLServerBackend",
            _tracking_class(FakeBackendBase, "MissingViewBackend", MissingViewIntrospector),
        )
        with pytest.raises(SystemExit) as exc:
            introspect_mod.handle(make_args(["introspect", "views", "nope", "--database", "db"]))
        assert exc.value.code == 1
        assert "View 'nope' not found" in capsys.readouterr().err

    def test_extended_properties_ask_by_table_name(self):
        """A name is the whole question: the statement resolves the object id."""
        introspect_mod.handle(
            make_args(["introspect", "extended-properties", "users", "--database", "db"])
        )
        method, kwargs = FakeIntrospector.instances[-1].calls[-1]
        assert (method, kwargs) == (
            "list_extended_properties",
            {"table_name": "users", "schema": None},
        )

    def test_a_table_without_properties_is_not_a_missing_table(
        self, monkeypatch, capsys
    ):
        """No rows and no table are two answers, and only the second is an error."""

        class NoPropertiesIntrospector(FakeIntrospector):
            def list_extended_properties(self, *args, **kwargs):
                return []

        monkeypatch.setattr(
            introspect_mod,
            "SQLServerBackend",
            _tracking_class(FakeBackendBase, "NoPropertiesBackend", NoPropertiesIntrospector),
        )
        introspect_mod.handle(
            make_args(["introspect", "extended-properties", "users", "--database", "db"])
        )
        assert json.loads(capsys.readouterr().out) == []

    def test_an_unknown_table_exits_one(self, monkeypatch, capsys):
        class UnknownTableIntrospector(FakeIntrospector):
            def list_extended_properties(self, *args, **kwargs):
                return []

            def table_exists(self, table_name, schema=None):
                return False

        monkeypatch.setattr(
            introspect_mod,
            "SQLServerBackend",
            _tracking_class(FakeBackendBase, "UnknownTableBackend", UnknownTableIntrospector),
        )
        with pytest.raises(SystemExit) as exc:
            introspect_mod.handle(
                make_args(
                    ["introspect", "extended-properties", "ghost", "--database", "db"]
                )
            )
        assert exc.value.code == 1
        assert "Table 'ghost' not found" in capsys.readouterr().err

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

    def test_database_with_a_name_is_refused(self):
        """A name must not smuggle the aggregate back in -- nor be ignored.

        ``database users`` used to answer the same three-part table detail as
        ``table users``. Both are gone. A name is now refused instead of
        ignored: silently answering the unnamed question reads as a filter that
        matched everything, which is the one shape a wrong answer must not take.
        """
        with pytest.raises(SystemExit) as exc:
            introspect_mod.handle(
                make_args(["introspect", "database", "users", "--database", "db"])
            )
        assert exc.value.code == 2


class TestDeclaredVocabulary:
    """The advertised types, the switches and the NAME rules are one statement."""

    def test_the_advertised_list_is_the_capability_table(self):
        assert list(introspect_mod._TYPE_CAPABILITIES) == introspect_mod.INTROSPECT_TYPES

    def test_every_declared_type_has_a_name_rule(self):
        assert set(introspect_mod._NAME_RULE) == set(introspect_mod.INTROSPECT_TYPES)

    def test_the_removed_aggregate_is_not_readvertised(self):
        assert "table" not in introspect_mod.INTROSPECT_TYPES
        assert "table" not in introspect_mod._TYPE_CAPABILITIES

    @pytest.mark.parametrize(
        ("kind", "switch"), sorted(introspect_mod._TYPE_CAPABILITIES.items())
    )
    def test_every_switch_is_declared_by_the_dialect(self, kind, switch):
        from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

        dialect = SQLServerDialect(version=(16, 0, 0))
        answer = getattr(dialect, switch, None)
        assert callable(answer), f"{kind} names {switch}, which the dialect lacks"

    #: The two families SQL Server does not answer. The CLI offers them all
    #: the same -- a type the engine refuses is refused at the capability
    #: question with exit 2, not hidden from the parser -- so these are
    #: asserted as the dialect's "no" rather than dropped from the table.
    UNANSWERED_SWITCHES = {
        "table-stats": "supports_table_stats",
        "ddl": "supports_ddl_extraction",
    }

    def test_the_two_unanswered_families_are_refused_by_the_dialect(self):
        from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

        dialect = SQLServerDialect(version=(16, 0, 0))
        for kind, switch in self.UNANSWERED_SWITCHES.items():
            assert introspect_mod._TYPE_CAPABILITIES[kind] == switch
            assert getattr(dialect, switch)() is False, kind

    def test_every_answered_family_answers_true(self):
        """2022 is the newest release the matrix runs; every family the engine
        answers must answer there.

        The version floors the DMV families carry -- 2005 for the index usage
        view and the performance counters, 2008 for the dependency view, 2012
        for the pagination clause ``value-samples`` renders -- are all below
        it, so a gate that refused here would be a gate set one release too
        high.
        """
        from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

        dialect = SQLServerDialect(version=(16, 0, 0))
        for kind, switch in introspect_mod._TYPE_CAPABILITIES.items():
            if kind in self.UNANSWERED_SWITCHES:
                continue
            assert getattr(dialect, switch)() is True, kind

    def test_help_lists_every_declared_type(self, capsys):
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        introspect_mod.create_parser(sub)
        with pytest.raises(SystemExit):
            parser.parse_args(["introspect", "--help"])
        help_text = capsys.readouterr().out
        for kind in introspect_mod.INTROSPECT_TYPES:
            assert kind in help_text


class TestSupportedScopes:
    """``get_supported_introspection_scopes`` is not core's empty default."""

    @staticmethod
    def _scopes():
        from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

        return SQLServerDialect(version=(16, 0, 0)).get_supported_introspection_scopes()

    def test_the_scopes_are_the_families_that_answer(self):
        from rhosocial.activerecord.backend.introspection.types import IntrospectionScope

        assert set(self._scopes()) == {
            IntrospectionScope.DATABASE,
            IntrospectionScope.TABLE,
            IntrospectionScope.COLUMN,
            IntrospectionScope.INDEX,
            IntrospectionScope.FOREIGN_KEY,
            IntrospectionScope.VIEW,
            IntrospectionScope.TRIGGER,
            IntrospectionScope.SEQUENCE,
        }

    def test_a_caller_is_not_told_nothing(self):
        assert self._scopes()

    def test_every_declared_switch_answers_true(self):
        """Kept for the families the engine answers; the two it does not are
        asserted False in :class:`TestDeclaredVocabulary` instead."""
        from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

        dialect = SQLServerDialect(version=(16, 0, 0))
        for kind, switch in introspect_mod._TYPE_CAPABILITIES.items():
            if kind in TestDeclaredVocabulary.UNANSWERED_SWITCHES:
                continue
            assert getattr(dialect, switch)() is True, switch


class TestCapabilityGate:
    def test_a_switch_that_says_no_refuses_the_type(self, monkeypatch, capsys):
        cls = _tracking_class(FakeBackendBase, "RefusingBackend")
        cls.dialect = type(
            "RefusingDialect",
            (),
            {"supports_table_introspection": lambda self: False},
        )()
        monkeypatch.setattr(introspect_mod, "SQLServerBackend", cls)
        with pytest.raises(SystemExit) as exc:
            introspect_mod.handle(make_args(["introspect", "tables", "--database", "db"]))
        assert exc.value.code == 2
        assert (
            "Error: tables introspection is not supported by this server"
            in capsys.readouterr().err
        )
        # Asked after the adaptation: the switch answers for this server.
        assert cls.instances[-1].adaptations == 1
        assert cls.instances[-1].introspector.calls == [], "refused before the question"

    def test_a_stub_without_a_dialect_is_not_refused(self):
        """The offline fakes have no dialect; the gate must not invent one."""
        introspect_mod.handle(make_args(["introspect", "tables", "--database", "db"]))
        assert FakeIntrospector.instances[-1].calls != []


class TestNameGate:
    @pytest.mark.parametrize(
        "kind",
        ["tables", "database", "procedures", "functions", "sequences", "schemas"],
    )
    def test_a_name_the_type_cannot_use_exits_two(self, kind, capsys):
        with pytest.raises(SystemExit) as exc:
            introspect_mod.handle(
                make_args(["introspect", kind, "users", "--database", "db"])
            )
        assert exc.value.code == 2
        assert f"Error: {kind} introspection takes no name" in capsys.readouterr().err

    def test_a_forbidden_name_is_refused_before_connecting(self, capsys):
        with pytest.raises(SystemExit):
            introspect_mod.handle(
                make_args(["introspect", "schemas", "dbo", "--database", "db"])
            )
        assert introspect_mod.SQLServerBackend.created == []
        assert "takes no name" in capsys.readouterr().err

    def test_the_optional_names_are_not_refused(self):
        introspect_mod.handle(make_args(["introspect", "views", "users", "--database", "db"]))
        assert FakeIntrospector.instances[-1].calls[-1][0] == "get_view_info"
        introspect_mod.handle(
            make_args(["introspect", "triggers", "users", "--database", "db"])
        )
        assert FakeIntrospector.instances[-1].calls[-1][0] == "list_triggers"


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
        cls = _tracking_class(FakeAsyncBackendBase, "AsyncFake")
        monkeypatch.setattr(
            async_backend_mod,
            "AsyncSQLServerBackend",
            cls,
            raising=False,
        )
        introspect_mod.handle(
            make_args(["introspect", "tables", "--database", "db", "-o", "json", "--async"])
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["method"] == "list_tables"
        assert cls.instances[-1].adaptations == 1

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

    def test_async_extended_properties_dispatch(self, monkeypatch, capsys):
        monkeypatch.setattr(
            async_backend_mod,
            "AsyncSQLServerBackend",
            _tracking_class(FakeAsyncBackendBase, "AsyncExtFake"),
            raising=False,
        )
        introspect_mod.handle(
            make_args(
                [
                    "introspect",
                    "extended-properties",
                    "users",
                    "--database",
                    "db",
                    "-o",
                    "json",
                    "--async",
                ]
            )
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["method"] == "list_extended_properties"

    def test_async_unknown_table_exits_one(self, monkeypatch, capsys):
        """The existence read is awaited too, not left as an unfired coroutine."""

        class UnknownTable(FakeAsyncIntrospector):
            async def list_extended_properties(self, *args, **kwargs):
                return []

            async def table_exists(self, table_name, schema=None):
                return False

        monkeypatch.setattr(
            async_backend_mod,
            "AsyncSQLServerBackend",
            _tracking_class(FakeAsyncBackendBase, "AsyncUnknownTable", UnknownTable),
            raising=False,
        )
        with pytest.raises(SystemExit) as exc:
            introspect_mod.handle(
                make_args(
                    [
                        "introspect",
                        "extended-properties",
                        "ghost",
                        "--database",
                        "db",
                        "--async",
                    ]
                )
            )
        assert exc.value.code == 1
        assert "Table 'ghost' not found" in capsys.readouterr().err
