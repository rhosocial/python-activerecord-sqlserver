# src/rhosocial/activerecord/backend/impl/sqlserver/introspection/status_introspector.py
"""SQL Server status introspector.

Provides server status information by querying SQL Server DMVs:
sys.configurations, sys.dm_exec_sessions, sys.dm_os_performance_counters,
sys.databases, sys.server_principals, SERVERPROPERTY().

Every query below is built from expression nodes and rendered by the dialect
(org guide §16.2): this layer asks the catalogue a question, it does not spell
the SQL. The row shapes the parsers read -- the projection order and the
aliases -- are the ones the previous statement text produced, so the parsing
above and below is unchanged.
"""

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.introspection.status import (
    StatusItem,
    StatusCategory,
    ServerOverview,
    DatabaseBriefInfo,
    UserInfo,
    ConnectionInfo,
    StorageInfo,
    SessionInfo,
    SyncAbstractStatusIntrospector,
    AsyncAbstractStatusIntrospector,
)

from ..query_nodes import SQLServerNodeBuilderMixin

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class SQLServerStatusIntrospectorMixin(SQLServerNodeBuilderMixin):
    """Shared non-I/O logic for SQL Server status introspectors."""

    @property
    def dialect(self) -> "SQLDialectBase":
        """The dialect these status queries are rendered by."""
        return self._backend.dialect

    def _get_vendor_name(self) -> str:
        return "SQL Server"

    def _parse_value(self, value: Any) -> Any:
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return value

    def _create_status_item(
        self, name: str, value: Any, category: StatusCategory,
        description: Optional[str] = None, unit: Optional[str] = None,
        is_readonly: bool = True, is_dynamic: bool = False,
    ) -> StatusItem:
        return StatusItem(
            name=name, value=self._parse_value(value),
            category=category, description=description, unit=unit,
            is_readonly=is_readonly, is_dynamic=is_dynamic,
        )

    def _build_server_overview(
        self, version: str, session: SessionInfo,
        configuration: List[StatusItem], performance: List[StatusItem],
        connections: ConnectionInfo, storage: StorageInfo,
        databases: List[DatabaseBriefInfo], users: List[UserInfo],
    ) -> ServerOverview:
        return ServerOverview(
            server_version=version,
            server_vendor=self._get_vendor_name(),
            session=session,
            configuration=configuration + performance,
            connections=connections,
            storage=storage,
            databases=databases,
            users=users,
        )

    # ------------------------------------------------------------------
    # The status queries, expressed once for both sync and async
    # ------------------------------------------------------------------

    def _version_sql(self) -> Tuple[str, tuple]:
        """The engine's product version as text."""
        return self._select([self._cast(self._server_property("ProductVersion"), "NVARCHAR(128)")])

    def _server_property(self, name: str):
        """``SERVERPROPERTY('<name>')``; the name is part of the question."""
        return self._fn("SERVERPROPERTY", self._lit(name, inline=True))

    def _configuration_sql(self) -> Tuple[str, tuple]:
        """``sys.configurations``, one row per server setting, ordered by name."""
        return self._select(
            [
                self._col("name"),
                self._cast(self._col("value_in_use"), "NVARCHAR(4000)").as_("value_in_use"),
                self._col("is_dynamic"),
                self._col("is_advanced"),
            ],
            from_=self._relation("configurations", "sys"),
            order_by=[self._col("name")],
        )

    def _performance_metrics_sql(self, limit: Optional[int] = 50) -> Tuple[str, tuple]:
        """The busiest performance counters, highest first, capped at *limit*.

        The cap travels as the pagination node, which SQL Server spells
        ``OFFSET 0 ROWS FETCH NEXT n ROWS ONLY`` -- the same rows, in the same
        order, that ``SELECT TOP 50`` returned. That spelling is 2012+, so the
        caller passes ``None`` on an older server: the ordering still holds and
        every counter is read, where dropping the cap into an unsupported
        clause would raise and the caller's handler would report no metrics at
        all. Both shapes are the dialect's; the choice between them is this
        backend's.
        """
        return self._select(
            [
                self._fn("RTRIM", self._col("counter_name"), alias="counter_name"),
                self._col("cntr_value"),
                self._fn("RTRIM", self._col("object_name"), alias="object_name"),
            ],
            from_=self._relation("dm_os_performance_counters", "sys"),
            where=self._gt(self._col("cntr_value"), self._lit(0, inline=True)),
            order_by=[(self._col("cntr_value"), "DESC")],
            limit=limit,
        )

    def _performance_metrics_limit(self) -> Optional[int]:
        """The row cap to ask for, or ``None`` where pagination is unavailable.

        SQL Server learned ``OFFSET``/``FETCH`` in 2012. An unadapted dialect
        (no version yet) is treated as current: the backend adapts before the
        status introspector runs, and guessing "old" would silently uncap a
        modern server.
        """
        from ..mixins.version_constants import SQL_SERVER_2012

        try:
            version = self.dialect.version
        except Exception:
            return 50
        return 50 if version >= SQL_SERVER_2012 else None

    def _connection_info_sql(self) -> Tuple[str, tuple]:
        """Live connection count plus the server's configured ceiling.

        Both halves are scalar subqueries: they read different catalogues, and
        the row is one row of answers rather than a join.
        """
        return self._select(
            [
                self._subquery(
                    [self._fn("COUNT", self._row_count_wildcard())],
                    from_=self._relation("dm_exec_connections", "sys"),
                    alias="active",
                ),
                self._subquery(
                    [self._cast(self._col("value_in_use"), "INT")],
                    from_=self._relation("configurations", "sys"),
                    where=self._eq(
                        self._col("name"), self._lit("user connections", inline=True)
                    ),
                    alias="max_conn",
                ),
            ]
        )

    def _storage_info_sql(self) -> Tuple[str, tuple]:
        """Total bytes across the file set, in the engine's 8 KiB page units."""
        size_bytes = self._mul(
            self._mul(self._col("size"), self._lit(8, inline=True)),
            self._lit(1024, inline=True),
        )
        return self._select(
            [self._fn("SUM", size_bytes, alias="total_bytes")],
            from_=self._relation("master_files", "sys"),
            where=self._gt(self._col("database_id"), self._lit(0, inline=True)),
        )

    def _database_list_sql(self) -> Tuple[str, tuple]:
        """Each database with its data-file bytes (``mf.type = 0``)."""
        size_bytes = self._mul(
            self._mul(self._col("size", "mf"), self._lit(8, inline=True)),
            self._lit(1024, inline=True),
        )
        joins = self._join(
            self._relation("databases", "sys", alias="d"),
            self._relation("master_files", "sys", alias="mf"),
            join_type="LEFT JOIN",
            condition=self._and(
                self._eq(
                    self._col("database_id", "d"), self._col("database_id", "mf")
                ),
                self._eq(self._col("type", "mf"), self._lit(0, inline=True)),
            ),
        )
        return self._select(
            [
                self._col("name", "d", alias="db_name"),
                self._fn("SUM", size_bytes, alias="size_bytes"),
            ],
            from_=joins,
            group_by=[self._col("name", "d")],
            order_by=[self._col("name", "d")],
        )

    def _user_list_sql(self) -> Tuple[str, tuple]:
        """Server principals that can log in, with the sysadmin flag."""
        return self._select(
            [
                self._col("name"),
                self._col("type_desc"),
                self._fn(
                    "IS_SRVROLEMEMBER",
                    self._lit("sysadmin", inline=True),
                    self._col("name"),
                    alias="is_sysadmin",
                ),
            ],
            from_=self._relation("server_principals", "sys"),
            where=self._in(self._col("type"), ("S", "U", "G")),
            order_by=[self._col("name")],
        )

    def _session_info_sql(self) -> Tuple[str, tuple]:
        """The current session: login, database, host, transport, TLS flag.

        ``SYSTEM_USER`` is the niladic value function, not a column of that
        name, so it is built as a call with no parentheses; quoting it as an
        identifier would ask the catalogue for a column instead.
        """
        return self._select(
            [
                self._fn("SYSTEM_USER", alias="session_user", niladic=True),
                self._fn("DB_NAME", alias="cur_db"),
                self._fn("HOST_NAME", alias="host"),
                self._fn(
                    "CONNECTIONPROPERTY",
                    self._lit("net_transport", inline=True),
                    alias="transport",
                ),
                self._fn(
                    "CONNECTIONPROPERTY",
                    self._lit("encrypt_option", inline=True),
                    alias="encrypt",
                ),
            ]
        )



