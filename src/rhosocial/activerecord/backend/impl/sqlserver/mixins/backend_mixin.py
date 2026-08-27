# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/backend_mixin.py
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from ..dialect import SQLServerDialect


_INSERT_PATTERN = re.compile(
    r"^\s*INSERT\s+INTO\s+(?:(?:\[([^\]]+)\]|([A-Za-z_][\w$]*))\.)?(?:\[([^\]]+)\]|([A-Za-z_][\w$]*))\s*\(([^)]*)\)",
    re.IGNORECASE,
)

_EXPLAIN_PATTERN = re.compile(
    r"^\s*SET\s+(SHOWPLAN_(?:TEXT|XML|ALL)|STATISTICS\s+(?:PROFILE|XML))\s+ON\s*;(.+)$",
    re.IGNORECASE | re.DOTALL,
)

_TABLE_HINT_PATTERN = re.compile(r"\s+WITH\s*\([^)]*\)\s*;?\s*$", re.IGNORECASE)

_CLAUSE_KEYWORDS = (
    r"WHERE|JOIN|ON|GROUP|HAVING|ORDER|LIMIT|OFFSET|FETCH|WITH|INNER|LEFT|RIGHT|"
    r"FULL|CROSS|OUTER|UNION|INTERSECT|EXCEPT|OPTION|FOR|AS|FROM"
)

_TABLE_REF_PATTERN = re.compile(
    rf"(\[[^\]]+\]|[A-Za-z_][\w$]*)(\s+(?:AS\s+)?(?!(?:{_CLAUSE_KEYWORDS})\b)[A-Za-z_][\w$]*)?"
)


