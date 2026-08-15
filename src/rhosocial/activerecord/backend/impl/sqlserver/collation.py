# src/rhosocial/activerecord/backend/impl/sqlserver/collation.py
"""
SQL Server collation names supported by the dialect whitelist.
"""

from enum import Enum
from typing import Dict, Optional, Tuple


class SQLServerCollation(Enum):
    """Common SQL Server collations for expression-level COLLATE."""

    LATIN1_GENERAL_CI_AS = "Latin1_General_CI_AS"
    LATIN1_GENERAL_CS_AS = "Latin1_General_CS_AS"
    LATIN1_GENERAL_BIN2 = "Latin1_General_BIN2"
    SQL_LATIN1_GENERAL_CP1_CI_AS = "SQL_Latin1_General_CP1_CI_AS"
    SQL_LATIN1_GENERAL_CP1_CS_AS = "SQL_Latin1_General_CP1_CS_AS"
    SQL_LATIN1_GENERAL_CP1_BIN2 = "SQL_Latin1_General_CP1_BIN2"
    DATABASE_DEFAULT = "DATABASE_DEFAULT"


_SQLSERVER_COLLATIONS: Dict[str, str] = {
    collation.value.upper(): collation.value for collation in SQLServerCollation
}


def validate_sqlserver_collation_name(
    name: str,
    version: Optional[Tuple[int, int, int]] = None,
) -> str:
    normalized = name.upper()
    if normalized not in _SQLSERVER_COLLATIONS:
        raise ValueError(f"Unsupported SQL Server collation: {name!r}")
    return _SQLSERVER_COLLATIONS[normalized]
