# src/rhosocial/activerecord/backend/impl/sqlserver/introspection/introspector.py
"""SQL Server concrete introspectors.

Implements SyncAbstractIntrospector and AsyncAbstractIntrospector for SQL Server
using INFORMATION_SCHEMA and sys.* catalog views.
"""

import copy
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.introspection.base import (
    IntrospectorMixin,
    SyncAbstractIntrospector,
    AsyncAbstractIntrospector,
)
from rhosocial.activerecord.backend.introspection.cache import IntrospectionCache
from rhosocial.activerecord.backend.introspection.executor import (
    SyncIntrospectorExecutor,
    AsyncIntrospectorExecutor,
)
from rhosocial.activerecord.backend.introspection.types import (
    IntrospectionDatabaseInfo,
    IntrospectionTableInfo,
    TableType,
    IntrospectionColumnInfo,
    ColumnNullable,
    IndexInfo,
    IndexColumnInfo,
    IndexType,
    IntrospectionForeignKeyInfo,
    ReferentialAction,
    IntrospectionViewInfo,
    IntrospectionTriggerInfo,
    IntrospectionScope,
)
from rhosocial.activerecord.backend.expression.types._base import DataType

from ..mixins.introspection import DEFAULT_SCHEMA
from ..query_nodes import SQLServerNodeBuilderMixin
from .types import (
    SQLServerExtendedPropertyInfo,
    SQLServerRoutineInfo,
    SQLServerSchemaInfo,
    SQLServerSequenceInfo,
)

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase
    from ..expression.introspection import (
        SQLServerExtendedPropertyListQueryStatement,
        SQLServerPrimaryKeyQueryStatement,
        SQLServerRoutineListQueryStatement,
        SQLServerSchemaListQueryStatement,
        SQLServerSequenceListQueryStatement,
    )

#: ``INFORMATION_SCHEMA.COLUMNS.CHARACTER_MAXIMUM_LENGTH`` reports ``-1``
#: for a MAX-capable column.  Only these three spell that marker as a length
#: argument (``(MAX)``).  ``xml`` reports ``-1`` as well but takes no length
#: argument, and the deprecated LOBs (``text``/``ntext``/``image``) report
#: their own maximum (2^31-1 / 2^30-1 / 2^31-1) rather than ``-1``, so they
#: keep the bare-word path.
_MAX_LENGTH_TYPES = frozenset({"varchar", "nvarchar", "varbinary"})

#: The three temporal types that take a fractional-seconds precision.  The
#: catalog reports it in ``DATETIME_PRECISION``, and it is the *only* place the
#: precision lives — ``NUMERIC_PRECISION`` is NULL for all three — so before it
#: was selected every ``time(3)``/``datetime2(3)``/``datetimeoffset(3)`` column
#: rebuilt to its bare word and re-read as the *default* precision: a phantom
#: diff against the declaration that produced it, and a missed change between
#: ``time(0)`` and ``time(7)``.  See the normalization note below.
#:
#: ``datetime`` (reports 3) and ``smalldatetime`` (reports 0) also carry a
#: value in ``DATETIME_PRECISION``, but those two are fixed legacy aliases
#: folded into the ``DATETIME2`` concept, so they keep the existing bare-word
#: path and are deliberately absent here.
_DATETIME_PRECISION_TYPES = frozenset({"time", "datetime2", "datetimeoffset"})

