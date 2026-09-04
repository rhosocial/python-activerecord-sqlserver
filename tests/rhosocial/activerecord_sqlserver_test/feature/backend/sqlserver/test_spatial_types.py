# tests/rhosocial/activerecord_sqlserver_test/feature/backend/sqlserver/test_spatial_types.py
"""
SQL Server spatial data type support tests.

This module tests SQL Server-specific spatial data type functionality including:
- Type support detection (geometry/geography since SQL Server 2008)
- Spatial literal formatting (geometry::STGeomFromText)
- Spatial function formatting (STAsText, STDistance, STWithin, ...)
- SPATIAL index creation
"""
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


class TestSpatialTypeProtocol:
    """Test spatial data type protocol implementation."""

    def test_supports_spatial_type_point(self):
        """Test POINT type support - SQL Server supports spatial types in all versions."""
        dialect_2008 = SQLServerDialect(version=(10, 3, 0))
        assert dialect_2008.supports_spatial_type('POINT')

        dialect_2016 = SQLServerDialect(version=(13, 0, 0))
        assert dialect_2016.supports_spatial_type('POINT')

    def test_supports_spatial_type_all_types(self):
        """Test all spatial types support."""
        dialect = SQLServerDialect(version=(10, 3, 0))

        spatial_types = [
            'GEOMETRY', 'GEOGRAPHY', 'POINT', 'LINESTRING', 'POLYGON',
            'MULTIPOINT', 'MULTILINESTRING', 'MULTIPOLYGON',
            'GEOMETRYCOLLECTION'
        ]

        for stype in spatial_types:
            assert dialect.supports_spatial_type(stype), f"{stype} should be supported"

    def test_supports_spatial_type_invalid(self):
        """Test invalid spatial type."""
        dialect = SQLServerDialect(version=(10, 3, 0))
        assert not dialect.supports_spatial_type('INVALID_TYPE')

    def test_supports_spatial_index(self):
        """Test SPATIAL index support - SQL Server 2008+."""
        dialect_2008 = SQLServerDialect(version=(10, 0, 0))
        assert dialect_2008.supports_spatial_index()

        dialect_2016 = SQLServerDialect(version=(13, 0, 0))
        assert dialect_2016.supports_spatial_index()

    def test_supports_geojson(self):
        """Test GeoJSON support - not available in the SQL Server types assembly."""
        dialect_2008 = SQLServerDialect(version=(10, 3, 0))
        assert not dialect_2008.supports_geojson()

        dialect_2022 = SQLServerDialect(version=(16, 0, 0))
        assert not dialect_2022.supports_geojson()


class TestSpatialLiteralFormatting:
    """Test spatial literal formatting."""

    def test_format_spatial_literal(self):
        """Test spatial literal formatting."""
        dialect = SQLServerDialect(version=(10, 3, 0))
        sql, params = dialect.format_spatial_literal("POINT(1 1)")
        assert "STGeomFromText" in sql
        assert params == ("POINT(1 1)", 0)

    def test_format_spatial_literal_with_srid(self):
        """Test spatial literal formatting with SRID."""
        dialect = SQLServerDialect(version=(10, 3, 0))
        sql, params = dialect.format_spatial_literal("POINT(1 1)", srid=4326)
        assert "STGeomFromText" in sql
        assert 4326 in params


class TestSpatialFunctionFormatting:
    """Test spatial function formatting."""

    def test_format_st_geom_from_text(self):
        """Test ST_GeomFromText formatting."""
        dialect = SQLServerDialect(version=(10, 3, 0))
        sql, params = dialect.format_st_geom_from_text("POINT(1 1)")
        assert "STGeomFromText" in sql
        assert params == ("POINT(1 1)", 0)

    def test_format_st_as_text(self):
        """Test STAsText formatting."""
        dialect = SQLServerDialect(version=(10, 3, 0))
        sql, params = dialect.format_st_as_text("geom_col")
        assert "STAsText" in sql
        assert "geom_col" in sql

    def test_format_st_as_geojson(self):
        """Test STAsGeoJSON formatting."""
        dialect = SQLServerDialect(version=(10, 3, 0))
        sql, params = dialect.format_st_as_geojson("geom_col")
        assert "STAsGeoJSON" in sql
        assert "geom_col" in sql

    def test_format_st_distance(self):
        """Test STDistance formatting."""
        dialect = SQLServerDialect(version=(10, 3, 0))
        sql, params = dialect.format_st_distance("geom1", "geom2")
        assert "STDistance" in sql

    def test_format_st_within(self):
        """Test STWithin formatting."""
        dialect = SQLServerDialect(version=(10, 3, 0))
        sql, params = dialect.format_st_within("geom1", "geom2")
        assert "STWithin" in sql

    def test_format_st_contains(self):
        """Test STContains formatting."""
        dialect = SQLServerDialect(version=(10, 3, 0))
        sql, params = dialect.format_st_contains("geom1", "geom2")
        assert "STContains" in sql

    def test_format_st_distance_sphere(self):
        """Test spherical distance formatting (STDistance approximation)."""
        dialect = SQLServerDialect(version=(10, 3, 0))
        sql, params = dialect.format_st_distance_sphere("geom1", "geom2")
        assert "STDistance" in sql

    def test_format_st_intersects(self):
        """Test STIntersects formatting."""
        dialect = SQLServerDialect(version=(10, 3, 0))
        sql, params = dialect.format_st_intersects("geom1", "geom2")
        assert "STIntersects" in sql


class TestSpatialIndexFormatting:
    """Test SPATIAL index creation formatting."""

    def test_format_create_spatial_index(self):
        """Test CREATE SPATIAL INDEX formatting."""
        dialect = SQLServerDialect(version=(10, 3, 0))
        sql, params = dialect.format_create_spatial_index("idx_spatial", "test_table", "geom_col")
        assert "SPATIAL INDEX" in sql
        assert "idx_spatial" in sql
        assert "test_table" in sql
        assert "geom_col" in sql

    def test_format_create_spatial_index_unsupported(self):
        """Test CREATE SPATIAL INDEX does not raise for supported versions."""
        # SQL Server supports spatial indexes since 2008, so this should not raise
        dialect = SQLServerDialect(version=(10, 3, 0))
        sql, params = dialect.format_create_spatial_index("idx_spatial", "test_table", "geom_col")
        assert "SPATIAL INDEX" in sql
