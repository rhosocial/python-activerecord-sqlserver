# src/rhosocial/activerecord/backend/impl/sqlserver/cli/introspect.py
"""introspect subcommand - Database introspection.

Every type this command offers is answered by ``backend.introspector``. The
introspector speaks the core API -- ``list_tables``/``list_views``/
``list_columns``/... -- plus this backend's own ``list_schemas``,
``list_procedures``, ``list_functions``, ``list_sequences``,
``list_partitions``, ``list_types`` and ``list_constraints``; there are no
``get_tables``/``get_views``/``get_columns`` methods anywhere, and asking for
them was why this command used to fail for every type.

The mapping from a type name to an introspector method lives in ``_steps``
and nowhere else, so a new type is one entry there plus one title. The sync
and async paths differ in exactly one keyword: whether the method is
awaited.

What NAME means for a type is decided once, in ``_NAME_RULE``, and applied by
one validator before the connection is opened. It is not decided in the
branches: a name a type has no question for is refused with exit 2 rather
than parsed and dropped, and a type added without a rule is a type nobody has
decided for.

The nine families the MySQL and PostgreSQL CLIs ask for are considered here
too, each gated on the switch that answers for it. SQL Server answers eight
of the nine from its dynamic management views and the rows themselves; the
one it does not answer at all -- per-table usage counters, which it keeps per
*index* -- answers ``False``, and the capability check refuses it with exit 2
rather than letting a rendered statement fail at execution.

DDL extraction is not offered by this command at all. The engine has no
per-object call of the kind ``SHOW CREATE TABLE`` is, so
``supports_ddl_extraction()`` is permanently ``False``; advertising a type
whose capability can never be true would promise only a refusal, so ``ddl``
is not a CLI type. The formatter and the DDL expression stay in the backend,
where a real implementation can reuse them.
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
from .output import OUTPUT_CHOICES, create_provider

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
    "partitions": "supports_partition_metadata_introspection",
    "types": "supports_type_introspection",
    "constraints": "supports_constraint_introspection",
    # The eight of the nine families shared with the MySQL and PostgreSQL
    # CLIs that this engine answers. Each names the probe that answers for it
    # here, which is not automatically the same answer it gives there: the
    # dependency graph and the runtime listing come from the DMVs, the
    # unused-index and index-counter families from the index usage DMV, and
    # the three data families from the rows themselves. The ninth,
    # per-table usage counters, is offered and refused by the engine's own
    # answer; ``ddl`` is not offered at all because the capability is
    # permanently false.
    "unused-indexes": "supports_unused_indexes_detection",
    "table-stats": "supports_table_stats",
    "runtime": "supports_runtime_stats",
    "index-stats": "supports_index_stats",
    "dependencies": "supports_object_dependencies",
    "column-profiles": "supports_column_data_profile",
    "value-samples": "supports_column_value_sample",
    "join-coverage": "supports_join_coverage",
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
#:
#: The order is the order ``_TYPE_CAPABILITIES`` declares and the parser and
#: ``--help`` print, and the two tables cover the same keys: a type offered
#: without a rule is a type whose NAME decision nobody has made. One validator
#: reads this table, before the connection is opened, and the dispatcher
#: consumes its answer rather than re-deciding per branch.
_NAME_RULE = {
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
    "partitions": "optional",
    "types": "optional",
    "constraints": "optional",
    # The shared families: the counters and the listings describe the database
    # and take no name; the graph narrows to one object and answers the whole
    # graph without one; the one-object families ask about a table. ``ddl`` is
    # absent because the CLI does not offer it: the capability is permanently
    # false, so there is no NAME decision to make.
    "unused-indexes": "forbidden",
    "table-stats": "forbidden",
    "runtime": "forbidden",
    "index-stats": "forbidden",
    "dependencies": "optional",
    "column-profiles": "required",
    "value-samples": "required",
    "join-coverage": "forbidden",
}

#: Options whose meaning depends on the type, and whether they must be given.
#:
#: ``--column`` and ``--limit`` belong to ``value-samples``, the four join
#: names to ``join-coverage``, and nothing else has an option beyond NAME. A
#: flag supplied to a type that does not read it is refused rather than
#: ignored, for the same reason a NAME nothing reads is: a silently dropped
#: argument produces a successful run that looks like it answered a narrower
#: question.
_TYPE_OPTIONS = {
    "value-samples": (
        ("column", "--column", True),
        ("limit", "--limit", False),
    ),
    "join-coverage": (
        ("left_table", "--left-table", True),
        ("left_column", "--left-column", True),
        ("right_table", "--right-table", True),
        ("right_column", "--right-column", True),
    ),
}

#: Every option in ``_TYPE_OPTIONS``, by attribute, for the stray-flag check.
_TYPE_OPTION_FLAGS = {
    attribute: flag
    for options in _TYPE_OPTIONS.values()
    for attribute, flag, _required in options
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
    "list_partitions": "Partitions",
    "list_types": "User-Defined Types",
    "list_constraints": "Constraints",
    "get_database_info": "Database Info",
    "list_unused_indexes": "Indexes with no recorded use",
    "list_table_usage_stats": "Table usage counters",
    "list_runtime_metrics": "Runtime metrics",
    "list_index_usage_stats": "Index usage counters",
    "list_object_dependencies": "Object dependencies",
    "list_column_data_profiles": "Column profiles",
    "estimate_join_coverage": "Join coverage",
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

  # Partition functions, schemes and aligned indexes (all, or one table's)
  %(prog)s partitions --database mydb
  %(prog)s partitions orders --database mydb

  # User-defined alias, table and CLR types (all, or one type)
  %(prog)s types --database mydb
  %(prog)s types order_note --database mydb

  # Constraint objects, including CHECK and DEFAULT constraints
  %(prog)s constraints --database mydb
  %(prog)s constraints orders --database mydb

  # Operational readings: indexes with no recorded use, per-index counters,
  # live instance counters, the dependency graph
  %(prog)s unused-indexes --database mydb
  %(prog)s index-stats --database mydb
  %(prog)s runtime --database mydb
  %(prog)s dependencies --database mydb
  %(prog)s dependencies orders --database mydb

  # Data profiles: exact counts, paid for with a full scan per column
  %(prog)s column-profiles orders --database mydb
  %(prog)s value-samples orders --column status --limit 20 --database mydb

  # How much two columns' value domains overlap
  %(prog)s join-coverage --left-table orders --left-column customer_id \\
      --right-table customers --right-column id --database mydb

  # A family SQL Server cannot answer is refused by capability, not hidden:
  # table-stats exits 2 with "not supported by this server" once the version
  # is known.
  %(prog)s table-stats --database mydb

  # Output as JSON
  %(prog)s tables --database mydb -o json

  # Using environment variables for connection
  export SQLSERVER_HOST=localhost SQLSERVER_DATABASE=mydb SQLSERVER_USERNAME=sa
  %(prog)s tables

NAME per type:
  columns, indexes, foreign-keys, extended-properties, column-profiles,
  value-samples               a table name, required
  partitions, constraints    a table name, optional
  types                      a type name, optional
  views                       a view name, optional
  triggers, dependencies      optional narrowing
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
    parser.add_argument(
        "--column",
        default=None,
        help="Column name for the value-samples type.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Maximum values to list for value-samples "
            "(default: the introspector's own limit)."
        ),
    )
    parser.add_argument(
        "--left-table",
        dest="left_table",
        default=None,
        help="Left table for the join-coverage type.",
    )
    parser.add_argument(
        "--left-column",
        dest="left_column",
        default=None,
        help="Left column for the join-coverage type.",
    )
    parser.add_argument(
        "--right-table",
        dest="right_table",
        default=None,
        help="Right table for the join-coverage type.",
    )
    parser.add_argument(
        "--right-column",
        dest="right_column",
        default=None,
        help="Right column for the join-coverage type.",
    )

    return parser


def _validate_name(args) -> None:
    """Apply the NAME rule table before anything connects.

    A *missing* name is an incomplete invocation and leaves with 1; a name
    the type has no use for is a request this command declines and leaves with
    2. Both are checked here, once, rather than being left to each branch to
    remember -- a branch that forgot would answer a wider question than the
    one asked and look successful.
    """
    rule = _NAME_RULE.get(args.type)
    if rule == "required" and not args.name:
        print(
            f"Error: Table name is required for '{args.type}' introspection",
            file=sys.stderr,
        )
        sys.exit(1)
    if rule == "forbidden" and args.name:
        print(
            f"Error: {args.type} introspection takes no name",
            file=sys.stderr,
        )
        sys.exit(2)


def _validate_options(args) -> None:
    """Refuse a flag the type does not read, or a missing one it needs.

    A missing required option is an incomplete invocation (exit 1); an option
    the type has no use for is a request this command declines (exit 2), like
    a NAME it cannot use. Reading the flags with ``getattr`` keeps the
    hand-built namespaces the offline tests use working: an absent attribute
    is "not given", not an error.
    """
    options = _TYPE_OPTIONS.get(args.type, ())
    accepted = {attribute for attribute, _flag, _required in options}

    missing = [
        flag
        for attribute, flag, required in options
        if required and not getattr(args, attribute, None)
    ]
    if missing:
        print(
            f"Error: {', '.join(missing)} is required for "
            f"'{args.type}' introspection",
            file=sys.stderr,
        )
        sys.exit(1)

    for attribute, flag in _TYPE_OPTION_FLAGS.items():
        if attribute in accepted:
            continue
        if getattr(args, attribute, None) not in (None, ""):
            print(
                f"Error: '{args.type}' introspection takes no {flag}",
                file=sys.stderr,
            )
            sys.exit(2)


def _value_sample_arguments(args) -> Dict[str, int]:
    """The optional arguments ``value-samples`` sends, given the parsed argument.

    ``limit`` is forwarded only when the caller supplied ``--limit``. When the
    flag is absent the introspector's signature answers with its own default,
    so a forwarder that filled in ``100`` would be a second place writing a
    number the signature already owns -- and a place no test could keep in
    step with it.
    """
    limit = getattr(args, "limit", None)
    return {} if limit is None else {"limit": limit}


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

    # Before a connection is opened: whether a NAME or a flag belongs to the
    # type is a question about the request, not about the server.
    _validate_name(args)
    _validate_options(args)

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


def _name_of(args, kind: str) -> str:
    """The object name a table-scoped type asks with.

    ``_validate_name`` has already refused a run that omitted one: a
    ``required`` type whose NAME is missing never reaches this function. The
    table is read here as well only so a caller that skipped the validator
    still meets the rule rather than sending a ``None`` the introspector would
    answer as a wider question than the one asked -- the decision is written
    once, in ``_NAME_RULE``, and every reader reads it.
    """
    if _NAME_RULE.get(kind) == "required" and not args.name:
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

    The NAME each type accepts is *not* decided here. ``_validate_name`` reads
    ``_NAME_RULE`` before the connection is opened -- a missing one is an
    incomplete invocation, a name the type has no question for is refused
    with exit 2 -- so by the time this runs a ``required`` type always has its
    name and the branches consume ``args.name`` directly. The branches below
    that used to carry their own "Table name is required" sentence now rely on
    that, so there is one decision rather than one per branch.
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
    if kind == "partitions":
        return [(
            "list_partitions",
            {"table_name": args.name, "schema": None},
        )]
    if kind == "types":
        if args.name:
            return [("get_type_info", {"type_name": args.name, "schema": None})]
        return [("list_types", {"schema": None})]
    if kind == "constraints":
        return [(
            "list_constraints",
            {"table_name": args.name, "schema": None},
        )]

    # ---- the shared families from the MySQL and PostgreSQL CLIs ----------
    # The counters and the listings answer for the whole schema, so none
    # takes a name; the graph narrows to one object and answers the whole
    # graph without one; the one-object families ask about a table.
    if kind == "unused-indexes":
        return [("list_unused_indexes", {"schema": None})]
    if kind == "table-stats":
        return [("list_table_usage_stats", {"schema": None})]
    if kind == "runtime":
        return [("list_runtime_metrics", {"schema": None})]
    if kind == "index-stats":
        return [("list_index_usage_stats", {"schema": None})]
    if kind == "dependencies":
        return [(
            "list_object_dependencies",
            {"object_name": args.name, "schema": None},
        )]
    if kind == "column-profiles":
        return [(
            "list_column_data_profiles",
            {"table_name": _name_of(args, kind), "schema": None},
        )]
    if kind == "value-samples":
        if not getattr(args, "column", None):
            print(
                "Error: --column is required for 'value-samples' introspection",
                file=sys.stderr,
            )
            sys.exit(1)
        return [(
            "sample_column_values",
            {
                "table_name": _name_of(args, kind),
                "column_name": args.column,
                "schema": None,
                **_value_sample_arguments(args),
            },
        )]
    if kind == "join-coverage":
        missing = [
            flag
            for attribute, flag, required in _TYPE_OPTIONS["join-coverage"]
            if required and not getattr(args, attribute, None)
        ]
        if missing:
            print(
                f"Error: {', '.join(missing)} is required for "
                "'join-coverage' introspection",
                file=sys.stderr,
            )
            sys.exit(1)
        return [(
            "estimate_join_coverage",
            {
                "left_table": args.left_table,
                "left_column": args.left_column,
                "right_table": args.right_table,
                "right_column": args.right_column,
                "schema": None,
            },
        )]

    # columns / indexes / foreign-keys / extended-properties
    method = f"list_{kind.replace('-', '_')}"
    return [(
        method,
        {"table_name": _name_of(args, kind), "schema": None},
    )]


def _title_for(method: str, kwargs: Dict[str, Any]) -> str:
    """The heading for one section of output."""
    if method in _RESULT_TITLES:
        # Two of the shared families name the object in their title: the
        # graph may be narrowed to one object, and the data families are
        # about one table. The rest describe the database and read the same
        # whatever the caller asked.
        if method == "list_object_dependencies" and kwargs.get("object_name"):
            return f"Dependencies of {kwargs['object_name']}"
        if method == "list_column_data_profiles":
            return f"Column profiles of {kwargs.get('table_name', '')}"
        if method == "list_partitions" and kwargs.get("table_name"):
            return f"Partitions of {kwargs['table_name']}"
        if method == "list_constraints" and kwargs.get("table_name"):
            return f"Constraints of {kwargs['table_name']}"
        return _RESULT_TITLES[method]
    if method == "get_view_info":
        return f"View {kwargs.get('view_name', '')}"
    if method == "get_type_info":
        return f"Type {kwargs.get('type_name', '')}"
    name = kwargs.get("table_name", "")
    if method == "list_columns":
        return f"Columns of {name}"
    if method == "list_indexes":
        return f"Indexes of {name}"
    if method == "list_foreign_keys":
        return f"Foreign Keys of {name}"
    if method == "list_extended_properties":
        return f"Extended Properties of {name}"
    if method == "sample_column_values":
        column = kwargs.get("column_name", "")
        return f"Most frequent values of {name}.{column}"
    if method == "estimate_join_coverage":
        left = f"{kwargs.get('left_table', '')}.{kwargs.get('left_column', '')}"
        right = f"{kwargs.get('right_table', '')}.{kwargs.get('right_column', '')}"
        return f"Join coverage of {left} and {right}"
    return method


#: The per-object questions, and the name each one answers with nothing. A type
#: with no single object to be missing is absent: an empty *list* is a true
#: answer for those ("this schema has no triggers"), not a failed lookup.
_NAMED_TYPES: Dict[str, Tuple[str, str]] = {
    "get_view_info": ("View", "view_name"),
    "get_type_info": ("Type", "type_name"),
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


def _require_measured(method: str, kwargs: Dict[str, Any], value: Any) -> None:
    """Refuse a ``None`` answer that means "not measured", not zero.

    ``join-coverage`` answers with a single object or nothing: ``None`` from
    the coverage question says the overlap could not be measured, which is a
    different answer from an empty row and from a measured zero. It leaves
    with 1 rather than printing a row of nulls that a reader would take for a
    measurement.
    """
    if value is not None:
        return
    if method == "estimate_join_coverage":
        left = f"{kwargs.get('left_table', '')}.{kwargs.get('left_column', '')}"
        right = f"{kwargs.get('right_table', '')}.{kwargs.get('right_column', '')}"
        print(
            f"Error: this server could not measure the overlap of {left} and {right}",
            file=sys.stderr,
        )
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
        _require_capability(backend, args.type)
        introspector = backend.introspector
        sections: List[Tuple[str, Any]] = []
        for method, kwargs in _steps(args):
            value = getattr(introspector, method)(**kwargs)
            _require_found(introspector, method, kwargs, value)
            _require_measured(method, kwargs, value)
            if method == "list_column_data_profiles":
                print(
                    "Note: column profiles are aggregated from the rows themselves "
                    "(source='aggregate') -- exact, and paid for with a full scan per column.",
                    file=sys.stderr,
                )
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
            _require_measured(method, kwargs, value)
            if method == "list_column_data_profiles":
                print(
                    "Note: column profiles are aggregated from the rows themselves "
                    "(source='aggregate') -- exact, and paid for with a full scan per column.",
                    file=sys.stderr,
                )
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
