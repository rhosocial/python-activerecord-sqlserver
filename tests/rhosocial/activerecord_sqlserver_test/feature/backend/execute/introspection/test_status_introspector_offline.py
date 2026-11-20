# tests/rhosocial/activerecord_sqlserver_test/feature/backend/execute/introspection/test_status_introspector_offline.py
"""Self-owned offline unit tests for the synchronous SQL Server status introspector.

These tests exercise the backend's own parsing and query-building logic with
``MagicMock``/controlled rows only; no SQL Server (or any other DB) is needed.
The testsuite's compatibility contracts cover only the shared API, so the
backend-specific row-shape parsing lives here.
"""
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.introspection.status_introspector import (
    SQLServerStatusIntrospector,
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


def make_introspector(version=(16, 0, 0)):
    """Build a sync introspector over a mock backend with a real (offline) dialect."""
    backend = MagicMock()
    backend.dialect = SQLServerDialect(version=version)
    return SQLServerStatusIntrospector(backend=backend)


class TestStatusIntrospectorHelpers:
    """Pure helpers on ``SQLServerStatusIntrospectorMixin``."""

    def test_dialect_property_returns_backend_dialect(self):
        introspector = make_introspector()
        assert introspector.dialect is introspector._backend.dialect

    def test_get_vendor_name(self):
        assert make_introspector()._get_vendor_name() == "SQL Server"

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("123", 123),
            ("0", 0),
            ("007", 7),
            ("abc", "abc"),
            ("-5", "-5"),
            ("12.5", "12.5"),
            ("", ""),
            (42, 42),
            (None, None),
        ],
    )
    def test_parse_value(self, raw, expected):
        assert make_introspector()._parse_value(raw) == expected

    def test_create_status_item_defaults(self):
        item = make_introspector()._create_status_item(
            name="max connections", value="100", category=StatusCategory.CONFIGURATION,
        )
        assert isinstance(item, StatusItem)
        assert item.name == "max connections"
        assert item.value == 100
        assert item.category == StatusCategory.CONFIGURATION
        assert item.description is None
        assert item.unit is None
        assert item.is_readonly is True
        assert item.is_dynamic is False

    def test_create_status_item_explicit_flags(self):
        item = make_introspector()._create_status_item(
            name="Batch Requests/sec", value="4096", category=StatusCategory.PERFORMANCE,
            description="SQL Server:SQL Statistics", unit="requests/s",
            is_readonly=False, is_dynamic=True,
        )
        assert item.value == 4096
        assert item.description == "SQL Server:SQL Statistics"
        assert item.unit == "requests/s"
        assert item.is_readonly is False
        assert item.is_dynamic is True
        assert item.category == StatusCategory.PERFORMANCE

    def test_build_server_overview_combines_configuration_and_performance(self):
        introspector = make_introspector()
        config = [StatusItem(name="a", value=1)]
        perf = [StatusItem(name="b", value=2, category=StatusCategory.PERFORMANCE)]
        session = SessionInfo(user="svc", ssl_enabled=True)
        conn = ConnectionInfo(active_count=3)
        storage = StorageInfo(total_size_bytes=8192)
        databases = [DatabaseBriefInfo(name="master")]
        users = [UserInfo(name="sa", is_superuser=True)]

        overview = introspector._build_server_overview(
            "16.0.1000.6", session, config, perf, conn, storage, databases, users,
        )

        assert isinstance(overview, ServerOverview)
        assert overview.server_version == "16.0.1000.6"
        assert overview.server_vendor == "SQL Server"
        assert overview.session is session
        assert overview.configuration == config + perf
        assert overview.performance == []
        assert overview.connections is conn
        assert overview.storage is storage
        assert overview.databases == databases
        assert overview.users == users


