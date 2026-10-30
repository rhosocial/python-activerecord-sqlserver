# src/rhosocial/activerecord/backend/impl/sqlserver/cli/introspect.py
"""introspect subcommand - Database introspection.

Every type this command offers is answered by ``backend.introspector``. The
introspector speaks the core API -- ``list_tables``/``list_views``/
``list_columns``/... -- plus this backend's own ``list_schemas``,
``list_procedures``, ``list_functions`` and ``list_sequences``; there are no
``get_tables``/``get_views``/``get_columns`` methods anywhere, and asking for
them was why this command used to fail for every type.

The mapping from a type name to an introspector method lives in ``_steps``
and nowhere else, so a new type is one entry there plus one title. The sync
and async paths differ in exactly one keyword: whether the method is
awaited.
"""

import argparse
import asyncio
import sys
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any, Dict, List, Tuple

from rhosocial.activerecord.backend.errors import ConnectionError, QueryError
from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from .connection import add_connection_args, resolve_connection_config_from_args
from .output import create_provider

OUTPUT_CHOICES = ['table', 'json', 'csv', 'tsv']

INTROSPECT_TYPES = [
    "tables",
    "views",
    "columns",
    "indexes",
    "foreign-keys",
    "triggers",
    "database",
    "procedures",
    "functions",
    "sequences",
    "schemas",
]

#: Titles for the one-result types. The table-scoped types build their title
#: from the table name instead (see ``_title_for``).
_RESULT_TITLES = {
    "list_tables": "Tables",
    "list_views": "Views",
    "list_triggers": "Triggers",
    "list_procedures": "Stored Procedures",
    "list_functions": "User-Defined Functions",
    "list_sequences": "Sequences",
    "list_schemas": "Schemas",
    "get_database_info": "Database Info",
}


