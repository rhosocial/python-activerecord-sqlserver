# src/rhosocial/activerecord/backend/impl/sqlserver/examples/named_connections/development.py
"""Development environment connection examples.

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


def local_dev():
    """Local development SQL Server database connection.

    Reads connection parameters from environment variables with
    fallback to localhost defaults.

    Returns:
        SQLServerConnectionConfig: Development database configuration.
    """
    return SQLServerConnectionConfig(
        host=_env_or_default("SQLSERVER_HOST", "127.0.0.1"),
        port=_env_int_or_default("SQLSERVER_PORT", 1433),
        username=_env_or_default("SQLSERVER_USERNAME", "sa"),
        password=_env_or_default("SQLSERVER_PASSWORD", "Password123!"),
        database=_env_or_default("SQLSERVER_DATABASE", "master"),
        driver=_env_or_default("SQLSERVER_DRIVER", "ODBC Driver 17 for SQL Server"),
        encrypt=_env_bool_or_default("SQLSERVER_ENCRYPT", False),
        trust_server_certificate=_env_bool_or_default(
            "SQLSERVER_TRUST_SERVER_CERTIFICATE", True
        ),
        autocommit=True,
    )


def local_dev_no_trust():
    """Local SQL Server connection with full encryption verification.

    Uses full SSL verification against the server certificate.

    Returns:
        SQLServerConnectionConfig: SSL-verified database configuration.
    """
    return SQLServerConnectionConfig(
        host=_env_or_default("SQLSERVER_HOST", "127.0.0.1"),
        port=_env_int_or_default("SQLSERVER_PORT", 1433),
        username=_env_or_default("SQLSERVER_USERNAME", "sa"),
        password=_env_or_default("SQLSERVER_PASSWORD", "Password123!"),
        database=_env_or_default("SQLSERVER_DATABASE", "master"),
        driver=_env_or_default("SQLSERVER_DRIVER", "ODBC Driver 17 for SQL Server"),
        encrypt=True,
        trust_server_certificate=False,
        autocommit=True,
    )


def local_dev_docker():
    """SQL Server connection for a Docker container.

    Docker containers typically expose SQL Server on a high port with
    encryption disabled and the certificate trusted.

    Returns:
        SQLServerConnectionConfig: Docker database configuration.
    """
    return SQLServerConnectionConfig(
        host=_env_or_default("SQLSERVER_HOST", "127.0.0.1"),
        port=_env_int_or_default("SQLSERVER_PORT", 11435),
        username=_env_or_default("SQLSERVER_USERNAME", "sa"),
        password=_env_or_default("SQLSERVER_PASSWORD", "Password123!"),
        database=_env_or_default("SQLSERVER_DATABASE", "master"),
        driver=_env_or_default("SQLSERVER_DRIVER", "ODBC Driver 17 for SQL Server"),
        encrypt=False,
        trust_server_certificate=True,
        autocommit=True,
    )
