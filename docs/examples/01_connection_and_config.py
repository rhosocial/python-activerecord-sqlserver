# docs/examples/01_connection_and_config.py
"""Connect to SQL Server and inspect what the backend can do.

Run with a reachable SQL Server; see docs/examples/README.md for the
environment variables used for connection details.
"""
import os

from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig


def make_config() -> SQLServerConnectionConfig:
    """Build the connection config used by this example."""
    return SQLServerConnectionConfig(
        host=os.environ.get("SQLSERVER_HOST", "localhost"),
        port=int(os.environ.get("SQLSERVER_PORT", "1433")),
        database=os.environ.get("SQLSERVER_DATABASE", "test_db"),
        username=os.environ.get("SQLSERVER_USERNAME", "sa"),
        password=os.environ.get("SQLSERVER_PASSWORD", ""),
        driver=os.environ.get("SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server"),
        encrypt=os.environ.get("SQLSERVER_ENCRYPT", "true").lower() == "true",
        trust_server_certificate=(
            os.environ.get("SQLSERVER_TRUST_SERVER_CERTIFICATE", "false").lower() == "true"
        ),
    )


def main() -> None:
    config = make_config()

    # __repr__ masks the password; show that, not the raw connection string.
    print("Config:", repr(config))
    print("ODBC driver:", config.driver)

    backend = SQLServerBackend(connection_config=config)
    backend.connect()
    try:
        # Refresh the detected server version so version-gated probes answer
        # for the server actually reached.
        backend.introspect_and_adapt()

        dialect = backend.dialect
        print("Dialect:", dialect.name)
        print("Server version:", dialect.get_server_version())
        print("Introspection supported:", dialect.supports_introspection())
        print("SQL Graph supported:", dialect.supports_sql_graph())
        print("Temporal tables supported:", dialect.supports_system_versioning())
        print("DDL extraction supported:", dialect.supports_ddl_extraction())
    finally:
        backend.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    main()
