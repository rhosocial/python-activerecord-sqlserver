# src/rhosocial/activerecord/backend/impl/sqlserver/expression/spatial.py
"""SQL Server spatial expression classes for format_* signature compliance."""

from typing import Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import SQLValueExpression
from rhosocial.activerecord.backend.expression.mixins import (
    AliasableMixin,
    ComparisonMixin,
)

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class SQLServerSpatialLiteralExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server WKT literal using geometry::STGeomFromText.

    Example:
        >>> expr = SQLServerSpatialLiteralExpression(dialect, "POINT (1 2)", srid=4326)
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        wkt: str,
        srid: Optional[int] = None,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.wkt = wkt
        self.srid = srid
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_spatial_literal"


class SQLServerSTGeomFromTextExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server geometry::STGeomFromText call.

    Example:
        >>> expr = SQLServerSTGeomFromTextExpression(dialect, "POINT (1 2)", srid=0)
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        wkt: str,
        srid: Optional[int] = None,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.wkt = wkt
        self.srid = srid
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_st_geom_from_text"


class SQLServerSTAsTextExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server geometry STAsText method call.

    Example:
        >>> expr = SQLServerSTAsTextExpression(dialect, "geom_col")
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        geom: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.geom = geom
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_st_as_text"


class SQLServerSTAsGeoJSONExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server geometry STAsGeoJSON method call.

    Example:
        >>> expr = SQLServerSTAsGeoJSONExpression(dialect, "geom_col")
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        geom: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.geom = geom
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_st_as_geojson"


class SQLServerSTDistanceExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server geometry STDistance method call.

    Example:
        >>> expr = SQLServerSTDistanceExpression(dialect, "geom1", "geom2")
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        geom1: str,
        geom2: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.geom1 = geom1
        self.geom2 = geom2
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_st_distance"


class SQLServerSTWithinExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server geometry STWithin method call.

    Example:
        >>> expr = SQLServerSTWithinExpression(dialect, "geom1", "geom2")
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        geom1: str,
        geom2: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.geom1 = geom1
        self.geom2 = geom2
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_st_within"


class SQLServerSTContainsExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server geometry STContains method call.

    Example:
        >>> expr = SQLServerSTContainsExpression(dialect, "geom1", "geom2")
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        geom1: str,
        geom2: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.geom1 = geom1
        self.geom2 = geom2
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_st_contains"


class SQLServerSTDistanceSphereExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server spherical distance check.

    SQL Server has no ST_Distance_Sphere; STDistance is used for planar distance.

    Example:
        >>> expr = SQLServerSTDistanceSphereExpression(dialect, "geom1", "geom2")
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        geom1: str,
        geom2: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.geom1 = geom1
        self.geom2 = geom2
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_st_distance_sphere"


class SQLServerSTIntersectsExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server geometry STIntersects method call.

    Example:
        >>> expr = SQLServerSTIntersectsExpression(dialect, "geom1", "geom2")
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        geom1: str,
        geom2: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.geom1 = geom1
        self.geom2 = geom2
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_st_intersects"


class SQLServerCreateSpatialIndexExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server CREATE SPATIAL INDEX statement.

    Example:
        >>> expr = SQLServerCreateSpatialIndexExpression(dialect, "idx", "table", "geom")
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        index_name: str,
        table_name: str,
        column: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.index_name = index_name
        self.table_name = table_name
        self.column = column
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_create_spatial_index"
