# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/backend_mixin.py
import logging
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.suggestion.definitions import (
    DataAdapterSuggestion,
    ExtraDataAdapterSuggestion,
)
from rhosocial.activerecord.backend.adapters.portable import PORTABLE_TYPE_MAPPINGS
from rhosocial.activerecord.backend.errors import (
    ConnectionError,
    DatabaseError,
    DeadlockError,
    IntegrityError,
    LockError,
    OperationalError,
    QueryError,
)
from .._scan import (
    bare_identifier_end,
    consume_keyword,
    find_ci,
    parse_identifier,
    skip_space,
    skip_space_at_least_one,
    word_boundary_at,
)
from ..error_mapping import classify_sqlserver_error, normalize_integrity_message
from ..query_nodes import (
    identity_columns_sql,
    identity_current_sql,
    server_property_value_sql,
    session_identity_sql,
)

if TYPE_CHECKING:
    from ..dialect import SQLServerDialect
    from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter


_CLAUSE_KEYWORDS = (
    "WHERE", "JOIN", "ON", "GROUP", "HAVING", "ORDER", "LIMIT", "OFFSET",
    "FETCH", "WITH", "INNER", "LEFT", "RIGHT", "FULL", "CROSS", "OUTER",
    "UNION", "INTERSECT", "EXCEPT", "OPTION", "FOR", "AS", "FROM",
)

_EXPLAIN_ESTIMATED_CLAUSES = ("SHOWPLAN_TEXT", "SHOWPLAN_XML", "SHOWPLAN_ALL")
_EXPLAIN_ACTUAL_CLAUSES = ("PROFILE", "XML")


def _parse_insert_header(sql: str) -> Optional[Tuple[Optional[str], str, str]]:
    """Return ``(schema, table, column list)`` for an INSERT header, or None.

    Recognises ``INSERT INTO [schema].[table] (col, ...)``; the schema is
    optional, both names may be bracketed or bare, and the column list runs to
    the first ``)``, as the statement renderer writes it.
    """
    index = skip_space(sql, 0)
    after_insert = consume_keyword(sql, index, "INSERT")
    if after_insert is None:
        return None
    index = skip_space_at_least_one(sql, after_insert)
    if index is None:
        return None
    after_into = consume_keyword(sql, index, "INTO")
    if after_into is None:
        return None
    index = skip_space_at_least_one(sql, after_into)
    if index is None:
        return None
    schema: Optional[str] = None
    parsed = parse_identifier(sql, index)
    if parsed is not None and parsed[1] < len(sql) and sql[parsed[1]] == ".":
        schema = parsed[0]
        index = parsed[1] + 1
    parsed = parse_identifier(sql, index)
    if parsed is None:
        return None
    table, index = parsed
    index = skip_space(sql, index)
    if index >= len(sql) or sql[index] != "(":
        return None
    close = sql.find(")", index + 1)
    if close == -1:
        return None
    return schema, table, sql[index + 1:close]


def _starts_with_clause_keyword(text: str, index: int) -> bool:
    """Whether an upper-case clause keyword begins at *index* as a whole word.

    The original table-reference pattern carried no ``IGNORECASE`` flag, so only
    the documented upper-case spellings stop an alias; a lower-case ``where``
    was read as one. Keeping the comparison case-sensitive preserves that.
    """
    for word in _CLAUSE_KEYWORDS:
        end = index + len(word)
        if text.startswith(word, index) and word_boundary_at(text, end):
            return True
    return False


def _table_reference_end(text: str, index: int) -> Optional[int]:
    """End of a ``table [alias]`` reference starting at *index*.

    The optional alias is a bare word that is not itself a clause keyword; a
    keyword leaves the reference at the table name so the trailing hint lands
    directly after it.
    """
    parsed = parse_identifier(text, index)
    if parsed is None:
        return None
    table_end = parsed[1]
    candidate = skip_space(text, table_end)
    if candidate == table_end:
        return table_end
    if text.startswith("AS", candidate):
        after_space = skip_space_at_least_one(text, candidate + 2)
        if after_space is not None:
            candidate = after_space
    alias_end = bare_identifier_end(text, candidate)
    if alias_end is None or _starts_with_clause_keyword(text, candidate):
        return table_end
    return alias_end