def create_parser(subparsers):
    """Create the introspect subcommand parser."""
    parser = subparsers.add_parser(
        'introspect',
        help='Database introspection',
        epilog="""Examples:
  # List all schemas and their owners
  %(prog)s schemas --database mydb

  # List all tables in database
  %(prog)s tables --database mydb

  # List all views
  %(prog)s views --database mydb

  # Get column details for a table
  %(prog)s columns users --database mydb

  # Get index information
  %(prog)s indexes users --database mydb

  # Get foreign key relationships
  %(prog)s foreign-keys users --database mydb

  # List triggers (all of them, or one table's)
  %(prog)s triggers --database mydb
  %(prog)s triggers users --database mydb

  # Get database information
  %(prog)s database --database mydb

  # List stored procedures (SQL Server specific)
  %(prog)s procedures --database mydb

  # List user-defined functions (SQL Server specific)
  %(prog)s functions --database mydb

  # List sequences
  %(prog)s sequences --database mydb

  # Output as JSON
  %(prog)s tables --database mydb -o json

  # Using environment variables for connection
  export SQLSERVER_HOST=localhost SQLSERVER_DATABASE=mydb SQLSERVER_USERNAME=sa
  %(prog)s tables
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
        '--rich-ascii',
        action='store_true',
        help='Use ASCII characters for rich table borders.',
    )

    parser.add_argument(
        "type",
        choices=INTROSPECT_TYPES,
        help="Introspection type",
    )
    parser.add_argument(
        "name",
        nargs="?",
        default=None,
        help="Table/view name (required for some types)",
    )
    parser.add_argument(
        "--include-system",
        action="store_true",
        help="Include system tables in output",
    )

    return parser


def handle(args):
    """Handle the introspect subcommand."""
    provider = create_provider(args.output, ascii_borders=args.rich_ascii)

    named_conn = getattr(args, "named_connection", None)
    if not named_conn and not args.database:
        print("Error: --database is required for introspection", file=sys.stderr)
        sys.exit(1)

    config = resolve_connection_config_from_args(args)

    if args.is_async:
        from rhosocial.activerecord.backend.impl.sqlserver.backend.async_backend import AsyncSQLServerBackend
        backend = AsyncSQLServerBackend(connection_config=config)
        asyncio.run(_handle_introspect_async(args, backend, provider))
    else:
        backend = SQLServerBackend(connection_config=config)
        _handle_introspect_sync(args, backend, provider)


# ---------------------------------------------------------------------------
# Introspection plan
# ---------------------------------------------------------------------------


def _require_name(args, kind: str) -> str:
    """Return the object name a table-scoped type needs, or exit."""
    if not args.name:
        print(
            f"Error: Table name is required for '{kind}' introspection",
            file=sys.stderr,
        )
        sys.exit(1)
    return args.name


def _steps(args) -> List[Tuple[str, Dict[str, Any]]]:
    """Map the requested type to ``(introspector method, kwargs)`` calls.

    This is the single place that decides which introspector method answers
    which type: one type, one question. The table detail that used to be
    assembled here went with the aggregate type it belonged to.

    The NAME each type accepts is decided here too, because it *is* part of
    the question: ``views NAME`` is the single-view question, not a filter over
    the list.
    """
    kind = args.type

    if kind == "database":
        return [("get_database_info", {})]
    if kind == "tables":
        return [(
            "list_tables",
            {"schema": None, "include_system": args.include_system},
        )]
    if kind == "views":
        # One named view is a different question from the list: it answers
        # with the definition and ``is_updatable``. The list now carries the
        # same two facts, so filtering it here would be a second way to ask
        # the first question.
        if args.name:
            return [("get_view_info", {"view_name": args.name, "schema": None})]
        return [(
            "list_views",
            {"schema": None, "include_system": args.include_system},
        )]
    if kind == "triggers":
        # ``list_triggers`` already takes an optional table; iterating tables
        # here was never needed, and it swallowed each table's error.
        return [(
            "list_triggers",
            {"table_name": args.name, "schema": None},
        )]
    if kind == "procedures":
        return [("list_procedures", {"schema": None})]
    if kind == "functions":
        return [("list_functions", {"schema": None})]
    if kind == "sequences":
        return [("list_sequences", {"schema": None})]
    if kind == "schemas":
        return [("list_schemas", {})]

    # columns / indexes / foreign-keys
    method = f"list_{kind.replace('-', '_')}"
    return [(
        method,
        {"table_name": _require_name(args, kind), "schema": None},
    )]


def _title_for(method: str, kwargs: Dict[str, Any]) -> str:
    """The heading for one section of output."""
    if method in _RESULT_TITLES:
        return _RESULT_TITLES[method]
    if method == "get_view_info":
        return f"View {kwargs.get('view_name', '')}"
    name = kwargs.get("table_name", "")
    if method == "list_columns":
        return f"Columns of {name}"
    if method == "list_indexes":
        return f"Indexes of {name}"
    if method == "list_foreign_keys":
        return f"Foreign Keys of {name}"
    return method


#: The per-object questions, and the name each one answers with nothing. A type
#: with no single object to be missing is absent: an empty *list* is a true
#: answer for those ("this schema has no triggers"), not a failed lookup.
_NAMED_TYPES: Dict[str, Tuple[str, str]] = {"get_view_info": ("View", "view_name")}


def _require_found(method: str, kwargs: Dict[str, Any], value: Any) -> None:
    """Refuse a NAME that named nothing, rather than print an empty answer."""
    if value:
        return
    spec = _NAMED_TYPES.get(method)
    if spec is None:
        return
    label, argument = spec
    name = kwargs.get(argument)
    if name is None:
        return
    print(f"Error: {label} '{name}' not found", file=sys.stderr)
    sys.exit(1)


def _value_sections(
    method: str, kwargs: Dict[str, Any], value: Any
) -> List[Tuple[str, Any]]:
    """Turn one introspection result into the sections to render.

    One result, one section. Nothing is expanded into parts here any more,
    because no type asks more than one question.
    """

    if method == "get_database_info":
        return [(_title_for(method, kwargs), [value])]

    return [(_title_for(method, kwargs), value)]


# ---------------------------------------------------------------------------
# Internal helper functions
# ---------------------------------------------------------------------------


def _serialize_for_output(obj: Any) -> Any:
    """Serialize object for JSON output, handling non-serializable types."""
    if obj is None:
        return None
    if hasattr(obj, 'model_dump'):
        try:
            result = obj.model_dump(mode='json')
            return _serialize_for_output(result)
        except TypeError:
            result = obj.model_dump()
            return _serialize_for_output(result)
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


def _render(provider, sections: List[Tuple[str, Any]]) -> None:
    """Render each section through the configured output provider."""
    for title, value in sections:
        data = _serialize_for_output(value)
        if not isinstance(data, list):
            data = [data]
        provider.display_results(data, title=title)


def _handle_introspect_sync(args, backend: SQLServerBackend, provider):
    """Handle introspect subcommand synchronously."""
    try:
        backend.connect()
        # Adapt before the first question: the dialect's capability gates and
        # its version-syntax rendering read a version the handshake supplies,
        # and a CLI that skipped this asked them while they still refused.
        backend.introspect_and_adapt()
        introspector = backend.introspector
        sections: List[Tuple[str, Any]] = []
        for method, kwargs in _steps(args):
            value = getattr(introspector, method)(**kwargs)
            _require_found(method, kwargs, value)
            sections.extend(_value_sections(method, kwargs, value))
        _render(provider, sections)

    except ConnectionError as e:
        provider.display_connection_error(e)
        sys.exit(1)
    except QueryError as e:
        provider.display_query_error(e)
        sys.exit(1)
    except Exception as e:
        print(f"Error during introspection: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if backend._connection:  # type: ignore
            backend.disconnect()


async def _handle_introspect_async(args, backend, provider):
    """Handle introspect subcommand asynchronously."""
    try:
        await backend.connect()
        await backend.introspect_and_adapt()
        introspector = backend.introspector
        sections: List[Tuple[str, Any]] = []
        for method, kwargs in _steps(args):
            value = await getattr(introspector, method)(**kwargs)
            _require_found(method, kwargs, value)
            sections.extend(_value_sections(method, kwargs, value))
        _render(provider, sections)

    except ConnectionError as e:
        provider.display_connection_error(e)
        sys.exit(1)
    except QueryError as e:
        provider.display_query_error(e)
        sys.exit(1)
    except Exception as e:
        print(f"Error during introspection: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if backend._connection:  # type: ignore
            await backend.disconnect()
