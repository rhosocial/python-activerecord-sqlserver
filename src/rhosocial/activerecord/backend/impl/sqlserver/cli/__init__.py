# src/rhosocial/activerecord/backend/impl/sqlserver/cli/__init__.py
"""SQL Server CLI common definitions and subcommand registration."""

import importlib

COMMAND_NAMES = [
    'info',
    'query',
    'introspect',
    'status',
    'named-expression',
    'named-procedure',
    'named-procedure-graph',
    'named-connection',
]


def register_commands(subparsers):
    """Register all subcommands."""
    from .info import create_parser as info_parser
    from .query import create_parser as query_parser
    from .introspect import create_parser as introspect_parser
    from .status import create_parser as status_parser
    from .named_expression import create_parser as ne_parser
    from .named_procedure import create_parser as np_parser
    from .named_procedure_graph import create_parser as npg_parser
    from .named_connection import create_parser as nc_parser

    info_parser(subparsers)
    query_parser(subparsers)
    introspect_parser(subparsers)
    status_parser(subparsers)
    ne_parser(subparsers)
    np_parser(subparsers)
    npg_parser(subparsers)
    nc_parser(subparsers)


def get_handler(command_name: str):
    """Get the handler function for a subcommand."""
    module_name = command_name.replace('-', '_')
    module = importlib.import_module(f'.{module_name}', __name__)
    return module.handle
