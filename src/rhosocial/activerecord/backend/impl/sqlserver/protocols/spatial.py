# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/spatial.py
"""SQL Server spatial data type protocol.

SQL Server exposes spatial operations through the ``geometry``/``geography``
types (``geometry::STGeomFromText``, ``geom.STAsText()``, ...). Each
formatter accepts its expression node and reads the state off
``expr.<attr>``.
"""

from typing import Protocol, Tuple, runtime_checkable


@runtime_checkable
class SQLServerSpatialSupport(Protocol):
    """SQL Server spatial data type protocol."""

    def supports_spatial_type(self, type_name: str) -> bool:
        """Whether a specific spatial data type is supported (2008+)."""
        ...

    def supports_spatial_index(self) -> bool:
        """Whether SPATIAL indexes are supported (2008+)."""
        ...

    def supports_geojson(self) -> bool:
        """Whether STAsGeoJSON is available in the installed types assembly."""
        ...

    def format_spatial_literal(self, expr) -> Tuple[str, tuple]:
        """Format a :class:`SQLServerSpatialLiteralExpression` node."""
        ...

    def format_st_geom_from_text(self, expr) -> Tuple[str, tuple]:
        """Format a :class:`SQLServerSTGeomFromTextExpression` node."""
        ...

    def format_st_as_text(self, expr) -> Tuple[str, tuple]:
        """Format a :class:`SQLServerSTAsTextExpression` node."""
        ...

    def format_st_as_geojson(self, expr) -> Tuple[str, tuple]:
        """Format a :class:`SQLServerSTAsGeoJSONExpression` node."""
        ...

    def format_st_distance(self, expr) -> Tuple[str, tuple]:
        """Format a :class:`SQLServerSTDistanceExpression` node."""
        ...

    def format_st_within(self, expr) -> Tuple[str, tuple]:
        """Format a :class:`SQLServerSTWithinExpression` node."""
        ...

    def format_st_contains(self, expr) -> Tuple[str, tuple]:
        """Format a :class:`SQLServerSTContainsExpression` node."""
        ...

    def format_st_distance_sphere(self, expr) -> Tuple[str, tuple]:
        """Format a :class:`SQLServerSTDistanceSphereExpression` node."""
        ...

    def format_st_intersects(self, expr) -> Tuple[str, tuple]:
        """Format a :class:`SQLServerSTIntersectsExpression` node."""
        ...

    def format_create_spatial_index(self, expr) -> Tuple[str, tuple]:
        """Format a :class:`SQLServerCreateSpatialIndexExpression` node."""
        ...
