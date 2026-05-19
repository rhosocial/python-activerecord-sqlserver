# src/rhosocial/activerecord/backend/impl/sqlserver/cli/info.py
"""info subcommand - Display SQL Server environment information.

info can optionally connect to a database for version introspection,
falling back to --version flag when no connection is available.
"""

import argparse
import inspect
import json
import logging
import sys
from typing import Any, Dict, List, Optional, Tuple

from rhosocial.activerecord.backend.dialect.protocols import (
    WindowFunctionSupport,
    CTESupport,
    FilterClauseSupport,
    ReturningSupport,
    UpsertSupport,
    LateralJoinSupport,
    JoinSupport,
    JSONSupport,
    ExplainSupport,
    GraphSupport,
    SetOperationSupport,
    ViewSupport,
    TableSupport,
    TruncateSupport,
    GeneratedColumnSupport,
    TriggerSupport,
    FunctionSupport,
    AdvancedGroupingSupport,
    ArraySupport,
    ILIKESupport,
    IndexSupport,
    LockingSupport,
    MergeSupport,
    OrderedSetAggregationSupport,
    QualifyClauseSupport,
    SchemaSupport,
    SequenceSupport,
    TemporalTableSupport,
)

from rhosocial.activerecord.backend.impl.sqlserver.protocols import (
    SQLServerIndexedViewSupport,
    SQLServerIdentitySupport,
    SQLServerTableHintSupport,
    SQLServerOutputSupport,
)

from .connection import add_connection_args, add_version_arg, resolve_connection_config_from_args
from .output import create_provider, RICH_AVAILABLE

logger = logging.getLogger(__name__)

OUTPUT_CHOICES = ['table', 'json']

DIALECT_SPECIFIC_GROUPS = {"SQL Server Native"}

PROTOCOL_FAMILY_GROUPS: Dict[str, list] = {
    "Query Features": [
        WindowFunctionSupport,
        CTESupport,
        FilterClauseSupport,
        SetOperationSupport,
        AdvancedGroupingSupport,
    ],
    "JOIN Support": [JoinSupport, LateralJoinSupport],
    "Data Types": [JSONSupport, ArraySupport],
    "DML Features": [
        ReturningSupport,
        UpsertSupport,
        MergeSupport,
        OrderedSetAggregationSupport,
    ],
    "Transaction & Locking": [LockingSupport, TemporalTableSupport],
    "Query Analysis": [ExplainSupport, GraphSupport, QualifyClauseSupport],
    "DDL - Table": [TableSupport, TruncateSupport, GeneratedColumnSupport],
    "DDL - View": [ViewSupport],
    "DDL - Schema & Index": [SchemaSupport, IndexSupport],
    "DDL - Sequence & Trigger": [SequenceSupport, TriggerSupport, FunctionSupport],
    "String Matching": [ILIKESupport],
    "SQL Server Native": [
        SQLServerIndexedViewSupport,
        SQLServerIdentitySupport,
        SQLServerTableHintSupport,
        SQLServerOutputSupport,
    ],
}

SUPPORT_METHOD_ALL_ARGS: Dict[str, List[str]] = {
    "supports_explain_format": ["TEXT", "XML"],
}


