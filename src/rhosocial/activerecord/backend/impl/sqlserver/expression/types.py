# src/rhosocial/activerecord/backend/impl/sqlserver/expression/types.py
"""SQL Server-specific DataType subclasses.

Backend-specific types carry the ``sqlserver_`` prefix in their ``name``
attribute.  Core types (inherited from ``rhosocial.activerecord.backend.expression.types``)
retain their pure names and are rendered to SQL Server syntax by the dialect's
``format_data_type_<name>`` methods.
"""

from typing import Any, Dict, Optional, Set

from rhosocial.activerecord.backend.expression.types import (
    VarCharType,
    CharType,
    IntegerType,
    BlobType,
    BooleanType,
)


class SQLServerNVarCharType(VarCharType):
    """SQL Server NVARCHAR type."""

    name = "sqlserver_nvarchar"

    def __init__(self, dialect=None, length: Optional[int] = None,
                 dialect_options: Optional[Dict[str, Any]] = None):
        super().__init__(dialect, length=length, dialect_options=dialect_options)

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"VarCharType"}


class SQLServerNCharType(CharType):
    """SQL Server NCHAR type."""

    name = "sqlserver_nchar"

    def __init__(self, dialect=None, length: Optional[int] = None,
                 dialect_options: Optional[Dict[str, Any]] = None):
        super().__init__(dialect, length=length, dialect_options=dialect_options)

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"CharType"}


class SQLServerNVarCharMaxType(VarCharType):
    """SQL Server NVARCHAR(MAX) type."""

    name = "sqlserver_nvarchar_max"

    def __init__(self, dialect=None, dialect_options: Optional[Dict[str, Any]] = None):
        super().__init__(dialect, length=None, dialect_options=dialect_options)

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"VarCharType", "TextType"}


class SQLServerVarBinaryType(BlobType):
    """SQL Server VARBINARY type."""

    name = "sqlserver_varbinary"

    length: Optional[int] = None

    def __init__(self, dialect=None, length: Optional[int] = None,
                 dialect_options: Optional[Dict[str, Any]] = None):
        super().__init__(dialect, dialect_options=dialect_options)
        self.length = length

    def _type_params(self) -> tuple:
        return (self.length,)

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"BlobType"}


class SQLServerVarBinaryMaxType(BlobType):
    """SQL Server VARBINARY(MAX) type."""

    name = "sqlserver_varbinary_max"

    def __init__(self, dialect=None, dialect_options: Optional[Dict[str, Any]] = None):
        super().__init__(dialect, dialect_options=dialect_options)

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"BlobType", "TextType"}


class SQLServerXmlType(VarCharType):
    """SQL Server XML type."""

    name = "sqlserver_xml"

    def __init__(self, dialect=None, dialect_options: Optional[Dict[str, Any]] = None):
        super().__init__(dialect, length=None, dialect_options=dialect_options)

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"VarCharType", "TextType"}


class SQLServerTinyIntType(IntegerType):
    """SQL Server TINYINT type."""

    name = "sqlserver_tinyint"

    def __init__(self, dialect=None, dialect_options: Optional[Dict[str, Any]] = None):
        super().__init__(dialect, dialect_options=dialect_options)

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"TinyIntType"}


class SQLServerBitType(BooleanType):
    """SQL Server BIT type."""

    name = "sqlserver_bit"

    def __init__(self, dialect=None, dialect_options: Optional[Dict[str, Any]] = None):
        super().__init__(dialect, dialect_options=dialect_options)

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"BooleanType"}


class SQLServerImageType(BlobType):
    """SQL Server IMAGE type (deprecated)."""

    name = "sqlserver_image"

    def __init__(self, dialect=None, dialect_options: Optional[Dict[str, Any]] = None):
        super().__init__(dialect, dialect_options=dialect_options)

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"BlobType"}


__all__ = [
    "SQLServerNVarCharType",
    "SQLServerNCharType",
    "SQLServerNVarCharMaxType",
    "SQLServerVarBinaryType",
    "SQLServerVarBinaryMaxType",
    "SQLServerXmlType",
    "SQLServerTinyIntType",
    "SQLServerBitType",
    "SQLServerImageType",
]
