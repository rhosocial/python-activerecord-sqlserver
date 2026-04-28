# src/rhosocial/activerecord/backend/impl/sqlserver/cli/named_query.py
"""named-query subcommand - Adapter for shared CLI helper.

named-query requires connection arguments and output arguments.
"""

from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend
from rhosocial.activerecord.backend.options import ExecutionOptions
from .connection import create_connection_parent_parser, resolve_connection_config_from_args
from .output import create_provider


def create_parser(subparsers):
    """Create the named-query subcommand parser.

    Reuses the shared create_named_query_parser, passing a parent parser
    containing only connection and output arguments.
    """
    from rhosocial.activerecord.backend.named_query.cli import create_named_query_parser

    local_parent = create_connection_parent_parser()
    nq_epilog = """Examples:
  # Execute named query with connection parameters
  %(prog)s myapp.queries.orders.high_value_pending --host localhost --database mydb --username sa --password secret

  # Override parameters
  %(prog)s myapp.queries.orders.high_value_pending --host localhost --database mydb \\
    --param threshold=5000 --param days=7

  # Show signature without executing
  %(prog)s myapp.queries.orders.high_value_pending --describe

  # Preview SQL without executing
  %(prog)s myapp.queries.orders.orders_by_status --database mydb --param status=pending --dry-run

  # List all named queries in a module
  %(prog)s myapp.queries.orders --list

  # Using environment variables
  export SQLSERVER_HOST=localhost SQLSERVER_DATABASE=mydb SQLSERVER_USERNAME=sa SQLSERVER_PASSWORD=secret
  %(prog)s myapp.queries.orders --list
"""
    return create_named_query_parser(subparsers, local_parent, epilog=nq_epilog)


def handle(args):
    """Handle the named-query subcommand."""
    from rhosocial.activerecord.backend.named_query.cli import handle_named_query as handle_nq

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

        handle_nq(
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

    handle_nq(
        args,
        provider,
        backend_factory=backend_factory,
        get_dialect=get_dialect,
        execute_query=execute_query,
        disconnect=disconnect,
    )
