# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/data_type.py
"""SQL Server column-type protocol.

The generic ``format_data_type_<name>`` / ``supports_data_type_<name>`` pair is
the dispatch contract, and it is enough to render a type.  It is *not* enough
to answer the questions a caller actually has about SQL Server's own types,
which is why the ones that exist only here get a stated shape: whether ``xml``
is a real type here or a text column in disguise, whether the 8-bit integer is
signed, whether ``BIT`` is a boolean or a bit string.  Those are the questions
this backend got wrong, so they are the ones the protocol asks.

Membership is structural (``runtime_checkable``), so ``isinstance(dialect,
SQLServerTypeSupport)`` succeeds for any dialect that implements the family —
the point being that the family has one declared shape rather than being
merely implied by a naming pattern.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class SQLServerTypeSupport(Protocol):
    """The support switches for the types SQL Server spells its own way."""

    def supports_data_type_sqlserver_nvarchar(self) -> bool:
        ...

    def supports_data_type_sqlserver_nchar(self) -> bool:
        ...

    def supports_data_type_sqlserver_nvarchar_max(self) -> bool:
        ...

    def supports_data_type_sqlserver_varbinary(self) -> bool:
        ...

    def supports_data_type_sqlserver_varbinary_max(self) -> bool:
        ...

    def supports_data_type_sqlserver_image(self) -> bool:
        """``IMAGE`` is creatable on every version here but deprecated since
        2005; a backend that stops accepting it must change this gate."""
        ...

    def supports_data_type_sqlserver_tinyint(self) -> bool:
        ...

    def supports_data_type_sqlserver_bit(self) -> bool:
        ...

    def supports_data_type_sqlserver_xml(self) -> bool:
        ...

    def supports_data_type_sqlserver_uniqueidentifier(self) -> bool:
        ...


__all__ = ["SQLServerTypeSupport"]
