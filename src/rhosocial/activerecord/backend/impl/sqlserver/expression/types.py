# src/rhosocial/activerecord/backend/impl/sqlserver/expression/types.py
"""SQL Server-specific DDL DataType subclasses."""

from rhosocial.activerecord.backend.expression.types import VarCharType, IntegerType


class SQLServerNVarCharType(VarCharType):
    """SQL Server NVARCHAR type."""
    pass


class SQLServerNCharType(VarCharType):
    """SQL Server NCHAR type."""
    pass


class SQLServerNVarCharMaxType(VarCharType):
    """SQL Server NVARCHAR(MAX) type."""
    pass


class SQLServerVarBinaryType(VarCharType):
    """SQL Server VARBINARY type."""
    pass


class SQLServerVarBinaryMaxType(VarCharType):
    """SQL Server VARBINARY(MAX) type."""
    pass


class SQLServerXmlType(VarCharType):
    """SQL Server XML type."""
    pass


class SQLServerTinyIntType(IntegerType):
    """SQL Server TINYINT type."""
    pass


class SQLServerBitType(IntegerType):
    """SQL Server BIT type."""
    pass


class SQLServerImageType(VarCharType):
    """SQL Server IMAGE type (deprecated)."""
    pass


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