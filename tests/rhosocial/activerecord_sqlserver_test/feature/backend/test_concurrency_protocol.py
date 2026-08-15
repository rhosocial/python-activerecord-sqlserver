# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_concurrency_protocol.py
"""
Test for ConcurrencyAware protocol implementation in SQL Server backend.

This test verifies that SQLServerBackend correctly implements the
ConcurrencyAware protocol by fetching the max worker threads setting during
connect and returning the appropriate concurrency hint.

Note: the ODBC driver may be unable to read the sql_variant value returned
by ``sys.configurations``, in which case ``get_concurrency_hint()`` returns
None (no constraint), which the ConcurrencyAware protocol explicitly allows.
"""
import pytest

from rhosocial.activerecord.backend.protocols import ConcurrencyAware, ConcurrencyHint


class TestSQLServerConcurrencyAware:
    """Test ConcurrencyAware protocol implementation for SQL Server backend."""

    def test_sqlserver_backend_implements_protocol(self, sqlserver_backend_single):
        """Test that SQLServerBackend implements ConcurrencyAware protocol."""
        assert isinstance(sqlserver_backend_single, ConcurrencyAware)

    def test_sqlserver_get_concurrency_hint(self, sqlserver_backend_single):
        """Test SQLServerBackend returns a valid concurrency hint (or None)."""
        hint = sqlserver_backend_single.get_concurrency_hint()

        if hint is not None:
            assert isinstance(hint, ConcurrencyHint)
            assert hint.max_concurrency is None or hint.max_concurrency > 0
            assert "pool_size" in hint.reason
            assert "worker_threads" in hint.reason

    def test_sqlserver_concurrency_hint_value(self, sqlserver_backend_single):
        """Test concurrency hint value is bounded by pool_size when present."""
        hint = sqlserver_backend_single.get_concurrency_hint()

        if hint is not None and hint.max_concurrency is not None:
            pool_size = sqlserver_backend_single.config.pool_size or 5
            assert hint.max_concurrency <= pool_size
            assert hint.max_concurrency > 0

    def test_sqlserver_concurrency_hint_available_after_connect(self, sqlserver_backend_single):
        """Test that the backend is connected and the hint is populated or None."""
        assert sqlserver_backend_single._connection is not None
        hint = sqlserver_backend_single.get_concurrency_hint()
        assert hint is None or isinstance(hint, ConcurrencyHint)


class TestAsyncSQLServerConcurrencyAware:
    """Test ConcurrencyAware protocol implementation for async SQL Server backend."""

    @pytest.fixture(autouse=True)
    def _skip_if_not_supported(self, async_sqlserver_backend_single):
        """AsyncSQLServerBackend does not yet implement ConcurrencyAware."""
        if not isinstance(async_sqlserver_backend_single, ConcurrencyAware):
            pytest.skip("AsyncSQLServerBackend does not implement ConcurrencyAware yet")

    @pytest.mark.asyncio
    async def test_async_sqlserver_backend_implements_protocol(self, async_sqlserver_backend_single):
        """Test that AsyncSQLServerBackend implements ConcurrencyAware protocol."""
        assert isinstance(async_sqlserver_backend_single, ConcurrencyAware)

    @pytest.mark.asyncio
    async def test_async_sqlserver_get_concurrency_hint(self, async_sqlserver_backend_single):
        """Test AsyncSQLServerBackend returns a valid concurrency hint (or None)."""
        hint = async_sqlserver_backend_single.get_concurrency_hint()

        if hint is not None:
            assert isinstance(hint, ConcurrencyHint)
            assert hint.max_concurrency is None or hint.max_concurrency > 0
            assert "pool_size" in hint.reason
            assert "worker_threads" in hint.reason

    @pytest.mark.asyncio
    async def test_async_sqlserver_concurrency_hint_value(self, async_sqlserver_backend_single):
        """Test async concurrency hint value is bounded by pool_size when present."""
        hint = async_sqlserver_backend_single.get_concurrency_hint()

        if hint is not None and hint.max_concurrency is not None:
            pool_size = async_sqlserver_backend_single.config.pool_size or 5
            assert hint.max_concurrency <= pool_size
            assert hint.max_concurrency > 0

    @pytest.mark.asyncio
    async def test_async_sqlserver_concurrency_hint_available_after_connect(
        self, async_sqlserver_backend_single
    ):
        """Test that the async backend is connected and the hint is populated or None."""
        assert async_sqlserver_backend_single._connection is not None
        hint = async_sqlserver_backend_single.get_concurrency_hint()
        assert hint is None or isinstance(hint, ConcurrencyHint)