#: The fractional-seconds precision the server reports for a *bare*
#: ``time``/``datetime2``/``datetimeoffset`` declaration, and equally for an
#: explicit ``(7)`` one: the server cannot tell those two declarations apart,
#: so neither can this rebuild.  ``(n)`` is rebuilt only when ``n`` differs
#: from this default and the bare word is rebuilt at it.
#:
#: Every number above was read off a live server, identically on SQL Server
#: 2019 (15.0.4465.1), 2022 (16.0.4250.1) and 2025 (17.0.4035.5)::
#:
#:     CREATE TABLE t (t TIME, t0 TIME(0), t3 TIME(3), t7 TIME(7),
#:                     d DATETIME2, d3 DATETIME2(3), o DATETIMEOFFSET(3))
#:     -- INFORMATION_SCHEMA.COLUMNS.DATETIME_PRECISION
#:     --   t  -> 7        t0 -> 0       t3 -> 3       t7 -> 7
#:     --   d  -> 7        d3 -> 3       o3 -> 3
#:
#: The one residual this does not close: a declared explicit ``(7)`` parses to
#: a type carrying precision 7 while the rebuilt column is bare, so those two
#: still compare unequal.  Closing *that* is the server-defaults question (a
#: bare word and an explicit default name one server column), which belongs
#: with the dialect's ``type_parameter_defaults`` machinery rather than this
#: catalog rebuild; it is recorded here rather than silently widened.
_DATETIME_DEFAULT_PRECISION = 7

#: ``sys.objects.type`` codes for user-defined functions: scalar (``FN``),
#: inline table-valued (``IF``), multi-statement table-valued (``TF``),
#: CLR scalar (``FS``) and CLR table-valued (``FT``). ``sys.procedures``
#: covers the procedure half.
_FUNCTION_TYPE_CODES = ("FN", "IF", "TF", "FS", "FT")


