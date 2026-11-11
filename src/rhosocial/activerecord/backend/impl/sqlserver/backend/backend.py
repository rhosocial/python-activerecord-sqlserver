# src/rhosocial/activerecord/backend/impl/sqlserver/backend/backend.py
"""
SQL Server-specific implementation of the StorageBackend.

This module provides the concrete implementation for interacting with SQL Server databases,
handling connections, queries, transactions, and type adaptations tailored for SQL Server's
specific behaviors and SQL dialect.
"""

import logging
import time
from contextvars import ContextVar
from typing import Any, Dict, List, Optional, Tuple, Type

import pyodbc
from pyodbc import Error as PyODBCError, InterfaceError

from rhosocial.activerecord.backend.base import StorageBackend
from rhosocial.activerecord.backend.base.execution_logging import (
    log_batch_start,
    log_batch_summary,
    log_execution_error,
)
from rhosocial.activerecord.backend.errors import (
    ConnectionError,
    DatabaseError,
    TransactionError,
)
from rhosocial.activerecord.backend.options import ExecutionOptions, StatementType
from rhosocial.activerecord.backend.result import QueryResult
from rhosocial.activerecord.logging.redaction import unwrap_sensitive
from rhosocial.activerecord.backend.introspection.backend_mixin import IntrospectorBackendMixin
from rhosocial.activerecord.backend.explain import SyncExplainBackendMixin
from ..config import SQLServerConnectionConfig
from ..dialect import SQLServerDialect
from ..error_mapping import classify_sqlserver_error
from ..transaction import SQLServerTransactionManager
from ..mixins import SQLServerBackendMixin, SQLServerConcurrencyMixin
from ..query_nodes import health_check_sql, server_property_value_sql


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

    # Keep the library logger name stable even though this class lives in the
    # extension package (rhosocial.activerecord.backend.impl.sqlserver).
    _logger_name = "rhosocial.activerecord.backend.sqlserver"

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
            deployment_target: Deployment target label for capability gates
            **kwargs: Additional connection options
        """
        version = kwargs.pop('version', None) or (16, 0, 0)
        deployment_target = kwargs.pop('deployment_target', None)
        
        connection_config = kwargs.get('connection_config')
        
        if connection_config is None:
            config_params = {}
            sqlserver_params = [
                'host', 'port', 'database', 'deployment_target', 'username', 'password',
                'trusted_connection', 'driver', 'encrypt',
                'trust_server_certificate',
                'client_certificate', 'client_key', 'client_key_password',
                'host_name_in_certificate',
                'timeout', 'query_timeout',
                'autocommit', 'charset', 'pool_size', 'pool_timeout',
            ]
            
            for param in sqlserver_params:
                if param in kwargs:
                    config_params[param] = kwargs[param]
            if deployment_target is not None:
                config_params["deployment_target"] = deployment_target
            
            if 'host' not in config_params:
                config_params['host'] = 'localhost'
            if 'port' not in config_params:
                config_params['port'] = 1433
            
            kwargs['connection_config'] = SQLServerConnectionConfig(**config_params)
        
        super().__init__(**kwargs)

        configured_target = getattr(self.config, "deployment_target", None)
        if deployment_target is not None:
            configured_target = deployment_target
        self.deployment_target = (
            configured_target if configured_target is not None else "sqlserver"
        )
        self._version = version
        self._dialect = SQLServerUnicodeDialect(
            version,
            deployment_target=self.deployment_target,
        )
        self._connection = None
        self._transaction_manager = None
        self._default_suggestions_cache = None
        self._execution_noscan: ContextVar[Optional[bool]] = ContextVar(
            "sqlserver_execution_noscan", default=None
        )

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
        from ..adapters import (
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

        import datetime as dt
        import decimal
        import uuid
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
            self.log(logging.DEBUG, f"Failed to connect to SQL Server: {str(e)}")
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
            probe, probe_params = health_check_sql(self.dialect)
            cursor = self._connection.cursor()
            cursor.execute(probe, probe_params)
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
            self._execute_control_sql(f"SET {set_clause} ON")
            try:
                return self._execute_with_options(statement, params, options)
            finally:
                self._execute_control_sql_quietly(f"SET {set_clause} OFF")

        identity_table = self._identity_insert_info(sql, params)
        if identity_table is not None:
            self.set_identity_insert(identity_table, True)
        try:
            result = self._execute_with_options(sql, params, options)
        finally:
            if identity_table is not None:
                self._reset_identity_insert_quietly(identity_table)

        if options.stmt_type == StatementType.DML and sql_upper.startswith("INSERT"):
            scope_id = self.get_scope_identity()
            if scope_id is not None:
                result.last_insert_id = scope_id

        return result

    def _execute_with_options(
        self, sql: str, params: Optional[Tuple], options: ExecutionOptions
    ) -> QueryResult:
        token = self._execution_noscan.set(getattr(options, "noscan", None))
        try:
            return super().execute(sql, params, options=options)
        finally:
            self._execution_noscan.reset(token)

    def _execute_query(self, cursor: Any, sql: str, params: Optional[Tuple]) -> Any:
        noscan = self._execution_noscan.get()
        if noscan is None:
            return super()._execute_query(cursor, sql, params)

        previous = cursor.noscan
        try:
            cursor.noscan = noscan
            return super()._execute_query(cursor, sql, params)
        finally:
            cursor.noscan = previous

    def _reset_identity_insert_quietly(self, table: str) -> None:
        """Turn ``IDENTITY_INSERT`` off without replacing an in-flight failure."""
        try:
            self.set_identity_insert(table, False)
        except Exception as exc:
            self.log(
                logging.WARNING,
                f"Failed to disable IDENTITY_INSERT for {table}: {exc}",
            )

    def execute_many(
        self,
        sql: str,
        params_list: List[Tuple],
        *,
        options: Optional[ExecutionOptions] = None,
    ) -> Optional[QueryResult]:
        """Execute the same SQL statement multiple times with different parameters.

        Args:
            sql: SQL statement to execute
            params_list: List of parameter tuples
            options: ExecutionOptions carrying the logging context

        Returns:
            QueryResult with affected_rows populated
        """
        if options is None:
            options = ExecutionOptions(stmt_type=StatementType.DML)
        params_list = [unwrap_sensitive(params) for params in params_list]
        log_batch_start(self, sql, params_list, options)
        start_time = time.perf_counter()

        cursor = None
        try:
            if not self._connection:
                self.connect()

            cursor = self._get_cursor()

            if not params_list:
                duration = time.perf_counter() - start_time
                log_batch_summary(self, sql, params_list, 0, duration, options)
                return QueryResult(affected_rows=0, data=None, duration=duration)

            cursor.executemany(sql, params_list)

            duration = time.perf_counter() - start_time
            affected_rows = cursor.rowcount

            log_batch_summary(self, sql, params_list, affected_rows, duration, options)
            self._handle_auto_commit_if_needed()

            return QueryResult(affected_rows=affected_rows, data=None, duration=duration)

        except Exception as e:
            log_execution_error(self, e, options)
            if isinstance(e, DatabaseError):
                raise
            self._handle_error(e)
            # ``_handle_error`` must raise; keep a defensive fallback so a
            # handler cannot turn a failure into a ``None`` result.
            raise DatabaseError(str(e)) from e

        finally:
            if cursor:
                self._close_cursor_quietly(cursor)
    
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
            probe, probe_params = server_property_value_sql(
                self.dialect, "ProductVersion"
            )
            cursor = self._get_cursor()
            cursor.execute(probe, probe_params)
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
            
            probe, probe_params = health_check_sql(self.dialect)
            cursor = self._get_cursor()
            cursor.execute(probe, probe_params)
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
                    self.log(logging.WARNING, f"Reconnect failed: {str(connect_error)}")
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
            self._dialect = SQLServerUnicodeDialect(
                actual_version,
                deployment_target=self.deployment_target,
            )
            self.log(logging.INFO, f"Adapted to SQL Server version {actual_version}")
    
    def executescript(self, sql_script: str) -> None:
        """Execute a multi-statement SQL script.
        
        SQL Server scripts use GO as batch separator. This method
        splits the script on GO and executes each batch.
        
        Args:
            sql_script: SQL script with GO separators
        """
        self.log(logging.DEBUG, "Executing SQL script")
        start_time = time.perf_counter()
        
        if not self._connection:
            self.connect()
        
        try:
            batches = sql_script.split('GO')
            
            for batch in batches:
                batch = batch.strip()
                if not batch:
                    continue
                cursor = self._connection.cursor()
                try:
                    cursor.execute(batch)
                finally:
                    self._close_cursor_quietly(cursor)
            
            self._handle_auto_commit_if_needed()
            duration = time.perf_counter() - start_time
            self.log(logging.INFO, f"SQL script executed successfully, duration={duration:.3f}s")
            
        except Exception as e:
            self.log(logging.DEBUG, f"Error executing SQL script: {str(e)}")
            if isinstance(e, DatabaseError):
                raise
            self._handle_error(e)
            raise DatabaseError(str(e)) from e
    
    def _handle_error(self, error: Exception) -> None:
        """Handle SQL Server-specific errors and convert to appropriate exceptions.

        Recognition follows the phase 3b order: native error number first,
        then class, then message text. The mapped error carries diagnostics
        (driver code, backend, transient hint) before it is raised.

        Args:
            error: The exception to handle

        Raises:
            IntegrityError: For unique, foreign key and NOT NULL violations
            DeadlockError: For deadlock situations (error 1205)
            LockError: For lock-wait timeouts (error 1222)
            QueryError: For syntax errors and unknown objects
            ConnectionError: For login/connect failures
            OperationalError: For network and timeout failures
            DatabaseError: For other database errors
        """
        # A framework error already carries its phase semantics; re-mapping it
        # would replace the original type with a generic driver error.
        if isinstance(error, DatabaseError):
            raise error
        mapped = classify_sqlserver_error(error)
        self._log_classified_error(error, mapped)
        raise mapped from error
    
    def _handle_auto_commit_if_needed(self) -> None:
        """Handle auto-commit for SQL Server.
        
        Commits the current transaction if:
        - Not in an active transaction
        - Autocommit is enabled in configuration
        """
        if not self.in_transaction and self._connection:
            if not self.config.autocommit:
                self._handle_auto_commit()

    def _handle_auto_commit(self) -> None:
        """Commit outside a transaction, surfacing a failure as a transaction error."""
        if self._connection is None or self.config.autocommit:
            return
        try:
            self._connection.commit()
        except Exception as exc:
            raise TransactionError("Auto-commit failed") from exc
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
            SQLServerIntrospector instance
        """
        from ..introspection import SQLServerIntrospector
        from rhosocial.activerecord.backend.introspection.executor import IntrospectorExecutor
        return SQLServerIntrospector(self, IntrospectorExecutor(self))
    
    def _parse_explain_result(self, raw_rows, sql, duration):
        """Parse SQL Server EXPLAIN result.
        
        Args:
            raw_rows: Raw result rows
            sql: Original SQL query
            duration: Query duration
        
        Returns:
            SQLServerExplainResult instance
        """
        from ..explain import SQLServerExplainResult, SQLServerExplainRow
        rows = [SQLServerExplainRow(**r) for r in raw_rows]
        return SQLServerExplainResult(raw_rows=raw_rows, sql=sql, duration=duration, rows=rows)
