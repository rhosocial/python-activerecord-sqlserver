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
from rhosocial.activerecord.backend.introspection.executor import (
    SyncIntrospectorExecutor,
    AsyncIntrospectorExecutor,
)
from rhosocial.activerecord.backend.introspection.types import (
    DatabaseInfo,
    TableInfo,
    TableType,
    ColumnInfo,
    ColumnNullable,
    IndexInfo,
    IndexColumnInfo,
    IndexType,
    ForeignKeyInfo,
    ReferentialAction,
    ViewInfo,
    TriggerInfo,
    IntrospectionScope,
)
from rhosocial.activerecord.backend.expression.types._base import DataType


class SQLServerIntrospectorMixin(IntrospectorMixin):
    """Shared non-I/O logic for SQL Server introspectors."""

    def _get_default_schema(self) -> str:
        return "dbo"

    def _get_version(self) -> tuple:
        return getattr(self._backend, '_version', (15, 0, 0))

    # ------------------------------------------------------------------
    # SQL builders
    # ------------------------------------------------------------------

    def _build_database_info_sql(self) -> Tuple[str, tuple]:
        return ("""
            SELECT
                DB_NAME() AS db_name,
                CAST(SERVERPROPERTY('ProductVersion') AS NVARCHAR(128)) AS version,
                CAST(SERVERPROPERTY('Collation') AS NVARCHAR(128)) AS collation,
                CAST(SERVERPROPERTY('Edition') AS NVARCHAR(128)) AS edition
        """, ())

    def _build_table_list_sql(
        self, schema: Optional[str], include_system: bool,
        include_views: bool = True, table_type: Optional[str] = None,
    ) -> Tuple[str, tuple]:
        target = schema or self._get_default_schema()
        params: List[str] = [target]
        conditions = ["TABLE_SCHEMA = ?"]
        if table_type:
            conditions.append("TABLE_TYPE = ?")
            params.append(table_type)
        elif not include_views:
            conditions.append("TABLE_TYPE = 'BASE TABLE'")
        where = " AND ".join(conditions)
        return (f"""
            SELECT TABLE_NAME, TABLE_TYPE
            FROM INFORMATION_SCHEMA.TABLES
            WHERE {where}
            ORDER BY TABLE_NAME
        """, tuple(params))

    def _build_column_info_sql(
        self, table: str, schema: Optional[str]
    ) -> Tuple[str, tuple]:
        target = schema or self._get_default_schema()
        return ("""
            SELECT
                c.COLUMN_NAME, c.DATA_TYPE, c.IS_NULLABLE,
                c.COLUMN_DEFAULT, c.CHARACTER_MAXIMUM_LENGTH,
                c.NUMERIC_PRECISION, c.NUMERIC_SCALE,
                c.ORDINAL_POSITION, c.COLLATION_NAME,
                COLUMNPROPERTY(
                    OBJECT_ID(c.TABLE_SCHEMA + '.' + c.TABLE_NAME),
                    c.COLUMN_NAME, 'IsIdentity'
                ) AS IS_IDENTITY
            FROM INFORMATION_SCHEMA.COLUMNS c
            WHERE c.TABLE_SCHEMA = ? AND c.TABLE_NAME = ?
            ORDER BY c.ORDINAL_POSITION
        """, (target, table))

    def _build_primary_key_sql(
        self, table: str, schema: str
    ) -> Tuple[str, tuple]:
        return ("""
            SELECT ccu.COLUMN_NAME
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
                ON tc.CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
                AND tc.TABLE_SCHEMA = ccu.TABLE_SCHEMA
            WHERE tc.TABLE_SCHEMA = ?
              AND tc.TABLE_NAME = ?
              AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
        """, (schema, table))

    def _build_index_info_sql(
        self, table: str, schema: Optional[str]
    ) -> Tuple[str, tuple]:
        target = schema or self._get_default_schema()
        return ("""
            SELECT
                i.name AS index,
                i.is_unique,
                i.is_primary_key,
                i.type_desc AS index_type,
                c.name AS column_name,
                ic.key_ordinal AS column_position,
                ic.is_descending_key
            FROM sys.indexes i
            JOIN sys.tables t ON i.object_id = t.object_id
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            JOIN sys.index_columns ic
                ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            JOIN sys.columns c
                ON ic.object_id = c.object_id AND ic.column_id = c.column_id
            WHERE s.name = ? AND t.name = ?
              AND i.name IS NOT NULL
            ORDER BY i.name, ic.key_ordinal
        """, (target, table))

    def _build_foreign_key_sql(
        self, table: str, schema: Optional[str]
    ) -> Tuple[str, tuple]:
        target = schema or self._get_default_schema()
        return ("""
            SELECT
                fk.name AS fk_name,
                COL_NAME(fc.parent_object_id, fc.parent_column_id) AS col_name,
                OBJECT_NAME(fk.referenced_object_id) AS ref_table,
                COL_NAME(fc.referenced_object_id, fc.referenced_column_id) AS ref_col,
                fk.delete_referential_action_desc AS on_delete,
                fk.update_referential_action_desc AS on_update,
                fc.constraint_column_id AS col_position
            FROM sys.foreign_keys fk
            JOIN sys.foreign_key_columns fc
                ON fk.object_id = fc.constraint_object_id
            JOIN sys.tables t ON fk.parent_object_id = t.object_id
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            WHERE s.name = ? AND t.name = ?
            ORDER BY fk.name, fc.constraint_column_id
        """, (target, table))

    def _build_view_list_sql(
        self, schema: Optional[str], include_system: bool
    ) -> Tuple[str, tuple]:
        target = schema or self._get_default_schema()
        return ("""
            SELECT TABLE_NAME AS view_name
            FROM INFORMATION_SCHEMA.VIEWS
            WHERE TABLE_SCHEMA = ?
            ORDER BY TABLE_NAME
        """, (target,))

    def _build_view_info_sql(
        self, view_name: str, schema: Optional[str]
    ) -> Tuple[str, tuple]:
        target = schema or self._get_default_schema()
        return ("""
            SELECT
                TABLE_NAME AS view_name,
                VIEW_DEFINITION AS definition,
                IS_UPDATABLE
            FROM INFORMATION_SCHEMA.VIEWS
            WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
        """, (target, view_name))

    def _build_trigger_list_sql(
        self, table: Optional[str], schema: Optional[str]
    ) -> Tuple[str, tuple]:
        target = schema or self._get_default_schema()
        params: List[str] = [target]
        table_filter = "AND t.name = ?" if table else ""
        if table:
            params.append(table)
        return (f"""
            SELECT
                tr.name AS trigger,
                t.name AS table,
                tr.is_disabled,
                tr.is_instead_of_trigger,
                OBJECT_DEFINITION(tr.object_id) AS definition
            FROM sys.triggers tr
            JOIN sys.tables t ON tr.parent_id = t.object_id
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            WHERE s.name = ? {table_filter}
            ORDER BY tr.name
        """, tuple(params))

    # ------------------------------------------------------------------
    # Parse methods — pure Python, no I/O
    # ------------------------------------------------------------------

    def _parse_database_info(self, rows: List[Dict[str, Any]]) -> DatabaseInfo:
        row = rows[0] if rows else {}
        version_str = row.get("version", "Unknown")
        parts = version_str.split(".")
        try:
            version_tuple = tuple(int(p) for p in parts[:3])
        except (ValueError, IndexError):
            version_tuple = (0, 0, 0)
        return DatabaseInfo(
            name=row.get("db_name", ""),
            version=version_str,
            version_tuple=version_tuple,
            vendor="SQL Server",
            encoding=None,
            collation=row.get("collation"),
        )

    def _parse_tables(
        self, rows: List[Dict[str, Any]], schema: Optional[str]
    ) -> List[TableInfo]:
        target = schema or self._get_default_schema()
        return [
            TableInfo(
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
        self, rows: List[Dict[str, Any]], table: str, schema: str,
        primary_keys: Optional[List[str]] = None,
    ) -> List[ColumnInfo]:
        pk_set = set(primary_keys or [])
        columns: List[ColumnInfo] = []
        for row in rows:
            data_type = (row.get("DATA_TYPE") or "").lower()
            max_len = row.get("CHARACTER_MAXIMUM_LENGTH")
            precision = row.get("NUMERIC_PRECISION")
            scale = row.get("NUMERIC_SCALE")

            if max_len and max_len > 0:
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

            columns.append(ColumnInfo(
                name=col_name,
                table_name=table,
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
        self, rows: List[Dict[str, Any]], table: str, schema: str
    ) -> List[IndexInfo]:
        type_map = {
            "CLUSTERED": IndexType.BTREE,
            "NONCLUSTERED": IndexType.BTREE,
            "HEAP": IndexType.BTREE,
        }
        index_map: Dict[str, IndexInfo] = {}
        for row in rows:
            idx_name = row.get("index", "")
            if idx_name not in index_map:
                idx_type_str = (row.get("index_type") or "").upper()
                index_map[idx_name] = IndexInfo(
                    name=idx_name,
                    table_name=table,
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
        self, rows: List[Dict[str, Any]], table: str, schema: str
    ) -> List[ForeignKeyInfo]:
        action_map = {
            "NO_ACTION": ReferentialAction.NO_ACTION,
            "CASCADE": ReferentialAction.CASCADE,
            "SET_NULL": ReferentialAction.SET_NULL,
            "SET_DEFAULT": ReferentialAction.SET_DEFAULT,
        }
        fk_map: Dict[str, ForeignKeyInfo] = {}
        for row in rows:
            fk_name = row.get("fk_name", "")
            if fk_name not in fk_map:
                on_del = (row.get("on_delete") or "NO_ACTION").upper()
                on_upd = (row.get("on_update") or "NO_ACTION").upper()
                fk_map[fk_name] = ForeignKeyInfo(
                    name=fk_name,
                    table_name=table,
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
    ) -> List[ViewInfo]:
        return [
            ViewInfo(
                name=row.get("view_name", ""),
                schema=schema,
                definition=None,
            )
            for row in rows
        ]

    def _parse_view_info(
        self, rows: List[Dict[str, Any]], view_name: str, schema: str
    ) -> Optional[ViewInfo]:
        if not rows:
            return None
        row = rows[0]
        return ViewInfo(
            name=row.get("view_name", view_name),
            schema=schema,
            definition=row.get("definition"),
            is_updatable=row.get("IS_UPDATABLE") == "YES",
        )

    def _parse_triggers(
        self, rows: List[Dict[str, Any]], schema: str
    ) -> List[TriggerInfo]:
        return [
            TriggerInfo(
                name=row.get("trigger", ""),
                table_name=row.get("table", ""),
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
        self, backend: Any, executor: SyncIntrospectorExecutor
    ) -> None:
        super().__init__(backend, executor)

    def get_table_info(
        self, table: str, schema: Optional[str] = None
    ) -> Optional[TableInfo]:
        key = self._make_cache_key(
            IntrospectionScope.TABLE, table, schema=schema
        )
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        tables = self.list_tables(schema)
        found = next(
            (t for t in tables if t.name == table), None
        )
        if found is None:
            return None

        info = copy.copy(found)
        info.columns = self.list_columns(table, schema)
        info.indexes = self.list_indexes(table, schema)
        info.foreign_keys = self.list_foreign_keys(table, schema)
        self._set_cached(key, info)
        return info

    def list_columns(
        self, table: str, schema: Optional[str] = None
    ) -> List[ColumnInfo]:
        target = schema if schema is not None else self._get_default_schema()
        key = self._make_cache_key(
            IntrospectionScope.COLUMN, table, schema=target
        )
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        pk_sql, pk_params = self._build_primary_key_sql(table, target)
        pk_rows = self._executor.execute(pk_sql, pk_params)
        primary_keys = [r.get("COLUMN_NAME") for r in pk_rows]

        sql, params = self._build_column_info_sql(table, schema)
        rows = self._executor.execute(sql, params)
        columns = self._parse_columns(
            rows, table, target, primary_keys
        )
        self._set_cached(key, columns)
        return columns


class AsyncSQLServerIntrospector(
    SQLServerIntrospectorMixin, AsyncAbstractIntrospector
):
    """Asynchronous introspector for SQL Server backends."""

    def __init__(
        self, backend: Any, executor: AsyncIntrospectorExecutor
    ) -> None:
        super().__init__(backend, executor)

    async def get_table_info(
        self, table: str, schema: Optional[str] = None
    ) -> Optional[TableInfo]:
        key = self._make_cache_key(
            IntrospectionScope.TABLE, table, schema=schema
        )
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        tables = await self.list_tables(schema)
        found = next(
            (t for t in tables if t.name == table), None
        )
        if found is None:
            return None

        info = copy.copy(found)
        info.columns = await self.list_columns(table, schema)
        info.indexes = await self.list_indexes(table, schema)
        info.foreign_keys = await self.list_foreign_keys(
            table, schema
        )
        self._set_cached(key, info)
        return info

    async def list_columns(
        self, table: str, schema: Optional[str] = None
    ) -> List[ColumnInfo]:
        target = schema if schema is not None else self._get_default_schema()
        key = self._make_cache_key(
            IntrospectionScope.COLUMN, table, schema=target
        )
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        pk_sql, pk_params = self._build_primary_key_sql(table, target)
        pk_rows = await self._executor.execute(pk_sql, pk_params)
        primary_keys = [r.get("COLUMN_NAME") for r in pk_rows]

        sql, params = self._build_column_info_sql(table, schema)
        rows = await self._executor.execute(sql, params)
        columns = self._parse_columns(
            rows, table, target, primary_keys
        )
        self._set_cached(key, columns)
        return columns
