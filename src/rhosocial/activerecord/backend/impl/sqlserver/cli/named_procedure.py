# src/rhosocial/activerecord/backend/impl/sqlserver/cli/named_procedure.py
"""named-procedure subcommand - Adapter for shared CLI helper.

named-procedure requires connection arguments, output arguments, and --rich-ascii.
"""

from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend
from rhosocial.activerecord.backend.options import ExecutionOptions
from .connection import create_connection_parent_parser, resolve_connection_config_from_args
from .output import create_provider


def create_parser(subparsers):
    """Create the named-procedure subcommand parser.

    Reuses the shared create_named_procedure_parser, passing a parent parser
    containing only connection and output arguments.
    """
    from rhosocial.activerecord.backend.named_query.cli_procedure import create_named_procedure_parser

    local_parent = create_connection_parent_parser()
    np_epilog = """Examples:
  # Execute named procedure with connection parameters
  %(prog)s myapp.procedures.monthly_report --host localhost --database mydb --param month=2026-03

  # Show signature without executing
  %(prog)s myapp.procedures.monthly_report --describe

  # Preview execution plan
  %(prog)s myapp.procedures.monthly_report --database mydb --dry-run --param month=2026-03

  # List all procedures in a module
  %(prog)s myapp.procedures --list

  # Execute with step transaction mode
  %(prog)s myapp.procedures.monthly_report --database mydb --param month=2026-03 --transaction step

  # Async execution
  %(prog)s myapp.procedures.monthly_report --database mydb --param month=2026-03 --async
"""
    return create_named_procedure_parser(subparsers, local_parent, epilog=np_epilog)


def handle(args):
    """Handle the named-procedure subcommand."""
    from rhosocial.activerecord.backend.named_query.cli_procedure import handle_named_procedure as handle_np

    provider = create_provider(args.output, ascii_borders=args.rich_ascii)
    backend = None

    def backend_factory():
        nonlocal backend
        config = resolve_connection_config_from_args(args)
        backend = SQLServerBackend(connection_config=config)
        backend.connect()
        backend.introspect_and_adapt()
        return backend

    def get_dialect(b):
        return b.dialect

    def execute_query(sql, params, stmt_type):
        return backend.execute(sql, params, options=ExecutionOptions(stmt_type=stmt_type))

    def disconnect():
        if backend and backend._connection:
            backend.disconnect()

    is_async = getattr(args, "is_async", False)
    if is_async:
        from rhosocial.activerecord.backend.impl.sqlserver import AsyncSQLServerBackend
        async_backend = None

        def backend_async_factory():
            nonlocal async_backend
            config = resolve_connection_config_from_args(args)
            async_backend = AsyncSQLServerBackend(connection_config=config)
            return async_backend

        async def get_dialect_async(b):
            return b.dialect

        async def execute_query_async(sql, params, stmt_type):
            return await async_backend.execute(sql, params, options=ExecutionOptions(stmt_type=stmt_type))

        async def disconnect_async():
            if async_backend and async_backend._connection:
                await async_backend.disconnect()

        handle_np(
            args,
            provider,
            backend_factory=backend_factory,
            get_dialect=get_dialect,
            execute_query=execute_query,
            disconnect=disconnect,
            backend_async_factory=backend_async_factory,
            get_dialect_async=get_dialect_async,
            execute_query_async=execute_query_async,
            disconnect_async=disconnect_async,
        )
        return

    handle_np(
        args,
        provider,
        backend_factory=backend_factory,
        get_dialect=get_dialect,
        execute_query=execute_query,
        disconnect=disconnect,
    )