class TestStatusIntrospectorQueryBuilders:
    """The private ``*_sql`` helpers render through the dialect, not hand-written SQL."""

    def test_version_sql(self):
        sql, params = make_introspector()._version_sql()
        assert "SERVERPROPERTY('ProductVersion')" in sql
        assert "CAST" in sql
        assert params == ()

    def test_configuration_sql(self):
        sql, params = make_introspector()._configuration_sql()
        assert "[sys].[configurations]" in sql
        assert "[value_in_use]" in sql
        assert "ORDER BY [name]" in sql
        assert params == ()

    def test_performance_metrics_sql_with_limit(self):
        sql, params = make_introspector()._performance_metrics_sql(50)
        assert "[sys].[dm_os_performance_counters]" in sql
        assert "RTRIM([counter_name])" in sql
        assert "OFFSET 0 ROWS FETCH NEXT 50 ROWS ONLY" in sql
        assert params == ()

    def test_performance_metrics_sql_without_limit(self):
        sql, _ = make_introspector()._performance_metrics_sql(None)
        assert "FETCH NEXT" not in sql
        assert "ORDER BY [cntr_value] DESC" in sql

    @pytest.mark.parametrize(
        ("version", "expected"),
        # SQL Server 2012 is version 11.0 -- that is the OFFSET/FETCH boundary.
        [((16, 0, 0), 50), ((11, 0, 0), 50), ((10, 50, 0), None)],
    )
    def test_performance_metrics_limit_by_version(self, version, expected):
        assert make_introspector(version)._performance_metrics_limit() == expected

    def test_performance_metrics_limit_defaults_to_50_when_version_unavailable(self):
        backend = MagicMock()
        type(backend.dialect).version = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("no version yet"))
        )
        introspector = SQLServerStatusIntrospector(backend=backend)
        assert introspector._performance_metrics_limit() == 50

    def test_connection_info_sql(self):
        sql, params = make_introspector()._connection_info_sql()
        assert "COUNT(*)" in sql
        assert "[sys].[dm_exec_connections]" in sql
        assert "'user connections'" in sql
        assert "AS [active]" in sql
        assert "AS [max_conn]" in sql
        assert params == ()

    def test_storage_info_sql(self):
        sql, params = make_introspector()._storage_info_sql()
        assert "[sys].[master_files]" in sql
        assert "SUM([size] * 8 * 1024)" in sql
        assert "AS [total_bytes]" in sql
        assert params == ()

    def test_database_list_sql(self):
        sql, params = make_introspector()._database_list_sql()
        assert "LEFT JOIN" in sql
        assert "[sys].[databases]" in sql
        assert "[mf].[type] = 0" in sql
        assert "GROUP BY [d].[name]" in sql
        assert "AS [size_bytes]" in sql
        assert "AS [db_name]" in sql
        assert params == ()

    def test_user_list_sql(self):
        sql, params = make_introspector()._user_list_sql()
        assert "[sys].[server_principals]" in sql
        assert "IS_SRVROLEMEMBER('sysadmin', [name])" in sql
        assert "IN ('S', 'U', 'G')" in sql
        assert params == ()

    def test_session_info_sql(self):
        sql, params = make_introspector()._session_info_sql()
        assert "SYSTEM_USER AS [session_user]" in sql  # niladic: no parentheses
        assert "DB_NAME() AS [cur_db]" in sql
        assert "HOST_NAME() AS [host]" in sql
        assert sql.count("CONNECTIONPROPERTY(") == 2
        assert "'encrypt_option'" in sql
        assert params == ()


class TestStatusIntrospectorExecution:
    """The two cursor-reading primitives, with a mocked cursor."""

    def test_execute_query_returns_rows_and_closes_cursor(self):
        introspector = make_introspector()
        cursor = MagicMock()
        cursor.fetchall.return_value = [("16.0.1000.6",)]
        introspector._backend._get_cursor.return_value = cursor

        rows = introspector._execute_query("SELECT 1")

        assert rows == [("16.0.1000.6",)]
        cursor.execute.assert_called_once_with("SELECT 1")
        cursor.fetchall.assert_called_once_with()
        cursor.close.assert_called_once_with()

    def test_execute_query_closes_cursor_on_error(self):
        introspector = make_introspector()
        cursor = MagicMock()
        cursor.execute.side_effect = RuntimeError("boom")
        introspector._backend._get_cursor.return_value = cursor

        with pytest.raises(RuntimeError, match="boom"):
            introspector._execute_query("SELECT bad")
        cursor.close.assert_called_once_with()

    def test_execute_query_dict_lowercases_column_names(self):
        introspector = make_introspector()
        cursor = MagicMock()
        cursor.description = [("Name",), ("Value_In_Use",)]
        cursor.fetchall.return_value = [("max connections", "100")]
        introspector._backend._get_cursor.return_value = cursor

        rows = introspector._execute_query_dict("SELECT name, value_in_use FROM sys.configurations")

        assert rows == [{"name": "max connections", "value_in_use": "100"}]
        cursor.close.assert_called_once_with()

    def test_execute_query_dict_closes_cursor_on_error(self):
        introspector = make_introspector()
        cursor = MagicMock()
        cursor.description = [("Name",)]
        cursor.fetchall.side_effect = RuntimeError("boom")
        introspector._backend._get_cursor.return_value = cursor

        with pytest.raises(RuntimeError, match="boom"):
            introspector._execute_query_dict("SELECT name")
        cursor.close.assert_called_once_with()