class SQLServerIntrospectorMixin(SQLServerNodeBuilderMixin, IntrospectorMixin):
    """Shared non-I/O logic for SQL Server introspectors."""

    @property
    def default_schema(self) -> str:
        return DEFAULT_SCHEMA

    @property
    def _node_dialect(self) -> "SQLDialectBase":
        """The dialect the node builders bind their trees to."""
        return self.dialect

    def _get_version(self) -> tuple:
        return getattr(self._backend, '_version', (15, 0, 0))

    # ------------------------------------------------------------------
    # Backend-specific statement factories
    #
    # Every family core models is a statement its dialect renders; this
    # layer constructs it and executes what comes back. The families core has
    # no statement for are SQL Server's own -- the primary key, schemas,
    # extended properties, routines and sequences -- and each gets a factory
    # here returning the statement object. Each collects every parameter at
    # construction (keyword-only: a question is asked once and never edited),
    # the dialect renders it, and each carries the family name into its cache
    # key (see the managers below) so two families never answer each other's
    # question.
    #
    # Nothing here renders: a SQL string is the dialect formatter's, so a
    # factory below names a statement and stops.
    # ------------------------------------------------------------------

    def primary_key_statement(
        self, *, table_name: str, schema: str
    ) -> "SQLServerPrimaryKeyQueryStatement":
        """Return the statement that lists one table's primary-key columns."""
        from ..expression.introspection import SQLServerPrimaryKeyQueryStatement

        return SQLServerPrimaryKeyQueryStatement(self.dialect, table_name=table_name, schema=schema)

    def schema_list_statement(self) -> "SQLServerSchemaListQueryStatement":
        """Return the statement that lists this database's schemas."""
        from ..expression.introspection import SQLServerSchemaListQueryStatement

        return SQLServerSchemaListQueryStatement(self.dialect)

    def extended_property_list_statement(
        self,
        *,
        major_id: int,
        minor_id: Optional[int] = None,
        class_name: str = "OBJECT_OR_COLUMN",
        schema: Optional[str] = None,
    ) -> "SQLServerExtendedPropertyListQueryStatement":
        """Return the statement that reads one object's extended properties.

        ``major_id`` is the object id for ``OBJECT_OR_COLUMN`` (class 1) and
        the id in the family's own space for the other classes; ``minor_id``
        narrows to one column's properties. ``schema`` only means something
        for the object-scoped classes, and the formatter refuses it for a
        family that has none rather than returning nothing.
        """
        from ..expression.introspection import (
            SQLServerExtendedPropertyListQueryStatement,
        )

        return SQLServerExtendedPropertyListQueryStatement(
            self.dialect,
            major_id=major_id,
            minor_id=minor_id,
            class_name=class_name,
            schema=schema,
        )

    def routine_list_statement(
        self, *, type_codes: Tuple[str, ...], schema: Optional[str]
    ) -> "SQLServerRoutineListQueryStatement":
        """Return the statement that lists the routines with these type codes.

        One statement class for both routine families -- what separates a
        procedure from a function is the ``sys.objects.type`` code set.
        """
        from ..expression.introspection import SQLServerRoutineListQueryStatement

        return SQLServerRoutineListQueryStatement(
            self.dialect, type_codes=type_codes, schema=schema
        )

    def procedure_list_statement(
        self, *, schema: Optional[str]
    ) -> "SQLServerRoutineListQueryStatement":
        """Return the statement that lists procedures (types ``P``/``PC``)."""
        return self.routine_list_statement(type_codes=("P", "PC"), schema=schema)

    def function_list_statement(
        self, *, schema: Optional[str]
    ) -> "SQLServerRoutineListQueryStatement":
        """Return the statement that lists user-defined functions."""
        return self.routine_list_statement(type_codes=_FUNCTION_TYPE_CODES, schema=schema)

    def sequence_list_statement(
        self, *, schema: Optional[str]
    ) -> "SQLServerSequenceListQueryStatement":
        """Return the statement that lists this database's sequences."""
        from ..expression.introspection import SQLServerSequenceListQueryStatement

        return SQLServerSequenceListQueryStatement(self.dialect, schema=schema)

    # ------------------------------------------------------------------
    # Parse methods — pure Python, no I/O
    # ------------------------------------------------------------------

    def parse_database_info(self, rows: List[Dict[str, Any]]) -> IntrospectionDatabaseInfo:
        row = rows[0] if rows else {}
        version_str = row.get("version", "Unknown")
        parts = version_str.split(".")
        try:
            version_tuple = tuple(int(p) for p in parts[:3])
        except (ValueError, IndexError):
            version_tuple = (0, 0, 0)
        return IntrospectionDatabaseInfo(
            name=row.get("db_name", ""),
            version=version_str,
            version_tuple=version_tuple,
            vendor="SQL Server",
            encoding=None,
            collation=row.get("collation"),
        )

    def parse_tables(
        self, rows: List[Dict[str, Any]], schema: Optional[str]
    ) -> List[IntrospectionTableInfo]:
        target = schema or self.default_schema
        return [
            IntrospectionTableInfo(
                name=row["TABLE_NAME"],
                schema=target,
                table_type=(
                    TableType.VIEW if row.get("TABLE_TYPE") == "VIEW"
                    else TableType.BASE_TABLE
                ),
            )
            for row in rows
        ]

    def parse_columns(
        self, rows: List[Dict[str, Any]], table_name: str, schema: str,
        primary_keys: Optional[List[str]] = None,
    ) -> List[IntrospectionColumnInfo]:
        pk_set = set(primary_keys or [])
        columns: List[IntrospectionColumnInfo] = []
        for row in rows:
            data_type = (row.get("DATA_TYPE") or "").lower()
            max_len = row.get("CHARACTER_MAXIMUM_LENGTH")
            precision = row.get("NUMERIC_PRECISION")
            scale = row.get("NUMERIC_SCALE")
            dt_precision = row.get("DATETIME_PRECISION")

            if max_len == -1 and data_type in _MAX_LENGTH_TYPES:
                # Rebuild the ``(MAX)`` spelling the catalog marker stands
                # for; ``parse_type`` reads it as the documented widening
                # (``TextType`` for the character pair,
                # ``SQLServerVarBinaryMaxType`` for ``varbinary``).  Dropping
                # the marker rebuilt a bare word, which re-read as the
                # declared default width (``nvarchar`` -> 255) — a MAX
                # column then compared equal to a 255 one, and against a
                # declared ``NVARCHAR(MAX)`` it produced a phantom diff.
                full_type = f"{data_type}(MAX)"
            elif data_type in _DATETIME_PRECISION_TYPES:
                # Rebuild the fractional-seconds precision the column was
                # declared with, except at the server default: a bare word
                # and ``(7)`` are the same column to the server, so the bare
                # word is what the default rebuilds to and ``(n)`` appears
                # only where the declaration was genuinely narrower.  Before
                # ``DATETIME_PRECISION`` was read at all, a ``time(3)``
                # column came back bare and re-read as the default
                # (``TimeType(None)`` vs the declared ``TimeType(3)``), while
                # ``time(0)`` and ``time(7)`` both folded to the same bare
                # type and could not be told apart.  The measured rows and
                # the explicit-``(7)`` residual are written down on
                # ``_DATETIME_DEFAULT_PRECISION``.
                if (dt_precision is not None
                        and dt_precision != _DATETIME_DEFAULT_PRECISION):
                    full_type = f"{data_type}({dt_precision})"
                else:
                    full_type = data_type
            elif max_len and max_len > 0:
                full_type = f"{data_type}({max_len})"
            elif precision is not None:
                if scale:
                    full_type = f"{data_type}({precision},{scale})"
                else:
                    full_type = f"{data_type}({precision})"
            else:
                full_type = data_type

            col_name = row.get("COLUMN_NAME", "")

            parsed = None
            try:
                parsed = DataType.parse_data_type_str(self._backend.dialect, full_type)
            except Exception:
                pass

            columns.append(IntrospectionColumnInfo(
                name=col_name,
                table_name=table_name,
                schema=schema,
                ordinal_position=row.get("ORDINAL_POSITION", 0),
                data_type=data_type,
                data_type_full=full_type,
                parsed_data_type=parsed,
                nullable=(
                    ColumnNullable.NULLABLE
                    if row.get("IS_NULLABLE") == "YES"
                    else ColumnNullable.NOT_NULL
                ),
                default_value=row.get("COLUMN_DEFAULT"),
                is_primary_key=col_name in pk_set,
                is_unique=False,
                is_auto_increment=bool(row.get("IS_IDENTITY")),
                character_maximum_length=max_len,
                numeric_precision=precision,
                numeric_scale=scale,
                charset=None,
            ))
        return columns

    def parse_indexes(
        self, rows: List[Dict[str, Any]], table_name: str, schema: str
    ) -> List[IndexInfo]:
        type_map = {
            "CLUSTERED": IndexType.BTREE,
            "NONCLUSTERED": IndexType.BTREE,
            "HEAP": IndexType.BTREE,
        }
        index_map: Dict[str, IndexInfo] = {}
        for row in rows:
            idx_name = row.get("index_name", "")
            if idx_name not in index_map:
                idx_type_str = (row.get("index_type") or "").upper()
                index_map[idx_name] = IndexInfo(
                    name=idx_name,
                    table_name=table_name,
                    schema=schema,
                    is_unique=bool(row.get("is_unique")),
                    is_primary=bool(row.get("is_primary_key")),
                    index_type=type_map.get(idx_type_str, IndexType.BTREE),
                    columns=[],
                )
            index_map[idx_name].columns.append(IndexColumnInfo(
                name=row.get("column_name", ""),
                ordinal_position=int(row.get("column_position", 1)),
                is_descending=bool(row.get("is_descending_key")),
            ))
        return list(index_map.values())

    def parse_foreign_keys(
        self, rows: List[Dict[str, Any]], table_name: str, schema: str
    ) -> List[IntrospectionForeignKeyInfo]:
        action_map = {
            "NO_ACTION": ReferentialAction.NO_ACTION,
            "CASCADE": ReferentialAction.CASCADE,
            "SET_NULL": ReferentialAction.SET_NULL,
            "SET_DEFAULT": ReferentialAction.SET_DEFAULT,
        }
        fk_map: Dict[str, IntrospectionForeignKeyInfo] = {}
        for row in rows:
            fk_name = row.get("fk_name", "")
            if fk_name not in fk_map:
                on_del = (row.get("on_delete") or "NO_ACTION").upper()
                on_upd = (row.get("on_update") or "NO_ACTION").upper()
                fk_map[fk_name] = IntrospectionForeignKeyInfo(
                    name=fk_name,
                    table_name=table_name,
                    schema=schema,
                    referenced_table=row.get("ref_table", ""),
                    on_delete=action_map.get(
                        on_del, ReferentialAction.NO_ACTION
                    ),
                    on_update=action_map.get(
                        on_upd, ReferentialAction.NO_ACTION
                    ),
                    columns=[],
                    referenced_columns=[],
                )
            fk_map[fk_name].columns.append(row.get("col_name", ""))
            fk_map[fk_name].referenced_columns.append(
                row.get("ref_col", "")
            )
        return list(fk_map.values())

    def parse_views(
        self, rows: List[Dict[str, Any]], schema: str
    ) -> List[IntrospectionViewInfo]:
        return [
            IntrospectionViewInfo(
                name=row.get("view_name", ""),
                schema=schema,
                definition=None,
            )
            for row in rows
        ]

    def parse_view_info(
        self, rows: List[Dict[str, Any]], view_name: str, schema: str
    ) -> Optional[IntrospectionViewInfo]:
        if not rows:
            return None
        row = rows[0]
        return IntrospectionViewInfo(
            name=row.get("view_name", view_name),
            schema=schema,
            definition=row.get("definition"),
            is_updatable=row.get("IS_UPDATABLE") == "YES",
        )

    def parse_triggers(
        self, rows: List[Dict[str, Any]], schema: str
    ) -> List[IntrospectionTriggerInfo]:
        return [
            IntrospectionTriggerInfo(
                name=row.get("trigger_name", ""),
                table_name=row.get("table_name", ""),
                schema=schema,
                timing=(
                    "INSTEAD OF" if row.get("is_instead_of_trigger")
                    else "AFTER"
                ),
                events=[],
                definition=row.get("definition"),
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Backend-specific parsers
    # ------------------------------------------------------------------

    def parse_schemas(
        self, rows: List[Dict[str, Any]]
    ) -> List[SQLServerSchemaInfo]:
        return [
            SQLServerSchemaInfo(
                name=row.get("schema_name", ""),
                schema_id=int(row.get("schema_id") or 0),
                owner=row.get("owner"),
            )
            for row in rows
        ]

    def parse_extended_properties(
        self, rows: List[Dict[str, Any]]
    ) -> List[SQLServerExtendedPropertyInfo]:
        properties: List[SQLServerExtendedPropertyInfo] = []
        for row in rows:
            value = row.get("property_value")
            properties.append(
                SQLServerExtendedPropertyInfo(
                    name=row.get("property_name", ""),
                    # The cast widened a sql_variant to text; a NULL value is
                    # a property that was set to NULL, not a missing property,
                    # so it stays None rather than becoming "".
                    value=None if value is None else str(value),
                    class_id=int(row.get("class_id") or 0),
                    class_name=row.get("class_name") or "",
                    major_id=int(row.get("major_id") or 0),
                    minor_id=int(row.get("minor_id") or 0),
                )
            )
        return properties

    def parse_routines(
        self, rows: List[Dict[str, Any]]
    ) -> List[SQLServerRoutineInfo]:
        return [
            SQLServerRoutineInfo(
                name=row.get("routine_name", ""),
                schema=row.get("schema_name"),
                type_code=(row.get("type_code") or "").strip(),
                type_desc=row.get("type_desc") or "",
                created_at=row.get("created_at"),
                modified_at=row.get("modified_at"),
                is_ms_shipped=bool(row.get("is_ms_shipped")),
            )
            for row in rows
        ]

    def parse_sequences(
        self, rows: List[Dict[str, Any]]
    ) -> List[SQLServerSequenceInfo]:
        sequences: List[SQLServerSequenceInfo] = []
        for row in rows:
            cache_size = row.get("cache_size")
            sequences.append(
                SQLServerSequenceInfo(
                    name=row.get("sequence_name", ""),
                    schema=row.get("schema_name"),
                    data_type=row.get("data_type"),
                    start_value=self._as_decimal(row.get("start_value")),
                    increment=self._as_decimal(row.get("increment")),
                    minimum_value=self._as_decimal(row.get("minimum_value")),
                    maximum_value=self._as_decimal(row.get("maximum_value")),
                    current_value=self._as_decimal(row.get("current_value")),
                    is_cycling=bool(row.get("is_cycling")),
                    is_cached=bool(row.get("is_cached")),
                    cache_size=int(cache_size) if cache_size is not None else None,
                )
            )
        return sequences

    @staticmethod
    def _as_decimal(value: Any) -> Optional[Decimal]:
        """Read a cast-to-text sequence value back as an exact number.

        ``None`` means the server reported NULL (an unstarted sequence has no
        ``current_value``); unparseable text also degrades to ``None`` rather
        than aborting the whole listing, matching the contract
        ``parsed_data_type`` follows for columns.
        """
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None


class SyncSQLServerIntrospector(
    SQLServerIntrospectorMixin, SyncAbstractIntrospector
):
    """Synchronous introspector for SQL Server backends."""

    def __init__(
        self,
        backend: Any,
        executor: SyncIntrospectorExecutor,
        cache: Optional[IntrospectionCache] = None,
    ) -> None:
        super().__init__(backend, executor, cache)

    def get_table_info(
        self, table_name: str, schema: Optional[str] = None
    ) -> Optional[IntrospectionTableInfo]:
        key = self._cache.key(
            IntrospectionScope.TABLE, table_name, schema=schema
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        tables = self.list_tables(schema)
        table = next(
            (t for t in tables if t.name == table_name), None
        )
        if table is None:
            return None

        table = copy.copy(table)
        table.columns = self.list_columns(table_name, schema)
        table.indexes = self.list_indexes(table_name, schema)
        table.foreign_keys = self.list_foreign_keys(table_name, schema)
        self._cache.set(key, table)
        return table

    def list_columns(
        self, table_name: str, schema: Optional[str] = None
    ) -> List[IntrospectionColumnInfo]:
        target = schema if schema is not None else self.default_schema
        key = self._cache.key(
            IntrospectionScope.COLUMN, table_name, schema=target
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        pk_sql, pk_params = self.primary_key_statement(
            table_name=table_name, schema=target
        ).to_sql()
        pk_rows = self._executor.execute(pk_sql, pk_params)
        primary_keys = [r.get("COLUMN_NAME") for r in pk_rows]

        sql, params = self.column_info_statement(
            table_name=table_name, schema=schema
        ).to_sql()
        rows = self._executor.execute(sql, params)
        columns = self.parse_columns(
            rows, table_name, target, primary_keys
        )
        self._cache.set(key, columns)
        return columns

    # ------------------------------------------------------------------
    # Backend-specific questions (sync)
    #
    # The cache keys follow the same discipline as core's shared methods:
    # the scope comes from IntrospectionScope, the schema rides the
    # dedicated argument, and a family that shares a scope with another
    # family names itself in ``extra``. Comparison is by scope value and
    # schema, so ``list_procedures(schema="dbo")`` and
    # ``list_functions(schema="dbo")`` never answer each other.
    # ------------------------------------------------------------------

    def list_schemas(self) -> List[SQLServerSchemaInfo]:
        """List the database's schemas with their owning principal."""
        key = self._cache.key(IntrospectionScope.SCHEMA)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.schema_list_statement().to_sql()
        schemas = self.parse_schemas(self._executor.execute(sql, params))
        self._cache.set(key, schemas)
        return schemas

    def list_extended_properties(
        self,
        major_id: int,
        minor_id: Optional[int] = None,
        class_name: str = "OBJECT_OR_COLUMN",
        schema: Optional[str] = None,
    ) -> List[SQLServerExtendedPropertyInfo]:
        """List ``sys.extended_properties`` rows for one catalogue object.

        Args:
            major_id: The object id for ``OBJECT_OR_COLUMN`` (class 1), or the
                id in the family's own space for other classes.
            minor_id: ``None`` for every row of the object (the object's own
                properties plus its columns'), or the exact ``minor_id`` --
                ``0`` for an object-level property, a ``column_id`` for a
                column-level one.
            class_name: The ``class_desc`` family, ``OBJECT_OR_COLUMN`` by
                default -- the family ``MS_Description`` normally lives in.
            schema: Restrict to objects in this schema. Only meaningful for
                the object-scoped classes; asking for a schema on a family
                that has none raises ``ValueError`` instead of returning
                nothing.

        The cache entry is keyed on the object id rather than a table name,
        so ``invalidate_cache(TABLE, "<table>")`` does not drop it; clear the
        scope or pass the object id instead.
        """
        key = self._cache.key(
            IntrospectionScope.TABLE,
            str(major_id),
            schema=schema,
            extra=f"extended_properties:{class_name}:{minor_id}",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.extended_property_list_statement(
            major_id=major_id,
            minor_id=minor_id,
            class_name=class_name,
            schema=schema,
        ).to_sql()
        properties = self.parse_extended_properties(
            self._executor.execute(sql, params)
        )
        self._cache.set(key, properties)
        return properties

    def list_procedures(
        self, schema: Optional[str] = None
    ) -> List[SQLServerRoutineInfo]:
        """List stored procedures in *schema* (``sys.objects`` types P/PC)."""
        key = self._cache.key(
            IntrospectionScope.TABLE, schema=schema, extra="procedures"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.procedure_list_statement(schema=schema).to_sql()
        procedures = self.parse_routines(self._executor.execute(sql, params))
        self._cache.set(key, procedures)
        return procedures

    def list_functions(
        self, schema: Optional[str] = None
    ) -> List[SQLServerRoutineInfo]:
        """List user-defined functions in *schema*."""
        key = self._cache.key(
            IntrospectionScope.TABLE, schema=schema, extra="functions"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.function_list_statement(schema=schema).to_sql()
        functions = self.parse_routines(self._executor.execute(sql, params))
        self._cache.set(key, functions)
        return functions

    def list_sequences(
        self, schema: Optional[str] = None
    ) -> List[SQLServerSequenceInfo]:
        """List sequences in *schema* (``sys.sequences``)."""
        key = self._cache.key(IntrospectionScope.SEQUENCE, schema=schema)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.sequence_list_statement(schema=schema).to_sql()
        sequences = self.parse_sequences(self._executor.execute(sql, params))
        self._cache.set(key, sequences)
        return sequences


class AsyncSQLServerIntrospector(
    SQLServerIntrospectorMixin, AsyncAbstractIntrospector
):
    """Asynchronous introspector for SQL Server backends."""

    def __init__(
        self,
        backend: Any,
        executor: AsyncIntrospectorExecutor,
        cache: Optional[IntrospectionCache] = None,
    ) -> None:
        super().__init__(backend, executor, cache)

    async def get_table_info(
        self, table_name: str, schema: Optional[str] = None
    ) -> Optional[IntrospectionTableInfo]:
        key = self._cache.key(
            IntrospectionScope.TABLE, table_name, schema=schema
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        tables = await self.list_tables(schema)
        table = next(
            (t for t in tables if t.name == table_name), None
        )
        if table is None:
            return None

        table = copy.copy(table)
        table.columns = await self.list_columns(table_name, schema)
        table.indexes = await self.list_indexes(table_name, schema)
        table.foreign_keys = await self.list_foreign_keys(
            table_name, schema
        )
        self._cache.set(key, table)
        return table

    async def list_columns(
        self, table_name: str, schema: Optional[str] = None
    ) -> List[IntrospectionColumnInfo]:
        target = schema if schema is not None else self.default_schema
        key = self._cache.key(
            IntrospectionScope.COLUMN, table_name, schema=target
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        pk_sql, pk_params = self.primary_key_statement(
            table_name=table_name, schema=target
        ).to_sql()
        pk_rows = await self._executor.execute(pk_sql, pk_params)
        primary_keys = [r.get("COLUMN_NAME") for r in pk_rows]

        sql, params = self.column_info_statement(
            table_name=table_name, schema=schema
        ).to_sql()
        rows = await self._executor.execute(sql, params)
        columns = self.parse_columns(
            rows, table_name, target, primary_keys
        )
        self._cache.set(key, columns)
        return columns

    # ------------------------------------------------------------------
    # Backend-specific questions (async)
    #
    # Same signatures as the sync manager, same cache keys, same parsers;
    # only the executor is awaited.
    # ------------------------------------------------------------------

    async def list_schemas(self) -> List[SQLServerSchemaInfo]:
        """List the database's schemas with their owning principal."""
        key = self._cache.key(IntrospectionScope.SCHEMA)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.schema_list_statement().to_sql()
        schemas = self.parse_schemas(await self._executor.execute(sql, params))
        self._cache.set(key, schemas)
        return schemas

    async def list_extended_properties(
        self,
        major_id: int,
        minor_id: Optional[int] = None,
        class_name: str = "OBJECT_OR_COLUMN",
        schema: Optional[str] = None,
    ) -> List[SQLServerExtendedPropertyInfo]:
        """List ``sys.extended_properties`` rows for one catalogue object."""
        key = self._cache.key(
            IntrospectionScope.TABLE,
            str(major_id),
            schema=schema,
            extra=f"extended_properties:{class_name}:{minor_id}",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.extended_property_list_statement(
            major_id=major_id,
            minor_id=minor_id,
            class_name=class_name,
            schema=schema,
        ).to_sql()
        properties = self.parse_extended_properties(
            await self._executor.execute(sql, params)
        )
        self._cache.set(key, properties)
        return properties

    async def list_procedures(
        self, schema: Optional[str] = None
    ) -> List[SQLServerRoutineInfo]:
        """List stored procedures in *schema* (``sys.objects`` types P/PC)."""
        key = self._cache.key(
            IntrospectionScope.TABLE, schema=schema, extra="procedures"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.procedure_list_statement(schema=schema).to_sql()
        procedures = self.parse_routines(
            await self._executor.execute(sql, params)
        )
        self._cache.set(key, procedures)
        return procedures

    async def list_functions(
        self, schema: Optional[str] = None
    ) -> List[SQLServerRoutineInfo]:
        """List user-defined functions in *schema*."""
        key = self._cache.key(
            IntrospectionScope.TABLE, schema=schema, extra="functions"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.function_list_statement(schema=schema).to_sql()
        functions = self.parse_routines(
            await self._executor.execute(sql, params)
        )
        self._cache.set(key, functions)
        return functions

    async def list_sequences(
        self, schema: Optional[str] = None
    ) -> List[SQLServerSequenceInfo]:
        """List sequences in *schema* (``sys.sequences``)."""
        key = self._cache.key(IntrospectionScope.SEQUENCE, schema=schema)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.sequence_list_statement(schema=schema).to_sql()
        sequences = self.parse_sequences(
            await self._executor.execute(sql, params)
        )
        self._cache.set(key, sequences)
        return sequences

