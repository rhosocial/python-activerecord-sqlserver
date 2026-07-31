# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/backend_mixin.py
import logging
from typing import Any, Dict, Optional, Tuple, Type

from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter

from ..dialect import SQLServerDialect


class SQLServerBackendMixin:
    _dialect: SQLServerDialect
    _connection: Optional[object]

    def set_nocount(self, on: bool = True) -> None:
        state = "ON" if on else "OFF"
        cursor = self._get_cursor()
        cursor.execute(f"SET NOCOUNT {state}")
        cursor.close()

    def set_identity_insert(self, table: str, on: bool = True) -> None:
        state = "ON" if on else "OFF"
        sql = f"SET IDENTITY_INSERT {self.dialect.format_identifier(table)} {state}"
        cursor = self._get_cursor()
        cursor.execute(sql)
        cursor.close()

    def get_scope_identity(self) -> Optional[int]:
        cursor = self._get_cursor()
        cursor.execute("SELECT @@IDENTITY")
        row = cursor.fetchone()
        cursor.close()
        if row and row[0] is not None:
            return int(row[0])
        return None

    def get_identity_current(self, table: str) -> Optional[int]:
        cursor = self._get_cursor()
        cursor.execute(f"SELECT IDENT_CURRENT('{table}')")
        row = cursor.fetchone()
        cursor.close()
        if row and row[0] is not None:
            return int(row[0])
        return None

    def reset_identity(self, table: str, seed: int = 1) -> None:
        cursor = self._get_cursor()
        cursor.execute(f"DBCC CHECKIDENT('{table}', RESEED, {seed})")
        cursor.close()

    def set_lock_timeout(self, timeout_ms: int) -> None:
        cursor = self._get_cursor()
        cursor.execute(f"SET LOCK_TIMEOUT {timeout_ms}")
        cursor.close()

    def set_deadlock_priority(self, priority) -> None:
        if isinstance(priority, int):
            sql = f"SET DEADLOCK_PRIORITY {priority}"
        else:
            sql = f"SET DEADLOCK_PRIORITY {priority.upper()}"
        cursor = self._get_cursor()
        cursor.execute(sql)
        cursor.close()

    def set_ansi_nulls(self, on: bool = True) -> None:
        state = "ON" if on else "OFF"
        cursor = self._get_cursor()
        cursor.execute(f"SET ANSI_NULLS {state}")
        cursor.close()

    def set_quoted_identifier(self, on: bool = True) -> None:
        state = "ON" if on else "OFF"
        cursor = self._get_cursor()
        cursor.execute(f"SET QUOTED_IDENTIFIER {state}")
        cursor.close()

    def set_ansi_padding(self, on: bool = True) -> None:
        state = "ON" if on else "OFF"
        cursor = self._get_cursor()
        cursor.execute(f"SET ANSI_PADDING {state}")
        cursor.close()

    def set_textsize(self, size: int) -> None:
        cursor = self._get_cursor()
        cursor.execute(f"SET TEXTSIZE {size}")
        cursor.close()

    def set_language(self, language: str) -> None:
        cursor = self._get_cursor()
        cursor.execute(f"SET LANGUAGE {language}")
        cursor.close()

    def set_dateformat(self, format: str) -> None:
        cursor = self._get_cursor()
        cursor.execute(f"SET DATEFORMAT {format}")
        cursor.close()

    def get_product_version(self) -> str:
        cursor = self._get_cursor()
        cursor.execute("SELECT SERVERPROPERTY('ProductVersion')")
        row = cursor.fetchone()
        cursor.close()
        return row[0] if row else ""

    def get_product_level(self) -> str:
        cursor = self._get_cursor()
        cursor.execute("SELECT SERVERPROPERTY('ProductLevel')")
        row = cursor.fetchone()
        cursor.close()
        return row[0] if row else ""

    def get_edition(self) -> str:
        cursor = self._get_cursor()
        cursor.execute("SELECT SERVERPROPERTY('Edition')")
        row = cursor.fetchone()
        cursor.close()
        return row[0] if row else ""

    def get_machine_name(self) -> str:
        cursor = self._get_cursor()
        cursor.execute("SELECT SERVERPROPERTY('MachineName')")
        row = cursor.fetchone()
        cursor.close()
        return row[0] if row else ""

    def get_server_name(self) -> str:
        cursor = self._get_cursor()
        cursor.execute("SELECT SERVERPROPERTY('ServerName')")
        row = cursor.fetchone()
        cursor.close()
        return row[0] if row else ""

    def is_case_sensitive(self) -> bool:
        cursor = self._get_cursor()
        cursor.execute("SELECT SERVERPROPERTY('Collation')")
        row = cursor.fetchone()
        cursor.close()
        if row and row[0]:
            collation = str(row[0]).upper()
            return "_CS" in collation or collation.endswith("_CS_AS")
        return False

    def log(self, level: int, message: str) -> None:
        if hasattr(self, '_logger') and self._logger:
            self._logger.log(level, message)

    def get_default_adapter_suggestions(self) -> Dict[Type, Tuple[Any, Type]]:
        if hasattr(self, '_default_suggestions_cache') and self._default_suggestions_cache is not None:
            return self._default_suggestions_cache

        from datetime import date, datetime, time
        from decimal import Decimal
        from uuid import UUID

        suggestions = {}
        type_mappings = [
            (bool, bool), (int, int), (float, float),
            (str, str), (bytes, bytes),
            (datetime, datetime), (date, date), (time, time),
            (Decimal, Decimal), (UUID, str), (dict, str), (list, str),
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

    @property
    def dialect(self):
        from ..dialect import SQLServerDialect

        if self._dialect is None:
            self._dialect = SQLServerDialect(self._version)
        return self._dialect

    @dialect.setter
    def dialect(self, value):
        self._dialect = value

    @property
    def threadsafety(self) -> int:
        return 2

    def requires_manual_commit(self) -> bool:
        return not getattr(self.config, "autocommit", True)

    CONNECTION_ERROR_CODES = {"08001", "08004", "08S01", "HYT00"}

    def _is_connection_error(self, error: Exception) -> bool:
        if hasattr(error, "args") and error.args:
            code = str(error.args[0])
            if code in self.CONNECTION_ERROR_CODES:
                return True
        error_str = str(error).lower()
        connection_error_patterns = [
            "connection refused",
            "connection reset",
            "broken pipe",
            "communication link failure",
            "named pipes provider",
        ]
        return any(pattern in error_str for pattern in connection_error_patterns)

    def _handle_error(self, error: Exception) -> None:
        from pyodbc import (
            Error as PyODBCError,
            InterfaceError,
            DatabaseError as PyODBCDatabaseError,
        )
        from rhosocial.activerecord.backend.errors import (
            ConnectionError,
            DatabaseError,
            DeadlockError,
            IntegrityError,
            OperationalError,
            QueryError,
        )

        error_msg = str(error)

        if isinstance(error, InterfaceError):
            raise ConnectionError(error_msg) from error
        elif isinstance(error, PyODBCDatabaseError):
            if "deadlock" in error_msg.lower() or "1205" in error_msg:
                raise DeadlockError(error_msg) from error
            if "integrity" in error_msg.lower() or "547" in error_msg or "2627" in error_msg:
                raise IntegrityError(error_msg) from error
            raise DatabaseError(error_msg) from error
        elif isinstance(error, PyODBCError):
            if self._is_connection_error(error):
                raise ConnectionError(error_msg) from error
            raise OperationalError(error_msg) from error
        else:
            raise error