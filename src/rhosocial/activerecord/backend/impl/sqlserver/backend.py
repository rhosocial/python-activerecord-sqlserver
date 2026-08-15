# src/rhosocial/activerecord/backend/impl/sqlserver/backend.py
"""
SQL Server-specific implementation of the StorageBackend.

This module provides the concrete implementation for interacting with SQL Server databases,
handling connections, queries, transactions, and type adaptations tailored for SQL Server's
specific behaviors and SQL dialect.
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Type

import pyodbc
from pyodbc import Error as PyODBCError, InterfaceError, DatabaseError as PyODBCDatabaseError

from rhosocial.activerecord.backend.base import StorageBackend
from rhosocial.activerecord.backend.errors import (
    ConnectionError,
    DatabaseError,
    DeadlockError,
    IntegrityError,
    OperationalError,
    QueryError,
)
from rhosocial.activerecord.backend.result import QueryResult
from rhosocial.activerecord.backend.introspection.backend_mixin import IntrospectorBackendMixin
from rhosocial.activerecord.backend.explain import SyncExplainBackendMixin
from .config import SQLServerConnectionConfig
from .dialect import SQLServerDialect
from .transaction import SQLServerTransactionManager
from .mixins import SQLServerBackendMixin, SQLServerConcurrencyMixin


class SQLServerUnicodeDialect(SQLServerDialect):
    """SQL Server dialect that renders character types as their unicode variants.

    The shared testsuite stores arbitrary unicode text (including CJK and
    emoji) in plain ``VarCharType``/``CharType`` columns. SQL Server's
    non-unicode ``VARCHAR``/``CHAR`` types cannot hold such characters and
    silently replace them with ``?``. Rendering them as ``NVARCHAR``/``NCHAR``
    (the natural choice for SQL Server text columns) keeps those round-trips
    lossless. ``SQLServerDialect`` itself is left untouched so type-formatting
    unit tests keep observing ``VARCHAR``.
    """

    def format_data_type_varchar(self, data_type):
        return (f"NVARCHAR({data_type.length})" if data_type.length is not None else "NVARCHAR(255)"), ()

    def format_data_type_char(self, data_type):
        return (f"NCHAR({data_type.length})" if data_type.length is not None else "NCHAR(1)"), ()

    def format_cte(self, name, query_sql, columns=None, recursive=False, materialized=None, dialect_options=None):
        """Format a CTE, working around SQL Server's ``ORDER BY`` restriction.

        SQL Server rejects ``ORDER BY`` inside a CTE body unless ``TOP``,
        ``OFFSET`` or ``FOR XML`` is also present (error 1033). The shared
        testsuite builds CTE bodies with plain ``ORDER BY`` (valid on MySQL /
        PostgreSQL), so inject ``TOP (100) PERCENT`` before the sort when no
        ``TOP`` is already specified.
        """
        if re.search(r"\bORDER\s+BY\b", query_sql, re.IGNORECASE) and not re.search(
            r"\bTOP\s*\(?\d+\)?", query_sql, re.IGNORECASE
        ):
            match = re.match(r"(?is)^(\s*SELECT\s+)((?:DISTINCT\s+|ALL\s+)?)(.*)$", query_sql)
            if match:
                query_sql = f"{match.group(1)}TOP (100) PERCENT {match.group(2)}{match.group(3)}"
        return super().format_cte(
            name, query_sql, columns=columns, recursive=recursive,
            materialized=materialized, dialect_options=dialect_options,
        )


class SQLServerBackend(
    SyncExplainBackendMixin,
    IntrospectorBackendMixin,
    SQLServerConcurrencyMixin,
    SQLServerBackendMixin,
    StorageBackend
):
    """SQL Server-specific backend implementation using pyodbc.
    
    This backend provides synchronous connectivity to Microsoft SQL Server
    databases using the pyodbc driver. It supports:
    
    - Connection management with automatic reconnection
    - Transaction management with savepoint support
    - OUTPUT clause for returning modified data
    - SQL Server-specific data types
    - Error handling and conversion
    
    Example:
        >>> backend = SQLServerBackend(
        ...     host="localhost",
        ...     database="mydb",
        ...     trusted_connection=True
        ... )
        >>> backend.connect()
        >>> result = backend.execute("SELECT * FROM users WHERE id = ?", (1,))
        >>> print(result.data)
        >>> backend.disconnect()
    """
    
    CONNECTION_ERROR_CODES = {
        53,
        64,
        232,
        233,
        18456,
        4060,
        40197,
        40501,
        40613,
        11001,
    }
    
    def __init__(self, **kwargs):
        """Initialize SQL Server backend with connection configuration.
        
        Args:
            connection_config: SQLServerConnectionConfig instance, or
            host: Database server host (default: localhost)
            port: Database server port (default: 1433)
            database: Database name (required)
            username: Username for SQL authentication
            password: Password for SQL authentication
            trusted_connection: Use Windows Authentication (default: False)
            driver: ODBC driver name (default: ODBC Driver 17 for SQL Server)
            version: Expected SQL Server version tuple (default: (16, 0, 0))
            **kwargs: Additional connection options
        """
        version = kwargs.pop('version', None) or (16, 0, 0)
        
        connection_config = kwargs.get('connection_config')
        
        if connection_config is None:
            config_params = {}
            sqlserver_params = [
                'host', 'port', 'database', 'username', 'password',
                'trusted_connection', 'driver', 'encrypt',
                'trust_server_certificate', 'timeout', 'query_timeout',
                'autocommit', 'charset', 'pool_size', 'pool_timeout',
            ]
            
            for param in sqlserver_params:
                if param in kwargs:
                    config_params[param] = kwargs[param]
            
            if 'host' not in config_params:
                config_params['host'] = 'localhost'
            if 'port' not in config_params:
                config_params['port'] = 1433
            
            kwargs['connection_config'] = SQLServerConnectionConfig(**config_params)
        
        super().__init__(**kwargs)

        self._version = version
        self._dialect = SQLServerUnicodeDialect(version)
        self._connection = None
        self._transaction_manager = None
        self._default_suggestions_cache = None

        self._register_sqlserver_adapters()

        self.log(logging.INFO, f"SQLServerBackend initialized (version {version})")
    
    @property
    def dialect(self) -> SQLServerDialect:
        """Get the SQL Server dialect instance."""
        return self._dialect

    @property
    def transaction_manager(self) -> SQLServerTransactionManager:
        """Get the transaction manager."""
        if not self._transaction_manager:
            self._transaction_manager = SQLServerTransactionManager(self, self.logger)
        return self._transaction_manager

    def _register_sqlserver_adapters(self) -> None:
        """Register SQL Server-specific type adapters."""
        from .adapters import (
            SQLServerUUIDAdapter,
            SQLServerDateTimeAdapter,
            SQLServerDateTimeOffsetAdapter,
            SQLServerDateAdapter,
            SQLServerTimeAdapter,
            SQLServerJSONAdapter,
            SQLServerXMLAdapter,
            SQLServerDecimalAdapter,
        )
        sqlserver_adapters = [
            SQLServerUUIDAdapter(),
            SQLServerDateTimeAdapter(),
            SQLServerDateTimeOffsetAdapter(),
            SQLServerDateAdapter(),
            SQLServerTimeAdapter(),
            SQLServerJSONAdapter(),
            SQLServerXMLAdapter(),
            SQLServerDecimalAdapter(),
        ]
        for adapter in sqlserver_adapters:
            for py_type, db_types in adapter.supported_types.items():
                for db_type in db_types:
                    self.adapter_registry.register(adapter, py_type, db_type, allow_override=True)

        import datetime as dt, decimal, uuid
        type_map = [
            (SQLServerDateTimeAdapter(),      dt.datetime, dt.datetime),
            (SQLServerDateTimeOffsetAdapter(), dt.datetime, "datetimeoffset"),
            (SQLServerDateAdapter(),           dt.date,     dt.date),
            (SQLServerTimeAdapter(),           dt.time,     dt.time),
            (SQLServerDecimalAdapter(),        decimal.Decimal, decimal.Decimal),
            (SQLServerUUIDAdapter(),           uuid.UUID,   str),
        ]
        for adapter, py_type, db_type in type_map:
            self.adapter_registry.register(adapter, py_type, db_type, allow_override=True)

        self.log(logging.DEBUG, "Registered SQL Server-specific type adapters.")

    def get_default_adapter_suggestions(self) -> Dict[Type, Tuple[Any, Type]]:
        return super().get_default_adapter_suggestions()

    def connect(self) -> None:
        """Establish connection to SQL Server database.
        
        Connects to the database using the configured connection parameters.
        Supports both Windows Authentication (trusted_connection) and
        SQL Server Authentication.
        
        Raises:
            ConnectionError: If connection fails
        """
        try:
            conn_str = self.config.build_connection_string()
            
            self.log(
                logging.INFO,
                f"Connecting to SQL Server: {self.config.host}:{self.config.port}/{self.config.database}"
            )
            
            conn_args = {
                'autocommit': self.config.autocommit,
                'timeout': self.config.timeout,
            }
            
            self._connection = pyodbc.connect(conn_str, **conn_args)
            
            self.log(logging.INFO, "Connected to SQL Server database successfully")
            self.introspect_and_adapt()
            
        except PyODBCError as e:
            self.log(logging.ERROR, f"Failed to connect to SQL Server: {str(e)}")
            raise ConnectionError(f"Failed to connect to SQL Server: {str(e)}") from e
    
    def disconnect(self) -> None:
        """Close connection to SQL Server database.
        
        Safely closes the database connection, rolling back any
        active transaction first.
        """
        if self._connection:
            try:
                if self.transaction_manager.is_active:
                    self.transaction_manager.rollback()
                
                self._connection.close()
                self._connection = None
                self.log(logging.INFO, "Disconnected from SQL Server database")
                
            except PyODBCError as e:
                self.log(logging.WARNING, f"Error during disconnect: {str(e)}")
                self._connection = None
    
    def _get_cursor(self):
        """Get a database cursor, ensuring connection is active.
        
        This method implements automatic connection health checking:
        - Checks if connection object exists
        - Verifies connection with a lightweight query
        - Automatically reconnects if connection was lost
        
        Returns:
            Database cursor object
        """
        if not self._connection:
            self.log(logging.DEBUG, "No connection, connecting...")
            self.connect()
        
        try:
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
        except (PyODBCError, InterfaceError) as e:
            self.log(logging.DEBUG, f"Connection lost, reconnecting: {str(e)}")
            self.disconnect()
            self.connect()
        
        return self._connection.cursor()
    
    def execute(
        self,
        sql: str,
        params: Optional[Tuple] = None,
        *,
        options=None,
        **kwargs
    ) -> QueryResult:
        """Execute a SQL statement with optional parameters.
        
        Args:
            sql: SQL statement to execute
            params: Optional parameters for the SQL statement
            options: Execution options (ExecutionOptions)
            **kwargs: Additional keyword arguments
        
        Returns:
            QueryResult containing the query results
        
        Raises:
            IntegrityError: For constraint violations
            DeadlockError: For deadlock situations
            OperationalError: For connection/timeout errors
            DatabaseError: For other database errors
        """
        from rhosocial.activerecord.backend.options import ExecutionOptions, StatementType

        sql_upper = sql.strip().upper()

        if options is None:
            if sql_upper.startswith(("SELECT", "WITH", "EXEC", "EXECUTE")):
                stmt_type = StatementType.DQL
            elif sql_upper.startswith(("INSERT", "UPDATE", "DELETE", "MERGE")):
                stmt_type = StatementType.DML
            else:
                stmt_type = StatementType.DDL

            column_mapping = kwargs.get("column_mapping")
            column_adapters = kwargs.get("column_adapters")

            options = ExecutionOptions(
                stmt_type=stmt_type,
                column_adapters=column_adapters,
                column_mapping=column_mapping,
            )
        else:
            if "column_mapping" in kwargs:
                options.column_mapping = kwargs["column_mapping"]
            if "column_adapters" in kwargs:
                options.column_adapters = kwargs["column_adapters"]

        explain_split = self._split_explain_statement(sql)
        if explain_split is not None:
            set_clause, statement = explain_split
            cursor = self._get_cursor()
            cursor.execute(f"SET {set_clause} ON")
            cursor.close()
            try:
                return super().execute(statement, params, options=options)
            finally:
                cursor = self._get_cursor()
                cursor.execute(f"SET {set_clause} OFF")
                cursor.close()

        identity_table = self._identity_insert_info(sql, params)
        if identity_table is not None:
            self.set_identity_insert(identity_table, True)
        try:
            result = super().execute(sql, params, options=options)
        finally:
            if identity_table is not None:
                self.set_identity_insert(identity_table, False)

        if options.stmt_type == StatementType.DML and sql_upper.startswith("INSERT"):
            scope_id = self.get_scope_identity()
            if scope_id is not None:
                result.last_insert_id = scope_id

        return result

    def execute_many(self, sql: str, params_list: List[Tuple]) -> QueryResult:
        """Execute the same SQL statement multiple times with different parameters.
        
        Args:
            sql: SQL statement to execute
            params_list: List of parameter tuples
        
        Returns:
            QueryResult with affected_rows populated
        """
        if not self._connection:
            self.connect()

        cursor = None
        start_time = time.perf_counter()

        try:
            cursor = self._get_cursor()

            self.log(logging.DEBUG, f"Executing batch operation: {sql}")
            self.log(logging.DEBUG, f"With {len(params_list)} parameter sets")

            if not params_list:
                self.log(logging.DEBUG, "Empty parameter list, returning zero affected rows")
                return QueryResult(affected_rows=0, data=None, duration=0.0)

            cursor.executemany(sql, params_list)
            
            duration = time.perf_counter() - start_time
            affected_rows = cursor.rowcount
            
            self._handle_auto_commit_if_needed()
            
            self.log(logging.INFO, f"Batch operation completed, affected {affected_rows} rows")
            
            return QueryResult(affected_rows=affected_rows, data=None, duration=duration)
            
        except PyODBCError as e:
            self.log(logging.ERROR, f"Error in batch operation: {str(e)}")
            self._handle_error(e)
            
        finally:
            if cursor:
                cursor.close()
    
    def get_server_version(self) -> Tuple[int, int, int]:
        """Get SQL Server server version.
        
        Queries the server for its product version and parses it
        into a tuple of (major, minor, patch).
        
        Returns:
            Tuple of (major, minor, patch) version numbers
        """
        if not self._connection:
            self.connect()
        
        cursor = None
        try:
            cursor = self._get_cursor()
            cursor.execute("SELECT SERVERPROPERTY('ProductVersion')")
            version_str = cursor.fetchone()[0]
            
            parts = version_str.split('.')
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0
            
            version = (major, minor, patch)
            self.log(logging.INFO, f"SQL Server version: {major}.{minor}.{patch}")
            return version
            
        except Exception as e:
            self.log(logging.WARNING, f"Could not determine SQL Server version: {str(e)}")
            return self._version
            
        finally:
            if cursor:
                cursor.close()
    
    def ping(self, reconnect: bool = True) -> bool:
        """Ping the SQL Server to check if the connection is alive.
        
        Args:
            reconnect: If True, attempt to reconnect if the connection is dead
        
        Returns:
            True if connection is alive (or was successfully reconnected)
        """
        try:
            if not self._connection:
                if reconnect:
                    self.connect()
                    return True
                return False
            
            cursor = self._get_cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            return True
            
        except PyODBCError as e:
            self.log(logging.WARNING, f"Ping failed: {str(e)}")
            if reconnect:
                try:
                    self.disconnect()
                    self.connect()
                    return True
                except Exception as connect_error:
                    self.log(logging.ERROR, f"Reconnect failed: {str(connect_error)}")
                    return False
            return False
    
    def introspect_and_adapt(self) -> None:
        """Introspect backend and adapt to actual server capabilities.
        
        Queries the server for its version and updates the dialect
        to match the actual server capabilities.
        """
        if not self._connection:
            self.connect()
        
        actual_version = self.get_server_version()
        if self._version != actual_version:
            self._version = actual_version
            self._dialect = SQLServerUnicodeDialect(actual_version)
            self.log(logging.INFO, f"Adapted to SQL Server version {actual_version}")
    
    def executescript(self, sql_script: str) -> None:
        """Execute a multi-statement SQL script.
        
        SQL Server scripts use GO as batch separator. This method
        splits the script on GO and executes each batch.
        
        Args:
            sql_script: SQL script with GO separators
        """
        self.log(logging.INFO, "Executing SQL script")
        start_time = time.perf_counter()
        
        if not self._connection:
            self.connect()
        
        try:
            batches = sql_script.split('GO')
            
            for batch in batches:
                batch = batch.strip()
                if batch:
                    cursor = self._connection.cursor()
                    cursor.execute(batch)
                    cursor.close()
            
            self._handle_auto_commit_if_needed()
            duration = time.perf_counter() - start_time
            self.log(logging.INFO, f"SQL script executed successfully, duration={duration:.3f}s")
            
        except PyODBCError as e:
            self.log(logging.ERROR, f"Error executing SQL script: {str(e)}")
            self._handle_error(e)
    
    def _handle_error(self, error: Exception) -> None:
        """Handle SQL Server-specific errors and convert to appropriate exceptions.
        
        Converts pyodbc exceptions to the appropriate backend exceptions.
        
        Args:
            error: The exception to handle
        
        Raises:
            IntegrityError: For constraint violations
            DeadlockError: For deadlock situations
            OperationalError: For connection/timeout errors
            DatabaseError: For other database errors
        """
        error_msg = str(error).lower()
        
        if isinstance(error, pyodbc.IntegrityError):
            if "duplicate" in error_msg or "unique" in error_msg:
                self.log(logging.ERROR, f"Unique constraint violation: {str(error)}")
                raise IntegrityError(f"Unique constraint violation: {str(error)}")
            elif "foreign key" in error_msg or "reference" in error_msg:
                self.log(logging.ERROR, f"Foreign key constraint violation: {str(error)}")
                raise IntegrityError(f"Foreign key constraint violation: {str(error)}")
            self.log(logging.ERROR, f"Integrity error: {str(error)}")
            raise IntegrityError(self._normalize_integrity_message(str(error)))
        
        elif isinstance(error, pyodbc.DatabaseError):
            if hasattr(error, 'args') and len(error.args) > 0:
                error_code = error.args[0]
                if error_code == 1205:
                    self.log(logging.ERROR, f"Deadlock detected: {str(error)}")
                    raise DeadlockError(str(error))
            
            self.log(logging.ERROR, f"Database error: {str(error)}")
            raise DatabaseError(str(error))
        
        elif isinstance(error, pyodbc.OperationalError):
            self.log(logging.ERROR, f"Operational error: {str(error)}")
            raise OperationalError(str(error))
        
        elif isinstance(error, PyODBCError):
            self.log(logging.ERROR, f"SQL Server error: {str(error)}")
            raise DatabaseError(str(error))
        
        else:
            self.log(logging.ERROR, f"Unexpected error: {str(error)}")
            raise error
    
    def _handle_auto_commit_if_needed(self) -> None:
        """Handle auto-commit for SQL Server.
        
        Commits the current transaction if:
        - Not in an active transaction
        - Autocommit is enabled in configuration
        """
        if not self.in_transaction and self._connection:
            if not self.config.autocommit:
                self._connection.commit()
                self.log(logging.DEBUG, "Auto-committed operation")
    
    def _is_connection_error(self, error: Exception) -> bool:
        """Check if an error indicates a connection loss.
        
        Args:
            error: The exception to check
        
        Returns:
            True if the error indicates a connection problem
        """
        if hasattr(error, 'args') and len(error.args) > 0:
            error_code = error.args[0]
            if error_code in self.CONNECTION_ERROR_CODES:
                return True
        
        error_msg = str(error).lower()
        connection_patterns = [
            'connection', 'timeout', 'cannot connect',
            'network', 'broken', 'closed', 'unavailable'
        ]
        return any(pattern in error_msg for pattern in connection_patterns)
    
    def _create_introspector(self):
        """Create a SQL Server introspector.
        
        Returns:
            SyncSQLServerIntrospector instance
        """
        from .introspection import SyncSQLServerIntrospector
        from rhosocial.activerecord.backend.introspection.executor import SyncIntrospectorExecutor
        return SyncSQLServerIntrospector(self, SyncIntrospectorExecutor(self))
    
    def _parse_explain_result(self, raw_rows, sql, duration):
        """Parse SQL Server EXPLAIN result.
        
        Args:
            raw_rows: Raw result rows
            sql: Original SQL query
            duration: Query duration
        
        Returns:
            SQLServerExplainResult instance
        """
        from .explain import SQLServerExplainResult, SQLServerExplainRow
        rows = [SQLServerExplainRow(**r) for r in raw_rows]
        return SQLServerExplainResult(raw_rows=raw_rows, sql=sql, duration=duration, rows=rows)
