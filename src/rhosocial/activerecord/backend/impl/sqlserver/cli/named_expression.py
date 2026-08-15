# src/rhosocial/activerecord/backend/impl/sqlserver/cli/named_expression.py
"""named-expression subcommand - Adapter for shared CLI helper.

named-expression requires connection arguments, output arguments, and --rich-ascii.
"""

from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend
from rhosocial.activerecord.backend.options import ExecutionOptions

from .connection import create_connection_parent_parser, resolve_connection_config_from_args
from .output import create_provider


def create_parser(subparsers):
    """Create the named-expression subcommand parser."""
    from rhosocial.activerecord.backend.named_expression.cli import create_named_expression_parser

    local_parent = create_connection_parent_parser()
    parser = create_named_expression_parser(subparsers, local_parent)
    parser.add_argument(
        "--dialect-version",
        default=None,
        help="SQL Server dialect version for capability probing (e.g., 16.0.0, 15.0.0).",
    )
    return parser


def handle(args):
    """Handle the named-expression subcommand."""
    from rhosocial.activerecord.backend.named_expression.cli import handle_named_expression as handle_ne

    provider = create_provider(args.output, ascii_borders=args.rich_ascii)

    from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

    def _get_requested_version():
        ver = getattr(args, "dialect_version", None)
        if ver:
            return tuple(int(p) for p in ver.split("."))
        return None

    def create_dialect():
        return SQLServerDialect(version=_get_requested_version())

    backend = None

    def backend_factory():
        nonlocal backend
        config = resolve_connection_config_from_args(args)
        backend = SQLServerBackend(connection_config=config)
        backend.connect()
        backend.introspect_and_adapt()
        req_ver = _get_requested_version()
        if req_ver:
            backend._dialect.version = req_ver
        return backend

    def get_dialect(b):
        return b.dialect

    def execute_query_by_name(sql, params, stmt_type):
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

        handle_ne(
            args,
            provider,
            backend_factory=backend_factory,
            get_dialect=get_dialect,
            execute_query=execute_query_by_name,
            disconnect=disconnect,
            backend_async_factory=backend_async_factory,
            get_dialect_async=get_dialect_async,
            execute_query_async=execute_query_async,
            disconnect_async=disconnect_async,
            create_dialect=create_dialect,
        )
        return

    handle_ne(
        args,
        provider,
        backend_factory=backend_factory,
        get_dialect=get_dialect,
        execute_query=execute_query_by_name,
        disconnect=disconnect,
        create_dialect=create_dialect,
    )
