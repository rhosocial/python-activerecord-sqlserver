# src/rhosocial/activerecord/backend/impl/sqlserver/cli/named_connection.py
"""named-connection subcommand - Adapter for shared CLI helper.

named-connection does not need connection arguments (it manages connections)
or -o (all output is plain text).
"""

import argparse

from rhosocial.activerecord.backend.named_connection import NamedConnectionResolver


def create_parser(subparsers):
    """Create the named-connection subcommand parser.

    named-connection does not need connection or output arguments,
    but the shared CLI helper requires a parent_parser. Pass an empty one.
    """
    from rhosocial.activerecord.backend.named_connection.cli import create_named_connection_parser

    empty_parent = argparse.ArgumentParser(add_help=False)
    return create_named_connection_parser(subparsers, empty_parent)


def handle(args):
    """Handle the named-connection subcommand."""
    from rhosocial.activerecord.backend.named_connection.cli import handle_named_connection as handle_nc

    def named_connection_resolver_factory(name):
        return NamedConnectionResolver(name)

    handle_nc(args, named_connection_resolver_factory)
