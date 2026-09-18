# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_spatial_types_backend.py
"""
SQL Server spatial data type integration tests using real database connection.

This module tests the SQL Server spatial data type functionality with actual
database operations. SQL Server exposes spatial operations through the
geometry type (``geometry::STGeomFromText``, ``geom.STAsText()``, ...).
"""
import pytest

from rhosocial.activerecord.backend.impl.sqlserver.expression.spatial import (
    SQLServerCreateSpatialIndexExpression,
    SQLServerSpatialLiteralExpression,
    SQLServerSTContainsExpression,
    SQLServerSTDistanceExpression,
    SQLServerSTGeomFromTextExpression,
    SQLServerSTAsTextExpression,
    SQLServerSTWithinExpression,
)


class TestSQLServerSpatialTypeBackend:
    """Synchronous tests for SQL Server spatial types with real database."""

    def test_supports_spatial_type_detection(self, sqlserver_backend):
        """Test that dialect correctly detects spatial type support."""
        dialect = sqlserver_backend.dialect

        if dialect.version >= (10, 0, 0):
            assert dialect.supports_spatial_type('POINT')
            assert dialect.supports_spatial_type('GEOMETRY')
            assert not dialect.supports_spatial_type('INVALID_TYPE')
        else:
            assert not dialect.supports_spatial_type('POINT')

    def test_supports_spatial_index_detection(self, sqlserver_backend):
        """Test that dialect correctly detects SPATIAL index support."""
        dialect = sqlserver_backend.dialect

        if dialect.version >= (10, 0, 0):
            assert dialect.supports_spatial_index()
        else:
            assert not dialect.supports_spatial_index()

    def test_supports_geojson_detection(self, sqlserver_backend):
        """Test that dialect correctly detects GeoJSON support (unavailable)."""
        dialect = sqlserver_backend.dialect
        assert not dialect.supports_geojson()

    def test_format_spatial_literal_without_srid(self, sqlserver_backend):
        """Test format_spatial_literal generates correct SQL without SRID."""
        sqlserver_backend.execute("""
            CREATE TABLE #test_spatial_literal (
                id INT IDENTITY(1,1) PRIMARY KEY,
                location GEOMETRY
            )
        """)

        dialect = sqlserver_backend.dialect
        sql, params = SQLServerSpatialLiteralExpression(dialect, 'POINT(5 5)').to_sql()

        sqlserver_backend.execute(
            f"INSERT INTO #test_spatial_literal (location) VALUES ({sql})",
            params
        )

        result = sqlserver_backend.execute(
            "SELECT location.STAsText() as wkt FROM #test_spatial_literal WHERE id = 1"
        )

        assert 'POINT' in result.data[0]['wkt']
        assert '5 5' in result.data[0]['wkt']

        sqlserver_backend.execute("DROP TABLE IF EXISTS #test_spatial_literal")

    def test_format_spatial_literal_with_srid(self, sqlserver_backend):
        """Test format_spatial_literal generates correct SQL with SRID."""
        sqlserver_backend.execute("""
            CREATE TABLE #test_spatial_srid (
                id INT IDENTITY(1,1) PRIMARY KEY,
                location GEOMETRY
            )
        """)

        dialect = sqlserver_backend.dialect
        sql, params = SQLServerSpatialLiteralExpression(
            dialect, 'POINT(10 20)', srid=4326
        ).to_sql()

        sqlserver_backend.execute(
            f"INSERT INTO #test_spatial_srid (location) VALUES ({sql})",
            params
        )

        result = sqlserver_backend.execute(
            "SELECT location.STSrid as srid, location.STAsText() as wkt FROM #test_spatial_srid WHERE id = 1"
        )

        assert result.data[0]['srid'] == 4326
        assert 'POINT' in result.data[0]['wkt']
        assert '10 20' in result.data[0]['wkt']

        sqlserver_backend.execute("DROP TABLE IF EXISTS #test_spatial_srid")

    def test_format_st_geom_from_text_without_srid(self, sqlserver_backend):
        """Test format_st_geom_from_text generates correct SQL without SRID."""
        dialect = sqlserver_backend.dialect
        sql, params = SQLServerSTGeomFromTextExpression(dialect, 'POINT(3 4)').to_sql()

        result = sqlserver_backend.execute(
            f"SELECT {sql}.STAsText() as wkt",
            params
        )

        assert 'POINT' in result.data[0]['wkt']
        assert '3 4' in result.data[0]['wkt']

    def test_format_st_geom_from_text_with_srid(self, sqlserver_backend):
        """Test format_st_geom_from_text generates correct SQL with SRID."""
        dialect = sqlserver_backend.dialect
        sql, params = SQLServerSTGeomFromTextExpression(
            dialect, 'POINT(1 1)', srid=4326
        ).to_sql()

        result = sqlserver_backend.execute(
            f"SELECT {sql}.STSrid as srid",
            params
        )

        assert result.data[0]['srid'] == 4326

    def test_format_st_as_text(self, sqlserver_backend):
        """Test format_st_as_text generates correct SQL."""
        sqlserver_backend.execute("""
            CREATE TABLE #test_astext (
                id INT IDENTITY(1,1) PRIMARY KEY,
                location GEOMETRY
            )
        """)

        sqlserver_backend.execute(
            "INSERT INTO #test_astext (location) VALUES (geometry::STGeomFromText('POINT(7 8)', 0))"
        )

        dialect = sqlserver_backend.dialect
        sql, params = SQLServerSTAsTextExpression(dialect, 'location').to_sql()

        result = sqlserver_backend.execute(
            f"SELECT {sql} as wkt FROM #test_astext",
            params
        )

        assert 'POINT' in result.data[0]['wkt']
        assert '7 8' in result.data[0]['wkt']

        sqlserver_backend.execute("DROP TABLE IF EXISTS #test_astext")

    def test_format_st_as_geojson(self, sqlserver_backend):
        """Test format_st_as_geojson generates correct SQL."""
        dialect = sqlserver_backend.dialect
        if hasattr(dialect, 'supports_geojson') and not dialect.supports_geojson():
            pytest.skip("GeoJSON not supported by the SQL Server types assembly")

    def test_format_st_distance(self, sqlserver_backend):
        """Test format_st_distance generates correct SQL."""
        dialect = sqlserver_backend.dialect

        point1_sql, point1_params = SQLServerSTGeomFromTextExpression(
            dialect, 'POINT(0 0)'
        ).to_sql()
        point2_sql, point2_params = SQLServerSTGeomFromTextExpression(
            dialect, 'POINT(3 4)'
        ).to_sql()

        distance_sql, _ = SQLServerSTDistanceExpression(
            dialect, point1_sql, point2_sql
        ).to_sql()

        result = sqlserver_backend.execute(
            f"SELECT {distance_sql} as distance",
            point1_params + point2_params
        )

        assert abs(result.data[0]['distance'] - 5.0) < 0.001

    def test_format_st_within(self, sqlserver_backend):
        """Test format_st_within generates correct SQL."""
        dialect = sqlserver_backend.dialect

        point_sql, point_params = SQLServerSTGeomFromTextExpression(
            dialect, 'POINT(5 5)'
        ).to_sql()
        polygon_sql, polygon_params = SQLServerSTGeomFromTextExpression(
            dialect, 'POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))'
        ).to_sql()

        within_sql, _ = SQLServerSTWithinExpression(
            dialect, point_sql, polygon_sql
        ).to_sql()

        result = sqlserver_backend.execute(
            f"SELECT {within_sql} as is_within",
            point_params + polygon_params
        )

        assert result.data[0]['is_within'] == 1

    def test_format_st_contains(self, sqlserver_backend):
        """Test format_st_contains generates correct SQL."""
        dialect = sqlserver_backend.dialect

        polygon_sql, polygon_params = SQLServerSTGeomFromTextExpression(
            dialect, 'POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))'
        ).to_sql()
        point_sql, point_params = SQLServerSTGeomFromTextExpression(
            dialect, 'POINT(5 5)'
        ).to_sql()

        contains_sql, _ = SQLServerSTContainsExpression(
            dialect, polygon_sql, point_sql
        ).to_sql()

        result = sqlserver_backend.execute(
            f"SELECT {contains_sql} as contains_point",
            polygon_params + point_params
        )

        assert result.data[0]['contains_point'] == 1

    def test_format_create_spatial_index(self, sqlserver_backend):
        """Test format_create_spatial_index generates valid SQL."""
        dialect = sqlserver_backend.dialect
        if hasattr(dialect, 'supports_spatial_index') and not dialect.supports_spatial_index():
            pytest.skip("SPATIAL index not supported in this SQLServer version")

        sqlserver_backend.execute("""
            CREATE TABLE #test_spatial_idx (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name VARCHAR(100),
                location GEOMETRY NOT NULL
            )
        """)

        dialect = sqlserver_backend.dialect
        index_sql, params = SQLServerCreateSpatialIndexExpression(
            dialect, 'idx_location', '#test_spatial_idx', 'location'
        ).to_sql()

        sqlserver_backend.execute(index_sql)

        insert_sql, insert_params = SQLServerSpatialLiteralExpression(
            dialect, 'POINT(1 1)'
        ).to_sql()
        sqlserver_backend.execute(
            f"INSERT INTO #test_spatial_idx (name, location) VALUES ('test', {insert_sql})",
            insert_params
        )

        result = sqlserver_backend.execute(
            "SELECT COUNT(*) as cnt FROM #test_spatial_idx"
        )

        assert result.data[0]['cnt'] == 1

        sqlserver_backend.execute("DROP TABLE IF EXISTS #test_spatial_idx")


