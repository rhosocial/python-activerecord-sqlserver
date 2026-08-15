import pytest
import pytest_asyncio

from rhosocial.activerecord.backend.errors import ConnectionError


class TestIsConnectedMethod:
    """Test that is_connected() accurately reflects connection state."""

    def test_is_connected_after_connect(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        assert backend._connection is not None

    def test_is_connected_after_disconnect(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        backend.disconnect()
        assert backend._connection is None
        backend.connect()

    def test_execute_reconnects_after_disconnect(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        backend.disconnect()
        result = backend.execute("SELECT 1 AS value")
        assert result.data is not None
        assert result.data[0]["value"] == 1


class TestPingReconnect:
    """Test ping() and automatic reconnect."""

    def test_ping_returns_true_when_connected(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        assert backend.ping(reconnect=False) is True

    def test_ping_returns_false_when_disconnected_no_reconnect(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        backend.disconnect()
        assert backend.ping(reconnect=False) is False

    def test_ping_reconnects_when_disconnected(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        backend.disconnect()
        assert backend.ping(reconnect=True) is True
        assert backend._connection is not None

    def test_ping_two_consecutive_calls_with_disconnect(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        assert backend.ping(reconnect=False) is True
        backend.disconnect()
        assert backend.ping(reconnect=True) is True
        assert backend.ping(reconnect=False) is True


class TestGetCursorAutoReconnect:
    """Test that _get_cursor() automatically reconnects after connection loss."""

    def test_get_cursor_works_normally(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        cursor = backend._get_cursor()
        assert cursor is not None
        cursor.close()

    def test_get_cursor_reconnects_after_disconnect(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        backend.disconnect()
        cursor = backend._get_cursor()
        assert cursor is not None
        assert backend._connection is not None
        cursor.close()

    def test_execute_after_ping_reconnect(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        backend.disconnect()
        assert backend.ping(reconnect=True) is True
        result = backend.execute("SELECT @@VERSION AS version")
        assert result.data is not None
        assert len(result.data) > 0

    def test_execute_after_disconnect_reconnects_automatically(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        backend.disconnect()
        result = backend.execute("SELECT 1 AS value")
        assert result.data is not None
        assert result.data[0]["value"] == 1


class TestAsyncReconnect:
    @pytest.mark.asyncio
    async def test_async_ping_returns_true_when_connected(self, async_sqlserver_backend_single):
        backend = async_sqlserver_backend_single
        assert await backend.ping(reconnect=False) is True

    @pytest.mark.asyncio
    async def test_async_ping_reconnects_when_disconnected(self, async_sqlserver_backend_single):
        backend = async_sqlserver_backend_single
        await backend.disconnect()
        assert await backend.ping(reconnect=True) is True
        assert backend._connection is not None

    @pytest.mark.asyncio
    async def test_async_execute_after_reconnect(self, async_sqlserver_backend_single):
        backend = async_sqlserver_backend_single
        await backend.disconnect()
        assert await backend.ping(reconnect=True) is True
        result = await backend.execute("SELECT 1 AS value")
        assert result.data is not None
        assert result.data[0]["value"] == 1


class TestNetworkInterruptionSimulation:
    def test_execute_after_double_disconnect_reconnect(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        backend.disconnect()
        backend.connect()
        backend.disconnect()
        backend.connect()
        result = backend.execute("SELECT 1 AS value")
        assert result.data is not None
        assert result.data[0]["value"] == 1

    def test_multiple_alternating_execute_disconnect(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        for i in range(3):
            backend.disconnect()
            result = backend.execute(f"SELECT {i + 1} AS value")
            assert result.data is not None
            assert result.data[0]["value"] == i + 1


class TestMultiModelSharedBackend:
    def test_same_backend_multiple_operations(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        result1 = backend.execute("SELECT 1 AS value")
        result2 = backend.execute("SELECT 2 AS value")
        result3 = backend.execute("SELECT 3 AS value")
        assert result1.data[0]["value"] == 1
        assert result2.data[0]["value"] == 2
        assert result3.data[0]["value"] == 3

    def test_backend_works_after_interleaved_disconnect(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        result1 = backend.execute("SELECT 1 AS value")
        backend.disconnect()
        result2 = backend.execute("SELECT 2 AS value")
        backend.disconnect()
        result3 = backend.execute("SELECT 3 AS value")
        assert result1.data[0]["value"] == 1
        assert result2.data[0]["value"] == 2
        assert result3.data[0]["value"] == 3
