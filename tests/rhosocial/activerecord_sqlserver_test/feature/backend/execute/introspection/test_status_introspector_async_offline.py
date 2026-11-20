# tests/rhosocial/activerecord_sqlserver_test/feature/backend/execute/introspection/test_status_introspector_async_offline.py
"""Offline unit tests for the asynchronous SQL Server status introspector.

SQL Server has a native async driver, so its async paths must be covered just
like the synchronous ones. Every test here mocks the async I/O boundary with
``AsyncMock`` and uses a real dialect offline: no server connection is made.
"""
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.introspection.status_introspector import (
    AsyncSQLServerStatusIntrospector,
)
from rhosocial.activerecord.backend.introspection.status import (
    ConnectionInfo,
    DatabaseBriefInfo,
    ServerOverview,
    SessionInfo,
    StatusCategory,
    StatusItem,
    StorageInfo,
    UserInfo,
)


def make_async_introspector(version=(16, 0, 0)):
    """Build an async introspector over a mock backend with a real (offline) dialect."""
    backend = MagicMock()
    backend.dialect = SQLServerDialect(version=version)
    return AsyncSQLServerStatusIntrospector(backend=backend)


class TestAsyncStatusIntrospectorHelpers:
    """The shared, non-I/O helpers are inherited by the async introspector too."""

    def test_inherited_helpers_vendor_and_parse_value(self):
        introspector = make_async_introspector()
        assert introspector._get_vendor_name() == "SQL Server"
        assert introspector._parse_value("4096") == 4096
        assert introspector._parse_value("n/a") == "n/a"

    def test_inherited_create_status_item(self):
        item = make_async_introspector()._create_status_item(
            name="Batch Requests/sec", value="4096", category=StatusCategory.PERFORMANCE,
        )
        assert isinstance(item, StatusItem)
        assert item.value == 4096
        assert item.category == StatusCategory.PERFORMANCE
        assert item.is_readonly is True
        assert item.is_dynamic is False


class TestAsyncStatusIntrospectorExecution:
    """The async cursor-reading primitives, with a mocked cursor."""

    async def test_execute_query_returns_rows_and_closes_cursor(self):
        introspector = make_async_introspector()
        cursor = MagicMock()
        cursor.fetchall.return_value = [("16.0.1000.6",)]
        introspector._backend._get_cursor.return_value = cursor

        rows = await introspector._execute_query("SELECT 1")

        assert rows == [("16.0.1000.6",)]
        cursor.execute.assert_called_once_with("SELECT 1")
        cursor.fetchall.assert_called_once_with()
        cursor.close.assert_called_once_with()

    async def test_execute_query_closes_cursor_on_error(self):
        introspector = make_async_introspector()
        cursor = MagicMock()
        cursor.execute.side_effect = RuntimeError("boom")
        introspector._backend._get_cursor.return_value = cursor

        with pytest.raises(RuntimeError, match="boom"):
            await introspector._execute_query("SELECT bad")
        cursor.close.assert_called_once_with()

    async def test_execute_query_dict_lowercases_column_names(self):
        introspector = make_async_introspector()
        cursor = MagicMock()
        cursor.description = [("Name",), ("Value_In_Use",)]
        cursor.fetchall.return_value = [("max connections", "100")]
        introspector._backend._get_cursor.return_value = cursor

        rows = await introspector._execute_query_dict("SELECT name, value_in_use FROM sys.configurations")

        assert rows == [{"name": "max connections", "value_in_use": "100"}]
        cursor.close.assert_called_once_with()

    async def test_execute_query_dict_closes_cursor_on_error(self):
        introspector = make_async_introspector()
        cursor = MagicMock()
        cursor.description = [("Name",)]
        cursor.fetchall.side_effect = RuntimeError("boom")
        introspector._backend._get_cursor.return_value = cursor

        with pytest.raises(RuntimeError, match="boom"):
            await introspector._execute_query_dict("SELECT name")
        cursor.close.assert_called_once_with()