class TestAsyncSQLServerSpatialTypeBackend:
    """Asynchronous tests for SQL Server spatial types with real database."""

    @pytest.mark.asyncio
    async def test_async_supports_spatial_type_detection(self, async_sqlserver_backend):
        """Test that dialect correctly detects spatial type support (async)."""
        dialect = async_sqlserver_backend.dialect

        if dialect.version >= (10, 0, 0):
            assert dialect.supports_spatial_type('POINT')
            assert dialect.supports_spatial_type('GEOMETRY')
        else:
            assert not dialect.supports_spatial_type('POINT')

    @pytest.mark.asyncio
    async def test_async_format_spatial_literal(self, async_sqlserver_backend):
        """Test format_spatial_literal generates correct SQL (async)."""
        await async_sqlserver_backend.execute("""
            CREATE TABLE #test_async_spatial (
                id INT IDENTITY(1,1) PRIMARY KEY,
                location GEOMETRY
            )
        """)

        dialect = async_sqlserver_backend.dialect
        sql, params = SQLServerSpatialLiteralExpression(dialect, 'POINT(5 5)').to_sql()

        await async_sqlserver_backend.execute(
            f"INSERT INTO #test_async_spatial (location) VALUES ({sql})",
            params
        )

        result = await async_sqlserver_backend.execute(
            "SELECT location.STAsText() as wkt FROM #test_async_spatial WHERE id = 1"
        )

        assert 'POINT' in result.data[0]['wkt']
        assert '5 5' in result.data[0]['wkt']

        await async_sqlserver_backend.execute("DROP TABLE IF EXISTS #test_async_spatial")

    @pytest.mark.asyncio
    async def test_async_format_st_geom_from_text(self, async_sqlserver_backend):
        """Test format_st_geom_from_text generates correct SQL (async)."""
        dialect = async_sqlserver_backend.dialect
        sql, params = SQLServerSTGeomFromTextExpression(
            dialect, 'POINT(10 20)', srid=4326
        ).to_sql()

        result = await async_sqlserver_backend.execute(
            f"SELECT {sql}.STSrid as srid",
            params
        )

        assert result.data[0]['srid'] == 4326

    @pytest.mark.asyncio
    async def test_async_format_st_distance(self, async_sqlserver_backend):
        """Test format_st_distance generates correct SQL (async)."""
        dialect = async_sqlserver_backend.dialect

        point1_sql, point1_params = SQLServerSTGeomFromTextExpression(
            dialect, 'POINT(0 0)'
        ).to_sql()
        point2_sql, point2_params = SQLServerSTGeomFromTextExpression(
            dialect, 'POINT(3 4)'
        ).to_sql()

        distance_sql, _ = SQLServerSTDistanceExpression(
            dialect, point1_sql, point2_sql
        ).to_sql()

        result = await async_sqlserver_backend.execute(
            f"SELECT {distance_sql} as distance",
            point1_params + point2_params
        )

        assert abs(result.data[0]['distance'] - 5.0) < 0.001

    @pytest.mark.asyncio
    async def test_async_format_st_within(self, async_sqlserver_backend):
        """Test format_st_within generates correct SQL (async)."""
        dialect = async_sqlserver_backend.dialect

        point_sql, point_params = SQLServerSTGeomFromTextExpression(
            dialect, 'POINT(5 5)'
        ).to_sql()
        polygon_sql, polygon_params = SQLServerSTGeomFromTextExpression(
            dialect, 'POLYGON((0 0, 10 0, 10 10, 0 10, 0 0))'
        ).to_sql()

        within_sql, _ = SQLServerSTWithinExpression(
            dialect, point_sql, polygon_sql
        ).to_sql()

        result = await async_sqlserver_backend.execute(
            f"SELECT {within_sql} as is_within",
            point_params + polygon_params
        )

        assert result.data[0]['is_within'] == 1

    @pytest.mark.asyncio
    async def test_async_format_st_as_geojson(self, async_sqlserver_backend):
        """Test format_st_as_geojson generates correct SQL (async)."""
        dialect = async_sqlserver_backend.dialect
        if hasattr(dialect, 'supports_geojson') and not dialect.supports_geojson():
            pytest.skip("GeoJSON not supported by the SQL Server types assembly")

    @pytest.mark.asyncio
    async def test_async_format_create_spatial_index(self, async_sqlserver_backend):
        """Test format_create_spatial_index generates valid SQL (async)."""
        dialect = async_sqlserver_backend.dialect
        if hasattr(dialect, 'supports_spatial_index') and not dialect.supports_spatial_index():
            pytest.skip("SPATIAL index not supported in this SQLServer version")

        await async_sqlserver_backend.execute("""
            CREATE TABLE #test_async_idx (
                id INT IDENTITY(1,1) PRIMARY KEY,
                location GEOMETRY NOT NULL
            )
        """)

        dialect = async_sqlserver_backend.dialect
        index_sql, _ = SQLServerCreateSpatialIndexExpression(
            dialect, 'idx_loc', '#test_async_idx', 'location'
        ).to_sql()

        await async_sqlserver_backend.execute(index_sql)

        insert_sql, insert_params = SQLServerSpatialLiteralExpression(
            dialect, 'POINT(1 1)'
        ).to_sql()
        await async_sqlserver_backend.execute(
            f"INSERT INTO #test_async_idx (location) VALUES ({insert_sql})",
            insert_params
        )

        result = await async_sqlserver_backend.execute(
            "SELECT COUNT(*) as cnt FROM #test_async_idx"
        )

        assert result.data[0]['cnt'] == 1

        await async_sqlserver_backend.execute("DROP TABLE IF EXISTS #test_async_idx")
