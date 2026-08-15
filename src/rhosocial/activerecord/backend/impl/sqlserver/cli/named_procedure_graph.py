# src/rhosocial/activerecord/backend/impl/sqlserver/cli/named_procedure_graph.py
"""named-procedure-graph subcommand - Adapter for shared CLI helper.

named-procedure-graph requires connection arguments, output arguments, and --rich-ascii.
"""

from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend

from .connection import create_connection_parent_parser, resolve_connection_config_from_args
from .output import create_provider


def create_parser(subparsers):
    """Create the named-procedure-graph subcommand parser."""
    from rhosocial.activerecord.backend.named_expression.cli_procedure_graph import (
        create_named_procedure_graph_parser,
    )

    local_parent = create_connection_parent_parser()
    return create_named_procedure_graph_parser(subparsers, local_parent)


def handle(args):
    """Handle the named-procedure-graph subcommand."""
    from rhosocial.activerecord.backend.named_expression.cli_procedure_graph import (
        handle_named_procedure_graph as handle_npg,
    )

    provider = create_provider(args.output, ascii_borders=args.rich_ascii)

    backend = None

    def backend_factory():
        nonlocal backend
        config = resolve_connection_config_from_args(args)
        backend = SQLServerBackend(connection_config=config)
        backend.connect()
        backend.introspect_and_adapt()
        return backend

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

        async def disconnect_async():
            if async_backend and async_backend._connection:
                await async_backend.disconnect()

        handle_npg(
            args,
            provider,
            backend_factory=backend_factory,
            disconnect=disconnect,
            backend_async_factory=backend_async_factory,
            disconnect_async=disconnect_async,
        )
        return

    handle_npg(
        args,
        provider,
        backend_factory=backend_factory,
        disconnect=disconnect,
    )
