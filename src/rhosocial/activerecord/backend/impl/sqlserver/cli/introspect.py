# src/rhosocial/activerecord/backend/impl/sqlserver/cli/introspect.py
"""introspect subcommand - Database introspection.

SQL Server introspect includes the 'procedures' and 'functions' types
in addition to the standard types.
"""

import argparse
import asyncio
import sys
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend
from rhosocial.activerecord.backend.errors import ConnectionError, QueryError
from .connection import add_connection_args, resolve_connection_config_from_args
from .output import create_provider

OUTPUT_CHOICES = ['table', 'json', 'csv', 'tsv']

INTROSPECT_TYPES = [
    "tables",
    "views",
    "table",
    "columns",
    "indexes",
    "foreign-keys",
    "triggers",
    "database",
    "procedures",
    "functions",
    "sequences",
]


def create_parser(subparsers):
    """Create the introspect subcommand parser."""
    parser = subparsers.add_parser(
        'introspect',
        help='Database introspection',
        epilog="""Examples:
  # List all tables in database
  %(prog)s tables --database mydb

  # List all views
  %(prog)s views --database mydb

  # Get detailed table info (columns, indexes, foreign keys)
  %(prog)s table users --database mydb

  # Get column details for a table
  %(prog)s columns users --database mydb

  # Get index information
  %(prog)s indexes users --database mydb

  # Get foreign key relationships
  %(prog)s foreign-keys users --database mydb

  # List triggers
  %(prog)s triggers --database mydb

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

  # Specify schema
  %(prog)s tables --database mydb --schema dbo

  # Using environment variables for connection
  export SQLSERVER_HOST=localhost SQLSERVER_DATABASE=mydb SQLSERVER_USERNAME=sa SQLSERVER_PASSWORD=secret
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
        "--schema",
        default="dbo",
        help='Schema name (default: dbo)',
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

    if args.use_async:
        from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend
        backend = AsyncSQLServerBackend(connection_config=config)
        asyncio.run(_handle_introspect_async(args, backend, provider))
    else:
        backend = SQLServerBackend(connection_config=config)
        _handle_introspect_sync(args, backend, provider)


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


def _handle_introspect_sync(args, backend: SQLServerBackend, provider):
    """Handle introspect subcommand synchronously."""
    try:
        backend.connect()
        introspector = backend.introspector

        if args.type == "tables":
            tables = introspector.get_tables(
                schema=args.schema,
            )
            data = _serialize_for_output(tables)
            provider.display_results(data, title="Tables")

        elif args.type == "views":
            views = introspector.get_views(schema=args.schema)
            data = _serialize_for_output(views)
            provider.display_results(data, title="Views")

        elif args.type == "table":
            if not args.name:
                print("Error: Table name is required for 'table' introspection", file=sys.stderr)
                sys.exit(1)
            columns = introspector.get_columns(args.name, schema=args.schema)
            data = _serialize_for_output(columns)
            provider.display_results(data, title=f"Columns of {args.name}")
            indexes = introspector.get_indexes(args.name, schema=args.schema)
            if indexes:
                provider.display_results(_serialize_for_output(indexes), title=f"Indexes of {args.name}")
            fks = introspector.get_foreign_keys(args.name, schema=args.schema)
            if fks:
                provider.display_results(_serialize_for_output(fks), title=f"Foreign Keys of {args.name}")

        elif args.type == "columns":
            if not args.name:
                print("Error: Table name is required for 'columns' introspection", file=sys.stderr)
                sys.exit(1)
            columns = introspector.get_columns(args.name, schema=args.schema)
            data = _serialize_for_output(columns)
            provider.display_results(data, title=f"Columns of {args.name}")

        elif args.type == "indexes":
            if not args.name:
                print("Error: Table name is required for 'indexes' introspection", file=sys.stderr)
                sys.exit(1)
            indexes = introspector.get_indexes(args.name, schema=args.schema)
            data = _serialize_for_output(indexes)
            provider.display_results(data, title=f"Indexes of {args.name}")

        elif args.type == "foreign-keys":
            if not args.name:
                print("Error: Table name is required for 'foreign-keys' introspection", file=sys.stderr)
                sys.exit(1)
            fks = introspector.get_foreign_keys(args.name, schema=args.schema)
            data = _serialize_for_output(fks)
            provider.display_results(data, title=f"Foreign Keys of {args.name}")

        elif args.type == "triggers":
            if args.name:
                triggers = introspector.get_triggers(table=args.name, schema=args.schema)
            else:
                tables = introspector.get_tables(schema=args.schema)
                all_triggers = []
                for t in tables:
                    tname = t.name if hasattr(t, 'name') else t.get('TABLE_NAME', t.get('name', ''))
                    if tname:
                        try:
                            t_triggers = introspector.get_triggers(table=tname, schema=args.schema)
                            all_triggers.extend(t_triggers)
                        except Exception:
                            pass
                triggers = all_triggers
            data = _serialize_for_output(triggers)
            provider.display_results(data, title="Triggers")

        elif args.type == "database":
            if args.name:
                constraints = introspector.get_constraints(table=args.name, schema=args.schema)
                data = _serialize_for_output(constraints)
                provider.display_results([data] if isinstance(data, dict) else data, title=f"Constraints of {args.name}")
            else:
                tables = introspector.get_tables(schema=args.schema)
                db_info = {
                    "tables": _serialize_for_output(tables),
                    "schema": args.schema,
                }
                provider.display_results([db_info], title="Database Info")

        elif args.type == "procedures":
            procedures = introspector.get_procedures(schema=args.schema)
            data = _serialize_for_output(procedures)
            provider.display_results(data, title="Stored Procedures")

        elif args.type == "functions":
            functions = introspector.get_functions(schema=args.schema)
            data = _serialize_for_output(functions)
            provider.display_results(data, title="User-Defined Functions")

        elif args.type == "sequences":
            sequences = introspector.get_sequences(schema=args.schema)
            data = _serialize_for_output(sequences)
            provider.display_results(data, title="Sequences")

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
        if backend._connection: # type: ignore
            backend.disconnect()


async def _handle_introspect_async(args, backend, provider):
    """Handle introspect subcommand asynchronously."""
    try:
        await backend.connect()
        introspector = backend.introspector

        if args.type == "tables":
            tables = introspector.get_tables(schema=args.schema)
            data = _serialize_for_output(tables)
            provider.display_results(data, title="Tables")

        elif args.type == "views":
            views = introspector.get_views(schema=args.schema)
            data = _serialize_for_output(views)
            provider.display_results(data, title="Views")

        elif args.type == "table":
            if not args.name:
                print("Error: Table name is required for 'table' introspection", file=sys.stderr)
                sys.exit(1)
            columns = introspector.get_columns(args.name, schema=args.schema)
            data = _serialize_for_output(columns)
            provider.display_results(data, title=f"Columns of {args.name}")
            indexes = introspector.get_indexes(args.name, schema=args.schema)
            if indexes:
                provider.display_results(_serialize_for_output(indexes), title=f"Indexes of {args.name}")
            fks = introspector.get_foreign_keys(args.name, schema=args.schema)
            if fks:
                provider.display_results(_serialize_for_output(fks), title=f"Foreign Keys of {args.name}")

        elif args.type == "columns":
            if not args.name:
                print("Error: Table name is required for 'columns' introspection", file=sys.stderr)
                sys.exit(1)
            columns = introspector.get_columns(args.name, schema=args.schema)
            data = _serialize_for_output(columns)
            provider.display_results(data, title=f"Columns of {args.name}")

        elif args.type == "indexes":
            if not args.name:
                print("Error: Table name is required for 'indexes' introspection", file=sys.stderr)
                sys.exit(1)
            indexes = introspector.get_indexes(args.name, schema=args.schema)
            data = _serialize_for_output(indexes)
            provider.display_results(data, title=f"Indexes of {args.name}")

        elif args.type == "foreign-keys":
            if not args.name:
                print("Error: Table name is required for 'foreign-keys' introspection", file=sys.stderr)
                sys.exit(1)
            fks = introspector.get_foreign_keys(args.name, schema=args.schema)
            data = _serialize_for_output(fks)
            provider.display_results(data, title=f"Foreign Keys of {args.name}")

        elif args.type == "triggers":
            if args.name:
                triggers = introspector.get_triggers(table=args.name, schema=args.schema)
            else:
                tables = introspector.get_tables(schema=args.schema)
                all_triggers = []
                for t in tables:
                    tname = t.name if hasattr(t, 'name') else t.get('TABLE_NAME', t.get('name', ''))
                    if tname:
                        try:
                            t_triggers = introspector.get_triggers(table=tname, schema=args.schema)
                            all_triggers.extend(t_triggers)
                        except Exception:
                            pass
                triggers = all_triggers
            data = _serialize_for_output(triggers)
            provider.display_results(data, title="Triggers")

        elif args.type == "database":
            if args.name:
                constraints = introspector.get_constraints(table=args.name, schema=args.schema)
                data = _serialize_for_output(constraints)
                provider.display_results([data] if isinstance(data, dict) else data, title=f"Constraints of {args.name}")
            else:
                tables = introspector.get_tables(schema=args.schema)
                db_info = {
                    "tables": _serialize_for_output(tables),
                    "schema": args.schema,
                }
                provider.display_results([db_info], title="Database Info")

        elif args.type == "procedures":
            procedures = introspector.get_procedures(schema=args.schema)
            data = _serialize_for_output(procedures)
            provider.display_results(data, title="Stored Procedures")

        elif args.type == "functions":
            functions = introspector.get_functions(schema=args.schema)
            data = _serialize_for_output(functions)
            provider.display_results(data, title="User-Defined Functions")

        elif args.type == "sequences":
            sequences = introspector.get_sequences(schema=args.schema)
            data = _serialize_for_output(sequences)
            provider.display_results(data, title="Sequences")

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
        if backend._connection: # type: ignore
            await backend.disconnect()
