# tests/rhosocial/activerecord_sqlserver_test/feature/backend/cli/test_main_parse_args.py
"""Offline tests for ``__main__.parse_args`` with custom argv."""
import pytest

from rhosocial.activerecord.backend.impl.sqlserver.__main__ import parse_args


class TestParseArgs:
    def test_parse_args_with_help_exits(self):
        with pytest.raises(SystemExit) as excinfo:
            parse_args(["--help"])
        assert excinfo.value.code == 0

    def test_parse_args_with_query(self):
        args = parse_args(["query", "SELECT 1"])
        assert args.command == "query"

    def test_parse_args_with_info(self):
        args = parse_args(["info"])
        assert args.command == "info"