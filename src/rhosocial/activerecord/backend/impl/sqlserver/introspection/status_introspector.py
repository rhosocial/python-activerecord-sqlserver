# src/rhosocial/activerecord/backend/impl/sqlserver/introspection/status_introspector.py
"""SQL Server status introspector.

Provides server status information by querying SQL Server DMVs:
sys.configurations, sys.dm_exec_sessions, sys.dm_os_performance_counters,
sys.databases, sys.server_principals, SERVERPROPERTY().
"""

from typing import Any, Dict, List, Optional

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


class SQLServerStatusIntrospectorMixin:
    """Shared non-I/O logic for SQL Server status introspectors."""

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
            rows = self._execute_query(
                "SELECT CAST(SERVERPROPERTY('ProductVersion') AS NVARCHAR(128))"
            )
            return rows[0][0] if rows else "Unknown"
        except Exception:
            return "Unknown"

    def list_configuration(self, category: Optional[StatusCategory] = None) -> List[StatusItem]:
        items: List[StatusItem] = []
        try:
            rows = self._execute_query_dict("""
                SELECT name,
                       CAST(value_in_use AS NVARCHAR(4000)) AS value_in_use,
                       is_dynamic, is_advanced
                FROM sys.configurations
                ORDER BY name
            """)
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
            rows = self._execute_query_dict("""
                SELECT TOP 50
                    RTRIM(counter_name) AS counter_name,
                    cntr_value,
                    RTRIM(object_name) AS object_name
                FROM sys.dm_os_performance_counters
                WHERE cntr_value > 0
                ORDER BY cntr_value DESC
            """)
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
            rows = self._execute_query_dict("""
                SELECT
                    (SELECT COUNT(*) FROM sys.dm_exec_connections) AS active,
                    (SELECT CAST(value_in_use AS INT)
                     FROM sys.configurations
                     WHERE name = 'user connections') AS max_conn
            """)
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
            rows = self._execute_query_dict("""
                SELECT SUM(size * 8 * 1024) AS total_bytes
                FROM sys.master_files WHERE database_id > 0
            """)
            if rows:
                return StorageInfo(
                    total_size_bytes=int(rows[0]["total_bytes"] or 0),
                )
        except Exception:
            pass
        return StorageInfo()

    def list_databases(self) -> List[DatabaseBriefInfo]:
        try:
            rows = self._execute_query_dict("""
                SELECT
                    d.name AS db_name,
                    SUM(mf.size * 8 * 1024) AS size_bytes
                FROM sys.databases d
                LEFT JOIN sys.master_files mf
                    ON d.database_id = mf.database_id AND mf.type = 0
                GROUP BY d.name
                ORDER BY d.name
            """)
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
            rows = self._execute_query_dict("""
                SELECT name, type_desc,
                       IS_SRVROLEMEMBER('sysadmin', name) AS is_sysadmin
                FROM sys.server_principals
                WHERE type IN ('S', 'U', 'G')
                ORDER BY name
            """)
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
            rows = self._execute_query_dict("""
                SELECT
                    SYSTEM_USER AS session_user,
                    DB_NAME() AS cur_db,
                    HOST_NAME() AS host,
                    CONNECTIONPROPERTY('net_transport') AS transport,
                    CONNECTIONPROPERTY('encrypt_option') AS encrypt
            """)
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
            rows = await self._execute_query(
                "SELECT CAST(SERVERPROPERTY('ProductVersion') AS NVARCHAR(128))"
            )
            return rows[0][0] if rows else "Unknown"
        except Exception:
            return "Unknown"

    async def list_configuration(self, category: Optional[StatusCategory] = None) -> List[StatusItem]:
        items: List[StatusItem] = []
        try:
            rows = await self._execute_query_dict("""
                SELECT name,
                       CAST(value_in_use AS NVARCHAR(4000)) AS value_in_use,
                       is_dynamic, is_advanced
                FROM sys.configurations
                ORDER BY name
            """)
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
            rows = await self._execute_query_dict("""
                SELECT TOP 50
                    RTRIM(counter_name) AS counter_name,
                    cntr_value,
                    RTRIM(object_name) AS object_name
                FROM sys.dm_os_performance_counters
                WHERE cntr_value > 0
                ORDER BY cntr_value DESC
            """)
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
            rows = await self._execute_query_dict("""
                SELECT
                    (SELECT COUNT(*) FROM sys.dm_exec_connections) AS active,
                    (SELECT CAST(value_in_use AS INT)
                     FROM sys.configurations
                     WHERE name = 'user connections') AS max_conn
            """)
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
            rows = await self._execute_query_dict("""
                SELECT SUM(size * 8 * 1024) AS total_bytes
                FROM sys.master_files WHERE database_id > 0
            """)
            if rows:
                return StorageInfo(
                    total_size_bytes=int(rows[0]["total_bytes"] or 0),
                )
        except Exception:
            pass
        return StorageInfo()

    async def list_databases(self) -> List[DatabaseBriefInfo]:
        try:
            rows = await self._execute_query_dict("""
                SELECT
                    d.name AS db_name,
                    SUM(mf.size * 8 * 1024) AS size_bytes
                FROM sys.databases d
                LEFT JOIN sys.master_files mf
                    ON d.database_id = mf.database_id AND mf.type = 0
                GROUP BY d.name
                ORDER BY d.name
            """)
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
            rows = await self._execute_query_dict("""
                SELECT name, type_desc,
                       IS_SRVROLEMEMBER('sysadmin', name) AS is_sysadmin
                FROM sys.server_principals
                WHERE type IN ('S', 'U', 'G')
                ORDER BY name
            """)
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
            rows = await self._execute_query_dict("""
                SELECT
                    SYSTEM_USER AS session_user,
                    DB_NAME() AS cur_db,
                    HOST_NAME() AS host,
                    CONNECTIONPROPERTY('net_transport') AS transport,
                    CONNECTIONPROPERTY('encrypt_option') AS encrypt
            """)
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
