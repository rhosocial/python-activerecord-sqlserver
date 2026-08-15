# src/rhosocial/activerecord/backend/impl/sqlserver/functions/__init__.py
"""SQL Server-specific functions.

This module provides function factories for SQL Server-specific
and standard SQL functions that have SQL Server-specific syntax.

Modules:
- json: JSON functions (JSON_VALUE, JSON_QUERY, ISJSON, JSON_OBJECT, ...)
- string: String functions (STRING_AGG, CONCAT_WS, TRIM, FIND_IN_SET, ...)
- datetime: DateTime functions (EOMONTH, DATEFROMPARTS)
- utility: Utility functions (IIF, CHOOSE, TRY_CONVERT)
- spatial: Spatial functions (ST_GeomFromText, ST_Distance, ...)
- math: Math functions (ROUND, POWER, SQRT, ...)
- bitwise: Bitwise functions (BIT_COUNT, LEFT_SHIFT, ...)
- aggregate: Aggregate functions (MAX, MIN, AVG)
"""

from .json import (
    json_value,  # noqa: F401
    json_query,  # noqa: F401
    is_json,  # noqa: F401
    json_object,
    json_array,
    json_path_exists,  # noqa: F401
    json_extract,
    json_unquote,
    json_contains,
    json_set,
    json_remove,
    json_type,
    json_valid,
    json_search,
)

from .string import (
    string_agg,  # noqa: F401
    concat_ws,  # noqa: F401
    trim,  # noqa: F401
    format,  # noqa: F401
    string_split,  # noqa: F401
    find_in_set,
    elt,
    field,
    match_against,
)

from .datetime import (
    eomonth,  # noqa: F401
    datefromparts,  # noqa: F401
    datetime2fromparts,  # noqa: F401
    timefromparts,  # noqa: F401
    datediff_big,  # noqa: F401
)

from .utility import (
    iif,  # noqa: F401
    choose,  # noqa: F401
    try_cast,  # noqa: F401
    try_convert,  # noqa: F401
    try_parse,  # noqa: F401
    coalesce,  # noqa: F401
    nullif,  # noqa: F401
)

from .spatial import (
    st_geom_from_text,
    st_geom_from_wkb,
    st_as_text,
    st_as_geojson,
    st_distance,
    st_within,
    st_contains,
    st_intersects,
)

from .math import (
    round_,
    pow,
    power,
    sqrt,
    mod,
    ceil,
    floor,
    trunc,
)

from .aggregate import (
    max_,
    min_,
    avg,
)

from .bitwise import (
    bit_and,
    bit_or,
    bit_xor,
    bit_count,
    bit_get_bit,
    bit_shift_left,
    bit_shift_right,
)

__all__ = [
    # JSON
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
    # Spatial
    "st_geom_from_text",
    "st_geom_from_wkb",
    "st_as_text",
    "st_as_geojson",
    "st_distance",
    "st_within",
    "st_contains",
    "st_intersects",
    # Full-text / SET
    "match_against",
    "find_in_set",
    "elt",
    "field",
    # Math
    "round_",
    "pow",
    "power",
    "sqrt",
    "mod",
    "ceil",
    "floor",
    "trunc",
    # Aggregate
    "max_",
    "min_",
    "avg",
    # Bitwise
    "bit_and",
    "bit_or",
    "bit_xor",
    "bit_count",
    "bit_get_bit",
    "bit_shift_left",
    "bit_shift_right",
]
