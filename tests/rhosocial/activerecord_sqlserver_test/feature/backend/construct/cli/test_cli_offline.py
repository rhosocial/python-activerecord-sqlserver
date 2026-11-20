# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/cli/test_cli_offline.py
"""Connectionless CLI unit tests for the ``info``, ``status`` and
``named-expression`` subcommands.

The focus is the not-yet-covered surface: rich-rendering helpers, the native
async status path, and the named-expression adapter's callback seams. Every
backend, provider and I/O boundary is a ``MagicMock``/``AsyncMock``; no SQL
Server connection is attempted.
"""

import argparse
import json
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from rhosocial.activerecord.backend.errors import ConnectionError, QueryError
from rhosocial.activerecord.backend.introspection.status import StatusCategory
from rhosocial.activerecord.backend.impl.sqlserver.backend import async_backend as async_backend_mod
from rhosocial.activerecord.backend.impl.sqlserver.cli import info as info_mod
from rhosocial.activerecord.backend.impl.sqlserver.cli import named_expression as ne_mod
from rhosocial.activerecord.backend.impl.sqlserver.cli import status as status_mod
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

STATUS_INTROSPECTOR = (
    "rhosocial.activerecord.backend.impl.sqlserver.introspection.status_introspector"
)


def make_args(create_parser, argv):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    create_parser(sub)
    return parser.parse_args(argv)


@pytest.fixture
def fake_rich(monkeypatch):
    """Install module-level MagicMock stand-ins for the optional rich package."""
    console_mod = types.ModuleType("rich.console")
    console_mod.Console = MagicMock(name="Console")
    table_mod = types.ModuleType("rich.table")
    table_mod.Table = MagicMock(name="Table")
    rich_mod = types.ModuleType("rich")
    rich_mod.console = console_mod
    rich_mod.table = table_mod
    monkeypatch.setitem(sys.modules, "rich", rich_mod)
    monkeypatch.setitem(sys.modules, "rich.console", console_mod)
    monkeypatch.setitem(sys.modules, "rich.table", table_mod)
    return console_mod.Console.return_value


def printed(console):
    """Flatten all positional strings passed to ``console.print``."""
    return " ".join(
        str(arg)
        for call in console.print.call_args_list
        for arg in call.args
    )


class TestInfoRichDisplayHelpers:
    def test_format_method_display(self):
        assert info_mod._format_method_display("supports_explain_format") == "explain format"
        assert info_mod._format_method_display("is_json_available") == "is json available"

    def test_display_method_details_bool_values(self, fake_rich):
        info_mod._display_method_details(fake_rich, "supports_cte", True)
        info_mod._display_method_details(fake_rich, "supports_graph", False)
        out = printed(fake_rich)
        assert "[green][OK][/green]" in out
        assert "[red][X][/red]" in out
        assert "cte" in out

    def test_display_method_details_dict_value(self, fake_rich):
        info_mod._display_method_details(
            fake_rich, "supports_explain_format", {"args": {"TEXT": True, "XML": False}}
        )
        out = printed(fake_rich)
        assert "TEXT" in out and "XML" in out

    def test_display_protocol_item_progress_bar(self, fake_rich):
        stats = {"percentage": 100, "supported": 2, "total": 2}
        info_mod._display_protocol_item(fake_rich, "CTESupport", stats, verbose=0)
        out = printed(fake_rich)
        assert "CTESupport" in out
        assert "####################" in out
        assert "(2/2)" in out

    def test_display_protocol_item_verbose_methods(self, fake_rich):
        stats = {
            "percentage": 50,
            "supported": 1,
            "total": 2,
            "methods": {"supports_cte": True},
        }
        info_mod._display_protocol_item(fake_rich, "CTESupport", stats, verbose=2)
        assert "cte" in printed(fake_rich)

    @staticmethod
    def _stats():
        return {"percentage": 100, "supported": 1, "total": 1}

    def test_display_protocol_group_marks_dialect_specific(self, fake_rich):
        info_mod._display_protocol_group(
            fake_rich, "SQL Server Native", {"IdentitySupport": self._stats()}, 0
        )
        assert "(dialect-specific)" in printed(fake_rich)

    def test_display_protocol_group_normal(self, fake_rich):
        info_mod._display_protocol_group(
            fake_rich, "Query Features", {"CTESupport": self._stats()}, 0
        )
        assert "Query Features" in printed(fake_rich)

    @pytest.mark.parametrize("connected", [True, False])
    def test_display_info_rich_header(self, fake_rich, connected):
        info = {
            "protocols": {
                "Query Features": {
                    "CTESupport": {
                        "percentage": 100,
                        "supported": 1,
                        "total": 1,
                    }
                }
            }
        }
        info_mod._display_info_rich(info, 0, "16.0.0", is_connected=connected)
        out = printed(fake_rich)
        assert "SQL Server Environment Information" in out
        assert "16.0.0" in out
        assert ("from actual connection" in out) is connected