def create_parser(subparsers):
    """Create the info subcommand parser."""
    parser = subparsers.add_parser(
        'info',
        help='Display SQL Server environment information',
        epilog="""Examples:
  # Show info using default version (16.0.0)
  %(prog)s

  # Show info for a specific version
  %(prog)s --version 16.0.0

  # Show info from actual database connection
  %(prog)s --host localhost --database mydb

  # Output as JSON
  %(prog)s -o json

  # Detailed protocol support
  %(prog)s -vv
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
    add_version_arg(parser)

    parser.add_argument(
        '-v', '--verbose',
        action='count',
        default=0,
        help='Increase verbosity. -v for families, -vv for details.',
    )

    parser.add_argument(
        '--rich-ascii',
        action='store_true',
        help='Use ASCII characters for rich table borders.',
    )

    return parser


def handle(args):
    """Handle the info subcommand."""
    provider = create_provider(args.output, ascii_borders=args.rich_ascii)

    is_connected = False
    dialect = None
    version_display = None

    named_conn = getattr(args, "named_connection", None)
    if named_conn or args.database:
        try:
            from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend

            config = resolve_connection_config_from_args(args)
            backend = SQLServerBackend(connection_config=config)
            backend.connect()
            backend.introspect_and_adapt()

            dialect = backend.dialect
            version_tuple = backend.get_server_version()
            if version_tuple:
                version_display = f"{version_tuple[0]}.{version_tuple[1]}.{version_tuple[2]}"

            is_connected = True
            backend.disconnect()
        except Exception as e:
            logger.warning("Could not connect to database for introspection: %s", e)
            logger.warning("Using default values for dialect information.")

    if dialect is None:
        actual_version = args.version
        if actual_version:
            version = parse_version(actual_version)
        else:
            version = (16, 0, 0)

        from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
        dialect = SQLServerDialect(version=version)
        version_display = f"{version[0]}.{version[1]}.{version[2]}"

    info = {
        "database": {
            "type": "sqlserver",
            "version": version_display,
            "version_tuple": list(dialect.version),
            "connected": is_connected,
        },
        "protocols": {},
    }

    for group_name, protocols in PROTOCOL_FAMILY_GROUPS.items():
        info["protocols"][group_name] = _build_protocol_info(
            dialect, group_name, protocols, args.verbose
        )

    if args.output == "json" or not RICH_AVAILABLE:
        print(json.dumps(info, indent=2))
    else:
        info_legacy = {
            "sqlserver": info["database"],
            "protocols": info["protocols"],
        }
        _display_info_rich(info_legacy, args.verbose, version_display, is_connected)

    return info


# ---------------------------------------------------------------------------
# Internal helper functions
# ---------------------------------------------------------------------------


def get_protocol_support_methods(protocol_class: type) -> List[str]:
    """Get all support check methods from a protocol class."""
    methods = []
    for name, member in inspect.getmembers(protocol_class):
        is_supports = name.startswith("supports_")
        is_available = name.startswith("is_") and name.endswith("_available")
        if callable(member) and (is_supports or is_available):
            methods.append(name)
    return sorted(methods)


def check_protocol_support(dialect, protocol_class: type) -> Dict[str, Any]:
    """Check all support methods for a protocol against the dialect."""
    results = {}
    methods = get_protocol_support_methods(protocol_class)

    for method_name in methods:
        if hasattr(dialect, method_name):
            try:
                method = getattr(dialect, method_name)
                sig = inspect.signature(method)
                params = [p for p in sig.parameters.values() if p.default == inspect.Parameter.empty]
                required_params = [p for p in params if p.name != "self"]

                if len(required_params) == 0:
                    result = method()
                    results[method_name] = bool(result)
                elif method_name in SUPPORT_METHOD_ALL_ARGS:
                    all_args = SUPPORT_METHOD_ALL_ARGS[method_name]
                    arg_results = {}
                    for arg in all_args:
                        try:
                            arg_results[arg] = bool(method(arg))
                        except Exception:
                            arg_results[arg] = False
                    supported_count = sum(1 for v in arg_results.values() if v)
                    results[method_name] = {
                        "supported": supported_count,
                        "total": len(all_args),
                        "args": arg_results,
                    }
                else:
                    results[method_name] = False
            except Exception:
                results[method_name] = False
        else:
            results[method_name] = False

    return results


def parse_version(version_str: str) -> Tuple[int, int, int]:
    """Parse version string like '16.0.0' to tuple."""
    parts = version_str.split('.')
    major = int(parts[0]) if len(parts) > 0 else 0
    minor = int(parts[1]) if len(parts) > 1 else 0
    patch = int(parts[2]) if len(parts) > 2 else 0
    return (major, minor, patch)


def _calculate_protocol_stats(support_methods: Dict[str, Any]) -> Tuple[int, int]:
    """Calculate supported and total counts from support methods."""
    supported_count = 0
    total_count = 0
    for value in support_methods.values():
        if isinstance(value, dict):
            supported_count += value["supported"]
            total_count += value["total"]
        else:
            total_count += 1
            if value:
                supported_count += 1
    return supported_count, total_count


def _build_protocol_info(
    dialect,
    group_name: str,
    protocols: List[type],
    verbose: int,
) -> Dict[str, Dict[str, Any]]:
    """Build protocol support information for a single group."""
    group_info = {}
    for protocol in protocols:
        protocol_name = protocol.__name__
        support_methods = check_protocol_support(dialect, protocol)
        supported_count, total_count = _calculate_protocol_stats(support_methods)
        percentage = round(supported_count / total_count * 100, 1) if total_count > 0 else 0

        if verbose >= 2:
            group_info[protocol_name] = {
                "supported": supported_count,
                "total": total_count,
                "percentage": percentage,
                "methods": support_methods,
            }
        else:
            group_info[protocol_name] = {
                "supported": supported_count,
                "total": total_count,
                "percentage": percentage,
            }

    return group_info


def _get_status_style(pct: float) -> Tuple[str, str]:
    """Get color and symbol based on percentage."""
    if pct == 100:
        return "green", "[OK]"
    elif pct >= 50:
        return "yellow", "[~]"
    elif pct > 0:
        return "red", "[~]"
    else:
        return "red", "[X]"


def _format_method_display(method: str) -> str:
    """Format method name for display."""
    return (
        method.replace("supports_", "")
        .replace("_", " ")
        .replace("is_", "")
        .replace("_available", "")
    )


def _display_method_details(console, method: str, value: Any) -> None:
    """Display detailed method support information."""
    method_display = _format_method_display(method)
    if isinstance(value, dict):
        console.print(f"  [dim]{method_display}:[/dim]")
        for arg, supported in value.get("args", {}).items():
            m_status = "[green][OK][/green]" if supported else "[red][X][/red]"
            console.print(f"    {m_status} {arg}")
    else:
        m_status = "[green][OK][/green]" if value else "[red][X][/red]"
        console.print(f"    {m_status} {method_display}")


def _display_protocol_item(
    console,
    protocol_name: str,
    stats: Dict[str, Any],
    verbose: int,
) -> None:
    """Display a single protocol's support information."""
    pct = stats["percentage"]
    color, symbol = _get_status_style(pct)
    bar_len = 20
    filled = int(pct / 100 * bar_len)
    progress_bar = "#" * filled + "-" * (bar_len - filled)
    sup = stats["supported"]
    tot = stats["total"]
    console.print(
        f"  [{color}]{symbol}[/{color}] {protocol_name}: "
        f"[{color}]{progress_bar}[/{color}] {pct:.0f}% ({sup}/{tot})"
    )
    if verbose >= 2 and "methods" in stats:
        for method, value in stats["methods"].items():
            _display_method_details(console, method, value)


def _display_protocol_group(
    console,
    group_name: str,
    protocols: Dict[str, Any],
    verbose: int,
) -> None:
    """Display a protocol group's support information."""
    if group_name in DIALECT_SPECIFIC_GROUPS:
        console.print(f"\n  [bold underline]{group_name}:[/bold underline] [dim](dialect-specific)[/dim]")
    else:
        console.print(f"\n  [bold underline]{group_name}:[/bold underline]")

    for protocol_name, stats in protocols.items():
        _display_protocol_item(console, protocol_name, stats, verbose)


def _display_info_rich(
    info: Dict,
    verbose: int,
    version_display: str,
    is_connected: bool = True,
):
    """Display info using rich console."""
    from rich.console import Console

    console = Console(force_terminal=True)
    console.print("\n[bold cyan]SQL Server Environment Information[/bold cyan]\n")

    if is_connected:
        console.print(f"[bold]SQL Server Version:[/bold] {version_display} [dim](from actual connection)[/dim]\n")
    else:
        console.print(f"[bold]SQL Server Version:[/bold] {version_display} [yellow](default value - no database connection)[/yellow]\n")

    label = "Detailed" if verbose >= 2 else "Family Overview"
    console.print(f"[bold green]Protocol Support ({label}):[/bold green]")

    for group_name, protocols in info["protocols"].items():
        _display_protocol_group(console, group_name, protocols, verbose)

    console.print()
