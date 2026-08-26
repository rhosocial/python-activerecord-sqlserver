# src/rhosocial/activerecord/backend/impl/sqlserver/cli/connection.py
"""Connection argument parsing and backend creation for SQL Server CLI.

Encryption defaults matrix -- applied whenever the corresponding explicit
flag is absent. ``--encrypt``/``--no-encrypt`` and
``--trust-server-certificate``/``--no-trust-server-certificate`` always take
precedence over values derived from ``--ssl``:

===============  =========  ==========================
--ssl            encrypt    trust_server_certificate
===============  =========  ==========================
auto (default)   False      True
disabled         False      True
require          True       True
verify-ca        True       False
verify-full      True       False
===============  =========  ==========================

In particular, the default ``--ssl auto`` no longer implies
``encrypt=True``, matching the ``--encrypt`` flag's own default of off.
"""

import os


def add_connection_args(parser):
    """Add SQL Server connection arguments to a subcommand parser.

    Each subcommand that needs a database connection calls this.
    """
    parser.add_argument(
        "--host",
        default=os.getenv("SQLSERVER_HOST", "localhost"),
        help="Database host (env: SQLSERVER_HOST, default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("SQLSERVER_PORT", "1433")),
        help="Database port (env: SQLSERVER_PORT, default: 1433)",
    )
    parser.add_argument(
        "--database",
        default=os.getenv("SQLSERVER_DATABASE"),
        help="Database name (env: SQLSERVER_DATABASE, optional for some operations)",
    )
    parser.add_argument(
        "--user",
        "--username",
        dest="username",
        default=os.getenv("SQLSERVER_USERNAME", "sa"),
        help="Database username (env: SQLSERVER_USERNAME, default: sa). "
        "--username is an alias for --user.",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("SQLSERVER_PASSWORD", ""),
        help="Database password (env: SQLSERVER_PASSWORD)",
    )
    parser.add_argument(
        "--ssl",
        choices=["auto", "require", "verify-ca", "verify-full", "disabled"],
        default="auto",
        help="SSL mode (env: SQLSERVER_SSL, default: auto)",
    )
    parser.add_argument(
        "--trusted-connection",
        dest="trusted_connection",
        action="store_true",
        default=False,
        help="Use Windows Authentication",
    )
    parser.add_argument(
        "--driver",
        default=os.getenv("SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server"),
        help="ODBC driver name (env: SQLSERVER_DRIVER, default: ODBC Driver 18 for SQL Server)",
    )
    encrypt_group = parser.add_mutually_exclusive_group()
    encrypt_group.add_argument(
        "--encrypt",
        action="store_true",
        default=None,
        dest="encrypt",
        help="Encrypt connection (takes precedence over --ssl)",
    )
    encrypt_group.add_argument(
        "--no-encrypt",
        action="store_false",
        dest="encrypt",
        help="Do not encrypt connection (takes precedence over --ssl)",
    )
    parser.add_argument(
        "--trust-server-certificate",
        dest="trust_server_certificate",
        action="store_true",
        default=None,
        help="Trust server certificate (takes precedence over --ssl)",
    )
    parser.add_argument(
        "--no-trust-server-certificate",
        dest="trust_server_certificate",
        action="store_false",
        help="Do not trust server certificate (takes precedence over --ssl)",
    )
    parser.add_argument(
        "--async",
        action="store_true",
        dest="is_async",
        help="Use asynchronous backend",
    )
    parser.add_argument(
        "--named-connection",
        dest="named_connection",
        metavar="QUALIFIED_NAME",
        help="Named connection from Python module (e.g., myapp.connections.prod_db).",
    )
    parser.add_argument(
        "--conn-param",
        action="append",
        metavar="KEY=VALUE",
        default=[],
        dest="connection_params",
        help="Connection parameter override for named connection. Can be specified multiple times.",
    )


def add_version_arg(parser):
    """Add --version argument (used only by info subcommand)."""
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help='SQL Server version to simulate (e.g., "16.0.0"). Default: auto-detect.',
    )


def create_connection_parent_parser():
    """Create a parent parser with connection and output arguments.

    Used by shared CLI helpers (named-query, named-procedure) that require
    a parent_parser containing connection parameters.
    """
    import argparse

    parent = argparse.ArgumentParser(add_help=False)
    add_connection_args(parent)

    parent.add_argument(
        "-o", "--output",
        choices=["table", "json", "csv", "tsv"],
        default="table",
        help='Output format. Defaults to "table" if rich is installed.',
    )
    parent.add_argument(
        "--rich-ascii",
        action="store_true",
        help="Use ASCII characters for rich table borders.",
    )
    return parent


def resolve_connection_config_from_args(args):
    """Resolve SQL Server connection config from parsed args.

    Priority order:
    1. --named-connection + --conn-param
    2. Explicit connection parameters (--host, --port, etc.)
    3. Default values
    """
    from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig
    from rhosocial.activerecord.backend.named_connection.cli import parse_params
    from rhosocial.activerecord.backend.named_connection import NamedConnectionResolver

    named_conn = getattr(args, "named_connection", None)
    conn_params = getattr(args, "connection_params", [])

    if conn_params:
        conn_params = parse_params(conn_params)
    else:
        conn_params = {}

    if named_conn:
        resolver = NamedConnectionResolver(named_conn).load()
        if conn_params:
            return resolver.resolve(conn_params)
        return resolver.resolve({})

    # SSL parameter mapping. Explicit --encrypt/--no-encrypt and
    # --trust-server-certificate/--no-trust-server-certificate flags win over
    # the values derived from --ssl; see the matrix in the module docstring.
    ssl_param = getattr(args, "ssl", None)
    if ssl_param in ("require", "verify-ca", "verify-full"):
        ssl_encrypt = True
        # verify-ca/verify-full require a CA check; require trusts the cert
        ssl_trust_cert = ssl_param == "require"
    else:
        # "auto" (default) and "disabled" do not force encryption
        ssl_encrypt = False
        ssl_trust_cert = True

    explicit_encrypt = getattr(args, "encrypt", None)
    if explicit_encrypt is not None:
        ssl_encrypt = explicit_encrypt

    explicit_trust = getattr(args, "trust_server_certificate", None)
    if explicit_trust is not None:
        ssl_trust_cert = explicit_trust

    return SQLServerConnectionConfig(
        host=args.host or "localhost",
        port=args.port or 1433,
        database=args.database or "master",
        username=args.username,
        password=args.password,
        trusted_connection=getattr(args, "trusted_connection", False),
        driver=getattr(args, "driver", "ODBC Driver 18 for SQL Server"),
        encrypt=ssl_encrypt,
        trust_server_certificate=ssl_trust_cert,
    )


def create_backend(args):
    """Create, connect, and introspect a SQL Server backend from parsed args."""
    from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend

    config = resolve_connection_config_from_args(args)
    backend = SQLServerBackend(connection_config=config)
    backend.connect()
    backend.introspect_and_adapt()
    return backend
