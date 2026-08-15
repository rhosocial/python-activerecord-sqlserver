# src/rhosocial/activerecord/backend/impl/sqlserver/async_backend.py
"""
SQL Server asynchronous backend implementation.

This module provides async connectivity to SQL Server databases
using aioodbc as the async driver wrapper.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from rhosocial.activerecord.backend.base import AsyncStorageBackend
from rhosocial.activerecord.backend.base.operations import AsyncSQLOperationsMixin
from rhosocial.activerecord.backend.base.transaction_management import AsyncTransactionManagementMixin
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
from .config import SQLServerConnectionConfig
from .dialect import SQLServerDialect
from .async_transaction import AsyncSQLServerTransactionManager
from .backend import SQLServerUnicodeDialect
from .mixins import SQLServerBackendMixin

try:
    import aioodbc
except ImportError:
    aioodbc = None


class AsyncSQLServerBackend(
    IntrospectorBackendMixin,
    SQLServerBackendMixin,
    AsyncStorageBackend
):
    """Asynchronous SQL Server backend using aioodbc.
    
    This backend provides async connectivity to Microsoft SQL Server
    databases using the aioodbc driver. It supports:
    
    - Async connection management with automatic reconnection
    - Async transaction management with savepoint support
    - OUTPUT clause for returning modified data
    - SQL Server-specific data types
    - Async error handling and conversion
    
    Example:
        >>> backend = AsyncSQLServerBackend(
        ...     host="localhost",
        ...     database="mydb",
        ...     trusted_connection=True
        ... )
        >>> await backend.connect()
        >>> result = await backend.execute("SELECT * FROM users WHERE id = ?", (1,))
        >>> print(result.data)
        >>> await backend.disconnect()
    """
    
    CONNECTION_ERROR_CODES = {
        53, 64, 232, 233, 18456, 4060, 40197, 40501, 40613, 11001,
    }
    
    def __init__(self, **kwargs):
        """Initialize async SQL Server backend.
        
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
        """
        if aioodbc is None:
            raise ImportError(
                "aioodbc is required for async SQL Server support. "
                "Install it with: pip install aioodbc"
            )
        
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

        self.log(logging.INFO, f"AsyncSQLServerBackend initialized (version {version})")
    
    @property
    def dialect(self) -> SQLServerDialect:
        """Get the SQL Server dialect instance."""
        return self._dialect
    
    def _register_sqlserver_adapters(self) -> None:
        """Register SQL Server-specific type adapters (async mirror)."""
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

        self.log(logging.DEBUG, "Registered SQL Server-specific type adapters (async).")
    
    @property
    def transaction_manager(self) -> "AsyncSQLServerTransactionManager":
        """Get the async transaction manager."""
        if not self._transaction_manager:
            self._transaction_manager = AsyncSQLServerTransactionManager(self, self.logger)
        return self._transaction_manager
    
    async def connect(self) -> None:
        """Establish async connection to SQL Server database.
        
        Raises:
            ConnectionError: If connection fails
        """
        try:
            conn_str = self.config.build_connection_string()
            
            self.log(
                logging.INFO,
                f"Connecting to SQL Server (async): {self.config.host}:{self.config.port}/{self.config.database}"
            )
            
            self._connection = await aioodbc.connect(
                dsn=conn_str,
                autocommit=self.config.autocommit,
                timeout=self.config.timeout
            )
            
            self.log(logging.INFO, "Async connection to SQL Server established")
            await self.introspect_and_adapt()
            
        except Exception as e:
            self.log(logging.ERROR, f"Failed to connect to SQL Server: {str(e)}")
            raise ConnectionError(f"Failed to connect to SQL Server: {str(e)}") from e
    
    async def disconnect(self) -> None:
        """Close async connection to SQL Server database."""
        if self._connection:
            try:
                if self.transaction_manager.is_active:
                    await self.transaction_manager.rollback()
                
                await self._connection.close()
                self._connection = None
                self.log(logging.INFO, "Async connection to SQL Server closed")
                
            except Exception as e:
                self.log(logging.WARNING, f"Error during disconnect: {str(e)}")
                self._connection = None
    
    async def _get_cursor(self):
        """Get an async database cursor.
        
        Returns:
            Async database cursor object
        """
        if not self._connection:
            self.log(logging.DEBUG, "No connection, connecting...")
            await self.connect()
        
        return await self._connection.cursor()

    async def _get_scope_identity_async(self) -> Optional[int]:
        """Get the identity value of the last INSERT via @@IDENTITY."""
        async with await self._get_cursor() as cursor:
            await cursor.execute("SELECT @@IDENTITY")
            row = await cursor.fetchone()
        if row and row[0] is not None:
            return int(row[0])
        return None

    async def set_identity_insert(self, table: str, on: bool = True) -> None:
        """Enable or disable IDENTITY_INSERT for a table (async)."""
        state = "ON" if on else "OFF"
        sql = f"SET IDENTITY_INSERT {self.dialect.format_identifier(table)} {state}"
        async with await self._get_cursor() as cursor:
            await cursor.execute(sql)

    async def _get_identity_columns_async(self, table_name: str) -> Set[str]:
        """Return the set of identity column names for a table (async, cached)."""
        cache_key = table_name.lower()
        if cache_key in self._identity_columns_cache:
            return self._identity_columns_cache[cache_key]
        columns: Set[str] = set()
        try:
            async with await self._get_cursor() as cursor:
                await cursor.execute(
                    "SELECT c.name FROM sys.identity_columns c "
                    "JOIN sys.tables t ON c.object_id = t.object_id "
                    "WHERE t.name = ? AND SCHEMA_NAME(t.schema_id) = 'dbo'",
                    (table_name,),
                )
                for row in await cursor.fetchall():
                    columns.add(str(row[0]).lower())
        except Exception:
            columns = set()
        self._identity_columns_cache[cache_key] = columns
        return columns
    
    async def execute(
        self,
        sql: str,
        params: Optional[Tuple] = None,
        *,
        options=None,
        **kwargs
    ) -> QueryResult:
        """Execute a SQL statement asynchronously.
        
        Args:
            sql: SQL statement to execute
            params: Optional parameters for the SQL statement
            options: Execution options (ExecutionOptions)
            **kwargs: Additional keyword arguments
        
        Returns:
            QueryResult containing the query results
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
            async with await self._get_cursor() as cursor:
                await cursor.execute(f"SET {set_clause} ON")
            try:
                return await self._execute_statement(statement, params, options)
            finally:
                async with await self._get_cursor() as cursor:
                    await cursor.execute(f"SET {set_clause} OFF")
        
        return await self._execute_statement(sql, params, options)
    
    async def _execute_statement(
        self, sql: str, params: Optional[Tuple], options, start_time: Optional[float] = None
    ) -> QueryResult:
        from rhosocial.activerecord.backend.options import StatementType

        sql_upper = sql.strip().upper()
        
        if not self._connection:
            await self.connect()
        
        if start_time is None:
            start_time = time.perf_counter()
        
        try:
            # Prepare parameters using adapter suggestions
            all_suggestions = self.get_default_adapter_suggestions()
            prepared_params = params
            if params:
                param_adapters = []
                for param_value in params:
                    py_type = type(param_value)
                    suggestion = all_suggestions.get(py_type)
                    param_adapters.append(suggestion)
                prepared_params = self.prepare_parameters(params, param_adapters)
            
            async with await self._get_cursor() as cursor:
                final_sql, final_params = self._prepare_sql_and_params(sql, prepared_params)
                identity_columns = None
                table_name = self._insert_table_name(final_sql)
                if table_name is not None:
                    identity_columns = await self._get_identity_columns_async(table_name)
                identity_table = self._identity_insert_info(
                    final_sql, final_params, identity_columns
                )
                if identity_table is not None:
                    await self.set_identity_insert(identity_table, True)
                try:
                    await cursor.execute(final_sql, final_params or ())
                finally:
                    if identity_table is not None:
                        await self.set_identity_insert(identity_table, False)
                
                is_select = options.process_result_set if options.process_result_set is not None else options.stmt_type == StatementType.DQL
                data = None
                if is_select and cursor.description:
                    rows = await cursor.fetchall()
                    column_names = [desc[0].strip('"') for desc in cursor.description]
                    adapters = options.column_adapters or {}
                    mapping = options.column_mapping or {}
                    data = []
                    for row in rows:
                        row_dict = dict(zip(column_names, row))
                        adapted_row = self._adapt_row_types(row_dict, adapters)
                        final_row = self._remap_row_columns(adapted_row, mapping)
                        data.append(final_row)
                elif cursor.description:
                    # Also process result when cursor has data (e.g. OUTPUT clause)
                    try:
                        rows = await cursor.fetchall()
                        column_names = [desc[0].strip('"') for desc in cursor.description]
                        adapters = options.column_adapters or {}
                        mapping = options.column_mapping or {}
                        data = []
                        for row in rows:
                            row_dict = dict(zip(column_names, row))
                            adapted_row = self._adapt_row_types(row_dict, adapters)
                            final_row = self._remap_row_columns(adapted_row, mapping)
                            data.append(final_row)
                    except Exception:
                        data = None
                
                duration = time.perf_counter() - start_time
                
                await self._handle_auto_commit_if_needed()
                
                self.log(
                    logging.DEBUG,
                    f"Query executed in {duration:.3f}s, affected {cursor.rowcount} rows"
                )
                
                result = self._build_query_result(cursor, data, duration)

                if options.stmt_type == StatementType.DML and sql_upper.startswith("INSERT"):
                    scope_id = await self._get_scope_identity_async()
                    if scope_id is not None:
                        result.last_insert_id = scope_id

                return result
                
        except Exception as e:
            self.log(logging.ERROR, f"Error executing query: {str(e)}")
            await self._handle_error(e)
    
    async def execute_many(self, sql: str, params_list: List[Tuple]) -> QueryResult:
        """Execute the same SQL statement multiple times asynchronously.
        
        Args:
            sql: SQL statement to execute
            params_list: List of parameter tuples
        
        Returns:
            QueryResult with affected_rows populated
        """
        if not self._connection:
            await self.connect()

        start_time = time.perf_counter()

        try:
            if not params_list:
                self.log(logging.DEBUG, "Empty parameter list, returning zero affected rows")
                return QueryResult(affected_rows=0, data=None, duration=0.0)

            async with await self._get_cursor() as cursor:
                await cursor.executemany(sql, params_list)
                
                duration = time.perf_counter() - start_time
                affected_rows = cursor.rowcount
                
                await self._handle_auto_commit_if_needed()
                
                self.log(logging.INFO, f"Batch operation completed, affected {affected_rows} rows")
                
                return QueryResult(affected_rows=affected_rows, data=None, duration=duration)
                
        except Exception as e:
            self.log(logging.ERROR, f"Error in batch operation: {str(e)}")
            await self._handle_error(e)
    
    async def get_server_version(self) -> Tuple[int, int, int]:
        """Get SQL Server server version.
        
        Returns:
            Tuple of (major, minor, patch) version numbers
        """
        if not self._connection:
            await self.connect()
        
        try:
            async with await self._get_cursor() as cursor:
                await cursor.execute("SELECT SERVERPROPERTY('ProductVersion')")
                row = await cursor.fetchone()
                
                if row:
                    version_str = row[0]
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
    
    async def ping(self, reconnect: bool = True) -> bool:
        """Ping the SQL Server asynchronously.
        
        Args:
            reconnect: If True, attempt to reconnect if connection is dead
        
        Returns:
            True if connection is alive
        """
        try:
            if not self._connection:
                if reconnect:
                    await self.connect()
                    return True
                return False
            
            async with await self._get_cursor() as cursor:
                await cursor.execute("SELECT 1")
                await cursor.fetchone()
            return True
            
        except Exception as e:
            self.log(logging.WARNING, f"Ping failed: {str(e)}")
            if reconnect:
                try:
                    await self.disconnect()
                    await self.connect()
                    return True
                except Exception as connect_error:
                    self.log(logging.ERROR, f"Reconnect failed: {str(connect_error)}")
                    return False
            return False
    
    async def introspect_and_adapt(self) -> None:
        """Introspect backend and adapt to actual server capabilities."""
        if not self._connection:
            await self.connect()
        
        actual_version = await self.get_server_version()
        if self._version != actual_version:
            self._version = actual_version
            self._dialect = SQLServerUnicodeDialect(actual_version)
            self.log(logging.INFO, f"Adapted to SQL Server version {actual_version}")
    
    async def executescript(self, sql_script: str) -> None:
        """Execute a multi-statement SQL script asynchronously.
        
        Args:
            sql_script: SQL script with GO separators
        """
        self.log(logging.INFO, "Executing SQL script (async)")
        start_time = time.perf_counter()
        
        if not self._connection:
            await self.connect()
        
        try:
            batches = sql_script.split('GO')
            
            for batch in batches:
                batch = batch.strip()
                if batch:
                    async with await self._get_cursor() as cursor:
                        await cursor.execute(batch)
            
            await self._handle_auto_commit_if_needed()
            duration = time.perf_counter() - start_time
            self.log(logging.INFO, f"SQL script executed successfully, duration={duration:.3f}s")
            
        except Exception as e:
            self.log(logging.ERROR, f"Error executing SQL script: {str(e)}")
            await self._handle_error(e)
    
    async def _handle_error(self, error: Exception) -> None:
        """Handle SQL Server-specific errors.
        
        Args:
            error: The exception to handle
        
        Raises:
            Appropriate backend exception
        """
        error_msg = str(error).lower()
        
        if (
            'integrity' in error_msg
            or 'constraint' in error_msg
            or 'does not allow nulls' in error_msg
            or 'cannot insert the value null' in error_msg
        ):
            if "duplicate" in error_msg or "unique" in error_msg:
                self.log(logging.ERROR, f"Unique constraint violation: {str(error)}")
                raise IntegrityError(f"Unique constraint violation: {str(error)}")
            elif "foreign key" in error_msg or "reference" in error_msg:
                self.log(logging.ERROR, f"Foreign key constraint violation: {str(error)}")
                raise IntegrityError(f"Foreign key constraint violation: {str(error)}")
            self.log(logging.ERROR, f"Integrity error: {str(error)}")
            raise IntegrityError(self._normalize_integrity_message(str(error)))
        
        if 'deadlock' in error_msg or '1205' in error_msg:
            self.log(logging.ERROR, f"Deadlock detected: {str(error)}")
            raise DeadlockError(str(error))
        
        if 'timeout' in error_msg or 'connection' in error_msg:
            self.log(logging.ERROR, f"Operational error: {str(error)}")
            raise OperationalError(str(error))
        
        self.log(logging.ERROR, f"Database error: {str(error)}")
        raise DatabaseError(str(error))
    
    async def _handle_auto_commit_if_needed(self) -> None:
        """Handle auto-commit for async operations."""
        if not self.in_transaction and self._connection:
            if not self.config.autocommit:
                async with await self._get_cursor() as cursor:
                    await cursor.execute("COMMIT")
                self.log(logging.DEBUG, "Auto-committed operation")
    
    def _create_introspector(self):
        """Create a SQL Server introspector."""
        from .introspection import AsyncSQLServerIntrospector
        from rhosocial.activerecord.backend.introspection.executor import AsyncIntrospectorExecutor
        return AsyncSQLServerIntrospector(self, AsyncIntrospectorExecutor(self))