class TestInfoCheckProtocolEdges:
    def _protocol(self):
        class ProbeProtocol:
            def supports_simple(self):
                return True

            def supports_with_arg(self, level):
                return True

            def supports_boom(self, level):
                raise RuntimeError("bad probe")

        return ProbeProtocol

    def test_method_with_required_param_not_in_all_args_is_false(self):
        dialect = SimpleNamespace(
            supports_simple=lambda: True,
            supports_with_arg=lambda level: True,
        )
        results = info_mod.check_protocol_support(dialect, self._protocol())
        assert results["supports_simple"] is True
        assert results["supports_with_arg"] is False

    def test_method_raising_on_argument_is_false(self):
        dialect = SimpleNamespace(
            supports_simple=lambda: True,
            supports_boom=lambda level: 1 / 0,
        )
        results = info_mod.check_protocol_support(dialect, self._protocol())
        assert results["supports_boom"] is False


class TestInfoHandleBranches:
    def test_table_format_uses_rich_display_when_available(self, monkeypatch):
        monkeypatch.setattr(info_mod, "RICH_AVAILABLE", True)
        display = MagicMock()
        monkeypatch.setattr(info_mod, "_display_info_rich", display)
        info_mod.handle(make_args(info_mod.create_parser, ["info", "-o", "table"]))
        display.assert_called_once()
        legacy = display.call_args.args[0]
        assert "sqlserver" in legacy and "protocols" in legacy

    def test_connection_without_version_tuple_keeps_none(self, monkeypatch, capsys):
        class NoVersionBackend:
            def __init__(self, connection_config=None):
                self._dialect = SQLServerDialect((16, 0, 0))

            def connect(self):
                pass

            def introspect_and_adapt(self):
                pass

            def get_server_version(self):
                return None

            def disconnect(self):
                pass

            @property
            def dialect(self):
                return self._dialect

        monkeypatch.setattr(
            "rhosocial.activerecord.backend.impl.sqlserver.backend.SQLServerBackend",
            NoVersionBackend,
        )
        info = info_mod.handle(
            make_args(info_mod.create_parser, ["info", "--database", "db", "-o", "json"])
        )
        assert info["database"]["connected"] is True
        assert info["database"]["version"] is None
        json.loads(capsys.readouterr().out)


class TestStatusRichDisplay:
    def test_full_overview_renders_all_sections(self, fake_rich):
        status = SimpleNamespace(
            server_version="16.0",
            server_vendor="Microsoft",
            session=SimpleNamespace(user="sa", database="master"),
            connections=SimpleNamespace(active_count=7),
            configuration=[
                SimpleNamespace(
                    name="max memory", value=1024, category=StatusCategory.CONFIGURATION
                )
            ],
            databases=[SimpleNamespace(name="master", size_bytes=2048)],
        )
        status_mod._display_status_rich(status, verbose=1)
        out = printed(fake_rich)
        assert "SQL Server Status" in out
        assert "Session" in out and "sa" in out
        assert "Active Connections" in out
        assert "Configuration" in out
        assert "Databases" in out


def _async_status_args(status_type="all", output="json"):
    return SimpleNamespace(
        type=status_type,
        output=output,
        verbose=0,
        rich_ascii=False,
    )


def _async_backend():
    backend = MagicMock()
    backend.connect = AsyncMock()
    backend.introspect_and_adapt = AsyncMock()
    backend.disconnect = AsyncMock()
    backend._connection = object()
    return backend


def _async_introspector():
    introspector = MagicMock()
    for name in (
        "get_overview",
        "list_configuration",
        "list_performance_metrics",
        "get_connection_info",
        "get_storage_info",
        "list_databases",
        "list_users",
    ):
        setattr(introspector, name, AsyncMock(return_value={"ok": name}))
    return introspector


