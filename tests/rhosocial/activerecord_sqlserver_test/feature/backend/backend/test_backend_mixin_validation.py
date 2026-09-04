# tests/rhosocial/activerecord_sqlserver_test/feature/backend/backend/test_backend_mixin_validation.py
"""Offline tests for SQLServerBackendMixin validation and parameterization.

Covers the whitelist/range validation branches of ``set_deadlock_priority``,
``set_language`` and ``set_dateformat``, plus the parameterized identity
queries, without requiring a live server.
"""
from unittest.mock import MagicMock

import pytest

from rhosocial.activerecord.backend.impl.sqlserver import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig


def make_backend() -> SQLServerBackend:
    config = SQLServerConnectionConfig(
        host="localhost", port=1433, database="master",
        username="sa", password="",
    )
    backend = SQLServerBackend(connection_config=config)
    backend._connection = object()
    return backend


def make_cursor(backend):
    cursor = MagicMock()
    backend._get_cursor = lambda: cursor
    return cursor


class TestSetDeadlockPriority:
    def test_integer_in_range(self):
        backend = make_backend()
        cursor = make_cursor(backend)
        backend.set_deadlock_priority(-5)
        cursor.execute.assert_called_once_with("SET DEADLOCK_PRIORITY -5")

    def test_integer_out_of_range_raises(self):
        backend = make_backend()
        make_cursor(backend)
        for value in (-11, 11):
            with pytest.raises(ValueError, match="DEADLOCK_PRIORITY"):
                backend.set_deadlock_priority(value)

    def test_valid_name(self):
        backend = make_backend()
        cursor = make_cursor(backend)
        backend.set_deadlock_priority("high")
        cursor.execute.assert_called_once_with("SET DEADLOCK_PRIORITY HIGH")

    def test_invalid_name_raises(self):
        backend = make_backend()
        make_cursor(backend)
        with pytest.raises(ValueError, match="DEADLOCK_PRIORITY"):
            backend.set_deadlock_priority("EVIL")


class TestSetLanguage:
    def test_valid_language_lowercased(self):
        backend = make_backend()
        cursor = make_cursor(backend)
        backend.set_language("US_ENGLISH")
        cursor.execute.assert_called_once_with("SET LANGUAGE 'us_english'")

    def test_invalid_language_raises(self):
        backend = make_backend()
        make_cursor(backend)
        with pytest.raises(ValueError, match="Unsupported SQL Server language"):
            backend.set_language("klingon; DROP TABLE--")


class TestSetDateformat:
    def test_valid_format_lowercased(self):
        backend = make_backend()
        cursor = make_cursor(backend)
        backend.set_dateformat("MDY")
        cursor.execute.assert_called_once_with("SET DATEFORMAT mdy")

    def test_invalid_format_raises(self):
        backend = make_backend()
        make_cursor(backend)
        with pytest.raises(ValueError, match="DATEFORMAT"):
            backend.set_dateformat("XYZ")


class TestIdentityQueries:
    def test_get_identity_current_parameterized(self):
        backend = make_backend()
        cursor = make_cursor(backend)
        cursor.fetchone.return_value = (42,)
        assert backend.get_identity_current("users") == 42
        cursor.execute.assert_called_once_with(
            "SELECT IDENT_CURRENT(?)", ("users",)
        )

    def test_reset_identity_parameterized(self):
        backend = make_backend()
        cursor = make_cursor(backend)
        backend.reset_identity("users", 5)
        cursor.execute.assert_called_once_with(
            "DBCC CHECKIDENT(?, RESEED, ?)", ("users", 5)
        )