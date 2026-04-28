# src/rhosocial/activerecord/backend/impl/sqlserver/__main__.py
"""SQL Server backend command-line interface.

Provides SQL execution and database introspection capabilities.
"""

import argparse
import sys

from .cli import register_commands, COMMAND_NAMES


def _build_parser():
    """Build and return the argument parser with all subcommands registered."""
    parser = argparse.ArgumentParser(
        description="Execute SQL queries against a SQL Server backend.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    register_commands(subparsers)
    return parser


def parse_args():
    """Parse command-line arguments.

    Provided for test compatibility. In production, main() is used instead.
    """
    parser = _build_parser()
    return parser.parse_args()


def main():
    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        cmd_list = ", ".join(f"'{c}'" for c in COMMAND_NAMES[:-1])
        print(
            f"Error: Please specify a command: {cmd_list}, or '{COMMAND_NAMES[-1]}'",
            file=sys.stderr,
        )
        print("Use --help for more information.", file=sys.stderr)
        sys.exit(1)

    from .cli import get_handler

    handler = get_handler(args.command)
    handler(args)


if __name__ == "__main__":
    main()