class TestStatusAsyncDispatch:
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
    async def test_async_type_dispatch(self, monkeypatch, status_type, method):
        introspector = _async_introspector()
        monkeypatch.setattr(
            f"{STATUS_INTROSPECTOR}.AsyncSQLServerStatusIntrospector",
            MagicMock(return_value=introspector),
        )
        backend = _async_backend()
        provider = MagicMock()
        await status_mod._handle_status_async(_async_status_args(status_type), backend, provider)
        getattr(introspector, method).assert_awaited_once()
        provider.display_results.assert_called_once()
        backend.disconnect.assert_awaited_once()

    async def test_async_overview_json(self, monkeypatch, capsys):
        introspector = _async_introspector()
        introspector.get_overview.return_value = {"server_version": "16.0.0"}
        monkeypatch.setattr(
            f"{STATUS_INTROSPECTOR}.AsyncSQLServerStatusIntrospector",
            MagicMock(return_value=introspector),
        )
        await status_mod._handle_status_async(
            _async_status_args("all"), _async_backend(), MagicMock()
        )
        assert json.loads(capsys.readouterr().out)["server_version"] == "16.0.0"

    async def test_async_csv_tsv_overview_falls_back_to_json(self, monkeypatch, capsys):
        introspector = _async_introspector()
        introspector.get_overview.return_value = {"server_version": "16.0.0"}
        monkeypatch.setattr(
            f"{STATUS_INTROSPECTOR}.AsyncSQLServerStatusIntrospector",
            MagicMock(return_value=introspector),
        )
        for fmt in ("csv", "tsv"):
            await status_mod._handle_status_async(
                _async_status_args("all", fmt), _async_backend(), MagicMock()
            )
            assert json.loads(capsys.readouterr().out)["server_version"] == "16.0.0"

    @pytest.mark.parametrize(
        ("error", "provider_method"),
        [
            (ConnectionError("refused"), "display_connection_error"),
            (QueryError("bad query"), "display_query_error"),
        ],
    )
    async def test_async_known_errors(self, monkeypatch, error, provider_method):
        introspector = _async_introspector()
        introspector.get_overview.side_effect = error
        monkeypatch.setattr(
            f"{STATUS_INTROSPECTOR}.AsyncSQLServerStatusIntrospector",
            MagicMock(return_value=introspector),
        )
        provider = MagicMock()
        with pytest.raises(SystemExit) as exc:
            await status_mod._handle_status_async(
                _async_status_args("all"), _async_backend(), provider
            )
        assert exc.value.code == 1
        getattr(provider, provider_method).assert_called_once()

    async def test_async_unexpected_error(self, monkeypatch, capsys):
        introspector = _async_introspector()
        introspector.get_overview.side_effect = RuntimeError("boom")
        monkeypatch.setattr(
            f"{STATUS_INTROSPECTOR}.AsyncSQLServerStatusIntrospector",
            MagicMock(return_value=introspector),
        )
        with pytest.raises(SystemExit) as exc:
            await status_mod._handle_status_async(
                _async_status_args("all"), _async_backend(), MagicMock()
            )
        assert exc.value.code == 1
        assert "Error during status retrieval" in capsys.readouterr().err


class TestNamedExpressionParser:
    def test_parser_shape_and_dialect_version(self):
        args = make_args(
            ne_mod.create_parser,
            ["named-expression", "-o", "json", "--dialect-version", "15.0.4000"],
        )
        assert args.output == "json"
        assert args.dialect_version == "15.0.4000"
        assert args.is_async is False

    def test_no_dialect_version_by_default(self):
        args = make_args(ne_mod.create_parser, ["named-expression"])
        assert args.dialect_version is None