class TestAsyncStatusIntrospectorPublicMethods:
    """Row parsing and failure handling of the asynchronous public API."""

    async def test_get_version_string_from_row(self):
        introspector = make_async_introspector()
        with patch.object(
            introspector, "_execute_query", new_callable=AsyncMock,
            return_value=[("16.0.1000.6",)],
        ):
            assert await introspector._get_version_string() == "16.0.1000.6"

    @pytest.mark.parametrize("rows", [[], None])
    async def test_get_version_string_without_rows(self, rows):
        introspector = make_async_introspector()
        with patch.object(introspector, "_execute_query", new_callable=AsyncMock, return_value=rows):
            assert await introspector._get_version_string() == "Unknown"

    async def test_get_version_string_on_error(self):
        introspector = make_async_introspector()
        with patch.object(
            introspector, "_execute_query", new_callable=AsyncMock, side_effect=RuntimeError("down")
        ):
            assert await introspector._get_version_string() == "Unknown"

    async def test_list_configuration_parses_rows(self):
        introspector = make_async_introspector()
        rows = [
            {"name": "max connections", "value_in_use": "100", "is_dynamic": 0, "is_advanced": 0},
            {"name": "cursor threshold", "value_in_use": "-1", "is_dynamic": 1, "is_advanced": 1},
        ]
        with patch.object(introspector, "_execute_query_dict", new_callable=AsyncMock, return_value=rows):
            items = await introspector.list_configuration()

        assert [item.name for item in items] == ["max connections", "cursor threshold"]
        assert all(isinstance(item, StatusItem) for item in items)
        assert items[0].value == 100
        assert items[0].is_dynamic is False
        assert items[1].value == "-1"
        assert items[1].is_dynamic is True
        assert all(item.category == StatusCategory.CONFIGURATION for item in items)

    async def test_list_configuration_category_filter(self):
        introspector = make_async_introspector()
        rows = [{"name": "x", "value_in_use": "1", "is_dynamic": 1}]
        with patch.object(introspector, "_execute_query_dict", new_callable=AsyncMock, return_value=rows):
            assert len(await introspector.list_configuration(StatusCategory.CONFIGURATION)) == 1
            assert await introspector.list_configuration(StatusCategory.PERFORMANCE) == []

    async def test_list_configuration_on_error(self):
        introspector = make_async_introspector()
        with patch.object(
            introspector, "_execute_query_dict", new_callable=AsyncMock,
            side_effect=RuntimeError("down"),
        ):
            assert await introspector.list_configuration() == []

    async def test_list_performance_metrics_parses_rows(self):
        introspector = make_async_introspector()
        rows = [
            {"counter_name": "Batch Requests/sec", "cntr_value": 4096,
             "object_name": "SQL Server:SQL Statistics"},
            {"counter_name": "User Connections", "cntr_value": 12},
        ]
        with patch.object(introspector, "_execute_query_dict", new_callable=AsyncMock, return_value=rows):
            items = await introspector.list_performance_metrics()

        assert [item.name for item in items] == ["Batch Requests/sec", "User Connections"]
        assert items[0].value == 4096
        assert items[0].description == "SQL Server:SQL Statistics"
        assert items[1].description is None
        assert all(item.category == StatusCategory.PERFORMANCE for item in items)

    async def test_list_performance_metrics_on_error(self):
        introspector = make_async_introspector()
        with patch.object(
            introspector, "_execute_query_dict", new_callable=AsyncMock,
            side_effect=RuntimeError("down"),
        ):
            assert await introspector.list_performance_metrics() == []

    async def test_get_connection_info_populated(self):
        introspector = make_async_introspector()
        with patch.object(
            introspector, "_execute_query_dict", new_callable=AsyncMock,
            return_value=[{"active": 5, "max_conn": 100}],
        ):
            info = await introspector.get_connection_info()
        assert isinstance(info, ConnectionInfo)
        assert info.active_count == 5
        assert info.max_connections == 100

    async def test_get_connection_info_zero_max_becomes_none(self):
        introspector = make_async_introspector()
        with patch.object(
            introspector, "_execute_query_dict", new_callable=AsyncMock,
            return_value=[{"active": 5, "max_conn": 0}],
        ):
            info = await introspector.get_connection_info()
        assert info.active_count == 5
        assert info.max_connections is None

    @pytest.mark.parametrize("rows", [[], None])
    async def test_get_connection_info_without_rows(self, rows):
        introspector = make_async_introspector()
        with patch.object(introspector, "_execute_query_dict", new_callable=AsyncMock, return_value=rows):
            info = await introspector.get_connection_info()
        assert info.active_count is None
        assert info.max_connections is None

    async def test_get_connection_info_on_error(self):
        introspector = make_async_introspector()
        with patch.object(
            introspector, "_execute_query_dict", new_callable=AsyncMock,
            side_effect=RuntimeError("down"),
        ):
            info = await introspector.get_connection_info()
        assert info.active_count is None

    async def test_get_storage_info_converts_bytes(self):
        introspector = make_async_introspector()
        with patch.object(
            introspector, "_execute_query_dict", new_callable=AsyncMock,
            return_value=[{"total_bytes": "8192"}],
        ):
            info = await introspector.get_storage_info()
        assert isinstance(info, StorageInfo)
        assert info.total_size_bytes == 8192

    @pytest.mark.parametrize(
        ("rows", "expected"),
        [([{"total_bytes": None}], 0), ([], None), (None, None)],
    )
    async def test_get_storage_info_optional_shapes(self, rows, expected):
        introspector = make_async_introspector()
        with patch.object(introspector, "_execute_query_dict", new_callable=AsyncMock, return_value=rows):
            assert (await introspector.get_storage_info()).total_size_bytes == expected

    async def test_get_storage_info_on_error(self):
        introspector = make_async_introspector()
        with patch.object(
            introspector, "_execute_query_dict", new_callable=AsyncMock,
            side_effect=RuntimeError("down"),
        ):
            assert (await introspector.get_storage_info()).total_size_bytes is None

    async def test_list_databases_parses_rows(self):
        introspector = make_async_introspector()
        rows = [
            {"db_name": "master", "size_bytes": "8388608"},
            {"db_name": "tempdb", "size_bytes": None},
            {"db_name": "model"},
        ]
        with patch.object(introspector, "_execute_query_dict", new_callable=AsyncMock, return_value=rows):
            databases = await introspector.list_databases()

        assert [db.name for db in databases] == ["master", "tempdb", "model"]
        assert all(isinstance(db, DatabaseBriefInfo) for db in databases)
        assert databases[0].size_bytes == 8388608
        assert databases[1].size_bytes is None
        assert databases[2].size_bytes is None

    async def test_list_databases_on_error(self):
        introspector = make_async_introspector()
        with patch.object(
            introspector, "_execute_query_dict", new_callable=AsyncMock,
            side_effect=RuntimeError("down"),
        ):
            assert await introspector.list_databases() == []

    async def test_list_users_parses_rows(self):
        introspector = make_async_introspector()
        rows = [
            {"name": "sa", "type_desc": "SQL_LOGIN", "is_sysadmin": 1},
            {"name": "app_user", "type_desc": "SQL_LOGIN", "is_sysadmin": 0},
            {"name": "DOMAIN\\Group"},
        ]
        with patch.object(introspector, "_execute_query_dict", new_callable=AsyncMock, return_value=rows):
            users = await introspector.list_users()

        assert [user.name for user in users] == ["sa", "app_user", "DOMAIN\\Group"]
        assert all(isinstance(user, UserInfo) for user in users)
        assert users[0].is_superuser is True
        assert users[0].extra == {"type": "SQL_LOGIN"}
        assert users[1].is_superuser is False
        assert users[2].extra == {"type": None}

    async def test_list_users_on_error(self):
        introspector = make_async_introspector()
        with patch.object(
            introspector, "_execute_query_dict", new_callable=AsyncMock,
            side_effect=RuntimeError("down"),
        ):
            assert await introspector.list_users() == []

    @pytest.mark.parametrize(
        ("encrypt", "expected"),
        [("TRUE", True), ("FALSE", False), (None, None), ("", None)],
    )
    async def test_get_session_info_ssl_flag(self, encrypt, expected):
        introspector = make_async_introspector()
        rows = [{
            "session_user": "svc", "cur_db": "master", "host": "WIN-1",
            "transport": "TCP/IP", "encrypt": encrypt,
        }]
        with patch.object(introspector, "_execute_query_dict", new_callable=AsyncMock, return_value=rows):
            info = await introspector.get_session_info()
        assert isinstance(info, SessionInfo)
        assert info.user == "svc"
        assert info.database == "master"
        assert info.host == "WIN-1"
        assert info.ssl_enabled is expected

    @pytest.mark.parametrize("rows", [[], None])
    async def test_get_session_info_without_rows(self, rows):
        introspector = make_async_introspector()
        with patch.object(introspector, "_execute_query_dict", new_callable=AsyncMock, return_value=rows):
            info = await introspector.get_session_info()
        assert info.user is None

    async def test_get_session_info_on_error(self):
        introspector = make_async_introspector()
        with patch.object(
            introspector, "_execute_query_dict", new_callable=AsyncMock,
            side_effect=RuntimeError("down"),
        ):
            info = await introspector.get_session_info()
        assert info.user is None

    async def test_get_overview_delegates_and_builds_result(self):
        introspector = make_async_introspector()
        session = SessionInfo(user="svc")
        config = [StatusItem(name="max connections", value=100)]
        perf = [StatusItem(name="Batch Requests/sec", value=4096,
                           category=StatusCategory.PERFORMANCE)]
        conn = ConnectionInfo(active_count=5)
        storage = StorageInfo(total_size_bytes=8192)
        databases = [DatabaseBriefInfo(name="master")]
        users = [UserInfo(name="sa", is_superuser=True)]
        delegates = {
            "_get_version_string": "16.0.1000.6",
            "get_session_info": session,
            "list_configuration": config,
            "list_performance_metrics": perf,
            "get_connection_info": conn,
            "get_storage_info": storage,
            "list_databases": databases,
            "list_users": users,
        }
        with ExitStack() as stack:
            mocks = {
                name: stack.enter_context(
                    patch.object(introspector, name, new_callable=AsyncMock, return_value=value)
                )
                for name, value in delegates.items()
            }
            overview = await introspector.get_overview()

        assert isinstance(overview, ServerOverview)
        assert overview.server_version == "16.0.1000.6"
        assert overview.server_vendor == "SQL Server"
        assert overview.session is session
        assert overview.configuration == config + perf
        assert overview.connections is conn
        assert overview.storage is storage
        assert overview.databases == databases
        assert overview.users == users
        for mocked in mocks.values():
            mocked.assert_awaited_once_with()
