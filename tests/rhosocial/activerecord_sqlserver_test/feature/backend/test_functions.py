# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_functions.py
"""
Tests for SQLServer-specific SQL function factories.

Tests the supports_functions() method and function factories.
"""

import pytest

from rhosocial.activerecord.backend.impl.sqlserver import functions
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


class TestFunctionsModule:
    """Test the functions module structure."""

    def test_functions_module_imports(self):
        """Test that functions module can be imported."""
        assert functions is not None
        assert hasattr(functions, "__all__")

    def test_functions_all_contains_expected(self):
        """Test that __all__ contains expected function names."""
        expected = [
            "json_extract",
            "json_unquote",
            "json_object",
            "json_array",
            "json_contains",
            "json_set",
            "json_remove",
            "json_type",
            "json_valid",
            "json_search",
            "st_geom_from_text",
            "st_geom_from_wkb",
            "st_as_text",
            "st_as_geojson",
            "st_distance",
            "st_within",
            "st_contains",
            "st_intersects",
            "match_against",
            "find_in_set",
            "elt",
            "field",
            "round_",
            "pow",
            "power",
            "sqrt",
            "mod",
            "ceil",
            "floor",
            "trunc",
            "max_",
            "min_",
            "avg",
            "bit_and",
            "bit_or",
            "bit_xor",
            "bit_count",
            "bit_get_bit",
            "bit_shift_left",
            "bit_shift_right",
        ]
        for func in expected:
            assert func in functions.__all__, f"Missing function: {func}"

    def test_functions_count(self):
        """Test total number of functions."""
        assert len(functions.__all__) == 40


class TestSupportsFunctions:
    """Test the supports_functions() method."""

    def test_supports_functions_returns_dict(self):
        """Test that supports_functions returns a dictionary."""
        dialect = SQLServerDialect(version=(10, 6, 0))
        result = dialect.supports_functions()
        assert isinstance(result, dict)

    def test_supports_functions_all_values_are_bool(self):
        """Test that all values in supports_functions are booleans."""
        dialect = SQLServerDialect(version=(10, 6, 0))
        result = dialect.supports_functions()
        for key, value in result.items():
            assert isinstance(value, bool), f"Non-bool value for {key}: {value}"

    def test_supports_functions_json_functions(self):
        """Test JSON functions are supported on modern SQLServer."""
        dialect = SQLServerDialect(version=(10, 6, 0))
        result = dialect.supports_functions()
        json_funcs = ["json_extract", "json_type", "json_valid", "json_search"]
        for func in json_funcs:
            assert result.get(func) is True, f"{func} should be True"

    def test_supports_functions_spatial_functions(self):
        """Test spatial functions are supported on modern SQLServer."""
        dialect = SQLServerDialect(version=(10, 2, 0))
        result = dialect.supports_functions()
        spatial_funcs = ["st_geom_from_text", "st_distance", "st_contains"]
        for func in spatial_funcs:
            assert result.get(func) is True, f"{func} should be True on 10.2+"

    def test_supports_functions_old_version(self):
        """Test functions are not supported on old SQLServer versions."""
        dialect_old = SQLServerDialect(version=(10, 1, 0))
        result_old = dialect_old.supports_functions()

        dialect_new = SQLServerDialect(version=(10, 6, 0))
        result_new = dialect_new.supports_functions()

        assert result_old.get("json_extract") is False
        assert result_new.get("json_extract") is True

    def test_supports_functions_version_boundaries(self):
        """Test version boundary checks."""
        dialect_10_2_3 = SQLServerDialect(version=(10, 2, 3))
        dialect_10_2_2 = SQLServerDialect(version=(10, 2, 2))

        result_10_2_3 = dialect_10_2_3.supports_functions()
        result_10_2_2 = dialect_10_2_2.supports_functions()

        assert result_10_2_3.get("json_extract") is True
        assert result_10_2_2.get("json_extract") is False

    def test_supports_functions_math_functions(self):
        """Test math functions are available on all versions."""
        dialect = SQLServerDialect(version=(10, 0, 0))
        result = dialect.supports_functions()
        math_funcs = ["round_", "pow", "sqrt", "ceil", "floor", "trunc"]
        for func in math_funcs:
            assert result.get(func) is True, f"{func} should be True"


class TestFunctionFactories:
    """Test individual function factories."""

    @pytest.fixture
    def dialect(self):
        """Create a dialect instance for testing."""
        return SQLServerDialect(version=(10, 6, 0))

    def test_json_extract(self, dialect):
        """Test json_extract factory."""
        result = functions.json_extract(dialect, "column", "$.name")
        assert result is not None

    def test_json_type(self, dialect):
        """Test json_type factory."""
        result = functions.json_type(dialect, "column")
        assert result is not None

    def test_json_valid(self, dialect):
        """Test json_valid factory."""
        result = functions.json_valid(dialect, "column")
        assert result is not None

    def test_json_search(self, dialect):
        """Test json_search factory."""
        result = functions.json_search(dialect, "column", "search")
        assert result is not None

    def test_st_geom_from_text(self, dialect):
        """Test st_geom_from_text factory."""
        result = functions.st_geom_from_text(dialect, "POINT(0 0)")
        assert result is not None

    def test_st_distance(self, dialect):
        """Test st_distance factory."""
        result = functions.st_distance(dialect, "geom1", "geom2")
        assert result is not None

    def test_round_(self, dialect):
        """Test round_ factory."""
        result = functions.round_(dialect, "value")
        assert result is not None

    def test_pow(self, dialect):
        """Test pow factory."""
        result = functions.pow(dialect, 2, 3)
        assert result is not None

    def test_bit_and(self, dialect):
        """Test bit_and factory."""
        result = functions.bit_and(dialect, 1, 2)
        assert result is not None

    def test_bit_count(self, dialect):
        """Test bit_count factory."""
        result = functions.bit_count(dialect, 5)
        assert result is not None

    def test_find_in_set(self, dialect):
        """Test find_in_set factory."""
        result = functions.find_in_set(dialect, "value", "column")
        assert result is not None

    def test_elt(self, dialect):
        """Test elt factory."""
        result = functions.elt(dialect, 1, "a", "b", "c")
        assert result is not None

    def test_field(self, dialect):
        """Test field factory."""
        result = functions.field(dialect, "b", "a", "b", "c")
        assert result is not None

    def test_match_against(self, dialect):
        """Test match_against factory returns expression object."""
        result = functions.match_against(dialect, "content", "search")
        assert result is not None
        assert hasattr(result, '__class__')