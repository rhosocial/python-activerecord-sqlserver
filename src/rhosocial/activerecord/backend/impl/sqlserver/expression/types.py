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


class SQLServerNVarCharType(VarCharType):
    """SQL Server NVARCHAR type."""

    name = "sqlserver_nvarchar"

    def __init__(self, length: Optional[int] = None, dialect=None):
        super().__init__(length, dialect)

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.length == other.length

    def __hash__(self) -> int:
        return hash((type(self), self.length))

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"VarCharType"}


class SQLServerNCharType(CharType):
    """SQL Server NCHAR type."""

    name = "sqlserver_nchar"

    def __init__(self, length: Optional[int] = None, dialect=None):
        super().__init__(length, dialect)

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.length == other.length

    def __hash__(self) -> int:
        return hash((type(self), self.length))

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"CharType"}


class SQLServerNVarCharMaxType(VarCharType):
    """SQL Server NVARCHAR(MAX) type."""

    name = "sqlserver_nvarchar_max"

    def __init__(self, dialect=None):
        super().__init__(None, dialect)

    @classmethod
    def synonyms(cls) -> Set[str]:
        return {"VarCharType", "TextType"}


class SQLServerVarBinaryType(BlobType):
    """SQL Server VARBINARY type."""

    name = "sqlserver_varbinary"

    length: Optional[int] = None

    def __init__(self, length: Optional[int] = None, dialect=None):
        super().__init__(dialect)
        self.length = length

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.length == other.length

    def __hash__(self) -> int:
        return hash((type(self), self.length))

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
        super().__init__(None, dialect)

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
