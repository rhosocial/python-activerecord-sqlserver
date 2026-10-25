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

#: The ``sys.extended_properties.class_desc`` values SQL Server documents.
#: The property table is shared by objects, columns, schemas, indexes,
#: parameters and so on, and ``major_id``/``minor_id`` mean something
#: different for each; accepting a name outside this set would silently
#: return nothing instead of saying the family is unknown.
_EXTENDED_PROPERTY_CLASSES = frozenset({
    "DATABASE",
    "OBJECT_OR_COLUMN",
    "PARAMETER",
    "SCHEMA",
    "DATABASE_PRINCIPAL",
    "ASSEMBLY",
    "TYPE",
    "INDEX",
    "XML_SCHEMA_COLLECTION",
    "XML_SCHEMA_NAMESPACE",
    "TYPE_SCHEMA",
    "XML_INDEX",
    "PLAN_GUIDE",
})

#: ``sys.objects.type`` codes for user-defined functions: scalar (``FN``),
#: inline table-valued (``IF``), multi-statement table-valued (``TF``),
#: CLR scalar (``FS``) and CLR table-valued (``FT``). ``sys.procedures``
#: covers the procedure half.
_FUNCTION_TYPE_CODES = ("FN", "IF", "TF", "FS", "FT")

#: ``sys.sequences`` stores these as ``sql_variant``. The ODBC driver refuses
#: to fetch that type (``HY106``), so every one of them is cast to text in the
#: statement and parsed back here. Keeping the list in one place is what stops
#: a later column from being added to the projection without its cast.
_SEQUENCE_NUMERIC_COLUMNS = (
    "start_value",
    "increment",
    "minimum_value",
    "maximum_value",
    "current_value",
)



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
    # Backend-specific questions
    #
    # Every family core models is a statement its dialect renders; this
    # layer constructs it and executes what comes back. What core has no
    # statement for is built here -- the primary key is SQL Server's own
    # question, and so are the families below it. Each is a tree of the same
    # expression nodes, and each carries the family name into its cache key
    # (see the managers below) so two families never answer each other's
    # question.
    # ------------------------------------------------------------------

    def _build_primary_key_sql(
        self, table_name: str, schema: str
    ) -> Tuple[str, tuple]:
        from rhosocial.activerecord.backend.expression import JoinClause

        # The two catalogue views are joined on the constraint name *and* the
        # schema, so a same-named constraint in another schema cannot contribute
        # a column to this table's key.
        join = JoinClause(
            self.dialect,
            self._relation("TABLE_CONSTRAINTS", "INFORMATION_SCHEMA", alias="tc"),
            self._relation("CONSTRAINT_COLUMN_USAGE", "INFORMATION_SCHEMA", alias="ccu"),
            join_type="JOIN",
            condition=self._and(
                self._eq(
                    self._col("CONSTRAINT_NAME", "tc"),
                    self._col("CONSTRAINT_NAME", "ccu"),
                ),
                self._eq(
                    self._col("TABLE_SCHEMA", "tc"), self._col("TABLE_SCHEMA", "ccu")
                ),
            ),
        )
        return self._select(
            [self._col("COLUMN_NAME", "ccu")],
            from_=join,
            where=self._and(
                self._eq(self._col("TABLE_SCHEMA", "tc"), self._lit(schema)),
                self._eq(self._col("TABLE_NAME", "tc"), self._lit(table_name)),
                self._eq(
                    self._col("CONSTRAINT_TYPE", "tc"),
                    self._lit("PRIMARY KEY", inline=True),
                ),
            ),
        )

    def _build_schema_list_sql(self) -> Tuple[str, tuple]:
        """``sys.schemas`` with the owning principal's name.

        ``sys.schemas`` is joined to ``sys.database_principals`` on
        ``principal_id`` -- not on ``name`` -- because a schema and its owner
        need not share a name. The join is a ``LEFT JOIN``: the catalogue
        keeps a schema after its owning principal is dropped, leaving
        ``principal_id`` dangling, and that row is still a schema.
        """
        joined = self._join(
            self._relation("schemas", "sys", alias="s"),
            self._relation("database_principals", "sys", alias="p"),
            join_type="LEFT JOIN",
            condition=self._eq(
                self._col("principal_id", "s"), self._col("principal_id", "p")
            ),
        )
        return self._select(
            [
                self._col("schema_id", "s"),
                self._col("name", "s", alias="schema_name"),
                self._col("name", "p", alias="owner"),
            ],
            from_=joined,
            order_by=[self._col("name", "s")],
        )

    def _build_extended_property_list_sql(
        self,
        major_id: int,
        minor_id: Optional[int],
        class_name: str,
        schema: Optional[str],
    ) -> Tuple[str, tuple]:
        """``sys.extended_properties`` for one object, optionally one column.

        ``value`` is ``sql_variant`` and the driver cannot fetch it, so it is
        cast to ``NVARCHAR(4000)`` in the statement: the property text is
        what a caller wants, and truncation beyond 4000 characters is
        impossible to avoid without a second round trip.

        The schema filter is the one part that is not a column of
        ``sys.extended_properties``: it resolves ``major_id`` through
        ``sys.objects`` and ``sys.schemas``. That join only means something
        for the object-scoped classes (``OBJECT_OR_COLUMN`` above all), so
        asking for a schema while listing, say, ``DATABASE`` properties is a
        contradiction rather than an empty answer -- refused before the
        query is built.
        """
        if class_name not in _EXTENDED_PROPERTY_CLASSES:
            raise ValueError(
                f"unknown extended-property class {class_name!r}; "
                f"expected one of {sorted(_EXTENDED_PROPERTY_CLASSES)}"
            )
        if schema is not None and class_name not in ("OBJECT_OR_COLUMN", "INDEX"):
            raise ValueError(
                f"a schema can only narrow object-scoped extended properties; "
                f"{class_name!r} has no schema"
            )

        joined = self._join(
            self._relation("extended_properties", "sys", alias="ep"),
            self._relation("objects", "sys", alias="o"),
            join_type="LEFT JOIN",
            condition=self._eq(
                self._col("major_id", "ep"), self._col("object_id", "o")
            ),
        )
        joined = self._join(
            joined,
            self._relation("schemas", "sys", alias="s"),
            join_type="LEFT JOIN",
            condition=self._eq(
                self._col("schema_id", "o"), self._col("schema_id", "s")
            ),
        )

        conditions = [
            self._eq(self._col("major_id", "ep"), self._lit(major_id)),
            self._eq(self._col("class_desc", "ep"), self._lit(class_name)),
        ]
        if minor_id is not None:
            conditions.append(
                self._eq(self._col("minor_id", "ep"), self._lit(minor_id))
            )
        if schema is not None:
            conditions.append(self._eq(self._col("name", "s"), self._lit(schema)))

        return self._select(
            [
                self._col("class", "ep", alias="class_id"),
                self._col("class_desc", "ep", alias="class_name"),
                self._col("major_id", "ep", alias="major_id"),
                self._col("minor_id", "ep", alias="minor_id"),
                self._col("name", "ep", alias="property_name"),
                self._cast(
                    self._col("value", "ep"), "NVARCHAR(4000)"
                ).as_("property_value"),
            ],
            from_=joined,
            where=self._and(*conditions),
            order_by=[self._col("minor_id", "ep"), self._col("name", "ep")],
        )

    def _build_routine_list_sql(
        self, type_codes: Tuple[str, ...], schema: Optional[str]
    ) -> Tuple[str, tuple]:
        """Schema-scoped routines of the given ``sys.objects.type`` codes.

        One builder for both families: a procedure is a routine whose
        ``sys.objects.type`` is ``P``/``PC`` and a function is one of the
        ``FN``/``IF``/``TF``/``FS``/``FT`` codes. What differs is the code
        set, and that is the argument.
        """
        target = schema or self.default_schema
        joined = self._join(
            self._relation("objects", "sys", alias="o"),
            self._relation("schemas", "sys", alias="s"),
            join_type="JOIN",
            condition=self._eq(
                self._col("schema_id", "o"), self._col("schema_id", "s")
            ),
        )
        return self._select(
            [
                self._col("name", "o", alias="routine_name"),
                self._col("name", "s", alias="schema_name"),
                self._col("type", "o", alias="type_code"),
                self._col("type_desc", "o"),
                self._col("create_date", "o", alias="created_at"),
                self._col("modify_date", "o", alias="modified_at"),
                self._col("is_ms_shipped", "o"),
            ],
            from_=joined,
            where=self._and(
                self._in(self._col("type", "o"), type_codes),
                self._eq(self._col("name", "s"), self._lit(target)),
            ),
            order_by=[self._col("name", "o")],
        )

    def _build_procedure_list_sql(
        self, schema: Optional[str]
    ) -> Tuple[str, tuple]:
        """Stored procedures: ``sys.objects`` types ``P`` and ``PC``."""
        return self._build_routine_list_sql(("P", "PC"), schema)

    def _build_function_list_sql(
        self, schema: Optional[str]
    ) -> Tuple[str, tuple]:
        """User-defined functions: the five ``sys.objects`` function codes."""
        return self._build_routine_list_sql(_FUNCTION_TYPE_CODES, schema)

    def _build_sequence_list_sql(
        self, schema: Optional[str]
    ) -> Tuple[str, tuple]:
        """``sys.sequences`` with every ``sql_variant`` value cast to text.

        ``start_value``/``increment``/``minimum_value``/``maximum_value``/
        ``current_value`` are ``sql_variant``. pyodbc raises
        ``ODBC SQL type -25 is not yet supported`` on the very first of them,
        so a projection that selected them raw could not be fetched at all --
        which is why the cast is in the statement rather than the parser.
        """
        target = schema or self.default_schema
        joined = self._join(
            self._relation("sequences", "sys", alias="q"),
            self._relation("schemas", "sys", alias="s"),
            join_type="JOIN",
            condition=self._eq(
                self._col("schema_id", "q"), self._col("schema_id", "s")
            ),
        )
        projection = [
            self._col("name", "q", alias="sequence_name"),
            self._col("name", "s", alias="schema_name"),
            self._fn(
                "TYPE_NAME", self._col("user_type_id", "q"), alias="data_type"
            ),
        ]
        for column in _SEQUENCE_NUMERIC_COLUMNS:
            projection.append(
                self._cast(
                    self._col(column, "q"), "NVARCHAR(64)"
                ).as_(column)
            )
        projection.extend(
            [
                self._col("is_cycling", "q"),
                self._col("is_cached", "q"),
                self._cast(self._col("cache_size", "q"), "BIGINT").as_(
                    "cache_size"
                ),
            ]
        )
        return self._select(
            projection,
            from_=joined,
            where=self._eq(self._col("name", "s"), self._lit(target)),
            order_by=[self._col("name", "q")],
        )

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

        pk_sql, pk_params = self._build_primary_key_sql(table_name, target)
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

        sql, params = self._build_schema_list_sql()
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

        sql, params = self._build_extended_property_list_sql(
            major_id, minor_id, class_name, schema
        )
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

        sql, params = self._build_procedure_list_sql(schema)
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

        sql, params = self._build_function_list_sql(schema)
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

        sql, params = self._build_sequence_list_sql(schema)
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

        pk_sql, pk_params = self._build_primary_key_sql(table_name, target)
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

        sql, params = self._build_schema_list_sql()
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

        sql, params = self._build_extended_property_list_sql(
            major_id, minor_id, class_name, schema
        )
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

        sql, params = self._build_procedure_list_sql(schema)
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

        sql, params = self._build_function_list_sql(schema)
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

        sql, params = self._build_sequence_list_sql(schema)
        sequences = self.parse_sequences(
            await self._executor.execute(sql, params)
        )
        self._cache.set(key, sequences)
        return sequences