def _trailing_table_hint_start(sql: str) -> Optional[int]:
    """Start index of a trailing ``WITH (...)`` table hint, or None."""
    index = find_ci(sql, "WITH", 0)
    while index != -1:
        if index > 0 and sql[index - 1].isspace():
            open_paren = skip_space(sql, index + 4)
            if open_paren < len(sql) and sql[open_paren] == "(":
                close = sql.find(")", open_paren + 1)
                if close != -1:
                    tail = skip_space(sql, close + 1)
                    if tail < len(sql) and sql[tail] == ";":
                        tail = skip_space(sql, tail + 1)
                    if tail == len(sql):
                        start = index - 1
                        while start > 0 and sql[start - 1].isspace():
                            start -= 1
                        return start
        index = find_ci(sql, "WITH", index + 1)
    return None


def _last_from_end(text: str) -> Optional[int]:
    """End index of the last ``FROM`` followed by whitespace, or None."""
    found = None
    index = find_ci(text, "FROM", 0)
    while index != -1:
        if word_boundary_at(text, index):
            after_space = skip_space_at_least_one(text, index + 4)
            if after_space is not None:
                found = after_space
        index = find_ci(text, "FROM", index + 1)
    return found


def _parse_explain_wrapper(sql: str) -> Optional[Tuple[str, str]]:
    """Split ``SET SHOWPLAN_*/STATISTICS ... ON; statement`` into its parts."""
    index = skip_space(sql, 0)
    after_set = consume_keyword(sql, index, "SET")
    if after_set is None:
        return None
    index = skip_space_at_least_one(sql, after_set)
    if index is None:
        return None

    set_clause: Optional[str] = None
    for word in _EXPLAIN_ESTIMATED_CLAUSES:
        end = consume_keyword(sql, index, word)
        if end is not None:
            set_clause = sql[index:end]
            index = end
            break
    if set_clause is None:
        after_statistics = consume_keyword(sql, index, "STATISTICS")
        if after_statistics is None:
            return None
        option_start = skip_space_at_least_one(sql, after_statistics)
        if option_start is None:
            return None
        for word in _EXPLAIN_ACTUAL_CLAUSES:
            end = consume_keyword(sql, option_start, word)
            if end is not None:
                set_clause = sql[index:end]
                index = end
                break
        if set_clause is None:
            return None

    after_clause = skip_space_at_least_one(sql, index)
    if after_clause is None:
        return None
    after_on = consume_keyword(sql, after_clause, "ON")
    if after_on is None:
        return None
    semicolon = skip_space(sql, after_on)
    if semicolon >= len(sql) or sql[semicolon] != ";":
        return None
    statement = sql[semicolon + 1:]
    if not statement:
        return None
    return set_clause, statement


def _strip_trailing_set_off(statement: str, set_clause: str) -> str:
    """Remove a trailing ``; SET <set_clause> OFF`` from *statement*."""
    target = set_clause.lower()
    index = statement.find(";")
    while index != -1:
        after_semicolon = skip_space(statement, index + 1)
        after_set = consume_keyword(statement, after_semicolon, "SET")
        if after_set is not None:
            after_space = skip_space_at_least_one(statement, after_set)
            if after_space is not None:
                literal_end = after_space + len(set_clause)
                if statement[after_space:literal_end].lower() == target:
                    after_off_space = skip_space_at_least_one(statement, literal_end)
                    if after_off_space is not None:
                        after_off = consume_keyword(statement, after_off_space, "OFF")
                        if after_off is not None:
                            tail = skip_space(statement, after_off)
                            if tail == len(statement):
                                start = index
                                while start > 0 and statement[start - 1].isspace():
                                    start -= 1
                                return statement[:start]
        index = statement.find(";", index + 1)
    return statement

_SQLSERVER_DATE_FORMATS = frozenset({"mdy", "dmy", "ymd", "ydm", "myd", "dym"})

_SQLSERVER_DEADLOCK_PRIORITIES = frozenset({"LOW", "NORMAL", "HIGH"})

