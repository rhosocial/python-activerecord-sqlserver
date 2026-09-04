# tests/rhosocial/activerecord_sqlserver_test/feature/backend/sqlserver/test_sqlserver_functions.py
"""
Tests for SQL Server function factories.

These tests verify that function factories can be imported and
instantiate FunctionCall objects correctly.
"""
import pytest
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.functions import (
    json_value,
    json_query,
    is_json,
    json_object,
    json_array,
    string_agg,
    concat_ws,
    trim,
    eomonth,
    datefromparts,
    datetime2fromparts,
    iif,
    choose,
    try_convert,
    coalesce,
    nullif,
    string_split,
)


class TestJSONFunctionsImport:
    """Tests for importing JSON functions."""

    def test_import_json_value(self):
        """Test json_value can be imported."""
        assert json_value is not None

    def test_import_json_query(self):
        """Test json_query can be imported."""
        assert json_query is not None

    def test_import_is_json(self):
        """Test is_json can be imported."""
        assert is_json is not None


class TestStringFunctionsImport:
    """Tests for importing string functions."""

    def test_import_concat_ws(self):
        """Test concat_ws can be imported."""
        assert concat_ws is not None

    def test_import_trim(self):
        """Test trim can be imported."""
        assert trim is not None

    def test_import_string_agg(self):
        """Test string_agg can be imported."""
        assert string_agg is not None


class TestDateTimeFunctionsImport:
    """Tests for importing datetime functions."""

    def test_import_eomonth(self):
        """Test eomonth can be imported."""
        assert eomonth is not None

    def test_import_datefromparts(self):
        """Test datefromparts can be imported."""
        assert datefromparts is not None


class TestUtilityFunctionsImport:
    """Tests for importing utility functions."""

    def test_import_iif(self):
        """Test iif can be imported."""
        assert iif is not None

    def test_import_choose(self):
        """Test choose can be imported."""
        assert choose is not None

    def test_import_try_convert(self):
        """Test try_convert can be imported."""
        assert try_convert is not None


class TestFunctionInstantiation:
    """Tests that functions can be instantiated with a dialect."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(version=(16, 0, 0))

    def test_json_value_instantiation(self, dialect):
        """Test JSON_VALUE can be instantiated."""
        result = json_value(dialect, "data", "$.name")
        assert result is not None

    def test_iif_instantiation(self, dialect):
        """Test IIF can be instantiated."""
        result = iif(dialect, "x > 1", "yes", "no")
        assert result is not None

    def test_concat_ws_instantiation(self, dialect):
        """Test CONCAT_WS can be instantiated."""
        result = concat_ws(dialect, ",", "a", "b")
        assert result is not None