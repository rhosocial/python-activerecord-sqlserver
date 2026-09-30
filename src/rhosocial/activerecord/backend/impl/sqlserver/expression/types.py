# src/rhosocial/activerecord/backend/impl/sqlserver/expression/types.py
"""SQL Server-specific DataType subclasses.

Backend-specific types carry the ``sqlserver_`` prefix in their ``name``
attribute.  Core types (inherited from ``rhosocial.activerecord.backend.expression.types``)
retain their pure names and are rendered to SQL Server syntax by the dialect's
``format_data_type_<name>`` methods.
"""

from typing import Optional, Set

from rhosocial.activerecord.backend.expression.types import (
    VarCharType,
    CharType,
    IntegerType,
    BlobType,
    BooleanType,
)
from rhosocial.activerecord.backend.expression.types._base import DataType


class SQLServerNVarCharType(VarCharType):
    """SQL Server NVARCHAR type."""

    name = "sqlserver_nvarchar"

    def __init__(self, dialect=None, length: Optional[int] = None):
        super().__init__(dialect, length=length)

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"VarCharType"}


class SQLServerNCharType(CharType):
    """SQL Server NCHAR type."""

    name = "sqlserver_nchar"

    def __init__(self, dialect=None, length: Optional[int] = None):
        super().__init__(dialect, length=length)

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"CharType"}


class SQLServerNVarCharMaxType(VarCharType):
    """SQL Server NVARCHAR(MAX) type."""

    name = "sqlserver_nvarchar_max"

    def __init__(self, dialect=None):
        super().__init__(dialect, length=None)

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"VarCharType", "TextType"}


class SQLServerVarBinaryType(BlobType):
    """SQL Server VARBINARY type."""

    name = "sqlserver_varbinary"

    length: Optional[int] = None

    def __init__(self, dialect=None, length: Optional[int] = None):
        super().__init__(dialect)
        self.length = length

    def _type_params(self) -> tuple:
        return (self.length,)

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"BlobType"}


class SQLServerVarBinaryMaxType(BlobType):
    """SQL Server VARBINARY(MAX) type."""

    name = "sqlserver_varbinary_max"

    def __init__(self, dialect=None):
        super().__init__(dialect)

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"BlobType", "TextType"}


class SQLServerXmlType(VarCharType):
    """SQL Server XML type."""

    name = "sqlserver_xml"

    def __init__(self, dialect=None):
        super().__init__(dialect, length=None)

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"VarCharType", "TextType"}


class SQLServerTinyIntType(IntegerType):
    """SQL Server TINYINT type."""

    name = "sqlserver_tinyint"

    def __init__(self, dialect=None):
        super().__init__(dialect)

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"TinyIntType"}


class SQLServerBitType(BooleanType):
    """SQL Server BIT type."""

    name = "sqlserver_bit"

    def __init__(self, dialect=None):
        super().__init__(dialect)

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"BooleanType"}


class SQLServerImageType(BlobType):
    """SQL Server IMAGE type (deprecated)."""

    name = "sqlserver_image"

    def __init__(self, dialect=None):
        super().__init__(dialect)

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"BlobType"}


class SQLServerUniqueIdentifierType(DataType):
    """SQL Server ``UNIQUEIDENTIFIER``.

    The native storage for a UUID here. It is a distinct type rather than a
    rendering of the generic :class:`UUIDType` because SQL Server spells it
    differently, and because ``suggested_data_types()`` must not suggest a
    type the dialect can render itself: a suggestion is by definition a type
    with no ``format_data_type_<name>`` on this backend.

    Named ``sqlserver_uniqueidentifier`` so the dispatch key stays isolated
    from other backends' ``format_data_type_*`` families.
    """

    name = "sqlserver_uniqueidentifier"


__all__ = [
    "SQLServerUniqueIdentifierType",
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