class SyncSQLServerStatusIntrospector(SQLServerStatusIntrospectorMixin, SyncAbstractStatusIntrospector):
    """Synchronous SQL Server status introspector."""

    def _execute_query(self, sql: str) -> List[tuple]:
        cursor = self._backend._get_cursor()
        try:
            cursor.execute(sql)
            return cursor.fetchall()
        finally:
            cursor.close()

    def _execute_query_dict(self, sql: str) -> List[Dict[str, Any]]:
        cursor = self._backend._get_cursor()
        try:
            cursor.execute(sql)
            columns = [desc[0].lower() for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def get_overview(self) -> ServerOverview:
        version = self._get_version_string()
        session = self.get_session_info()
        config = self.list_configuration()
        perf = self.list_performance_metrics()
        conn = self.get_connection_info()
        storage = self.get_storage_info()
        databases = self.list_databases()
        users = self.list_users()
        return self._build_server_overview(
            version, session, config, perf, conn, storage, databases, users,
        )

    def _get_version_string(self) -> str:
        try:
            rows = self._execute_query(self._version_sql()[0])
            return rows[0][0] if rows else "Unknown"
        except Exception:
            return "Unknown"

    def list_configuration(self, category: Optional[StatusCategory] = None) -> List[StatusItem]:
        items: List[StatusItem] = []
        try:
            rows = self._execute_query_dict(self._configuration_sql()[0])
        except Exception:
            return items

        for row in rows:
            cat = StatusCategory.CONFIGURATION
            items.append(self._create_status_item(
                name=row["name"], value=row["value_in_use"], category=cat,
                is_dynamic=bool(row.get("is_dynamic")),
            ))
        if category:
            items = [i for i in items if i.category == category]
        return items

    def list_performance_metrics(self, category: Optional[StatusCategory] = None) -> List[StatusItem]:
        items: List[StatusItem] = []
        try:
            rows = self._execute_query_dict(
                self._performance_metrics_sql(self._performance_metrics_limit())[0]
            )
        except Exception:
            return items

        for row in rows:
            items.append(self._create_status_item(
                name=row["counter_name"], value=row["cntr_value"],
                category=StatusCategory.PERFORMANCE,
                description=row.get("object_name"),
            ))
        return items

    def get_connection_info(self) -> ConnectionInfo:
        try:
            rows = self._execute_query_dict(self._connection_info_sql()[0])
            if rows:
                return ConnectionInfo(
                    active_count=rows[0].get("active"),
                    max_connections=rows[0].get("max_conn") or None,
                )
        except Exception:
            pass
        return ConnectionInfo()

    def get_storage_info(self) -> StorageInfo:
        try:
            rows = self._execute_query_dict(self._storage_info_sql()[0])
            if rows:
                return StorageInfo(
                    total_size_bytes=int(rows[0]["total_bytes"] or 0),
                )
        except Exception:
            pass
        return StorageInfo()

    def list_databases(self) -> List[DatabaseBriefInfo]:
        try:
            rows = self._execute_query_dict(self._database_list_sql()[0])
        except Exception:
            return []

        return [
            DatabaseBriefInfo(
                name=row["db_name"],
                size_bytes=int(row["size_bytes"]) if row.get("size_bytes") else None,
            )
            for row in rows
        ]

    def list_users(self) -> List[UserInfo]:
        try:
            rows = self._execute_query_dict(self._user_list_sql()[0])
        except Exception:
            return []

        return [
            UserInfo(
                name=row["name"],
                is_superuser=bool(row.get("is_sysadmin")),
                extra={"type": row.get("type_desc")},
            )
            for row in rows
        ]

    def get_session_info(self) -> SessionInfo:
        try:
            rows = self._execute_query_dict(self._session_info_sql()[0])
        except Exception:
            return SessionInfo()

        if not rows:
            return SessionInfo()
        row = rows[0]
        ssl = row.get("encrypt") == "TRUE" if row.get("encrypt") else None
        return SessionInfo(
            user=row.get("session_user"),
            database=row.get("cur_db"),
            host=row.get("host"),
            ssl_enabled=ssl,
        )


class AsyncSQLServerStatusIntrospector(SQLServerStatusIntrospectorMixin, AsyncAbstractStatusIntrospector):
    """Asynchronous SQL Server status introspector."""

    async def _execute_query(self, sql: str) -> List[tuple]:
        cursor = self._backend._get_cursor()
        try:
            cursor.execute(sql)
            return cursor.fetchall()
        finally:
            cursor.close()

    async def _execute_query_dict(self, sql: str) -> List[Dict[str, Any]]:
        cursor = self._backend._get_cursor()
        try:
            cursor.execute(sql)
            columns = [desc[0].lower() for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            cursor.close()

    async def get_overview(self) -> ServerOverview:
        version = await self._get_version_string()
        session = await self.get_session_info()
        config = await self.list_configuration()
        perf = await self.list_performance_metrics()
        conn = await self.get_connection_info()
        storage = await self.get_storage_info()
        databases = await self.list_databases()
        users = await self.list_users()
        return self._build_server_overview(
            version, session, config, perf, conn, storage, databases, users,
        )

    async def _get_version_string(self) -> str:
        try:
            rows = await self._execute_query(self._version_sql()[0])
            return rows[0][0] if rows else "Unknown"
        except Exception:
            return "Unknown"

    async def list_configuration(self, category: Optional[StatusCategory] = None) -> List[StatusItem]:
        items: List[StatusItem] = []
        try:
            rows = await self._execute_query_dict(self._configuration_sql()[0])
        except Exception:
            return items

        for row in rows:
            items.append(self._create_status_item(
                name=row["name"], value=row["value_in_use"],
                category=StatusCategory.CONFIGURATION,
                is_dynamic=bool(row.get("is_dynamic")),
            ))
        if category:
            items = [i for i in items if i.category == category]
        return items

    async def list_performance_metrics(self, category: Optional[StatusCategory] = None) -> List[StatusItem]:
        items: List[StatusItem] = []
        try:
            rows = await self._execute_query_dict(
                self._performance_metrics_sql(self._performance_metrics_limit())[0]
            )
        except Exception:
            return items

        for row in rows:
            items.append(self._create_status_item(
                name=row["counter_name"], value=row["cntr_value"],
                category=StatusCategory.PERFORMANCE,
                description=row.get("object_name"),
            ))
        return items

    async def get_connection_info(self) -> ConnectionInfo:
        try:
            rows = await self._execute_query_dict(self._connection_info_sql()[0])
            if rows:
                return ConnectionInfo(
                    active_count=rows[0].get("active"),
                    max_connections=rows[0].get("max_conn") or None,
                )
        except Exception:
            pass
        return ConnectionInfo()

    async def get_storage_info(self) -> StorageInfo:
        try:
            rows = await self._execute_query_dict(self._storage_info_sql()[0])
            if rows:
                return StorageInfo(
                    total_size_bytes=int(rows[0]["total_bytes"] or 0),
                )
        except Exception:
            pass
        return StorageInfo()

    async def list_databases(self) -> List[DatabaseBriefInfo]:
        try:
            rows = await self._execute_query_dict(self._database_list_sql()[0])
        except Exception:
            return []

        return [
            DatabaseBriefInfo(
                name=row["db_name"],
                size_bytes=int(row["size_bytes"]) if row.get("size_bytes") else None,
            )
            for row in rows
        ]

    async def list_users(self) -> List[UserInfo]:
        try:
            rows = await self._execute_query_dict(self._user_list_sql()[0])
        except Exception:
            return []

        return [
            UserInfo(
                name=row["name"],
                is_superuser=bool(row.get("is_sysadmin")),
                extra={"type": row.get("type_desc")},
            )
            for row in rows
        ]

    async def get_session_info(self) -> SessionInfo:
        try:
            rows = await self._execute_query_dict(self._session_info_sql()[0])
        except Exception:
            return SessionInfo()

        if not rows:
            return SessionInfo()
        row = rows[0]
        ssl = row.get("encrypt") == "TRUE" if row.get("encrypt") else None
        return SessionInfo(
            user=row.get("session_user"),
            database=row.get("cur_db"),
            host=row.get("host"),
            ssl_enabled=ssl,
        )
