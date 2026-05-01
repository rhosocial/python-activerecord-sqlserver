# src/rhosocial/activerecord/backend/impl/sqlserver/functions/__init__.py
"""SQL Server-specific functions.

This module provides function factories for SQL Server-specific
and standard SQL functions that have SQL Server-specific syntax.

Modules:
- json: JSON functions (JSON_VALUE, JSON_QUERY, ISJSON)
- string: String functions (STRING_AGG, CONCAT_WS, TRIM)
- datetime: DateTime functions (EOMONTH, DATEFROMPARTS)
- utility: Utility functions (IIF, CHOOSE, TRY_CONVERT)
"""

from .json import (
    json_value,
    json_query,
    is_json,
    json_object,
    json_array,
    json_path_exists,
)

from .string import (
    string_agg,
    concat_ws,
    trim,
    format,
    string_split,
)

from .datetime import (
    eomonth,
    datefromparts,
    datetime2fromparts,
    timefromparts,
    datediff_big,
)

from .utility import (
    iif,
    choose,
    try_cast,
    try_convert,
    try_parse,
    coalesce,
    nullif,
)

__all__ = [
    # JSON
    "json_value",
    "json_query",
    "is_json",
    "json_object",
    "json_array",
    "json_path_exists",
    # String
    "string_agg",
    "concat_ws",
    "trim",
    "format",
    "string_split",
    # DateTime
    "eomonth",
    "datefromparts",
    "datetime2fromparts",
    "timefromparts",
    "datediff_big",
    # Utility
    "iif",
    "choose",
    "try_cast",
    "try_convert",
    "try_parse",
    "coalesce",
    "nullif",
]
