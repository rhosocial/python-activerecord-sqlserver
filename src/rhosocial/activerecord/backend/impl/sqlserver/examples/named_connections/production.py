# src/rhosocial/activerecord/backend/impl/sqlserver/examples/named_connections/production.py
"""Production environment connection examples.

All configuration values can be overridden via environment variables:
    SQLSERVER_HOST, SQLSERVER_PORT, SQLSERVER_USERNAME, SQLSERVER_PASSWORD,
    SQLSERVER_DATABASE, SQLSERVER_DRIVER
"""

import os

from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig


def _env_or_default(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_int_or_default(key: str, default: int) -> int:
    return int(os.environ.get(key, str(default)))


def _env_bool_or_default(key: str, default: bool) -> bool:
    return os.environ.get(key, str(default)).lower() == "true"


def prod_db():
    """Production SQL Server database connection.

    Reads connection parameters from environment variables with
    fallback to documentation defaults.

    Returns:
        SQLServerConnectionConfig: Production database configuration.
    """
    return SQLServerConnectionConfig(
        host=_env_or_default("SQLSERVER_HOST", "prod-sqlserver.example.com"),
        port=_env_int_or_default("SQLSERVER_PORT", 1433),
        username=_env_or_default("SQLSERVER_USERNAME", "app_user"),
        password=_env_or_default("SQLSERVER_PASSWORD", ""),
        database=_env_or_default("SQLSERVER_DATABASE", "production"),
        driver=_env_or_default("SQLSERVER_DRIVER", "ODBC Driver 17 for SQL Server"),
        encrypt=True,
        trust_server_certificate=False,
        autocommit=True,
    )


def prod_db_ssl():
    """Production SQL Server database with forced encryption.

    Uses TLS encryption with full certificate verification for
    secure production connections.

    Returns:
        SQLServerConnectionConfig: SSL-verified database configuration.
    """
    return SQLServerConnectionConfig(
        host=_env_or_default("SQLSERVER_HOST", "prod-sqlserver.example.com"),
        port=_env_int_or_default("SQLSERVER_PORT", 1433),
        username=_env_or_default("SQLSERVER_USERNAME", "app_user"),
        password=_env_or_default("SQLSERVER_PASSWORD", ""),
        database=_env_or_default("SQLSERVER_DATABASE", "production"),
        driver=_env_or_default("SQLSERVER_DRIVER", "ODBC Driver 17 for SQL Server"),
        encrypt=True,
        trust_server_certificate=False,
        autocommit=True,
    )


def prod_read_replica():
    """Production SQL Server read replica connection.

    For read-heavy workloads, connect to a read replica
    to distribute load.

    Returns:
        SQLServerConnectionConfig: Read replica database configuration.
    """
    return SQLServerConnectionConfig(
        host=_env_or_default("SQLSERVER_REPLICA_HOST", "prod-sqlserver-replica.example.com"),
        port=_env_int_or_default("SQLSERVER_REPLICA_PORT", 1433),
        username=_env_or_default("SQLSERVER_REPLICA_USER", "app_user"),
        password=_env_or_default("SQLSERVER_REPLICA_PASSWORD", ""),
        database=_env_or_default("SQLSERVER_DATABASE", "production"),
        driver=_env_or_default("SQLSERVER_DRIVER", "ODBC Driver 17 for SQL Server"),
        encrypt=True,
        trust_server_certificate=False,
        autocommit=True,
    )
