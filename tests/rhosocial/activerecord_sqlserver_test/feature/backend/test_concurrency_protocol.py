# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_concurrency_protocol.py
"""
Test for ConcurrencyAware protocol implementation in SQL Server backend.

This test verifies that SQLServerBackend correctly implements the ConcurrencyAware
protocol by fetching max_connections during connect and returning the appropriate
concurrency hint.
"""
import pytest

from rhosocial.activerecord.backend.protocols import ConcurrencyAware, ConcurrencyHint


class TestMySQLConcurrencyAware:
    """Test ConcurrencyAware protocol implementation for SQL Server backend."""

    def test_sqlserver_backend_implements_protocol(self, sqlserver_backend_single):
        """Test that SQLServerBackend implements ConcurrencyAware protocol."""
        assert isinstance(sqlserver_backend_single, ConcurrencyAware)

    def test_mysql_get_concurrency_hint(self, sqlserver_backend_single):
        """Test SQLServerBackend returns correct concurrency hint."""
        hint = sqlserver_backend_single.get_concurrency_hint()

        assert hint is not None
        assert isinstance(hint, ConcurrencyHint)
        assert hint.max_concurrency is not None
        assert hint.max_concurrency > 0
        assert "max_connections" in hint.reason
        assert "pool_size" in hint.reason

    def test_mysql_concurrency_hint_value(self, sqlserver_backend_single):
        """Test concurrency hint value is bounded by pool_size."""
        pool_size = sqlserver_backend_single.config.pool_size or 5
        hint = sqlserver_backend_single.get_concurrency_hint()

        assert hint.max_concurrency <= pool_size
        assert hint.max_concurrency > 0

    def test_mysql_concurrency_hint_not_none_after_connect(self, sqlserver_backend_single):
        """Test that concurrency hint is populated after connect."""
        assert sqlserver_backend_single._connection is not None
        assert sqlserver_backend_single.get_concurrency_hint() is not None


class TestAsyncMySQLConcurrencyAware:
    """Test ConcurrencyAware protocol implementation for async SQL Server backend."""

    @pytest.mark.asyncio
    async def test_async_sqlserver_backend_implements_protocol(self, async_sqlserver_backend_single):
        """Test that AsyncSQLServerBackend implements ConcurrencyAware protocol."""
        assert isinstance(async_sqlserver_backend_single, ConcurrencyAware)

    @pytest.mark.asyncio
    async def test_async_mysql_get_concurrency_hint(self, async_sqlserver_backend_single):
        """Test AsyncSQLServerBackend returns correct concurrency hint."""
        hint = async_sqlserver_backend_single.get_concurrency_hint()

        assert hint is not None
        assert isinstance(hint, ConcurrencyHint)
        assert hint.max_concurrency is not None
        assert hint.max_concurrency > 0
        assert "max_connections" in hint.reason
        assert "pool_size" in hint.reason

    @pytest.mark.asyncio
    async def test_async_mysql_concurrency_hint_value(self, async_sqlserver_backend_single):
        """Test async concurrency hint value is bounded by pool_size."""
        pool_size = async_sqlserver_backend_single.config.pool_size or 5
        hint = async_sqlserver_backend_single.get_concurrency_hint()

        assert hint.max_concurrency <= pool_size
        assert hint.max_concurrency > 0

    @pytest.mark.asyncio
    async def test_async_mysql_concurrency_hint_not_none_after_connect(
        self, async_sqlserver_backend_single
    ):
        """Test that async concurrency hint is populated after connect."""
        assert async_sqlserver_backend_single._connection is not None
        assert async_sqlserver_backend_single.get_concurrency_hint() is not None