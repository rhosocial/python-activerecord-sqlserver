# tests/rhosocial/activerecord_sqlserver_test/feature/backend/concurrency/test_concurrency_hint.py
"""Offline unit tests for SQLServerConcurrencyMixin.

The mixin fetches the ``max worker threads`` configuration value during
connect() and computes a concurrency hint bounded by the connection pool
size. These tests exercise every branch with mocked cursors and configs so
no live SQL Server connection is required.
"""

import logging
from types import SimpleNamespace
from unittest.mock import Mock

from rhosocial.activerecord.backend.impl.sqlserver.mixins.concurrency import (
    SQLServerConcurrencyMixin,
)
from rhosocial.activerecord.backend.protocols import ConcurrencyHint


class _FakeBase:
    """Minimal base class so the mixin's ``super().connect()`` resolves."""

    def connect(self):
        """Mark the fake base as connected."""
        self._connected = True


class _StubConcurrencyBackend(SQLServerConcurrencyMixin, _FakeBase):
    """Stub backend that wires the mixin to controllable mocks."""

    def __init__(self, connection=None, config=None):
        """Initialize with mock connection, config, and a log recorder."""
        self._connection = connection
        self.config = config
        self._connected = False
        self.logs = []

    def log(self, level, message):
        """Record log calls for later assertions."""
        self.logs.append((level, message))


def _make_connection(fetchone_result=None, execute_error=None):
    """Build a mock connection whose cursor behaves as requested."""
    connection = Mock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = fetchone_result
    if execute_error is not None:
        cursor.execute.side_effect = execute_error
    return connection


class TestSQLServerConcurrencyMixin:
    """Test the SQLServerConcurrencyMixin hint computation offline."""

    def test_get_concurrency_hint_returns_none_before_fetch(self):
        """Test that an unfetched hint defaults to None (no constraint)."""
        backend = _StubConcurrencyBackend(
            connection=Mock(), config=SimpleNamespace(pool_size=5)
        )
        assert backend.get_concurrency_hint() is None, (
            "the hint must be None until _fetch_concurrency_hint runs"
        )

    def test_connect_calls_super_then_fetches_hint(self):
        """Test that connect() delegates to super() and populates the hint."""
        backend = _StubConcurrencyBackend(
            connection=_make_connection(fetchone_result=(16,)),
            config=SimpleNamespace(pool_size=5),
        )
        backend.connect()
        assert backend._connected is True, "super().connect() must have run"
        hint = backend.get_concurrency_hint()
        assert hint is not None, "connect() must populate the concurrency hint"
        assert hint.max_concurrency == 5, "hint must be min(threads, pool_size)"

    def test_fetch_hint_bounded_by_pool_size(self):
        """Test that a large worker-thread count is capped by pool_size."""
        backend = _StubConcurrencyBackend(
            connection=_make_connection(fetchone_result=(64,)),
            config=SimpleNamespace(pool_size=8),
        )
        backend._fetch_concurrency_hint()
        hint = backend.get_concurrency_hint()
        assert hint is not None, "a valid row must produce a hint"
        assert hint.max_concurrency == 8, "pool_size must win when smaller"

    def test_fetch_hint_bounded_by_worker_threads(self):
        """Test that a small worker-thread count wins over pool_size."""
        backend = _StubConcurrencyBackend(
            connection=_make_connection(fetchone_result=(3,)),
            config=SimpleNamespace(pool_size=10),
        )
        backend._fetch_concurrency_hint()
        hint = backend.get_concurrency_hint()
        assert hint is not None, "a valid row must produce a hint"
        assert hint.max_concurrency == 3, "max_worker_threads must win when smaller"

    def test_fetch_hint_uses_default_pool_size_when_missing(self):
        """Test that a config without pool_size falls back to the default 5."""
        backend = _StubConcurrencyBackend(
            connection=_make_connection(fetchone_result=(8,)),
            config=SimpleNamespace(),
        )
        backend._fetch_concurrency_hint()
        hint = backend.get_concurrency_hint()
        assert hint is not None, "a valid row must produce a hint"
        assert hint.max_concurrency == 5, "default pool_size of 5 must be used"

    def test_fetch_hint_uses_default_pool_size_when_falsy(self):
        """Test that falsy pool_size values (0/None) fall back to the default 5."""
        for pool_size in (0, None):
            backend = _StubConcurrencyBackend(
                connection=_make_connection(fetchone_result=(8,)),
                config=SimpleNamespace(pool_size=pool_size),
            )
            backend._fetch_concurrency_hint()
            hint = backend.get_concurrency_hint()
            assert hint is not None, "a valid row must produce a hint"
            assert hint.max_concurrency == 5, (
                f"falsy pool_size {pool_size!r} must fall back to 5"
            )

    def test_fetch_hint_reason_message(self):
        """Test that the hint reason records both inputs."""
        backend = _StubConcurrencyBackend(
            connection=_make_connection(fetchone_result=(16,)),
            config=SimpleNamespace(pool_size=5),
        )
        backend._fetch_concurrency_hint()
        hint = backend.get_concurrency_hint()
        assert hint is not None, "a valid row must produce a hint"
        assert "max_worker_threads=16" in hint.reason, (
            "reason must include the worker thread count"
        )
        assert "pool_size=5" in hint.reason, "reason must include the pool size"

    def test_fetch_hint_logs_debug_on_success(self):
        """Test that a successful fetch emits a DEBUG log message."""
        backend = _StubConcurrencyBackend(
            connection=_make_connection(fetchone_result=(16,)),
            config=SimpleNamespace(pool_size=5),
        )
        backend._fetch_concurrency_hint()
        assert any(level == logging.DEBUG for level, _ in backend.logs), (
            "a DEBUG log must be recorded after a successful fetch"
        )

    def test_fetch_hint_returns_none_when_no_row(self):
        """Test that an empty result leaves the hint unset (None)."""
        backend = _StubConcurrencyBackend(
            connection=_make_connection(fetchone_result=None),
            config=SimpleNamespace(pool_size=5),
        )
        backend._fetch_concurrency_hint()
        assert backend.get_concurrency_hint() is None, (
            "no row must leave the hint as None"
        )
        assert backend.logs == [], "no log should be recorded when no row exists"

    def test_fetch_hint_warns_and_returns_none_on_error(self):
        """Test that a cursor error is swallowed with a WARNING log."""
        backend = _StubConcurrencyBackend(
            connection=_make_connection(
                fetchone_result=(16,), execute_error=RuntimeError("boom")
            ),
            config=SimpleNamespace(pool_size=5),
        )
        backend._fetch_concurrency_hint()
        assert backend.get_concurrency_hint() is None, (
            "the hint must be reset to None when the query fails"
        )
        assert any(level == logging.WARNING for level, _ in backend.logs), (
            "a WARNING log must be recorded when the query fails"
        )

    def test_get_concurrency_hint_returns_cached_hint(self):
        """Test that get_concurrency_hint returns the cached hint object."""
        backend = _StubConcurrencyBackend(
            connection=_make_connection(fetchone_result=(16,)),
            config=SimpleNamespace(pool_size=5),
        )
        backend._fetch_concurrency_hint()
        hint = backend.get_concurrency_hint()
        assert isinstance(hint, ConcurrencyHint), "the hint must be a ConcurrencyHint"
        assert hint.max_concurrency == 5, "the cached hint value must be preserved"