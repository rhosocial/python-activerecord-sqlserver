# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_spatial_expressions.py
"""
Tests for MySQL spatial expression classes.

This module tests the following expression classes:
- SQLServerSTGeomFromTextExpression
- SQLServerSTDistanceExpression
- SQLServerSTWithinExpression
- SQLServerSTContainsExpression
"""
import pytest
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression import (
    SQLServerSTGeomFromTextExpression,
    SQLServerSTDistanceExpression,
    SQLServerSTWithinExpression,
    SQLServerSTContainsExpression,
)


class TestMySQLSTGeomFromTextExpression:
    """Test SQLServerSTGeomFromTextExpression class."""

    def test_st_geom_from_text_basic(self):
        """Test basic geometry from text."""
        dialect = SQLServerDialect(version=(8, 0, 0))
        
        expr = SQLServerSTGeomFromTextExpression(dialect, 'POINT(1 1)')
        sql, params = expr.to_sql()
        
        assert 'ST_GeomFromText' in sql
        assert 'POINT(1 1)' in params
    
    def test_st_geom_from_text_with_alias(self):
        """Test geometry from text with alias."""
        dialect = SQLServerDialect(version=(8, 0, 0))
        
        expr = SQLServerSTGeomFromTextExpression(dialect, 'POINT(1 1)').as_('pt')
        sql, params = expr.to_sql()
        
        assert 'ST_GeomFromText' in sql
        assert 'AS `pt`' in sql
    
    def test_st_geom_from_text_linestring(self):
        """Test geometry from text with linestring."""
        dialect = SQLServerDialect(version=(8, 0, 0))
        
        expr = SQLServerSTGeomFromTextExpression(dialect, 'LINESTRING(0 0, 1 1, 2 2)')
        sql, params = expr.to_sql()
        
        assert 'ST_GeomFromText' in sql
        assert 'LINESTRING' in params[0]


class TestMySQLSTDistanceExpression:
    """Test SQLServerSTDistanceExpression class."""

    def test_st_distance_basic(self):
        """Test basic distance calculation."""
        dialect = SQLServerDialect(version=(8, 0, 0))
        
        expr = SQLServerSTDistanceExpression(dialect, 'pt1', 'pt2')
        sql, params = expr.to_sql()
        
        assert 'ST_Distance' in sql
        assert 'pt1' in sql
        assert 'pt2' in sql
    
    def test_st_distance_with_alias(self):
        """Test distance with alias."""
        dialect = SQLServerDialect(version=(8, 0, 0))
        
        expr = SQLServerSTDistanceExpression(dialect, 'pt1', 'pt2').as_('dist')
        sql, params = expr.to_sql()
        
        assert 'ST_Distance' in sql
        assert 'AS `dist`' in sql


class TestMySQLSTWithinExpression:
    """Test SQLServerSTWithinExpression class."""

    def test_st_within_basic(self):
        """Test basic within check."""
        dialect = SQLServerDialect(version=(8, 0, 0))
        
        expr = SQLServerSTWithinExpression(dialect, 'geom1', 'geom2')
        sql, params = expr.to_sql()
        
        assert 'ST_Within' in sql
        assert 'geom1' in sql
        assert 'geom2' in sql
    
    def test_st_within_with_alias(self):
        """Test within with alias."""
        dialect = SQLServerDialect(version=(8, 0, 0))
        
        expr = SQLServerSTWithinExpression(dialect, 'geom1', 'geom2').as_('within')
        sql, params = expr.to_sql()
        
        assert 'ST_Within' in sql
        assert 'AS `within`' in sql


class TestMySQLSTContainsExpression:
    """Test SQLServerSTContainsExpression class."""

    def test_st_contains_basic(self):
        """Test basic contains check."""
        dialect = SQLServerDialect(version=(8, 0, 0))
        
        expr = SQLServerSTContainsExpression(dialect, 'geom1', 'geom2')
        sql, params = expr.to_sql()
        
        assert 'ST_Contains' in sql
        assert 'geom1' in sql
        assert 'geom2' in sql
    
    def test_st_contains_with_alias(self):
        """Test contains with alias."""
        dialect = SQLServerDialect(version=(8, 0, 0))
        
        expr = SQLServerSTContainsExpression(dialect, 'geom1', 'geom2').as_('contains')
        sql, params = expr.to_sql()
        
        assert 'ST_Contains' in sql
        assert 'AS `contains`' in sql