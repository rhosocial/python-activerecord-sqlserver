# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_enum_adapter.py
"""
MySQL ENUM type adapter tests.

This module tests the SQLServer-specific ENUM adapter functionality.
"""
import pytest
from enum import Enum
from rhosocial.activerecord.backend.impl.sqlserver.adapters import SQLServerEnumAdapter


# Test Enum definitions
class Status(str, Enum):
    """String-based enum for testing."""
    DRAFT = 'draft'
    PUBLISHED = 'published'
    ARCHIVED = 'archived'


class Priority(int, Enum):
    """Integer-based enum for testing."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class Color(str, Enum):
    """Another string enum for testing."""
    RED = 'red'
    GREEN = 'green'
    BLUE = 'blue'


class TestMySQLEnumAdapter:
    """Tests for MySQL ENUM type adapter."""

    def test_string_enum_to_database_string(self):
        """Test converting string enum to database string (default mode)."""
        adapter = SQLServerEnumAdapter()
        
        result = adapter.to_database(Status.DRAFT, str)
        assert result == 'draft'
        
        result = adapter.to_database(Status.PUBLISHED, str)
        assert result == 'published'
        
        result = adapter.to_database(Status.ARCHIVED, str)
        assert result == 'archived'

    def test_string_enum_from_database_string(self):
        """Test converting database string to string enum."""
        adapter = SQLServerEnumAdapter()
        
        result = adapter.from_database('draft', Status)
        assert result == Status.DRAFT
        
        result = adapter.from_database('published', Status)
        assert result == Status.PUBLISHED
        
        result = adapter.from_database('archived', Status)
        assert result == Status.ARCHIVED

    def test_int_enum_to_database_int(self):
        """Test converting int enum to database int."""
        adapter = SQLServerEnumAdapter()
        
        result = adapter.to_database(Priority.LOW, int)
        assert result == 1
        
        result = adapter.to_database(Priority.MEDIUM, int)
        assert result == 2
        
        result = adapter.to_database(Priority.HIGH, int)
        assert result == 3

    def test_int_enum_from_database_int(self):
        """Test converting database int to int enum."""
        adapter = SQLServerEnumAdapter()
        
        result = adapter.from_database(1, Priority)
        assert result == Priority.LOW
        
        result = adapter.from_database(2, Priority)
        assert result == Priority.MEDIUM
        
        result = adapter.from_database(3, Priority)
        assert result == Priority.HIGH

    def test_use_int_storage_mode(self):
        """Test using MySQL internal integer index."""
        adapter = SQLServerEnumAdapter(use_int_storage=True)
        
        # MySQL ENUM uses 1-based index
        # DRAFT=1, PUBLISHED=2, ARCHIVED=3
        result = adapter.to_database(Status.DRAFT, int)
        assert result == 1
        
        result = adapter.to_database(Status.PUBLISHED, int)
        assert result == 2
        
        result = adapter.to_database(Status.ARCHIVED, int)
        assert result == 3

    def test_use_int_storage_mode_override(self):
        """Test overriding use_int_storage via options."""
        adapter = SQLServerEnumAdapter(use_int_storage=False)
        
        # Override to use int storage for this call
        result = adapter.to_database(Status.PUBLISHED, int, {'use_int_storage': True})
        assert result == 2

    def test_restore_from_mysql_index(self):
        """Test restoring enum from MySQL internal index."""
        adapter = SQLServerEnumAdapter(use_int_storage=True)
        
        # Restore from MySQL index (1-based)
        result = adapter.from_database(1, Status)
        assert result == Status.DRAFT
        
        result = adapter.from_database(2, Status)
        assert result == Status.PUBLISHED
        
        result = adapter.from_database(3, Status)
        assert result == Status.ARCHIVED

    def test_null_handling(self):
        """Test NULL value handling."""
        adapter = SQLServerEnumAdapter()
        
        # to_database with None
        assert adapter.to_database(None, str) is None
        assert adapter.to_database(None, int) is None
        
        # from_database with None
        assert adapter.from_database(None, Status) is None
        assert adapter.from_database(None, Priority) is None

    def test_enum_values_validation(self):
        """Test validation with enum_values option."""
        adapter = SQLServerEnumAdapter()
        
        # Should pass - value is in allowed list
        adapter.to_database(Status.DRAFT, str, {'enum_values': ['draft', 'published']})
        adapter.to_database(Status.PUBLISHED, str, {'enum_values': ['draft', 'published']})
        
        # Should raise - value not in allowed list
        with pytest.raises(ValueError) as exc_info:
            adapter.to_database(Status.ARCHIVED, str, {'enum_values': ['draft', 'published']})
        
        assert 'Invalid enum value' in str(exc_info.value)
        assert 'archived' in str(exc_info.value)

    def test_invalid_target_type(self):
        """Test conversion to invalid target type."""
        adapter = SQLServerEnumAdapter()
        
        with pytest.raises(TypeError) as exc_info:
            adapter.to_database(Status.DRAFT, float)
        
        assert 'Cannot convert' in str(exc_info.value)

    def test_invalid_string_to_enum(self):
        """Test converting invalid string to enum."""
        adapter = SQLServerEnumAdapter()
        
        with pytest.raises(ValueError) as exc_info:
            adapter.from_database('invalid_status', Status)
        
        assert 'Invalid enum value' in str(exc_info.value)

    def test_invalid_int_to_enum(self):
        """Test converting invalid int to enum."""
        adapter = SQLServerEnumAdapter()
        
        # Out of range index
        with pytest.raises(ValueError) as exc_info:
            adapter.from_database(99, Status)
        
        assert 'Invalid enum index' in str(exc_info.value)

    def test_string_enum_to_int_without_use_int_storage(self):
        """Test that string enum to int conversion requires use_int_storage."""
        adapter = SQLServerEnumAdapter(use_int_storage=False)
        
        # Should raise TypeError when trying to convert string enum to int
        with pytest.raises(TypeError) as exc_info:
            adapter.to_database(Status.DRAFT, int)
        
        assert 'use_int_storage=True' in str(exc_info.value)

    def test_multiple_enum_types(self):
        """Test adapter with multiple different enum types."""
        adapter = SQLServerEnumAdapter()
        
        # Status enum
        assert adapter.to_database(Status.DRAFT, str) == 'draft'
        assert adapter.from_database('draft', Status) == Status.DRAFT
        
        # Color enum
        assert adapter.to_database(Color.RED, str) == 'red'
        assert adapter.from_database('green', Color) == Color.GREEN
        
        # Priority enum
        assert adapter.to_database(Priority.HIGH, int) == 3
        assert adapter.from_database(2, Priority) == Priority.MEDIUM

    def test_mysql_index_boundaries(self):
        """Test MySQL index at boundary values."""
        adapter = SQLServerEnumAdapter(use_int_storage=True)
        
        # First element (index 1)
        result = adapter.from_database(1, Status)
        assert result == Status.DRAFT
        
        # Last element
        result = adapter.from_database(3, Status)
        assert result == Status.ARCHIVED
        
        # Out of range - zero
        with pytest.raises(ValueError):
            adapter.from_database(0, Status)
        
        # Out of range - too high
        with pytest.raises(ValueError):
            adapter.from_database(4, Status)

    def test_options_parameter_none(self):
        """Test that methods work correctly with options=None."""
        adapter = SQLServerEnumAdapter()
        
        # to_database with None options
        result = adapter.to_database(Status.DRAFT, str, None)
        assert result == 'draft'
        
        # from_database with None options
        result = adapter.from_database('draft', Status, None)
        assert result == Status.DRAFT
