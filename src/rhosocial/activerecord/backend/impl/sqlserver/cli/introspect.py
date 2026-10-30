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
from typing import Any, Dict, List, Optional, Tuple

from rhosocial.activerecord.backend.errors import ConnectionError, QueryError
from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from .connection import add_connection_args, resolve_connection_config_from_args
from .output import create_provider

OUTPUT_CHOICES = ['table', 'json', 'csv', 'tsv']

#: CLI type -> the dialect capability switch that answers for it.
#:
#: The advertised list below is derived from this mapping, so a family cannot
#: be added to one place and forgotten in the other: a type is in both or in
#: neither. A type whose switch is False on the *connected* server is refused
#: when handled rather than run and answered with an empty list -- "this
#: server cannot answer that" and "this database holds none" are different
#: answers.
_TYPE_CAPABILITIES = {
    "tables": "supports_table_introspection",
    "views": "supports_view_introspection",
    "columns": "supports_column_introspection",
    "indexes": "supports_index_introspection",
    "foreign-keys": "supports_foreign_key_introspection",
    "extended-properties": "supports_extended_property_introspection",
    "triggers": "supports_trigger_introspection",
    "database": "supports_database_info",
    "procedures": "supports_procedure_introspection",
    "functions": "supports_function_introspection",
    "sequences": "supports_sequence_introspection",
    "schemas": "supports_schema_introspection",
}

INTROSPECT_TYPES = list(_TYPE_CAPABILITIES)

#: What a NAME means per type, and whether the type takes one at all.
#:
#: ``required`` -- the name *is* the question (one table's columns);
#: ``optional`` -- the name narrows a list to one table or one view;
#: ``forbidden`` -- the type answers for the database, and a name that looks
#: like a filter would be silently ignored, which is the one thing a NAME
#: argument must never be.
#:
#: ``views NAME`` is a view name and ``triggers NAME`` is a *table* name: the
#: two are not the same kind of argument, which is why this table exists.
_NAME_RULES = {
    "tables": "forbidden",
    "views": "optional",
    "columns": "required",
    "indexes": "required",
    "foreign-keys": "required",
    "extended-properties": "required",
    "triggers": "optional",
    "database": "forbidden",
    "procedures": "forbidden",
    "functions": "forbidden",
    "sequences": "forbidden",
    "schemas": "forbidden",
}

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

  # One view, with its definition and IS_UPDATABLE
  %(prog)s views active_users --database mydb

  # Get column details for a table
  %(prog)s columns users --database mydb

  # Get index information
  %(prog)s indexes users --database mydb

  # Get foreign key relationships
  %(prog)s foreign-keys users --database mydb

  # Get a table's extended properties (MS_Description and friends)
  %(prog)s extended-properties users --database mydb

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

NAME per type:
  columns, indexes, foreign-keys, extended-properties
                              a table name, required
  views                       a view name, optional
  triggers                    a table name, optional
  everything else             no name: refused with exit 2, never ignored
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
        help=(
            "Object name: a table name for the table-scoped types, a view name "
            "for views. Types that answer for the database take none."
        ),
    )
    parser.add_argument(
        "--include-system",
        action="store_true",
        help="Include system tables in output",
    )

    return parser


def _refuse_unused_name(args) -> None:
    """Refuse a NAME the requested type cannot use, rather than ignore it.

    ``introspect tables users`` used to list every table and exit 0, which
    reads as "the filter matched everything" or "the filter was applied" --
    the most misleading shape a wrong answer can take. A name for a type that
    answers for the database is a misuse of the argument, so it leaves with 2.
    """
    if not args.name:
        return
    if _NAME_RULES.get(args.type) != "forbidden":
        return
    print(
        f"Error: {args.type} introspection takes no name",
        file=sys.stderr,
    )
    sys.exit(2)


