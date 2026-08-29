# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_adapter_suggestions.py
"""Offline coverage for SQLServerBackend type-adapter suggestions.

``get_default_adapter_suggestions`` is pure logic over the adapter registry;
exercising it needs no live server and closes a noted coverage gap in
backend_mixin (see .claude/plan/2026-08-26/coverage-restoration.md).
"""
import uuid
from datetime import date, datetime, time
from decimal import Decimal

import pytest

from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig


@pytest.fixture(scope="module")
def backend():
    config = SQLServerConnectionConfig(
        host="127.0.0.1",
        port=11433,
        database="master",
        username="sa",
        password="not-used-offline",
    )
    return SQLServerBackend(connection_config=config)


class TestDefaultAdapterSuggestions:
    def test_returns_mapping_for_registered_types(self, backend):
        suggestions = backend.get_default_adapter_suggestions()
        for py_type in (datetime, date, time, Decimal):
            assert py_type in suggestions, f"missing suggestion for {py_type}"

    def test_primitives_rely_on_default_binding(self, backend):
        """bool/int/float/str/bytes are intentionally not pre-registered."""
        suggestions = backend.get_default_adapter_suggestions()
        for py_type in (bool, int, float, str, bytes):
            assert py_type not in suggestions

    def test_complex_types_map_to_string_storage(self, backend):
        suggestions = backend.get_default_adapter_suggestions()
        for py_type in (uuid.UUID, dict, list):
            _, db_type = suggestions[py_type]
            assert db_type is str

    def test_result_is_cached(self, backend):
        first = backend.get_default_adapter_suggestions()
        second = backend.get_default_adapter_suggestions()
        assert first is second
