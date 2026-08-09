# src/rhosocial/activerecord/backend/impl/sqlserver/functions/spatial.py
"""
SQL Server spatial function factories.

SQL Server exposes spatial operations through the geometry/geography CLR
types (``geometry::STGeomFromText``, ``geom.STAsText()``, etc.). These
factories render approximations using the equivalent SQL Server functions.

Functions: st_geom_from_text, st_geom_from_wkb, st_as_text, st_as_geojson,
st_distance, st_within, st_contains, st_intersects
"""

from typing import Union, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression import bases, core

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase
    from .dialect import SQLServerDialect


def _convert_to_expression(
    dialect: "SQLDialectBase",
    expr: Union[str, "bases.BaseExpression"],
    handle_numeric_literals: bool = True,
) -> "bases.BaseExpression":
    """Convert an input value to a BaseExpression."""
    if isinstance(expr, bases.BaseExpression):
        return expr
    elif handle_numeric_literals and isinstance(expr, (int, float)):
        return core.Literal(dialect, expr)
    else:
        return core.Column(dialect, expr)


def st_geom_from_text(
    dialect: "SQLServerDialect",
    wkt: Union[str, "bases.BaseExpression"],
    srid: Optional[int] = None,
) -> "core.FunctionCall":
    """Creates a ST_GeomFromText function call (SQL Server 2008+)."""
    args = [_convert_to_expression(dialect, wkt)]
    if srid is not None:
        args.append(core.Literal(dialect, srid))
    return core.FunctionCall(dialect, "ST_GeomFromText", args)


def st_geom_from_wkb(
    dialect: "SQLServerDialect",
    wkb: Union[str, "bases.BaseExpression"],
    srid: Optional[int] = None,
) -> "core.FunctionCall":
    """Creates a ST_GeomFromWKB function call (SQL Server 2008+)."""
    args = [_convert_to_expression(dialect, wkb)]
    if srid is not None:
        args.append(core.Literal(dialect, srid))
    return core.FunctionCall(dialect, "ST_GeomFromWKB", args)


def st_as_text(
    dialect: "SQLServerDialect",
    geom: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Creates an ST_AsText function call."""
    return core.FunctionCall(dialect, "ST_AsText", [_convert_to_expression(dialect, geom)])


def st_as_geojson(
    dialect: "SQLServerDialect",
    geom: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Creates an ST_AsGeoJSON function call."""
    return core.FunctionCall(dialect, "ST_AsGeoJSON", [_convert_to_expression(dialect, geom)])


def st_distance(
    dialect: "SQLServerDialect",
    geom1: Union[str, "bases.BaseExpression"],
    geom2: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Creates an ST_Distance function call."""
    return core.FunctionCall(
        dialect,
        "ST_Distance",
        [_convert_to_expression(dialect, geom1), _convert_to_expression(dialect, geom2)],
    )


def st_within(
    dialect: "SQLServerDialect",
    geom1: Union[str, "bases.BaseExpression"],
    geom2: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Creates an ST_Within function call."""
    return core.FunctionCall(
        dialect,
        "ST_Within",
        [_convert_to_expression(dialect, geom1), _convert_to_expression(dialect, geom2)],
    )


def st_contains(
    dialect: "SQLServerDialect",
    geom1: Union[str, "bases.BaseExpression"],
    geom2: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Creates an ST_Contains function call."""
    return core.FunctionCall(
        dialect,
        "ST_Contains",
        [_convert_to_expression(dialect, geom1), _convert_to_expression(dialect, geom2)],
    )


def st_intersects(
    dialect: "SQLServerDialect",
    geom1: Union[str, "bases.BaseExpression"],
    geom2: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Creates an ST_Intersects function call."""
    return core.FunctionCall(
        dialect,
        "ST_Intersects",
        [_convert_to_expression(dialect, geom1), _convert_to_expression(dialect, geom2)],
    )