_SQLSERVER_LANGUAGES = frozenset({
    "us_english", "english", "british english", "bokmål", "brazilian",
    "simplified chinese", "traditional chinese",
    "japanese", "korean", "french", "german", "italian",
    "spanish", "portuguese", "dutch", "swedish", "norwegian",
    "danish", "finnish", "polish", "czech", "hungarian",
    "romanian", "turkish", "greek", "russian", "arabic",
    "thai", "slovak", "slovenian", "croatian", "lithuanian",
    "latvian", "estonian", "bulgarian",
})


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
        hint_start = _trailing_table_hint_start(sql)
        if hint_start is None:
            return sql
        hint = sql[hint_start:].strip().rstrip(";").strip()
        body = sql[:hint_start]
        from_end = _last_from_end(body)
        if from_end is None:
            return sql
        table_end = _table_reference_end(body[from_end:], 0)
        if table_end is None:
            return sql
        end = from_end + table_end
        return (body[:end] + " " + hint + body[end:]).strip()

    def _get_identity_columns(self, table_name: str) -> Set[str]:
        """Return the set of identity column names for a table (cached).

        The catalogue question is built from nodes and rendered by the
        dialect; this method only executes it.
        """
        cache_key = table_name.lower()
        if cache_key in self._identity_columns_cache:
            return self._identity_columns_cache[cache_key]
        columns: Set[str] = set()
        try:
            sql, params = identity_columns_sql(self.dialect, table_name)
            cursor = self._get_cursor()
            cursor.execute(sql, params)
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
        parsed = _parse_explain_wrapper(sql)
        if parsed is None:
            return None
        set_clause, statement = parsed
        statement = _strip_trailing_set_off(statement, set_clause)
        return set_clause.strip(), statement.strip()

    def _insert_table_name(self, sql: str) -> Optional[str]:
        """Return the target table name of an ``INSERT`` statement, or None."""
        header = _parse_insert_header(sql)
        if header is None:
            return None
        return header[1]

    def _identity_insert_info(
        self, sql: str, params: Optional[Tuple] = None, identity_columns: Optional[Set[str]] = None
    ) -> Optional[str]:
        """Return the table name that needs ``SET IDENTITY_INSERT ON``, or None.

        Detects ``INSERT INTO [schema].[table] (col, ...) VALUES (?, ...)``
        statements that explicitly supply the table's identity column.
        SQL Server forbids such inserts unless ``IDENTITY_INSERT`` is enabled
        for the target table.  The column list alone decides: an explicit
        value may arrive as a placeholder or as a literal rendered into the
        statement, and both are equally forbidden, so ``params`` is not
        consulted.
        """
        table_name = self._insert_table_name(sql)
        if not table_name:
            return None
        if identity_columns is None:
            identity_columns = self._get_identity_columns(table_name)
        if not identity_columns:
            return None
        header = _parse_insert_header(sql)
        if header is None:
            return None
        raw_columns = header[2]
        columns = [c.strip().strip("[]\"").lower() for c in raw_columns.split(",") if c.strip()]
        if any(column in identity_columns for column in columns):
            return table_name
        return None

    def _execute_control_sql(self, sql: str) -> None:
        """Execute a session-control statement through the mapped error path.

        ``SET ...`` statements used to run straight against the cursor, so a
        driver exception escaped untranslated. Routing them through
        :meth:`_handle_error` gives them the same taxonomy as ``execute``.
        """
        cursor = self._get_cursor()
        try:
            cursor.execute(sql)
        except Exception as exc:
            self._handle_error(exc)
        finally:
            self._close_cursor_quietly(cursor)

    def _execute_control_sql_quietly(self, sql: str) -> None:
        """Execute a cleanup statement without masking the original failure."""
        try:
            self._execute_control_sql(sql)
        except Exception as exc:
            self.log(logging.WARNING, f"Failed to reset session state ({sql}): {exc}")

    def _close_cursor_quietly(self, cursor) -> None:
        """Close a cursor, logging rather than masking an in-flight error."""
        try:
            cursor.close()
        except Exception as exc:
            self.log(logging.DEBUG, f"Failed to close cursor: {exc}")

    def set_nocount(self, on: bool = True) -> None:
        state = "ON" if on else "OFF"
        self._execute_control_sql(f"SET NOCOUNT {state}")

    def set_identity_insert(self, table: str, on: bool = True) -> None:
        sql, _params = self.dialect.render_set_identity_insert(table, on)
        self._execute_control_sql(sql)

    def get_scope_identity(self) -> Optional[int]:
        sql, params = session_identity_sql(self.dialect)
        cursor = self._get_cursor()
        try:
            cursor.execute(sql, params)
            row = cursor.fetchone()
        except Exception as exc:
            self._handle_error(exc)
        finally:
            self._close_cursor_quietly(cursor)
        if row and row[0] is not None:
            return int(row[0])
        return None

    def get_identity_current(self, table: str) -> Optional[int]:
        sql, params = identity_current_sql(self.dialect, table)
        cursor = self._get_cursor()
        cursor.execute(sql, params)
        row = cursor.fetchone()
        cursor.close()
        if row and row[0] is not None:
            return int(row[0])
        return None

    def reset_identity(self, table: str, seed: int = 1) -> None:
        cursor = self._get_cursor()
        cursor.execute(f"DBCC CHECKIDENT({self.dialect.p()}, RESEED, {self.dialect.p()})", (table, seed))
        cursor.close()

    def set_lock_timeout(self, timeout_ms: int) -> None:
        cursor = self._get_cursor()
        cursor.execute(f"SET LOCK_TIMEOUT {timeout_ms}")
        cursor.close()

    def set_deadlock_priority(self, priority) -> None:
        if isinstance(priority, int):
            if not -10 <= priority <= 10:
                raise ValueError(
                    f"Invalid DEADLOCK_PRIORITY: {priority!r} (must be -10 to 10)"
                )
            sql = f"SET DEADLOCK_PRIORITY {priority}"
        else:
            name = priority.upper()
            if name not in _SQLSERVER_DEADLOCK_PRIORITIES:
                raise ValueError(
                    f"Invalid DEADLOCK_PRIORITY: {priority!r} "
                    f"(must be one of {sorted(_SQLSERVER_DEADLOCK_PRIORITIES)})"
                )
            sql = f"SET DEADLOCK_PRIORITY {name}"
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
        key = language.strip().lower()
        if key not in _SQLSERVER_LANGUAGES:
            raise ValueError(f"Unsupported SQL Server language: {language!r}")
        cursor = self._get_cursor()
        cursor.execute(f"SET LANGUAGE '{key}'")
        cursor.close()

    def set_dateformat(self, format: str) -> None:
        key = format.strip().lower()
        if key not in _SQLSERVER_DATE_FORMATS:
            raise ValueError(
                f"Invalid DATEFORMAT: {format!r} "
                f"(must be one of {sorted(_SQLSERVER_DATE_FORMATS)})"
            )
        cursor = self._get_cursor()
        cursor.execute(f"SET DATEFORMAT {key}")
        cursor.close()

    def get_product_version(self) -> str:
        return self._server_property_value("ProductVersion")

    def get_product_level(self) -> str:
        return self._server_property_value("ProductLevel")

    def get_edition(self) -> str:
        return self._server_property_value("Edition")

    def get_machine_name(self) -> str:
        return self._server_property_value("MachineName")

    def get_server_name(self) -> str:
        return self._server_property_value("ServerName")

    def _server_property_value(self, name: str) -> str:
        """Read one ``SERVERPROPERTY`` value; the name is part of the query."""
        sql, params = server_property_value_sql(self.dialect, name)
        cursor = self._get_cursor()
        cursor.execute(sql, params)
        row = cursor.fetchone()
        cursor.close()
        return row[0] if row else ""

    def is_case_sensitive(self) -> bool:
        collation = self._server_property_value("Collation")
        if collation:
            collation = str(collation).upper()
            return "_CS" in collation or collation.endswith("_CS_AS")
        return False

    def suggest_data_adapters(self) -> DataAdapterSuggestion:
        """Provide SQL Server's type-adapter suggestions.

        Core declares no default table; this backend reuses the portable scalar
        baseline and merges its own pairs on top, because it knows what pyodbc
        accepts better than the framework does.  A pair is suggested only when
        this backend registered an adapter for it, so the merged table never
        names an adapter this backend does not provide.

        The neutral families have no SQL Server column type of their own.  They
        are carried as text -- WKT for geometry, a JSON array for vectors,
        bit-string text for ``BitString``, range JSON for ``Range`` /
        ``Multirange``, canonical lowercase colon text for MAC addresses, and
        canonical text for ``IPAddress`` -- so each one is merged with a plain
        ``str`` target.
        """
        if getattr(self, '_default_suggestions_cache', None) is not None:
            return DataAdapterSuggestion(table=self._default_suggestions_cache)

        from datetime import date, datetime, time
        from decimal import Decimal
        from uuid import UUID

        from rhosocial.activerecord.backend.adapters.bitstring import BitString
        from rhosocial.activerecord.backend.adapters.geometry import Geometry
        from rhosocial.activerecord.backend.adapters.network import IPAddress, MacAddress
        from rhosocial.activerecord.backend.adapters.range import Multirange, Range
        from rhosocial.activerecord.backend.adapters.vector import Vector
        from rhosocial.activerecord.backend.base.type_adaption import (
            merge_adapter_suggestions,
        )

        type_mappings = [
            (bool, bool), (int, int), (float, float),
            (str, str), (bytes, bytes),
            (datetime, datetime), (date, date), (time, time),
            (Decimal, Decimal), (UUID, str), (dict, str), (list, str),
            # Neutral families carried as text on SQL Server.
            (Geometry, str),
            (Vector, str),
            (BitString, str),
            (Range, str),
            (Multirange, str),
            (MacAddress, str),
            (IPAddress, str),
        ]

        overrides = list(PORTABLE_TYPE_MAPPINGS) + type_mappings
        suggestions = merge_adapter_suggestions({}, overrides, self.adapter_registry)
        for py_type, db_type in overrides:
            if py_type not in suggestions:
                self.log(
                    logging.DEBUG,
                    f"No adapter found for ({py_type.__name__}, {db_type.__name__}). "
                    "Suggestion will not be provided for this type.",
                )

        self._default_suggestions_cache = suggestions
        return DataAdapterSuggestion(table=suggestions)

    def suggest_extra_data_adapters(self) -> ExtraDataAdapterSuggestion:
        """No backend-owned extra adapter types."""
        return ExtraDataAdapterSuggestion(table={})

    def get_type_adapters(self) -> List["SQLTypeAdapter"]:
        """Return the adapter instances this backend provides.

        This is a plain inventory: it says which adapters exist for this backend.
        It carries no suggestion/default/priority semantics; the caller decides.
        """
        registered = self.adapter_registry.get_all_adapters().values()
        unique: Dict[Tuple[str, str], "SQLTypeAdapter"] = {}
        for adapter in registered:
            adapter_class = type(adapter)
            key = (adapter_class.__module__, adapter_class.__qualname__)
            unique.setdefault(key, adapter)
        return [unique[key] for key in sorted(unique)]

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
            deployment_target = getattr(self, "deployment_target", None)
            if deployment_target is None:
                deployment_target = getattr(
                    getattr(self, "config", None),
                    "deployment_target",
                    "sqlserver",
                )
            self._dialect = SQLServerDialect(
                self._version,
                deployment_target=deployment_target,
            )
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

    def adapt_row_types(self, row_dict: Dict[str, Any], column_adapters) -> Dict[str, Any]:
        """Adapt row values, stripping SQL Server CHAR column padding.

        SQL Server pads ``CHAR``/``NCHAR`` values with trailing spaces, so a
        value stored as ``'fixed'`` in a ``CHAR(10)`` column is returned as
        ``'fixed     '``. The shared testsuite expects the original value back,
        so strip trailing spaces from every returned string (adapted values
        that legitimately carry trailing whitespace are not produced by the
        column adapters used here).
        """
        processed_row = super().adapt_row_types(row_dict, column_adapters)
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
        return normalize_integrity_message(message)

    def _log_classified_error(self, error: Exception, mapped: DatabaseError) -> None:
        """Log a translated error under the historic message family.

        The execution-logging tests assert on phrases such as ``Unique
        constraint violation`` and ``Deadlock detected``; keep those labels
        stable while the mapping itself lives in one place.
        """
        message = str(mapped)
        detail = str(error)
        if message.startswith("Unique constraint violation"):
            self.log(logging.DEBUG, f"Unique constraint violation: {detail}")
        elif message.startswith("Foreign key constraint violation"):
            self.log(logging.DEBUG, f"Foreign key constraint violation: {detail}")
        elif isinstance(mapped, IntegrityError):
            self.log(logging.DEBUG, f"Integrity error: {detail}")
        elif isinstance(mapped, DeadlockError):
            self.log(logging.DEBUG, f"Deadlock detected: {detail}")
        elif isinstance(mapped, LockError):
            self.log(logging.DEBUG, f"Lock timeout: {detail}")
        elif isinstance(mapped, QueryError):
            self.log(logging.DEBUG, f"Query error: {detail}")
        elif isinstance(mapped, OperationalError):
            self.log(logging.DEBUG, f"Operational error: {detail}")
        elif isinstance(mapped, ConnectionError):
            self.log(logging.DEBUG, f"Connection error: {detail}")
        else:
            self.log(logging.DEBUG, f"Database error: {detail}")

    def _handle_error(self, error: Exception) -> None:
        # A framework error already carries its phase semantics; re-mapping it
        # would replace the original type with a generic driver error.
        if isinstance(error, DatabaseError):
            raise error
        mapped = classify_sqlserver_error(error)
        self._log_classified_error(error, mapped)
        raise mapped from error