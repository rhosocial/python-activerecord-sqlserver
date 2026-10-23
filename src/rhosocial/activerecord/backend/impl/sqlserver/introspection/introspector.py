# src/rhosocial/activerecord/backend/impl/sqlserver/introspection/introspector.py
"""SQL Server concrete introspectors.

Implements SyncAbstractIntrospector and AsyncAbstractIntrospector for SQL Server
using INFORMATION_SCHEMA and sys.* catalog views.
"""

import copy
from typing import Any, Dict, List, Optional, Tuple

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

from ..query_nodes import SQLServerNodeBuilderMixin

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


class SQLServerIntrospectorMixin(SQLServerNodeBuilderMixin, IntrospectorMixin):
    """Shared non-I/O logic for SQL Server introspectors."""

    def _get_default_schema(self) -> str:
        return "dbo"

    def _get_version(self) -> tuple:
        return getattr(self._backend, '_version', (15, 0, 0))

    # ------------------------------------------------------------------
    # SQL builders
    #
    # Every query below is a QueryStatement over catalogue relations built
    # from expression nodes; the dialect writes the SQL. What each query
    # *asks* is then a structure the rest of the framework can inspect,
    # instead of text assembled one clause at a time in this layer.
    #
    # The parameter positions are the ones the concatenated form used: a
    # schema or table name it bound stays bound, and a value it wrote into
    # the statement (``'BASE TABLE'``, ``'PRIMARY KEY'``, ``'IsIdentity'``)
    # stays an inline literal, so every caller keeps the parameter tuple it
    # already had.
    # ------------------------------------------------------------------

    def _cast_server_property(self, name: str, alias: Optional[str] = None):
        """``CAST(SERVERPROPERTY('<name>') AS NVARCHAR(128))``, optionally aliased.

        The property name is a literal of the statement, not data, so it stays
        inline: the request carries no parameters.
        """
        from rhosocial.activerecord.backend.expression import FunctionCall
        from ..expression.types import SQLServerNVarCharType

        node = FunctionCall(
            self.dialect, "SERVERPROPERTY", self._lit(name, inline=True)
        ).cast(SQLServerNVarCharType(self.dialect, 128))
        return node.as_(alias) if alias else node

    def _build_database_info_sql(self) -> Tuple[str, tuple]:
        from rhosocial.activerecord.backend.expression import FunctionCall

        # No FROM: this query reads no table, it asks the engine a question.
        return self._select(
            [
                FunctionCall(self.dialect, "DB_NAME", alias="db_name"),
                self._cast_server_property("ProductVersion", "version"),
                self._cast_server_property("Collation", "collation"),
                self._cast_server_property("Edition", "edition"),
            ]
        )

    def _build_table_list_sql(
        self, schema: Optional[str], include_system: bool,
        include_views: bool = True, table_type: Optional[str] = None,
    ) -> Tuple[str, tuple]:
        target = schema or self._get_default_schema()
        conditions = [self._eq(self._col("TABLE_SCHEMA"), self._lit(target))]
        if table_type:
            conditions.append(self._eq(self._col("TABLE_TYPE"), self._lit(table_type)))
        elif not include_views:
            conditions.append(
                self._eq(self._col("TABLE_TYPE"), self._lit("BASE TABLE", inline=True))
            )
        return self._select(
            [self._col("TABLE_NAME"), self._col("TABLE_TYPE")],
            from_=self._relation("TABLES", "INFORMATION_SCHEMA"),
            where=self._and(*conditions),
            order_by=[self._col("TABLE_NAME")],
        )

    def _build_column_info_sql(
        self, table_name: str, schema: Optional[str]
    ) -> Tuple[str, tuple]:
        from rhosocial.activerecord.backend.expression import FunctionCall
        from rhosocial.activerecord.backend.expression.operators import (
            ArithmeticOperation,
            ArithmeticOperator,
        )

        target = schema or self._get_default_schema()
        # OBJECT_ID takes the qualified object name as one string. SQL Server
        # spells string concatenation with ``+`` (``||`` only from 2025), so
        # this is the arithmetic ``add`` node, not the standard concatenation.
        qualified_name = ArithmeticOperation(
            self.dialect,
            ArithmeticOperator.ADD,
            ArithmeticOperation(
                self.dialect,
                ArithmeticOperator.ADD,
                self._col("TABLE_SCHEMA", "c"),
                self._lit(".", inline=True),
            ),
            self._col("TABLE_NAME", "c"),
        )
        is_identity = FunctionCall(
            self.dialect,
            "COLUMNPROPERTY",
            FunctionCall(self.dialect, "OBJECT_ID", qualified_name),
            self._col("COLUMN_NAME", "c"),
            self._lit("IsIdentity", inline=True),
            alias="IS_IDENTITY",
        )
        return self._select(
            [
                self._col("COLUMN_NAME", "c"),
                self._col("DATA_TYPE", "c"),
                self._col("IS_NULLABLE", "c"),
                self._col("COLUMN_DEFAULT", "c"),
                self._col("CHARACTER_MAXIMUM_LENGTH", "c"),
                self._col("NUMERIC_PRECISION", "c"),
                self._col("NUMERIC_SCALE", "c"),
                self._col("DATETIME_PRECISION", "c"),
                self._col("ORDINAL_POSITION", "c"),
                self._col("COLLATION_NAME", "c"),
                is_identity,
            ],
            from_=self._relation("COLUMNS", "INFORMATION_SCHEMA", alias="c"),
            where=self._and(
                self._eq(self._col("TABLE_SCHEMA", "c"), self._lit(target)),
                self._eq(self._col("TABLE_NAME", "c"), self._lit(table_name)),
            ),
            order_by=[self._col("ORDINAL_POSITION", "c")],
        )

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

    def _build_index_info_sql(
        self, table_name: str, schema: Optional[str]
    ) -> Tuple[str, tuple]:
        from rhosocial.activerecord.backend.expression import IsNullPredicate, JoinClause

        target = schema or self._get_default_schema()
        joins = JoinClause(
            self.dialect,
            JoinClause(
                self.dialect,
                JoinClause(
                    self.dialect,
                    JoinClause(
                        self.dialect,
                        self._relation("indexes", "sys", alias="i"),
                        self._relation("tables", "sys", alias="t"),
                        join_type="JOIN",
                        condition=self._eq(
                            self._col("object_id", "i"), self._col("object_id", "t")
                        ),
                    ),
                    self._relation("schemas", "sys", alias="s"),
                    join_type="JOIN",
                    condition=self._eq(
                        self._col("schema_id", "t"), self._col("schema_id", "s")
                    ),
                ),
                self._relation("index_columns", "sys", alias="ic"),
                join_type="JOIN",
                condition=self._and(
                    self._eq(self._col("object_id", "i"), self._col("object_id", "ic")),
                    self._eq(self._col("index_id", "i"), self._col("index_id", "ic")),
                ),
            ),
            self._relation("columns", "sys", alias="c"),
            join_type="JOIN",
            condition=self._and(
                self._eq(self._col("object_id", "ic"), self._col("object_id", "c")),
                self._eq(self._col("column_id", "ic"), self._col("column_id", "c")),
            ),
        )
        return self._select(
            [
                self._col("name", "i", alias="index_name"),
                self._col("is_unique", "i"),
                self._col("is_primary_key", "i"),
                self._col("type_desc", "i", alias="index_type"),
                self._col("name", "c", alias="column_name"),
                self._col("key_ordinal", "ic", alias="column_position"),
                self._col("is_descending_key", "ic"),
            ],
            from_=joins,
            where=self._and(
                self._eq(self._col("name", "s"), self._lit(target)),
                self._eq(self._col("name", "t"), self._lit(table_name)),
                IsNullPredicate(self.dialect, self._col("name", "i"), is_not=True),
            ),
            order_by=[self._col("name", "i"), self._col("key_ordinal", "ic")],
        )

    def _build_foreign_key_sql(
        self, table_name: str, schema: Optional[str]
    ) -> Tuple[str, tuple]:
        from rhosocial.activerecord.backend.expression import FunctionCall, JoinClause

        target = schema or self._get_default_schema()
        joins = JoinClause(
            self.dialect,
            JoinClause(
                self.dialect,
                JoinClause(
                    self.dialect,
                    self._relation("foreign_keys", "sys", alias="fk"),
                    self._relation("foreign_key_columns", "sys", alias="fc"),
                    join_type="JOIN",
                    condition=self._eq(
                        self._col("object_id", "fk"),
                        self._col("constraint_object_id", "fc"),
                    ),
                ),
                self._relation("tables", "sys", alias="t"),
                join_type="JOIN",
                condition=self._eq(
                    self._col("parent_object_id", "fk"), self._col("object_id", "t")
                ),
            ),
            self._relation("schemas", "sys", alias="s"),
            join_type="JOIN",
            condition=self._eq(
                self._col("schema_id", "t"), self._col("schema_id", "s")
            ),
        )
        return self._select(
            [
                self._col("name", "fk", alias="fk_name"),
                FunctionCall(
                    self.dialect,
                    "COL_NAME",
                    self._col("parent_object_id", "fc"),
                    self._col("parent_column_id", "fc"),
                    alias="col_name",
                ),
                FunctionCall(
                    self.dialect,
                    "OBJECT_NAME",
                    self._col("referenced_object_id", "fk"),
                    alias="ref_table",
                ),
                FunctionCall(
                    self.dialect,
                    "COL_NAME",
                    self._col("referenced_object_id", "fc"),
                    self._col("referenced_column_id", "fc"),
                    alias="ref_col",
                ),
                self._col("delete_referential_action_desc", "fk", alias="on_delete"),
                self._col("update_referential_action_desc", "fk", alias="on_update"),
                self._col("constraint_column_id", "fc", alias="col_position"),
            ],
            from_=joins,
            where=self._and(
                self._eq(self._col("name", "s"), self._lit(target)),
                self._eq(self._col("name", "t"), self._lit(table_name)),
            ),
            order_by=[
                self._col("name", "fk"),
                self._col("constraint_column_id", "fc"),
            ],
        )

    def _build_view_list_sql(
        self, schema: Optional[str], include_system: bool
    ) -> Tuple[str, tuple]:
        target = schema or self._get_default_schema()
        return self._select(
            [self._col("TABLE_NAME", alias="view_name")],
            from_=self._relation("VIEWS", "INFORMATION_SCHEMA"),
            where=self._eq(self._col("TABLE_SCHEMA"), self._lit(target)),
            order_by=[self._col("TABLE_NAME")],
        )

    def _build_view_info_sql(
        self, view_name: str, schema: Optional[str]
    ) -> Tuple[str, tuple]:
        target = schema or self._get_default_schema()
        return self._select(
            [
                self._col("TABLE_NAME", alias="view_name"),
                self._col("VIEW_DEFINITION", alias="definition"),
                self._col("IS_UPDATABLE"),
            ],
            from_=self._relation("VIEWS", "INFORMATION_SCHEMA"),
            where=self._and(
                self._eq(self._col("TABLE_SCHEMA"), self._lit(target)),
                self._eq(self._col("TABLE_NAME"), self._lit(view_name)),
            ),
        )

    def _build_trigger_list_sql(
        self, table_name: Optional[str], schema: Optional[str]
    ) -> Tuple[str, tuple]:
        from rhosocial.activerecord.backend.expression import FunctionCall, JoinClause

        target = schema or self._get_default_schema()
        joins = JoinClause(
            self.dialect,
            JoinClause(
                self.dialect,
                self._relation("triggers", "sys", alias="tr"),
                self._relation("tables", "sys", alias="t"),
                join_type="JOIN",
                condition=self._eq(
                    self._col("parent_id", "tr"), self._col("object_id", "t")
                ),
            ),
            self._relation("schemas", "sys", alias="s"),
            join_type="JOIN",
            condition=self._eq(
                self._col("schema_id", "t"), self._col("schema_id", "s")
            ),
        )
        conditions = [self._eq(self._col("name", "s"), self._lit(target))]
        if table_name:
            conditions.append(self._eq(self._col("name", "t"), self._lit(table_name)))
        return self._select(
            [
                self._col("name", "tr", alias="trigger_name"),
                self._col("name", "t", alias="table_name"),
                self._col("is_disabled", "tr"),
                self._col("is_instead_of_trigger", "tr"),
                FunctionCall(
                    self.dialect,
                    "OBJECT_DEFINITION",
                    self._col("object_id", "tr"),
                    alias="definition",
                ),
            ],
            from_=joins,
            where=self._and(*conditions),
            order_by=[self._col("name", "tr")],
        )

    # ------------------------------------------------------------------
    # Parse methods — pure Python, no I/O
    # ------------------------------------------------------------------

    def _parse_database_info(self, rows: List[Dict[str, Any]]) -> IntrospectionDatabaseInfo:
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

    def _parse_tables(
        self, rows: List[Dict[str, Any]], schema: Optional[str]
    ) -> List[IntrospectionTableInfo]:
        target = schema or self._get_default_schema()
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

    def _parse_columns(
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

    def _parse_indexes(
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

    def _parse_foreign_keys(
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

    def _parse_views(
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

    def _parse_view_info(
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

    def _parse_triggers(
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
        target = schema if schema is not None else self._get_default_schema()
        key = self._cache.key(
            IntrospectionScope.COLUMN, table_name, schema=target
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        pk_sql, pk_params = self._build_primary_key_sql(table_name, target)
        pk_rows = self._executor.execute(pk_sql, pk_params)
        primary_keys = [r.get("COLUMN_NAME") for r in pk_rows]

        sql, params = self._build_column_info_sql(table_name, schema)
        rows = self._executor.execute(sql, params)
        columns = self._parse_columns(
            rows, table_name, target, primary_keys
        )
        self._cache.set(key, columns)
        return columns


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
        target = schema if schema is not None else self._get_default_schema()
        key = self._cache.key(
            IntrospectionScope.COLUMN, table_name, schema=target
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        pk_sql, pk_params = self._build_primary_key_sql(table_name, target)
        pk_rows = await self._executor.execute(pk_sql, pk_params)
        primary_keys = [r.get("COLUMN_NAME") for r in pk_rows]

        sql, params = self._build_column_info_sql(table_name, schema)
        rows = await self._executor.execute(sql, params)
        columns = self._parse_columns(
            rows, table_name, target, primary_keys
        )
        self._cache.set(key, columns)
        return columns
