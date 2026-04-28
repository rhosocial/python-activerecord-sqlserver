# src/rhosocial/activerecord/backend/impl/sqlserver/cli/status.py
"""status subcommand - Display SQL Server server status overview.

SQL Server status includes Edition, Product Level, and Database Files
sections in addition to the standard sections.
"""

import argparse
import asyncio
import json
import sys
from typing import Any

from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend
from rhosocial.activerecord.backend.errors import ConnectionError, QueryError
from .connection import add_connection_args, resolve_connection_config_from_args
from .output import create_provider, RICH_AVAILABLE

OUTPUT_CHOICES = ['table', 'json', 'csv', 'tsv']

STATUS_TYPES = ["all", "config", "performance", "connections", "storage", "databases"]


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

  # Show performance metrics only
  %(prog)s performance --database mydb

  # Show connection information
  %(prog)s connections --database mydb

  # Show storage information
  %(prog)s storage --database mydb

  # Show databases list
  %(prog)s databases --database mydb

  # Output as JSON
  %(prog)s all --database mydb -o json

  # Using environment variables for connection
  export SQLSERVER_HOST=localhost SQLSERVER_DATABASE=mydb SQLSERVER_USERNAME=sa SQLSERVER_PASSWORD=secret
  %(prog)s all
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
        help="Status type: all (default), config, performance, connections, storage, databases",
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