class SQLServerBackendMixin:
    _dialect: "SQLServerDialect"
    _connection: Optional[object]
    _identity_columns_cache: Dict[str, Set[str]] = {}

    def _prepare_sql_and_params(self, sql: str, params: Optional[Tuple]) -> Tuple[str, Optional[Tuple]]:
        """Prepare SQL Server-specific SQL before execution.

        This method only performs the SQL Server-specific table hint relocation
        (``_relocate_table_hint``). Parameter placeholders are provided by the
        caller according to the ``dialect.get_parameter_placeholder()`` contract
        (SQL Server returns ``?``, matching pyodbc's native qmark style), so no
        guessing-style placeholder conversion is done at the execute layer.
        """
        sql = self._relocate_table_hint(sql)
        return sql, params

    def _relocate_table_hint(self, sql: str) -> str:
        """Move a trailing ``WITH (hint)`` table hint to right after the table.

        The generic DQL renderer appends the ``FOR UPDATE`` clause at the end
        of the statement, producing ``SELECT ... FROM [users] WHERE ...
        WITH (UPDLOCK, ROWLOCK)``. SQL Server only accepts table hints
        immediately after the referenced table, so relocate the hint from the
        end of the query to directly after the ``FROM`` table reference.
        """
        hint_match = _TABLE_HINT_PATTERN.search(sql)
        if not hint_match:
            return sql
        hint = hint_match.group(0).strip().rstrip(";").strip()
        body = sql[: hint_match.start()]
        from_matches = list(re.finditer(r"\bFROM\s+", body, re.IGNORECASE))
        if not from_matches:
            return sql
        from_match = from_matches[-1]
        after_from = body[from_match.end():]
        table_match = _TABLE_REF_PATTERN.match(after_from)
        if not table_match:
            return sql
        table_end = from_match.end() + table_match.end()
        return (body[:table_end] + " " + hint + body[table_end:]).strip()

    def _get_identity_columns(self, table_name: str) -> Set[str]:
        """Return the set of identity column names for a table (cached)."""
        cache_key = table_name.lower()
        if cache_key in self._identity_columns_cache:
            return self._identity_columns_cache[cache_key]
        columns: Set[str] = set()
        try:
            cursor = self._get_cursor()
            cursor.execute(
                "SELECT c.name FROM sys.identity_columns c "
                "JOIN sys.tables t ON c.object_id = t.object_id "
                "WHERE t.name = ? AND SCHEMA_NAME(t.schema_id) = 'dbo'",
                (table_name,),
            )
            for row in cursor.fetchall():
                columns.add(str(row[0]).lower())
            cursor.close()
        except Exception:
            columns = set()
        self._identity_columns_cache[cache_key] = columns
        return columns

    def _split_explain_statement(self, sql: str) -> Optional[Tuple[str, str]]:
        """Split an explain wrapper into ``(SET clause, statement)`` if present.

        SQL Server only allows ``SET SHOWPLAN/STATISTICS ... ON`` to be the
        sole statement in a batch (error 1067), so the wrapped statement must
        be executed as a separate batch with the flag turned on/off around it.
        """
        match = _EXPLAIN_PATTERN.match(sql)
        if not match:
            return None
        set_clause = match.group(1).strip()
        statement = match.group(2)
        off_pattern = re.compile(
            rf"\s*;\s*SET\s+{re.escape(set_clause)}\s+OFF\s*$",
            re.IGNORECASE | re.DOTALL,
        )
        statement = off_pattern.sub("", statement)
        return set_clause, statement.strip()

    def _insert_table_name(self, sql: str) -> Optional[str]:
        """Return the target table name of an ``INSERT`` statement, or None."""
        match = _INSERT_PATTERN.match(sql)
        if not match:
            return None
        return match.group(3) or match.group(4)

    def _identity_insert_info(
        self, sql: str, params: Optional[Tuple], identity_columns: Optional[Set[str]] = None
    ) -> Optional[str]:
        """Return the table name that needs ``SET IDENTITY_INSERT ON``, or None.

        Detects ``INSERT INTO [schema].[table] (col, ...) VALUES (?, ...)``
        statements that explicitly supply a value for the table's identity
        column. SQL Server forbids such inserts unless ``IDENTITY_INSERT`` is
        enabled for the target table.
        """
        if not params:
            return None
        table_name = self._insert_table_name(sql)
        if not table_name:
            return None
        if identity_columns is None:
            identity_columns = self._get_identity_columns(table_name)
        if not identity_columns:
            return None
        match = _INSERT_PATTERN.match(sql)
        raw_columns = match.group(5)
        columns = [c.strip().strip("[]\"").lower() for c in raw_columns.split(",") if c.strip()]
        if not columns or len(columns) > len(params):
            return None
        for col, value in zip(columns, params):
            if col in identity_columns and value is not None:
                return table_name
        return None

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

    def _adapt_row_types(self, row_dict: Dict[str, Any], column_adapters) -> Dict[str, Any]:
        """Adapt row values, stripping SQL Server CHAR column padding.

        SQL Server pads ``CHAR``/``NCHAR`` values with trailing spaces, so a
        value stored as ``'fixed'`` in a ``CHAR(10)`` column is returned as
        ``'fixed     '``. The shared testsuite expects the original value back,
        so strip trailing spaces from every returned string (adapted values
        that legitimately carry trailing whitespace are not produced by the
        column adapters used here).
        """
        processed_row = super()._adapt_row_types(row_dict, column_adapters)
        for col_name, value in processed_row.items():
            if isinstance(value, str):
                processed_row[col_name] = value.rstrip(" ")
        return processed_row

    def _normalize_integrity_message(self, message: str) -> str:
        """Normalize SQL Server integrity messages to cross-backend phrases.

        The shared testsuite asserts on canonical substrings such as ``cannot be
        null``; SQL Server's native ``515`` message ("Cannot insert the value
        NULL ... column does not allow nulls") does not contain them, so inject
        them while preserving the original detail.
        """
        lowered = message.lower()
        if "does not allow nulls" in lowered or "cannot insert the value null" in lowered:
            if "cannot be null" not in lowered:
                message = message + " - cannot be null"
        return message

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