class TestStatusIntrospectorPublicMethods:
    """Row parsing and failure handling of the synchronous public API."""

    def test_get_version_string_from_row(self):
        introspector = make_introspector()
        with patch.object(introspector, "_execute_query", return_value=[("16.0.1000.6",)]):
            assert introspector._get_version_string() == "16.0.1000.6"

    @pytest.mark.parametrize("rows", [[], None])
    def test_get_version_string_without_rows(self, rows):
        introspector = make_introspector()
        with patch.object(introspector, "_execute_query", return_value=rows):
            assert introspector._get_version_string() == "Unknown"

    def test_get_version_string_on_error(self):
        introspector = make_introspector()
        with patch.object(introspector, "_execute_query", side_effect=RuntimeError("down")):
            assert introspector._get_version_string() == "Unknown"

    def test_list_configuration_parses_rows(self):
        introspector = make_introspector()
        rows = [
            {"name": "max connections", "value_in_use": "100", "is_dynamic": 0, "is_advanced": 0},
            {"name": "cursor threshold", "value_in_use": "-1", "is_dynamic": 1, "is_advanced": 1},
        ]
        with patch.object(introspector, "_execute_query_dict", return_value=rows):
            items = introspector.list_configuration()

        assert [item.name for item in items] == ["max connections", "cursor threshold"]
        assert all(isinstance(item, StatusItem) for item in items)
        assert items[0].value == 100
        assert items[0].is_dynamic is False
        assert items[1].value == "-1"  # negative numeric text is kept verbatim
        assert items[1].is_dynamic is True
        assert all(item.category == StatusCategory.CONFIGURATION for item in items)

    def test_list_configuration_category_filter(self):
        introspector = make_introspector()
        rows = [{"name": "x", "value_in_use": "1", "is_dynamic": 1}]
        with patch.object(introspector, "_execute_query_dict", return_value=rows):
            assert len(introspector.list_configuration(StatusCategory.CONFIGURATION)) == 1
            assert introspector.list_configuration(StatusCategory.PERFORMANCE) == []

    def test_list_configuration_on_error(self):
        introspector = make_introspector()
        with patch.object(introspector, "_execute_query_dict", side_effect=RuntimeError("down")):
            assert introspector.list_configuration() == []

    def test_list_performance_metrics_parses_rows(self):
        introspector = make_introspector()
        rows = [
            {"counter_name": "Batch Requests/sec", "cntr_value": 4096,
             "object_name": "SQL Server:SQL Statistics"},
            {"counter_name": "User Connections", "cntr_value": 12},
        ]
        with patch.object(introspector, "_execute_query_dict", return_value=rows):
            items = introspector.list_performance_metrics()

        assert [item.name for item in items] == ["Batch Requests/sec", "User Connections"]
        assert items[0].value == 4096
        assert items[0].description == "SQL Server:SQL Statistics"
        assert items[1].description is None
        assert all(item.category == StatusCategory.PERFORMANCE for item in items)

    def test_list_performance_metrics_on_error(self):
        introspector = make_introspector()
        with patch.object(introspector, "_execute_query_dict", side_effect=RuntimeError("down")):
            assert introspector.list_performance_metrics() == []

    def test_get_connection_info_populated(self):
        introspector = make_introspector()
        with patch.object(
            introspector, "_execute_query_dict", return_value=[{"active": 5, "max_conn": 100}]
        ):
            info = introspector.get_connection_info()
        assert isinstance(info, ConnectionInfo)
        assert info.active_count == 5
        assert info.max_connections == 100

    def test_get_connection_info_zero_max_becomes_none(self):
        introspector = make_introspector()
        with patch.object(
            introspector, "_execute_query_dict", return_value=[{"active": 5, "max_conn": 0}]
        ):
            info = introspector.get_connection_info()
        assert info.active_count == 5
        assert info.max_connections is None

    @pytest.mark.parametrize("rows", [[], None])
    def test_get_connection_info_without_rows(self, rows):
        introspector = make_introspector()
        with patch.object(introspector, "_execute_query_dict", return_value=rows):
            info = introspector.get_connection_info()
        assert info.active_count is None
        assert info.max_connections is None

    def test_get_connection_info_on_error(self):
        introspector = make_introspector()
        with patch.object(introspector, "_execute_query_dict", side_effect=RuntimeError("down")):
            info = introspector.get_connection_info()
        assert info.active_count is None

    def test_get_storage_info_converts_bytes(self):
        introspector = make_introspector()
        with patch.object(introspector, "_execute_query_dict", return_value=[{"total_bytes": "8192"}]):
            info = introspector.get_storage_info()
        assert isinstance(info, StorageInfo)
        assert info.total_size_bytes == 8192

    @pytest.mark.parametrize(
        ("rows", "expected"),
        [([{"total_bytes": None}], 0), ([], None), (None, None)],
    )
    def test_get_storage_info_optional_shapes(self, rows, expected):
        introspector = make_introspector()
        with patch.object(introspector, "_execute_query_dict", return_value=rows):
            assert introspector.get_storage_info().total_size_bytes == expected

    def test_get_storage_info_on_error(self):
        introspector = make_introspector()
        with patch.object(introspector, "_execute_query_dict", side_effect=RuntimeError("down")):
            assert introspector.get_storage_info().total_size_bytes is None

    def test_list_databases_parses_rows(self):
        introspector = make_introspector()
        rows = [
            {"db_name": "master", "size_bytes": "8388608"},
            {"db_name": "tempdb", "size_bytes": None},
            {"db_name": "model"},
        ]
        with patch.object(introspector, "_execute_query_dict", return_value=rows):
            databases = introspector.list_databases()

        assert [db.name for db in databases] == ["master", "tempdb", "model"]
        assert all(isinstance(db, DatabaseBriefInfo) for db in databases)
        assert databases[0].size_bytes == 8388608
        assert databases[1].size_bytes is None
        assert databases[2].size_bytes is None

    def test_list_databases_on_error(self):
        introspector = make_introspector()
        with patch.object(introspector, "_execute_query_dict", side_effect=RuntimeError("down")):
            assert introspector.list_databases() == []

    def test_list_users_parses_rows(self):
        introspector = make_introspector()
        rows = [
            {"name": "sa", "type_desc": "SQL_LOGIN", "is_sysadmin": 1},
            {"name": "app_user", "type_desc": "SQL_LOGIN", "is_sysadmin": 0},
            {"name": "DOMAIN\\Group"},
        ]
        with patch.object(introspector, "_execute_query_dict", return_value=rows):
            users = introspector.list_users()

        assert [user.name for user in users] == ["sa", "app_user", "DOMAIN\\Group"]
        assert all(isinstance(user, UserInfo) for user in users)
        assert users[0].is_superuser is True
        assert users[0].extra == {"type": "SQL_LOGIN"}
        assert users[1].is_superuser is False
        assert users[2].extra == {"type": None}

    def test_list_users_on_error(self):
        introspector = make_introspector()
        with patch.object(introspector, "_execute_query_dict", side_effect=RuntimeError("down")):
            assert introspector.list_users() == []

    @pytest.mark.parametrize(
        ("encrypt", "expected"),
        [("TRUE", True), ("FALSE", False), (None, None), ("", None)],
    )
    def test_get_session_info_ssl_flag(self, encrypt, expected):
        introspector = make_introspector()
        rows = [{
            "session_user": "svc", "cur_db": "master", "host": "WIN-1",
            "transport": "TCP/IP", "encrypt": encrypt,
        }]
        with patch.object(introspector, "_execute_query_dict", return_value=rows):
            info = introspector.get_session_info()
        assert isinstance(info, SessionInfo)
        assert info.user == "svc"
        assert info.database == "master"
        assert info.host == "WIN-1"
        assert info.ssl_enabled is expected

    @pytest.mark.parametrize("rows", [[], None])
    def test_get_session_info_without_rows(self, rows):
        introspector = make_introspector()
        with patch.object(introspector, "_execute_query_dict", return_value=rows):
            info = introspector.get_session_info()
        assert info.user is None

    def test_get_session_info_on_error(self):
        introspector = make_introspector()
        with patch.object(introspector, "_execute_query_dict", side_effect=RuntimeError("down")):
            info = introspector.get_session_info()
        assert info.user is None

    def test_get_overview_delegates_and_builds_result(self):
        introspector = make_introspector()
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
                    patch.object(introspector, name, return_value=value)
                )
                for name, value in delegates.items()
            }
            overview = introspector.get_overview()

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
            mocked.assert_called_once_with()