def _require_capability(backend, kind: str) -> None:
    """Refuse a type the connected server cannot answer.

    The dialect is adapted before this runs, so the switch answers for the
    server in front of us rather than for the newest release this backend
    knows.
    """
    switch = _TYPE_CAPABILITIES.get(kind)
    if switch is None:
        return
    dialect = getattr(backend, "dialect", None)
    if dialect is None:
        # A stub standing in for the backend (the offline CLI tests) has no
        # dialect to ask; a real one always does.
        return
    supported = getattr(dialect, switch, None)
    if supported is None or supported():
        return
    print(
        f"Error: {kind} introspection is not supported by this server",
        file=sys.stderr,
    )
    sys.exit(2)


def handle(args):
    """Handle the introspect subcommand."""
    provider = create_provider(args.output, ascii_borders=args.rich_ascii)

    named_conn = getattr(args, "named_connection", None)
    if not named_conn and not args.database:
        print("Error: --database is required for introspection", file=sys.stderr)
        sys.exit(1)

    # Before a connection is opened: whether a NAME belongs to the type is a
    # question about the request, not about the server.
    _refuse_unused_name(args)

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

    # columns / indexes / foreign-keys / extended-properties
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
    if method == "list_extended_properties":
        return f"Extended Properties of {name}"
    return method


#: The per-object questions, and the name each one answers with nothing. A type
#: with no single object to be missing is absent: an empty *list* is a true
#: answer for those ("this schema has no triggers"), not a failed lookup.
_NAMED_TYPES: Dict[str, Tuple[str, str]] = {
    "get_view_info": ("View", "view_name"),
    "list_extended_properties": ("Table", "table_name"),
}


def _missing_from(
    method: str, kwargs: Dict[str, Any], value: Any
) -> Optional[Tuple[str, str]]:
    """The ``(label, name)`` of a NAME that answered nothing, or ``None``.

    An empty result is only ambiguous for a question that named one object.
    Extended properties are the one that can come back empty for two genuinely
    different reasons -- a table with no ``MS_Description`` and a table that is
    not there both answer with no rows -- so for that type the name is checked
    against the catalogue before it is called missing.
    """
    if value or method not in _NAMED_TYPES:
        return None
    label, argument = _NAMED_TYPES[method]
    name = kwargs.get(argument)
    return None if name is None else (label, name)


def _report_missing(missing: Tuple[str, str]) -> None:
    """Say that a NAME named nothing, and leave with the "no such object" code."""
    label, name = missing
    print(f"Error: {label} '{name}' not found", file=sys.stderr)
    sys.exit(1)


def _require_found(introspector: Any, method: str, kwargs: Dict[str, Any], value: Any) -> None:
    """Refuse a NAME that named nothing, rather than print an empty answer."""
    missing = _missing_from(method, kwargs, value)
    if missing is None:
        return
    if method == "list_extended_properties" and introspector.table_exists(
        kwargs["table_name"], kwargs.get("schema")
    ):
        return  # the table is there; it simply carries no properties
    _report_missing(missing)


async def _require_found_async(
    introspector: Any, method: str, kwargs: Dict[str, Any], value: Any
) -> None:
    """``_require_found`` against an asynchronous introspector.

    Same question, same answer, one ``await``: the existence read is the
    introspector's, and this backend's asynchronous manager answers with a
    coroutine.
    """
    missing = _missing_from(method, kwargs, value)
    if missing is None:
        return
    if method == "list_extended_properties" and await introspector.table_exists(
        kwargs["table_name"], kwargs.get("schema")
    ):
        return
    _report_missing(missing)


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
        _require_capability(backend, args.type)
        introspector = backend.introspector
        sections: List[Tuple[str, Any]] = []
        for method, kwargs in _steps(args):
            value = getattr(introspector, method)(**kwargs)
            _require_found(introspector, method, kwargs, value)
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
        _require_capability(backend, args.type)
        introspector = backend.introspector
        sections: List[Tuple[str, Any]] = []
        for method, kwargs in _steps(args):
            value = await getattr(introspector, method)(**kwargs)
            await _require_found_async(introspector, method, kwargs, value)
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
