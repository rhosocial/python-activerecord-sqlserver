# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/types/test_adapter_suggestions.py
"""Offline coverage for SQLServerBackend type-adapter suggestions.

``get_default_adapter_suggestions`` is pure logic over the adapter registry;
exercising it needs no live server and closes a noted coverage gap in
backend_mixin (see .claude/plan/2026-08-26/coverage-restoration.md).

The suggestion table has two levels: the framework's core defaults are the
base, and this backend merges its own pairs on top.  The assertions below
therefore describe the merged result, not the backend's override list alone.
"""
import uuid
from datetime import date, datetime, time
from decimal import Decimal

import pytest

from rhosocial.activerecord.backend.adapters import (
    BitString,
    Geometry,
    MacAddress,
    Multirange,
    Range,
    Vector,
)
from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig

NEUTRAL_FAMILIES = (Geometry, Vector, BitString, Range, Multirange, MacAddress)


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

    def test_merged_table_keeps_core_defaults(self, backend):
        """The core table is the base; the backend completes it."""
        suggestions = backend.get_default_adapter_suggestions()
        for py_type in (bool, dict, list):
            assert py_type in suggestions, f"core default for {py_type} was dropped"

    def test_driver_native_types_stay_unregistered(self, backend):
        """int/float/str/bytes are intentionally not pre-registered."""
        suggestions = backend.get_default_adapter_suggestions()
        for py_type in (int, float, str, bytes):
            assert py_type not in suggestions

    def test_backend_overrides_win_over_core_defaults(self, backend):
        """SQL Server's own targets replace the core defaults per type."""
        suggestions = backend.get_default_adapter_suggestions()
        assert suggestions[bool][1] is bool
        assert suggestions[datetime][1] is datetime
        assert suggestions[Decimal][1] is Decimal

    def test_complex_types_map_to_string_storage(self, backend):
        suggestions = backend.get_default_adapter_suggestions()
        for py_type in (uuid.UUID, dict, list):
            _, db_type = suggestions[py_type]
            assert db_type is str

    def test_neutral_families_map_to_text_carriers(self, backend):
        """Neutral families have no native SQL Server column; they use text."""
        suggestions = backend.get_default_adapter_suggestions()
        for py_type in NEUTRAL_FAMILIES:
            assert py_type in suggestions, f"missing neutral suggestion for {py_type}"
            _, db_type = suggestions[py_type]
            assert db_type is str

    def test_result_is_cached(self, backend):
        first = backend.get_default_adapter_suggestions()
        second = backend.get_default_adapter_suggestions()
        assert first is second
