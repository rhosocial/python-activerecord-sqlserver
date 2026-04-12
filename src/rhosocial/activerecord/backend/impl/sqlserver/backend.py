# src/rhosocial/activerecord/backend/impl/sqlserver/backend.py
"""
SQL Server-specific implementation of the StorageBackend.

This module provides the concrete implementation for interacting with SQL Server databases,
handling connections, queries, transactions, and type adaptations tailored for SQL Server's
specific behaviors and SQL dialect.
"""
import logging
from typing import List, Optional, Tuple

from rhosocial.activerecord.backend.base import StorageBackend
from rhosocial.activerecord.backend.result import QueryResult


class SQLServerBackend(StorageBackend):
    """SQL Server-specific backend implementation."""

    def __init__(self, **kwargs):
        """Initialize SQL Server backend with connection configuration.

        Args:
            connection_config: SQL Server connection configuration.
        """
        super().__init__(**kwargs)
        self._connection = None
        self._dialect = None
        self.log(logging.INFO, "SQLServerBackend initialized")

    def connect(self):
        """Establish connection to SQL Server database."""
        raise NotImplementedError("SQL Server backend is not yet implemented")

    def disconnect(self):
        """Close connection to SQL Server database."""
        raise NotImplementedError("SQL Server backend is not yet implemented")

    def execute(self, sql: str, params: Optional[Tuple] = None, *, options, **kwargs) -> QueryResult:
        """Execute a SQL statement with optional parameters.

        Args:
            sql: SQL string with placeholders
            params: Parameter tuple
            options: ExecutionOptions (REQUIRED - must include stmt_type)

        Returns:
            QueryResult with execution results
        """
        raise NotImplementedError("SQL Server backend is not yet implemented")

    def execute_many(self, sql: str, params_list: List[Tuple]) -> QueryResult:
        """Execute the same SQL statement multiple times with different parameters."""
        raise NotImplementedError("SQL Server backend is not yet implemented")

    def get_server_version(self) -> tuple:
        """Get SQL Server server version."""
        raise NotImplementedError("SQL Server backend is not yet implemented")

    def ping(self, reconnect: bool = True) -> bool:
        """Ping the SQL Server to check if the connection is alive."""
        raise NotImplementedError("SQL Server backend is not yet implemented")

    def executescript(self, sql_script: str) -> None:
        """Execute a multi-statement SQL script."""
        raise NotImplementedError("SQL Server backend is not yet implemented")
