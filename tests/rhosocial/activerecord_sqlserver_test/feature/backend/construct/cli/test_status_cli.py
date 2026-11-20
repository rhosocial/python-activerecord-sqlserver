# tests/activerecord_sqlserver_test/feature/backend/construct/cli/test_status_cli.py
"""Backend-owned tests for ``sqlserver.cli.status``.

The shared testsuite covers data-operation compatibility, not this backend's
CLI surface. These portable tests pin the parts of the status subcommand that
are common to every backend: parser shape, pure serialization/size helpers,
rich rendering of the overview header, and the dispatch guard. No live server
is needed.
"""
from dataclasses import dataclass
from enum import Enum
from unittest.mock import MagicMock, patch

import pytest

from rhosocial.activerecord.backend.impl.sqlserver.cli import status as mod
from rhosocial.activerecord.backend.introspection.status import ServerOverview


# ---------------------------------------------------------------------------
# create_parser
# ---------------------------------------------------------------------------


class TestCreateParser:
    def test_parser_defaults_and_choices(self):
        import argparse

        subs = argparse.ArgumentParser(prog="x").add_subparsers(dest="command")
        parser = mod.create_parser(subs)
        args = parser.parse_args([])
        assert args.type == "all"
        assert args.output == "table"
        assert args.verbose == 0
        assert args.rich_ascii is False

    @pytest.mark.parametrize("t", mod.STATUS_TYPES)
    def test_all_status_types_accepted(self, t):
        import argparse

        subs = argparse.ArgumentParser(prog="x").add_subparsers(dest="command")
        parser = mod.create_parser(subs)
        assert parser.parse_args([t]).type == t

    def test_verbose_is_counted(self):
        import argparse

        subs = argparse.ArgumentParser(prog="x").add_subparsers(dest="command")
        parser = mod.create_parser(subs)
        assert parser.parse_args(["-vvv"]).verbose == 3


# ---------------------------------------------------------------------------
# _serialize_for_output
# ---------------------------------------------------------------------------


class _Colour(Enum):
    RED = "red"


@dataclass
class _Point:
    x: int
    y: int


class _WithModelDump:
    def model_dump(self, mode="python"):
        return {"a": 1, "mode": mode}


class _Fallback:
    def __str__(self):
        return "fallback"


class TestSerializeForOutput:
    def test_none_and_scalars(self):
        assert mod._serialize_for_output(None) is None
        assert mod._serialize_for_output("x") == "x"
        assert mod._serialize_for_output(3) == 3
        assert mod._serialize_for_output(1.5) == 1.5
        assert mod._serialize_for_output(True) is True

    def test_enum(self):
        assert mod._serialize_for_output(_Colour.RED) == "red"

    def test_dataclass(self):
        assert mod._serialize_for_output(_Point(1, 2)) == {"x": 1, "y": 2}

    def test_dict_and_list_recursive(self):
        obj = {"p": _Point(1, 2), "c": _Colour.RED, "items": [_Colour.RED, 2]}
        assert mod._serialize_for_output(obj) == {
            "p": {"x": 1, "y": 2}, "c": "red", "items": ["red", 2],
        }

    def test_tuple_becomes_list(self):
        assert mod._serialize_for_output((1, 2)) == [1, 2]

    def test_model_dump(self):
        assert mod._serialize_for_output(_WithModelDump()) == {"a": 1, "mode": "json"}

    def test_model_dump_typeerror_falls_back(self):
        class BadNoMode:
            def model_dump(self):
                return {"ok": True}

        assert mod._serialize_for_output(BadNoMode()) == {"ok": True}

    def test_unknown_falls_back_to_str(self):
        assert mod._serialize_for_output(_Fallback()) == "fallback"


# ---------------------------------------------------------------------------
# _format_size
# ---------------------------------------------------------------------------


class TestFormatSize:
    @pytest.mark.parametrize(
        "size,expected",
        [
            (0, "0.0 B"),
            (512, "512.0 B"),
            (1024, "1.0 KB"),
            (1024 * 1024, "1.0 MB"),
            (1024**3, "1.0 GB"),
            (1024**4, "1.0 TB"),
            (1024**5, "1.0 PB"),
        ],
    )
    def test_units(self, size, expected):
        assert mod._format_size(size) == expected


# ---------------------------------------------------------------------------
# _display_status_rich (fake rich so it runs without the optional dependency)
# ---------------------------------------------------------------------------


class _FakeTable:
    def __init__(self, *a, **k):
        self.columns = []
        self.rows = []

    def add_column(self, *a, **k):
        self.columns.append((a, k))

    def add_row(self, *a, **k):
        self.rows.append((a, k))


class _FakeConsole:
    printed = []

    def __init__(self, *a, **k):
        pass

    def print(self, *a, **k):
        for item in a:
            if isinstance(item, _FakeTable):
                for args, kwargs in item.columns:
                    _FakeConsole.printed.extend(str(x) for x in args)
                for args, kwargs in item.rows:
                    _FakeConsole.printed.extend(str(x) for x in args)
            else:
                _FakeConsole.printed.append(str(item))


@pytest.fixture
def fake_rich():
    import sys
    import types

    console_mod = types.ModuleType("rich.console")
    console_mod.Console = _FakeConsole
    table_mod = types.ModuleType("rich.table")
    table_mod.Table = _FakeTable
    rich_mod = types.ModuleType("rich")
    rich_mod.console = console_mod
    rich_mod.table = table_mod
    with patch.dict(
        sys.modules,
        {"rich": rich_mod, "rich.console": console_mod, "rich.table": table_mod},
    ):
        _FakeConsole.printed = []
        yield


class TestDisplayStatusRich:
    def test_header_always_rendered(self, fake_rich):
        ov = ServerOverview(server_version="8.0", server_vendor="Vendor")
        mod._display_status_rich(ov)
        out = " ".join(_FakeConsole.printed)
        assert "Server Status" in out
        assert "8.0" in out
        assert "Vendor" in out

    def test_verbose_adds_columns(self, fake_rich):
        ov = ServerOverview(server_version="8.0", server_vendor="Vendor")
        mod._display_status_rich(ov, verbose=1)
        # At minimum the console was driven with more than the bare header.
        assert len(_FakeConsole.printed) >= 3


# ---------------------------------------------------------------------------
# handle: shared dispatch guard
# ---------------------------------------------------------------------------


class TestHandleDispatch:
    def test_requires_database(self, capsys):
        args = MagicMock()
        args.database = None
        args.named_connection = None
        with pytest.raises(SystemExit) as e:
            mod.handle(args)
        assert e.value.code == 1
        assert "database is required" in capsys.readouterr().err