def _ne_args(**overrides):
    values = dict(
        output="json",
        rich_ascii=False,
        dialect_version=None,
        is_async=False,
        database="db",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def ne_seams(monkeypatch):
    """Replace every named-expression adapter seam with a recording mock."""
    args = _ne_args()
    provider = MagicMock(name="provider")
    config = object()
    handle_ne = MagicMock(name="handle_named_expression")
    backend = MagicMock(name="backend")
    backend._connection = object()
    backend_cls = MagicMock(name="SQLServerBackend", return_value=backend)
    async_backend = MagicMock(name="async_backend")
    async_backend._connection = object()
    async_backend.disconnect = AsyncMock()
    async_backend_cls = MagicMock(name="AsyncSQLServerBackend", return_value=async_backend)

    monkeypatch.setattr(ne_mod, "create_provider", MagicMock(return_value=provider))
    monkeypatch.setattr(
        ne_mod, "resolve_connection_config_from_args", MagicMock(return_value=config)
    )
    monkeypatch.setattr(
        "rhosocial.activerecord.backend.named_expression.cli.handle_named_expression",
        handle_ne,
    )
    monkeypatch.setattr(ne_mod, "SQLServerBackend", backend_cls)
    monkeypatch.setattr(
        async_backend_mod, "AsyncSQLServerBackend", async_backend_cls, raising=False
    )
    return SimpleNamespace(
        args=args,
        provider=provider,
        config=config,
        handle_ne=handle_ne,
        backend=backend,
        backend_cls=backend_cls,
        async_backend=async_backend,
        async_backend_cls=async_backend_cls,
    )


class TestNamedExpressionSyncHandle:
    def test_sync_callback_set(self, ne_seams):
        ne_mod.handle(ne_seams.args)
        ne_seams.handle_ne.assert_called_once()
        kwargs = ne_seams.handle_ne.call_args.kwargs
        assert ne_seams.handle_ne.call_args.args[0] is ne_seams.args
        assert ne_seams.handle_ne.call_args.args[1] is ne_seams.provider
        assert set(kwargs) == {
            "backend_factory",
            "get_dialect",
            "execute_query",
            "disconnect",
            "create_dialect",
        }

    def test_backend_factory_and_dialect_helpers(self, ne_seams):
        ne_mod.handle(ne_seams.args)
        kwargs = ne_seams.handle_ne.call_args.kwargs

        backend = kwargs["backend_factory"]()
        ne_seams.backend_cls.assert_called_once_with(connection_config=ne_seams.config)
        backend.connect.assert_called_once_with()
        backend.introspect_and_adapt.assert_called_once_with()
        assert backend is ne_seams.backend
        assert kwargs["get_dialect"](backend) is backend.dialect

        dialect = kwargs["create_dialect"]()
        assert isinstance(dialect, SQLServerDialect)
        assert getattr(dialect, "_version", None) is None

    def test_execute_query_wraps_statement_type(self, ne_seams):
        ne_mod.handle(ne_seams.args)
        kwargs = ne_seams.handle_ne.call_args.kwargs
        kwargs["backend_factory"]()
        execute = kwargs["execute_query"]
        execute("SELECT 1", (), "SELECT")
        call = ne_seams.backend.execute.call_args
        assert call.args == ("SELECT 1", ())
        assert call.kwargs["options"].stmt_type == "SELECT"

    def test_disconnect_respects_connection_state(self, ne_seams):
        ne_mod.handle(ne_seams.args)
        kwargs = ne_seams.handle_ne.call_args.kwargs
        kwargs["backend_factory"]()
        disconnect = kwargs["disconnect"]
        ne_seams.backend._connection = None
        disconnect()
        ne_seams.backend.disconnect.assert_not_called()
        ne_seams.backend._connection = object()
        disconnect()
        ne_seams.backend.disconnect.assert_called_once_with()

    def test_dialect_version_override(self, ne_seams):
        ne_seams.args.dialect_version = "15.0.4000"
        ne_mod.handle(ne_seams.args)
        kwargs = ne_seams.handle_ne.call_args.kwargs
        assert kwargs["create_dialect"]().version == (15, 0, 4000)
        kwargs["backend_factory"]()
        assert ne_seams.backend._dialect.version == (15, 0, 4000)


class TestNamedExpressionAsyncHandle:
    def test_async_callback_set(self, ne_seams):
        ne_seams.args.is_async = True
        ne_mod.handle(ne_seams.args)
        kwargs = ne_seams.handle_ne.call_args.kwargs
        assert set(kwargs) == {
            "backend_factory",
            "get_dialect",
            "execute_query",
            "disconnect",
            "backend_async_factory",
            "get_dialect_async",
            "execute_query_async",
            "disconnect_async",
            "create_dialect",
        }

    async def test_async_backend_and_query_helpers(self, ne_seams):
        ne_seams.args.is_async = True
        ne_mod.handle(ne_seams.args)
        kwargs = ne_seams.handle_ne.call_args.kwargs

        backend = kwargs["backend_async_factory"]()
        ne_seams.async_backend_cls.assert_called_once_with(connection_config=ne_seams.config)
        assert backend is ne_seams.async_backend
        assert await kwargs["get_dialect_async"](backend) is backend.dialect

        ne_seams.async_backend.execute = AsyncMock(return_value="ok")
        assert await kwargs["execute_query_async"]("EXEC p", (1,), "EXECUTE") == "ok"
        ne_seams.async_backend.execute.assert_awaited_once()

        await kwargs["disconnect_async"]()
        ne_seams.async_backend.disconnect.assert_awaited_once()

    async def test_async_disconnect_noop_without_connection(self, ne_seams):
        ne_seams.args.is_async = True
        ne_mod.handle(ne_seams.args)
        ne_seams.async_backend._connection = None
        await ne_seams.handle_ne.call_args.kwargs["disconnect_async"]()
        ne_seams.async_backend.disconnect.assert_not_awaited()
