import argparse
import pytest

from rhosocial.activerecord.backend.impl.sqlserver.cli import COMMAND_NAMES, register_commands, get_handler
from rhosocial.activerecord.backend.impl.sqlserver.cli.connection import add_connection_args


class TestCLIParseArgs:
    def test_subcommands_defined(self):
        assert len(COMMAND_NAMES) > 0
        assert "info" in COMMAND_NAMES
        assert "query" in COMMAND_NAMES
        assert "introspect" in COMMAND_NAMES
        assert "status" in COMMAND_NAMES
        assert "named-procedure" in COMMAND_NAMES
        assert "named-connection" in COMMAND_NAMES

    def test_get_handler_returns_callable(self):
        for name in COMMAND_NAMES:
            handler = get_handler(name)
            assert callable(handler), f"Handler for '{name}' is not callable"

    def test_add_connection_args_adds_expected_args(self):
        parser = argparse.ArgumentParser(prog="test")
        add_connection_args(parser)
        dests = {a.dest for a in parser._actions}
        assert "host" in dests
        assert "port" in dests
        assert "database" in dests
        assert "username" in dests or "user" in dests

    def test_info_parser_has_expected_args(self):
        parser = argparse.ArgumentParser(prog="sqlserver-backend")
        subparsers = parser.add_subparsers(dest="command")
        register_commands(subparsers)
        info_parser = None
        for action in parser._actions:
            choices = getattr(action, 'choices', None)
            if choices and isinstance(choices, dict) and 'info' in choices:
                info_parser = choices['info']
                break
        assert info_parser is not None, "info subparser not found"
        dests = {a.dest for a in info_parser._actions}
        assert "verbose" in dests or "-v" in {a.option_strings[0] if a.option_strings else "" for a in info_parser._actions}

    @staticmethod
    def _get_subparser(parser, name):
        for action in parser._actions:
            choices = getattr(action, 'choices', None)
            if choices and isinstance(choices, dict) and name in choices:
                return choices[name]
        return None

    def test_query_parser_has_expected_args(self):
        parser = argparse.ArgumentParser(prog="sqlserver-backend")
        subparsers = parser.add_subparsers(dest="command")
        register_commands(subparsers)
        query_parser = self._get_subparser(parser, 'query')
        assert query_parser is not None, "query subparser not found"
        dests = {a.dest for a in query_parser._actions}
        assert "sql" in dests

    def test_introspect_parser_has_expected_args(self):
        parser = argparse.ArgumentParser(prog="sqlserver-backend")
        subparsers = parser.add_subparsers(dest="command")
        register_commands(subparsers)
        intro_parser = self._get_subparser(parser, 'introspect')
        assert intro_parser is not None, "introspect subparser not found"
        actions = {a.dest for a in intro_parser._actions}
        assert any("column" in a or "table" in a or "schema" in a for a in actions)


class TestCLIHelp:
    def test_help_output_contains_commands(self):
        parser = argparse.ArgumentParser(prog="sqlserver-backend", add_help=False)
        subparsers = parser.add_subparsers(dest="command")
        register_commands(subparsers)
        help_text = parser.format_help()
        for name in COMMAND_NAMES:
            assert name in help_text, f"Help text missing command '{name}'"

    def test_help_not_empty(self):
        parser = argparse.ArgumentParser(prog="sqlserver-backend", add_help=False)
        subparsers = parser.add_subparsers(dest="command")
        register_commands(subparsers)
        help_text = parser.format_help()
        assert len(help_text) > 0


class TestCLIProviderFactory:
    def test_create_provider_output_formats(self):
        from rhosocial.activerecord.backend.impl.sqlserver.cli.output import create_provider
        provider = create_provider("json")
        assert provider is not None
        provider_csv = create_provider("csv")
        assert provider_csv is not None
        provider_tsv = create_provider("tsv")
        assert provider_tsv is not None

    def test_create_provider_invalid_format_falls_back_to_json(self):
        from rhosocial.activerecord.backend.impl.sqlserver.cli.output import create_provider
        provider = create_provider("unknown_format")
        from rhosocial.activerecord.backend.output import JsonOutputProvider
        assert isinstance(provider, JsonOutputProvider)


class TestCLIBuildProtocolInfo:
    def test_dialect_supports_cte(self):
        from rhosocial.activerecord.backend.dialect.protocols import CTESupport
        from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
        dialect = SQLServerDialect((16, 0, 0))
        assert isinstance(dialect, CTESupport)
        assert dialect.supports_basic_cte() is True
        assert dialect.supports_recursive_cte() is True

    def test_dialect_supports_json(self):
        from rhosocial.activerecord.backend.dialect.protocols import JSONSupport
        from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
        dialect = SQLServerDialect((16, 0, 0))
        assert isinstance(dialect, JSONSupport)

    def test_dialect_supports_window_functions(self):
        from rhosocial.activerecord.backend.dialect.protocols import WindowFunctionSupport
        from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
        dialect = SQLServerDialect((16, 0, 0))
        assert isinstance(dialect, WindowFunctionSupport)

    def test_dialect_supports_savepoint(self):
        from rhosocial.activerecord.backend.dialect.protocols import TransactionControlSupport
        from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
        dialect = SQLServerDialect((16, 0, 0))
        assert isinstance(dialect, TransactionControlSupport)


class TestCLIDisplayFunctions:
    def test_display_nested_json_works(self):
        from rhosocial.activerecord.backend.impl.sqlserver.cli.output import display_nested_json
        import json
        data = {"key": "value", "nested": {"inner": 42}}
        # Just verify the function handles valid data without error
        # We can't easily capture stdout in a portable way, so just verify callability
        import io, sys
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            display_nested_json(data)
            output = captured.getvalue()
            assert "key" in output
            assert "value" in output
            assert "42" in output
        finally:
            sys.stdout = old_stdout



class TestCLINamedProcedureArgs:
    def test_named_procedure_parser_has_expected_args(self):
        parser = argparse.ArgumentParser(prog="sqlserver-backend")
        subparsers = parser.add_subparsers(dest="command")
        register_commands(subparsers)
        np_parser = TestCLIParseArgs._get_subparser(parser, 'named-procedure')
        assert np_parser is not None, "named-procedure subparser not found"
        dests = {a.dest for a in np_parser._actions}
        assert "qualified_name" in dests or "name" in dests or "procedure_name" in dests