# ---------------------------------------------------------------------------
# Internal helper functions
# ---------------------------------------------------------------------------


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
    try:
        backend.connect()
        backend.introspect_and_adapt()

        status_type = args.type

        if status_type == "all":
            status_data = _get_full_status_sync(backend)
            effective_output = args.output
            if effective_output in ("csv", "tsv"):
                effective_output = "json"

            if effective_output == "json" or not RICH_AVAILABLE:
                print(json.dumps(status_data, indent=2))
            else:
                _display_status_rich(status_data, args.verbose)

        elif status_type == "config":
            config_data = _get_config_sync(backend)
            provider.display_results(config_data, title="Configuration")

        elif status_type == "performance":
            perf_data = _get_performance_sync(backend)
            provider.display_results(perf_data, title="Performance")

        elif status_type == "connections":
            conn_data = _get_connections_sync(backend)
            provider.display_results([conn_data], title="Connections")

        elif status_type == "storage":
            storage_data = _get_storage_sync(backend)
            provider.display_results([storage_data], title="Storage")

        elif status_type == "databases":
            db_data = _get_databases_sync(backend)
            provider.display_results(db_data, title="Databases")

    except ConnectionError as e:
        provider.display_connection_error(e)
        sys.exit(1)
    except QueryError as e:
        provider.display_query_error(e)
        sys.exit(1)
    except Exception as e:
        print(f"Error during status introspection: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if backend._connection:  # type: ignore
            backend.disconnect()


def _handle_status_async(args, backend, provider):
    """Handle status subcommand asynchronously."""
    try:
        backend.connect()
        backend.introspect_and_adapt()

        status_type = args.type

        if status_type == "all":
            status_data = _get_full_status_sync(backend)
            effective_output = args.output
            if effective_output in ("csv", "tsv"):
                effective_output = "json"

            if effective_output == "json" or not RICH_AVAILABLE:
                print(json.dumps(status_data, indent=2))
            else:
                _display_status_rich(status_data, args.verbose)

        elif status_type == "config":
            config_data = _get_config_sync(backend)
            provider.display_results(config_data, title="Configuration")

        elif status_type == "performance":
            perf_data = _get_performance_sync(backend)
            provider.display_results(perf_data, title="Performance")

        elif status_type == "connections":
            conn_data = _get_connections_sync(backend)
            provider.display_results([conn_data], title="Connections")

        elif status_type == "storage":
            storage_data = _get_storage_sync(backend)
            provider.display_results([storage_data], title="Storage")

        elif status_type == "databases":
            db_data = _get_databases_sync(backend)
            provider.display_results(db_data, title="Databases")

    except ConnectionError as e:
        provider.display_connection_error(e)
        sys.exit(1)
    except QueryError as e:
        provider.display_query_error(e)
        sys.exit(1)
    except Exception as e:
        print(f"Error during status introspection: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if backend._connection:  # type: ignore
            backend.disconnect()


def _get_config_sync(backend) -> list:
    """Get SQL Server configuration settings."""
    cursor = backend._get_cursor()
    try:
        cursor.execute("""
            SELECT configuration_id, name,
                   CAST(value AS NVARCHAR(4000)) AS value,
                   CAST(value_in_use AS NVARCHAR(4000)) AS value_in_use,
                   is_dynamic, is_advanced
            FROM sys.configurations
            ORDER BY name
        """)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    finally:
        cursor.close()


def _get_performance_sync(backend) -> list:
    """Get SQL Server performance metrics."""
    cursor = backend._get_cursor()
    try:
        cursor.execute("""
            SELECT
                cntr.cntr_value AS counter_value,
                cntr.cntr_type,
                CAST(obj.name AS NVARCHAR(128)) AS object_name,
                CAST(cntr.instance_name AS NVARCHAR(128)) AS instance_name,
                CAST(cntr.counter_name AS NVARCHAR(128)) AS counter_name
            FROM sys.dm_os_performance_counters cntr
            INNER JOIN sys.objects obj ON cntr.object_id = obj.object_id
            ORDER BY obj.name, cntr.counter_name
        """)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        try:
            cursor.execute("""
                SELECT
                    CAST(counter_name AS NVARCHAR(128)) AS counter_name,
                    cntr_value,
                    CAST(instance_name AS NVARCHAR(128)) AS instance_name,
                    CAST(object_name AS NVARCHAR(128)) AS object_name
                FROM sys.dm_os_performance_counters
                ORDER BY object_name, counter_name
            """)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        except Exception:
            return []
    finally:
        cursor.close()


def _get_connections_sync(backend) -> dict:
    """Get SQL Server connection information."""
    cursor = backend._get_cursor()
    try:
        cursor.execute("""
            SELECT
                (SELECT COUNT(*) FROM sys.dm_exec_connections) AS active_connections,
                (SELECT CAST(value_in_use AS NVARCHAR(4000)) FROM sys.configurations WHERE name = 'user connections') AS max_connections
        """)
        row = cursor.fetchone()
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
    except Exception:
        return {"active_connections": 0, "max_connections": 0}
    finally:
        cursor.close()


def _get_storage_sync(backend) -> dict:
    """Get SQL Server storage information."""
    cursor = backend._get_cursor()
    try:
        cursor.execute("""
            SELECT
                SUM(size * 8 * 1024) AS total_size_bytes,
                COUNT(*) AS file_count
            FROM sys.master_files
            WHERE database_id > 0
        """)
        row = cursor.fetchone()
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
    except Exception:
        return {"total_size_bytes": 0, "file_count": 0}
    finally:
        cursor.close()


def _get_databases_sync(backend) -> list:
    """Get SQL Server databases list."""
    cursor = backend._get_cursor()
    try:
        cursor.execute("""
            SELECT
                CAST(d.name AS NVARCHAR(128)) AS database_name,
                CAST(d.state_desc AS NVARCHAR(128)) AS state,
                CAST(d.recovery_model_desc AS NVARCHAR(128)) AS recovery_model,
                CAST(d.collation_name AS NVARCHAR(128)) AS collation_name,
                SUM(mf.size * 8 * 1024) AS size_bytes
            FROM sys.databases d
            LEFT JOIN sys.master_files mf ON d.database_id = mf.database_id AND mf.type = 0
            GROUP BY d.name, d.state_desc, d.recovery_model_desc, d.collation_name
            ORDER BY d.name
        """)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    finally:
        cursor.close()


def _get_full_status_sync(backend) -> dict:
    """Get full status overview for SQL Server."""
    result = {
        "server": {},
        "databases": [],
    }

    cursor = backend._get_cursor()
    try:
        cursor.execute("""
            DECLARE @pv NVARCHAR(128), @pl NVARCHAR(128), @ed NVARCHAR(128),
                    @ee INT, @mn NVARCHAR(128), @sn NVARCHAR(128), @co NVARCHAR(128)
            SET @pv = CAST(SERVERPROPERTY('ProductVersion') AS NVARCHAR(128))
            SET @pl = CAST(SERVERPROPERTY('ProductLevel') AS NVARCHAR(128))
            SET @ed = CAST(SERVERPROPERTY('Edition') AS NVARCHAR(128))
            SET @ee = CAST(SERVERPROPERTY('EngineEdition') AS INT)
            SET @mn = CAST(SERVERPROPERTY('MachineName') AS NVARCHAR(128))
            SET @sn = CAST(SERVERPROPERTY('ServerName') AS NVARCHAR(128))
            SET @co = CAST(SERVERPROPERTY('Collation') AS NVARCHAR(128))
            SELECT @pv AS product_version, @pl AS product_level, @ed AS edition,
                   @ee AS engine_edition, @mn AS machine_name, @sn AS server_name, @co AS collation
        """)
        row = cursor.fetchone()
        columns = [desc[0] for desc in cursor.description]
        result["server"] = dict(zip(columns, row))
    finally:
        cursor.close()

    try:
        result["configuration"] = _get_config_sync(backend)
    except Exception:
        result["configuration"] = []

    try:
        result["databases"] = _get_databases_sync(backend)
    except Exception:
        result["databases"] = []

    return result


def _display_status_rich(status_data: dict, verbose: int = 0):
    """Display status using rich console.

    SQL Server-specific rich display includes Edition, Product Level,
    and Database Files sections.
    """
    from rich.console import Console
    from rich.table import Table

    console = Console(force_terminal=True)

    console.print("\n[bold cyan]SQL Server Status[/bold cyan]\n")

    server = status_data.get("server", {})
    if server:
        console.print("[bold green]Server[/bold green]")
        server_table = Table(show_header=True, header_style="bold")
        server_table.add_column("Property")
        server_table.add_column("Value")

        for key, value in server.items():
            if value is not None:
                server_table.add_row(str(key), str(value))

        console.print(server_table)
        console.print()

    config_items = status_data.get("configuration", [])
    if config_items:
        console.print("[bold green]Configuration[/bold green]")
        config_table = Table(show_header=True, header_style="bold")
        config_table.add_column("Name")
        config_table.add_column("Value")
        config_table.add_column("Value In Use")
        if verbose >= 1:
            config_table.add_column("Description")
            config_table.add_column("Dynamic")

        for item in config_items:
            row = [str(item.get("name", "")), str(item.get("value", "")), str(item.get("value_in_use", ""))]
            if verbose >= 1:
                desc = str(item.get("description", ""))[:60]
                row.extend([desc, "Yes" if item.get("is_dynamic") else "No"])
            config_table.add_row(*row)

        console.print(config_table)
        console.print()

    databases = status_data.get("databases", [])
    if databases:
        console.print("[bold green]Databases[/bold green]")
        db_table = Table(show_header=True, header_style="bold")
        db_table.add_column("Name")
        db_table.add_column("State")
        db_table.add_column("Recovery Model")
        if verbose >= 1:
            db_table.add_column("Collation")
            db_table.add_column("Size")

        for db in databases:
            row = [
                str(db.get("database_name", "")),
                str(db.get("state", "")),
                str(db.get("recovery_model", "")),
            ]
            if verbose >= 1:
                row.append(str(db.get("collation_name", "")))
                size_bytes = db.get("size_bytes")
                row.append(_format_size(size_bytes) if size_bytes else "N/A")
            db_table.add_row(*row)

        console.print(db_table)
        console.print()
