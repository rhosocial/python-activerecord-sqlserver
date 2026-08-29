# src/rhosocial/activerecord/backend/impl/sqlserver/examples/named_connections/__init__.py
"""Named connection examples for SQL Server backend.

This module provides example named connection configurations
that can be used with the named connection system.

Examples:
    >>> from rhosocial.activerecord.backend.impl.sqlserver.examples.named_connections import local_dev
    >>> config = local_dev()
"""

__all__ = [
    "local_dev",
    "local_dev_no_trust",
    "local_dev_docker",
    "prod_db",
    "prod_db_ssl",
    "prod_read_replica",
]

from rhosocial.activerecord.backend.impl.sqlserver.examples.named_connections.development import (
    local_dev,
    local_dev_no_trust,
    local_dev_docker,
)
from rhosocial.activerecord.backend.impl.sqlserver.examples.named_connections.production import (
    prod_db,
    prod_db_ssl,
    prod_read_replica,
)
