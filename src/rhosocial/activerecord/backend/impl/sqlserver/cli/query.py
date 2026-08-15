# src/rhosocial/activerecord/backend/impl/sqlserver/cli/query.py
"""query subcommand - Execute SQL queries.

query requires connection arguments, output arguments, and --log-level.
"""

import argparse
import asyncio
import logging
import sys

from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend
from rhosocial.activerecord.backend.errors import ConnectionError, QueryError
from .connection import add_connection_args, resolve_connection_config_from_args
from .output import create_provider, RICH_AVAILABLE

OUTPUT_CHOICES = ['table', 'json', 'csv', 'tsv']


def create_parser(subparsers):
    """Create the query subcommand parser."""
    parser = subparsers.add_parser(
        'query',
        help='Execute SQL query',
        epilog="""Examples:
  # Query a database
  %(prog)s --host localhost --database mydb "SELECT * FROM users"

  # Query using named connection
  %(prog)s --named-connection myapp.connections.prod_db "SELECT 1"

  # Execute SQL from file
  %(prog)s --host localhost --database mydb -f query.sql

  # Using environment variables for connection
  export SQLSERVER_HOST=localhost SQLSERVER_DATABASE=mydb SQLSERVER_USERNAME=sa SQLSERVER_PASSWORD=your_password_here
  %(prog)s "SELECT 1"
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        '-o', '--output',
        choices=OUTPUT_CHOICES,
        default='table',
        help='Output format (default: table)',
    )

    add_connection_args(parser)

    parser.add_argument(
        '--log-level',
        default='INFO',
        help='Set logging level (e.g., DEBUG, INFO)',
    )

    parser.add_argument(
        '--rich-ascii',
        action='store_true',
        help='Use ASCII characters for rich table borders.',
    )

    parser.add_argument(
        "sql",
        nargs="?",
        default=None,
        help="SQL query to execute. If not provided, reads from --file or stdin.",
    )
    parser.add_argument(
        "-f", "--file",
        default=None,
        help="Path to a file containing SQL to execute.",
    )

    return parser


def handle(args):
    """Handle the query subcommand."""
    numeric_level = getattr(logging, args.log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {args.log_level}")

    provider = create_provider(args.output, ascii_borders=args.rich_ascii)

    if RICH_AVAILABLE:
        from rhosocial.activerecord.backend.output_rich import RichOutputProvider
        if isinstance(provider, RichOutputProvider):
            from rich.console import Console
            from rich.logging import RichHandler
            handler = RichHandler(
                rich_tracebacks=True,
                show_path=False,
                console=Console(stderr=True),
            )
            logging.basicConfig(
                level=numeric_level,
                format="%(message)s",
                datefmt="[%X]",
                handlers=[handler],
            )
        else:
            logging.basicConfig(
                level=numeric_level,
                format="%(asctime)s - %(levelname)s - %(message)s",
                stream=sys.stderr,
            )
    else:
        logging.basicConfig(
            level=numeric_level,
            format="%(asctime)s - %(levelname)s - %(message)s",
            stream=sys.stderr,
        )

    provider.display_greeting()

    sql_source = None
    if args.sql:
        sql_source = args.sql
    elif args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                sql_source = f.read()
        except FileNotFoundError:
            logging.error(f"Error: File not found at {args.file}")
            sys.exit(1)
    elif not sys.stdin.isatty():
        sql_source = sys.stdin.read()

    if not sql_source:
        msg = "Error: No SQL query provided. Use SQL argument, --file, or stdin."
        print(msg, file=sys.stderr)
        sys.exit(1)

    if ";" in sql_source.strip().rstrip(";"):
        logging.error("Error: Multiple SQL statements are not supported.")
        sys.exit(1)

    config = resolve_connection_config_from_args(args)
    kwargs = {"use_ascii": args.rich_ascii}

    if args.use_async:
        from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend
        backend = AsyncSQLServerBackend(connection_config=config)
        asyncio.run(_execute_query_async(sql_source, backend, provider, **kwargs))
    else:
        backend = SQLServerBackend(connection_config=config)
        _execute_query_sync(sql_source, backend, provider, **kwargs)


# ---------------------------------------------------------------------------
# Internal helper functions
# ---------------------------------------------------------------------------


def _execute_query_sync(sql_query: str, backend: SQLServerBackend, provider, **kwargs):
    """Execute a SQL query synchronously."""
    try:
        backend.connect()
        provider.display_query(sql_query, is_async=False)
        result = backend.execute(sql_query)
        if not result:
            provider.display_no_result_object()
        else:
            provider.display_success(result.affected_rows, result.duration)
            if result.data:
                provider.display_results(result.data, **kwargs)
            else:
                provider.display_no_data()
    except ConnectionError as e:
        provider.display_connection_error(e)
        sys.exit(1)
    except QueryError as e:
        provider.display_query_error(e)
        sys.exit(1)
    except Exception as e:
        provider.display_unexpected_error(e, is_async=False)
        sys.exit(1)
    finally:
        if backend._connection:  # type: ignore
            backend.disconnect()
            provider.display_disconnect(is_async=False)


async def _execute_query_async(sql_query: str, backend, provider, **kwargs):
    """Execute a SQL query asynchronously."""
    try:
        await backend.connect()
        provider.display_query(sql_query, is_async=True)
        result = await backend.execute(sql_query)
        if not result:
            provider.display_no_result_object()
        else:
            provider.display_success(result.affected_rows, result.duration)
            if result.data:
                provider.display_results(result.data, **kwargs)
            else:
                provider.display_no_data()
    except ConnectionError as e:
        provider.display_connection_error(e)
        sys.exit(1)
    except QueryError as e:
        provider.display_query_error(e)
        sys.exit(1)
    except Exception as e:
        provider.display_unexpected_error(e, is_async=True)
        sys.exit(1)
    finally:
        if backend._connection:  # type: ignore
            await backend.disconnect()
            provider.display_disconnect(is_async=True)
