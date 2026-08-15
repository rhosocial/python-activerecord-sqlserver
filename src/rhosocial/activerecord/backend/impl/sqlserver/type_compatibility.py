# src/rhosocial/activerecord/backend/impl/sqlserver/type_compatibility.py
"""SQL Server type casting compatibility checks."""

from typing import Set, Tuple, Optional


DIRECT_COMPATIBLE_CASTS: Set[Tuple[str, str]] = {
    ("varchar", "varchar"),
    ("nvarchar", "nvarchar"),
    ("char", "char"),
    ("nchar", "nchar"),
    ("text", "text"),
    ("ntext", "ntext"),
    ("int", "int"),
    ("bigint", "bigint"),
    ("smallint", "smallint"),
    ("tinyint", "tinyint"),
    ("float", "float"),
    ("real", "real"),
    ("decimal", "decimal"),
    ("numeric", "numeric"),
    ("money", "money"),
    ("bit", "bit"),
    ("datetime", "datetime"),
    ("datetime2", "datetime2"),
    ("date", "date"),
    ("time", "time"),
    ("varbinary", "varbinary"),
    ("varchar", "nvarchar"),
    ("nvarchar", "varchar"),
    ("char", "nchar"),
    ("nchar", "char"),
    ("varchar", "text"),
    ("text", "varchar"),
    ("nvarchar", "ntext"),
    ("ntext", "nvarchar"),
    ("int", "bigint"),
    ("smallint", "int"),
    ("tinyint", "int"),
    ("tinyint", "smallint"),
    ("int", "bigint"),
    ("smallint", "bigint"),
    ("real", "float"),
    ("float", "real"),
    ("datetime2", "datetime"),
    ("bit", "int"),
    ("int", "bit"),
}


def check_cast_compatibility(source_type: Optional[str], target_type: str) -> bool:
    if source_type is None:
        return True
    if source_type.lower() == target_type.lower():
        return True
    if (source_type.lower(), target_type.lower()) not in DIRECT_COMPATIBLE_CASTS:
        import warnings
        warnings.warn(
            f"Type cast from '{source_type}' to '{target_type}' may fail or lose data in SQL Server.",
            UserWarning,
            stacklevel=3,
        )
    return True


def get_compatible_types(source_type: str) -> Set[str]:
    source_lower = source_type.lower()
    return {target for (source, target) in DIRECT_COMPATIBLE_CASTS if source == source_lower}


__all__ = [
    "DIRECT_COMPATIBLE_CASTS",
    "check_cast_compatibility",
    "get_compatible_types",
]