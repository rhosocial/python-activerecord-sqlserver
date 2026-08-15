# src/rhosocial/activerecord/backend/impl/sqlserver/cli/status.py
"""status subcommand - Display SQL Server server status overview."""

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend
from rhosocial.activerecord.backend.errors import ConnectionError, QueryError
from .connection import add_connection_args, resolve_connection_config_from_args
from .output import create_provider, RICH_AVAILABLE

OUTPUT_CHOICES = ['table', 'json', 'csv', 'tsv']

STATUS_TYPES = ["all", "config", "performance", "connections", "storage", "databases", "users"]


def create_parser(subparsers):
    """Create the status subcommand parser."""
    parser = subparsers.add_parser(
        'status',
        help='Display server status overview',
        epilog="""Examples:
  # Show complete status overview
  %(prog)s all --database mydb

  # Show configuration parameters only
  %(prog)s config --database mydb

  # Output as JSON
  %(prog)s all --database mydb -o json
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
        '-v', '--verbose',
        action='count',
        default=0,
        help='Increase verbosity for additional columns.',
    )

    parser.add_argument(
        '--rich-ascii',
        action='store_true',
        help='Use ASCII characters for rich table borders.',
    )

    parser.add_argument(
        "type",
        nargs="?",
        default="all",
        choices=STATUS_TYPES,
        help="Status type (default: all)",
    )

    return parser


def handle(args):
    """Handle the status subcommand."""
    provider = create_provider(args.output, ascii_borders=args.rich_ascii)

    named_conn = getattr(args, "named_connection", None)
    if not named_conn and not args.database:
        print("Error: --database is required for status", file=sys.stderr)
        sys.exit(1)

    config = resolve_connection_config_from_args(args)

    if args.use_async:
        from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend
        backend = AsyncSQLServerBackend(connection_config=config)
        asyncio.run(_handle_status_async(args, backend, provider))
    else:
        backend = SQLServerBackend(connection_config=config)
        _handle_status_sync(args, backend, provider)


def _serialize_for_output(obj: Any) -> Any:
    """Serialize object for JSON output."""
    if obj is None:
        return None
    if hasattr(obj, 'model_dump'):
        try:
            return _serialize_for_output(obj.model_dump(mode='json'))
        except TypeError:
            return _serialize_for_output(obj.model_dump())
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _serialize_for_output(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _serialize_for_output(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize_for_output(item) for item in obj]
    if isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


def _format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string."""
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    for unit in units:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def _handle_status_sync(args, backend: SQLServerBackend, provider):
    """Handle status subcommand synchronously."""
    from rhosocial.activerecord.backend.introspection.status import StatusCategory
    from ..introspection.status_introspector import SyncSQLServerStatusIntrospector

    try:
        backend.connect()
        backend.introspect_and_adapt()

        status_introspector = SyncSQLServerStatusIntrospector(backend)
        status_type = args.type

        if status_type == "all":
            status = status_introspector.get_overview()
            effective_output = args.output
            if effective_output in ("csv", "tsv"):
                effective_output = "json"

            if effective_output == "json" or not RICH_AVAILABLE:
                print(json.dumps(_serialize_for_output(status), indent=2))
            else:
                _display_status_rich(status, args.verbose)
        elif status_type == "config":
            items = status_introspector.list_configuration(StatusCategory.CONFIGURATION)
            provider.display_results(_serialize_for_output(items), title="Configuration")
        elif status_type == "performance":
            items = status_introspector.list_performance_metrics()
            provider.display_results(_serialize_for_output(items), title="Performance")
        elif status_type == "connections":
            conn = status_introspector.get_connection_info()
            provider.display_results([_serialize_for_output(conn)], title="Connections")
        elif status_type == "storage":
            storage = status_introspector.get_storage_info()
            provider.display_results([_serialize_for_output(storage)], title="Storage")
        elif status_type == "databases":
            dbs = status_introspector.list_databases()
            provider.display_results(_serialize_for_output(dbs), title="Databases")
        elif status_type == "users":
            users = status_introspector.list_users()
            provider.display_results(_serialize_for_output(users), title="Users")

    except ConnectionError as e:
        provider.display_connection_error(e)
        sys.exit(1)
    except QueryError as e:
        provider.display_query_error(e)
        sys.exit(1)
    except Exception as e:
        print(f"Error during status retrieval: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if backend._connection:  # type: ignore
            backend.disconnect()


async def _handle_status_async(args, backend, provider):
    """Handle status subcommand asynchronously."""
    from rhosocial.activerecord.backend.introspection.status import StatusCategory
    from ..introspection.status_introspector import AsyncSQLServerStatusIntrospector

    try:
        await backend.connect()
        await backend.introspect_and_adapt()

        status_introspector = AsyncSQLServerStatusIntrospector(backend)
        status_type = args.type

        if status_type == "all":
            status = await status_introspector.get_overview()
            effective_output = args.output
            if effective_output in ("csv", "tsv"):
                effective_output = "json"

            if effective_output == "json" or not RICH_AVAILABLE:
                print(json.dumps(_serialize_for_output(status), indent=2))
            else:
                _display_status_rich(status, args.verbose)
        elif status_type == "config":
            items = await status_introspector.list_configuration(StatusCategory.CONFIGURATION)
            provider.display_results(_serialize_for_output(items), title="Configuration")
        elif status_type == "performance":
            items = await status_introspector.list_performance_metrics()
            provider.display_results(_serialize_for_output(items), title="Performance")
        elif status_type == "connections":
            conn = await status_introspector.get_connection_info()
            provider.display_results([_serialize_for_output(conn)], title="Connections")
        elif status_type == "storage":
            storage = await status_introspector.get_storage_info()
            provider.display_results([_serialize_for_output(storage)], title="Storage")
        elif status_type == "databases":
            dbs = await status_introspector.list_databases()
            provider.display_results(_serialize_for_output(dbs), title="Databases")
        elif status_type == "users":
            users = await status_introspector.list_users()
            provider.display_results(_serialize_for_output(users), title="Users")

    except ConnectionError as e:
        provider.display_connection_error(e)
        sys.exit(1)
    except QueryError as e:
        provider.display_query_error(e)
        sys.exit(1)
    except Exception as e:
        print(f"Error during status retrieval: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if backend._connection:  # type: ignore
            await backend.disconnect()


def _display_status_rich(status: Any, verbose: int = 0):
    """Display status using rich console."""
    from rich.console import Console
    from rich.table import Table
    from rhosocial.activerecord.backend.introspection.status import StatusCategory

    console = Console(force_terminal=True)
    console.print("\n[bold cyan]SQL Server Status[/bold cyan]\n")
    console.print(f"[bold]Version:[/bold] {status.server_version}")
    console.print(f"[bold]Vendor:[/bold] {status.server_vendor}")

    if hasattr(status, 'session') and status.session:
        session = status.session
        console.print()
        console.print("[bold green]Session[/bold green]")
        if session.user:
            console.print(f"  [bold]User:[/bold] {session.user}")
        if session.database:
            console.print(f"  [bold]Database:[/bold] {session.database}")

    if hasattr(status, 'connections') and status.connections:
        conn = status.connections
        if conn.active_count is not None:
            console.print(f"[bold]Active Connections:[/bold] {conn.active_count}")

    console.print()

    config_items = [i for i in status.configuration
                    if i.category == StatusCategory.CONFIGURATION]
    if config_items:
        console.print("[bold green]Configuration[/bold green]")
        t = Table(show_header=True, header_style="bold")
        t.add_column("Parameter")
        t.add_column("Value")
        for item in config_items[:20]:
            t.add_row(item.name, str(item.value))
        console.print(t)
        console.print()

    if status.databases:
        console.print("[bold green]Databases[/bold green]")
        t = Table(show_header=True, header_style="bold")
        t.add_column("Name")
        t.add_column("Size")
        for db in status.databases:
            size = _format_size(db.size_bytes) if db.size_bytes else "N/A"
            t.add_row(db.name, size)
        console.print(t)
        console.print()
