# src/rhosocial/activerecord/backend/impl/sqlserver/mixins.py
"""
SQL Server-specific backend mixins.

This module provides mixin classes for SQL Server-specific functionality
that extends the base backend capabilities.
"""

import logging
from typing import Any, Dict, Optional, Tuple, Type

from .dialect import SQLServerDialect


class SQLServerBackendMixin:
    """SQL Server-specific backend methods."""
    
    _dialect: SQLServerDialect
    _connection: Optional[object]
    
    def set_nocount(self, on: bool = True) -> None:
        """
        Set NOCOUNT option to suppress row count messages.
        
        This improves performance by preventing SQL Server from sending
        DONE_IN_PROC messages for each statement.
        
        Args:
            on: True to enable NOCOUNT (suppress count), False to disable
        
        Example:
            >>> backend.set_nocount(True)  # Enable NOCOUNT
        """
        state = "ON" if on else "OFF"
        cursor = self._get_cursor()
        cursor.execute(f"SET NOCOUNT {state}")
        cursor.close()
    
    def set_identity_insert(self, table: str, on: bool = True) -> None:
        """
        Enable or disable IDENTITY_INSERT for a table.
        
        This allows explicit values to be inserted into IDENTITY columns.
        Only one table can have IDENTITY_INSERT enabled at a time.
        
        Args:
            table: Table name
            on: True to enable IDENTITY_INSERT, False to disable
        
        Example:
            >>> backend.set_identity_insert("users", True)
            >>> backend.execute("INSERT INTO users (id, name) VALUES (?, ?)", (100, "John"))
            >>> backend.set_identity_insert("users", False)
        """
        state = "ON" if on else "OFF"
        sql = f"SET IDENTITY_INSERT {self.dialect.format_identifier(table)} {state}"
        cursor = self._get_cursor()
        cursor.execute(sql)
        cursor.close()
    
    def get_scope_identity(self) -> Optional[int]:
        """
        Get the last inserted identity value for the current scope.
        
        SCOPE_IDENTITY() returns the last identity value generated
        in the current scope (stored procedure, trigger, function, batch).
        
        Returns:
            The last identity value, or None if no insert occurred
        
        Example:
            >>> backend.execute("INSERT INTO users (name) VALUES (?)", ("John",))
            >>> identity = backend.get_scope_identity()
        """
        cursor = self._get_cursor()
        cursor.execute("SELECT SCOPE_IDENTITY()")
        row = cursor.fetchone()
        cursor.close()
        if row and row[0] is not None:
            return int(row[0])
        return None
    
    def get_identity_current(self, table: str) -> Optional[int]:
        """
        Get the current identity value for a table.
        
        IDENT_CURRENT() returns the last identity value generated
        for the specified table in any session and any scope.
        
        Args:
            table: Table name
        
        Returns:
            Current identity value
        
        Example:
            >>> current = backend.get_identity_current("users")
        """
        cursor = self._get_cursor()
        cursor.execute(f"SELECT IDENT_CURRENT('{table}')")
        row = cursor.fetchone()
        cursor.close()
        if row and row[0] is not None:
            return int(row[0])
        return None
    
    def reset_identity(self, table: str, seed: int = 1) -> None:
        """
        Reset the identity seed for a table.
        
        Args:
            table: Table name
            seed: New seed value (default: 1)
        
        Example:
            >>> backend.reset_identity("users", 1)
        """
        cursor = self._get_cursor()
        cursor.execute(f"DBCC CHECKIDENT('{table}', RESEED, {seed})")
        cursor.close()
    
    def set_lock_timeout(self, timeout_ms: int) -> None:
        """
        Set the lock timeout for the current session.
        
        Args:
            timeout_ms: Lock timeout in milliseconds.
                       -1 = wait indefinitely (default)
                        0 = no wait (return immediately if lock not available)
        
        Example:
            >>> backend.set_lock_timeout(5000)  # 5 seconds
        """
        cursor = self._get_cursor()
        cursor.execute(f"SET LOCK_TIMEOUT {timeout_ms}")
        cursor.close()
    
    def set_deadlock_priority(self, priority) -> None:
        """
        Set the deadlock priority for the current session.
        
        Args:
            priority: "LOW", "NORMAL", "HIGH", or integer -10 to 10
                     (lower values are more likely to be chosen as victim)
        
        Example:
            >>> backend.set_deadlock_priority("LOW")
            >>> backend.set_deadlock_priority(-5)
        """
        if isinstance(priority, int):
            sql = f"SET DEADLOCK_PRIORITY {priority}"
        else:
            sql = f"SET DEADLOCK_PRIORITY {priority.upper()}"
        
        cursor = self._get_cursor()
        cursor.execute(sql)
        cursor.close()
    
    def set_ansi_nulls(self, on: bool = True) -> None:
        """
        Set ANSI_NULLS option for NULL comparisons.
        
        Args:
            on: True for ANSI behavior (NULL comparisons return UNKNOWN),
                False for non-ANSI behavior (NULL = NULL is TRUE)
        
        Example:
            >>> backend.set_ansi_nulls(True)
        """
        state = "ON" if on else "OFF"
        cursor = self._get_cursor()
        cursor.execute(f"SET ANSI_NULLS {state}")
        cursor.close()
    
    def set_quoted_identifier(self, on: bool = True) -> None:
        """
        Set QUOTED_IDENTIFIER option.
        
        Args:
            on: True to use double quotes for identifiers,
                False to use double quotes for strings
        """
        state = "ON" if on else "OFF"
        cursor = self._get_cursor()
        cursor.execute(f"SET QUOTED_IDENTIFIER {state}")
        cursor.close()
    
    def set_ansi_padding(self, on: bool = True) -> None:
        """
        Set ANSI_PADDING option.
        
        Controls how trailing spaces and zeros are stored.
        
        Args:
            on: True for ANSI padding behavior
        """
        state = "ON" if on else "OFF"
        cursor = self._get_cursor()
        cursor.execute(f"SET ANSI_PADDING {state}")
        cursor.close()
    
    def set_textsize(self, size: int) -> None:
        """
        Set TEXTSIZE option for text/image data.
        
        Args:
            size: Maximum size in bytes (0 = unlimited)
        """
        cursor = self._get_cursor()
        cursor.execute(f"SET TEXTSIZE {size}")
        cursor.close()
    
    def set_language(self, language: str) -> None:
        """
        Set the language for the session.
        
        This affects date format and system messages.
        
        Args:
            language: Language name (e.g., 'us_english', 'British')
        """
        cursor = self._get_cursor()
        cursor.execute(f"SET LANGUAGE {language}")
        cursor.close()
    
    def set_dateformat(self, format: str) -> None:
        """
        Set the date format for the session.
        
        Args:
            format: Date format: 'mdy', 'dmy', 'ymd', 'ydm', 'myd', 'dym'
        """
        cursor = self._get_cursor()
        cursor.execute(f"SET DATEFORMAT {format}")
        cursor.close()
    
    def get_product_version(self) -> str:
        """
        Get the SQL Server product version string.
        
        Returns:
            Version string (e.g., "16.0.1000.6")
        """
        cursor = self._get_cursor()
        cursor.execute("SELECT SERVERPROPERTY('ProductVersion')")
        row = cursor.fetchone()
        cursor.close()
        return row[0] if row else ""
    
    def get_product_level(self) -> str:
        """
        Get the SQL Server product level (service pack).
        
        Returns:
            Product level (e.g., "RTM", "SP1", "SP2")
        """
        cursor = self._get_cursor()
        cursor.execute("SELECT SERVERPROPERTY('ProductLevel')")
        row = cursor.fetchone()
        cursor.close()
        return row[0] if row else ""
    
    def get_edition(self) -> str:
        """
        Get the SQL Server edition.
        
        Returns:
            Edition string (e.g., "Enterprise Edition")
        """
        cursor = self._get_cursor()
        cursor.execute("SELECT SERVERPROPERTY('Edition')")
        row = cursor.fetchone()
        cursor.close()
        return row[0] if row else ""
    
    def get_machine_name(self) -> str:
        """
        Get the SQL Server machine name.
        
        Returns:
            Server machine name
        """
        cursor = self._get_cursor()
        cursor.execute("SELECT SERVERPROPERTY('MachineName')")
        row = cursor.fetchone()
        cursor.close()
        return row[0] if row else ""
    
    def get_server_name(self) -> str:
        """
        Get the SQL Server instance name.
        
        Returns:
            Server instance name
        """
        cursor = self._get_cursor()
        cursor.execute("SELECT SERVERPROPERTY('ServerName')")
        row = cursor.fetchone()
        cursor.close()
        return row[0] if row else ""
    
    def is_case_sensitive(self) -> bool:
        """
        Check if the server is case-sensitive.
        
        Returns:
            True if server collation is case-sensitive
        """
        cursor = self._get_cursor()
        cursor.execute("SELECT SERVERPROPERTY('Collation')")
        row = cursor.fetchone()
        cursor.close()
        if row and row[0]:
            collation = str(row[0]).upper()
            return "_CS" in collation or collation.endswith("_CS_AS")
        return False
    
    def log(self, level: int, message: str) -> None:
        """Log a message with the specified level."""
        if hasattr(self, '_logger') and self._logger:
            self._logger.log(level, message)

    def get_default_adapter_suggestions(self) -> Dict[Type, Tuple[Any, Type]]:
        """Provides default type adapter suggestions for SQL Server."""
        if hasattr(self, '_default_suggestions_cache') and self._default_suggestions_cache is not None:
            return self._default_suggestions_cache

        from datetime import date, datetime, time
        from decimal import Decimal
        from uuid import UUID

        suggestions = {}
        type_mappings = [
            (bool, bool),
            (int, int),
            (float, float),
            (str, str),
            (bytes, bytes),
            (datetime, datetime),
            (date, date),
            (time, time),
            (Decimal, Decimal),
            (UUID, str),
            (dict, str),
            (list, str),
        ]

        for py_type, db_type in type_mappings:
            adapter = self.adapter_registry.get_adapter(py_type, db_type)
            if adapter:
                suggestions[py_type] = (adapter, db_type)

        self._default_suggestions_cache = suggestions
        return suggestions

    def _build_query_result(self, cursor, data, duration: float):
        from rhosocial.activerecord.backend.result import QueryResult

        if data is not None:
            affected_rows = len(data) if data else 0
        else:
            affected_rows = cursor.rowcount
        last_insert_id = getattr(cursor, "lastrowid", None)

        return QueryResult(data=data, affected_rows=affected_rows, last_insert_id=last_insert_id, duration=duration)
