# src/rhosocial/activerecord/backend/impl/sqlserver/expression/types.py
"""SQL Server-specific DataType subclasses.

Backend-specific types carry the ``sqlserver_`` prefix in their ``name``
attribute.  Core types (inherited from ``rhosocial.activerecord.backend.expression.types``)
retain their pure names and are rendered to SQL Server syntax by the dialect's
``format_data_type_<name>`` methods.

Every class here is anchored to the core concept it *is*: T-SQL spells some of
those concepts differently and adds a few the standards do not have, but none of
them is a different concept.  The classes that exist rather than being rendered
by name alone are the ones where the written word cannot be reached from the
core type — ``NVARCHAR``/``NCHAR`` (SQL Server keeps national character data in
its own types), ``VARBINARY(n)``/``IMAGE``, ``UNIQUEIDENTIFIER``, ``TINYINT``,
``BIT`` and ``xml``.  Two of the base classes below were wrong until this
round and are fixed here with the reasoning recorded: :class:`SQLServerXmlType`
and :class:`SQLServerTinyIntType`.
"""

from typing import Optional

from rhosocial.activerecord.backend.expression.types import (
    BlobType,
    VarBinaryType,
    BooleanType,
    CharType,
    TinyIntType,
    UUIDType,
    VarCharType,
    XmlType,
)


class SQLServerNVarCharType(VarCharType):
    """SQL Server ``NVARCHAR(n)`` — variable-length Unicode string.

    ``NVARCHAR`` is not a spelling of ``VARCHAR``: the framework's core string
    types deliberately have no character-set dimension, so the national-character
    types are SQL Server's own and get their own classes here.  Deriving from
    :class:`VarCharType` says what they share — variable length — without
    claiming they are the same storage, which they are not: ``NVARCHAR`` stores
    UCS-2/UTF-16 and cannot hold characters outside it, ``VARCHAR`` follows the
    database collation's code page.
    """

    name = "sqlserver_nvarchar"

    def __init__(self, dialect=None, length: Optional[int] = None):
        super().__init__(dialect, length=length)


class SQLServerNCharType(CharType):
    """SQL Server ``NCHAR(n)`` — fixed-length Unicode string, blank-padded.

    The fixed-length twin of :class:`SQLServerNVarCharType`, and the reason this
    repository keeps ``CHAR`` and ``NCHAR`` apart is that both are *fixed*
    length: a shorter value is space-padded to ``n`` rather than stored as
    written.
    """

    name = "sqlserver_nchar"

    def __init__(self, dialect=None, length: Optional[int] = None):
        super().__init__(dialect, length=length)


class SQLServerNVarCharMaxType(VarCharType):
    """SQL Server ``NVARCHAR(MAX)`` — variable-length Unicode string, unbounded.

    ``MAX`` is not a length: it lifts the 8000-byte cap that makes a declared
    ``NVARCHAR(n)`` fixed-size.  The type is therefore variable-length and
    unbounded, which is exactly :class:`VarCharType` — the *unboundedness* is
    what the ``MAX`` spelling records, and it is carried by this class rather
    than by a length of ``None`` on the base, because ``NVARCHAR`` and
    ``NVARCHAR(MAX)`` are different declarations in the catalog.
    """

    name = "sqlserver_nvarchar_max"

    def __init__(self, dialect=None):
        super().__init__(dialect, length=None)


class SQLServerVarBinaryType(VarBinaryType):
    """SQL Server ``VARBINARY(n)`` — variable-length byte string.

    ``n`` is capped at 8000 bytes; the unbounded spelling is ``VARBINARY(MAX)``
    (:class:`SQLServerVarBinaryMaxType`).  T-SQL's own default for a declared
    ``VARBINARY`` is one byte, but this backend renders 255 when no length was
    given, matching what it does for ``VARCHAR`` and ``NVARCHAR`` — the default
    is the dialect's, not the server's, and it is visible in the DDL either way.

    Derived from :class:`VarBinaryType`, the concept whose dispatch key this
    class's own name (``sqlserver_varbinary``) claims.  It was previously
    derived from :class:`BlobType` on the reasoning that T-SQL's byte string is
    "the blob one" — but a ``VARBINARY(n)`` is *bounded* and a ``BLOB`` is not,
    and ``VARBINARY(MAX)`` is a different declaration again
    (:class:`SQLServerVarBinaryMaxType`).  Sibling ``SQLServerVarBinaryMaxType``
    stays on ``BlobType``, which is the concept that actually has no bound.
    """

    name = "sqlserver_varbinary"

    length: Optional[int] = None

    def __init__(self, dialect=None, length: Optional[int] = None):
        super().__init__(dialect)
        self.length = length

    PARAMETERS = ("length",)

class SQLServerVarBinaryMaxType(BlobType):
    """SQL Server ``VARBINARY(MAX)`` — byte string up to 2 GB.

    The same storage as :class:`SQLServerVarBinaryType` with the 8000-byte cap
    lifted, which is what ``BlobType`` is.  Kept as its own class because the
    declaration differs, and a schema diff compares declarations.
    """

    name = "sqlserver_varbinary_max"

    def __init__(self, dialect=None):
        super().__init__(dialect)


class SQLServerImageType(BlobType):
    """SQL Server ``IMAGE`` — deprecated unbounded byte string.

    Superseded by ``VARBINARY(MAX)`` in SQL Server 2005 and deprecated for
    removal; it is still creatable on every version this backend supports, so
    the type exists for reading existing schemas rather than for writing new
    ones.  Same storage as the ``(MAX)`` spelling, hence :class:`BlobType`.
    """

    name = "sqlserver_image"

    def __init__(self, dialect=None):
        super().__init__(dialect)


class SQLServerXmlType(XmlType):
    """SQL Server ``xml`` — an XML document with optional schema collection.

    **Not text.**  This class used to derive from ``VarCharType`` and that was
    wrong: SQL Server stores ``xml`` as an internal *binary* representation
    (optionally validated against a registered XML Schema Collection) and offers
    ``.nodes()`` / ``.value()`` / ``.exist()`` / ``.modify()`` over it.
    ``CAST(col AS varchar)`` is the documented way to *lose* that structure, so
    "it is a varchar" was not a simplification but the opposite of the truth.
    Deriving from :class:`XmlType` is what makes ``isinstance(col.data_type,
    XmlType)`` true for the same reason it is true on PostgreSQL.

    The associated XML Schema Collection is a column attribute, not part of the
    type's identity, so it does not appear here.  ``SQLServerXmlType`` and the
    core ``XmlType`` render the same SQL under their own namespaced names.
    """

    name = "sqlserver_xml"

    def __init__(self, dialect=None):
        super().__init__(dialect)


class SQLServerTinyIntType(TinyIntType):
    """SQL Server ``TINYINT`` — **unsigned** 8-bit integer (0–255).

    This class used to derive from ``IntegerType`` and that was wrong by three
    orders of magnitude: SQL Server's ``TINYINT`` holds 0…255 while ``INTEGER``
    holds -2147483648…2147483647.  ``TINYINT`` is the 1-byte integer, so the
    width is the class and :class:`TinyIntType` is the width; the signedness is
    the ``unsigned`` field, which is fixed to ``True`` here because no T-SQL
    spelling of this type is ever signed.

    ``==`` — which compares the class plus the values of its inherited
    ``PARAMETERS`` — therefore separates this from :class:`IntegerType` and from
    a signed :class:`TinyIntType`, which is the whole point of recording the
    field rather than assuming it.
    """

    name = "sqlserver_tinyint"

    def __init__(self, dialect=None, *, spelling: str = "tinyint"):
        super().__init__(dialect, unsigned=True, spelling=spelling)


class SQLServerBitType(BooleanType):
    """SQL Server ``BIT`` — a boolean: ``0``, ``1`` or ``NULL``.

    Deliberately **not** a bit string.  MySQL's and PostgreSQL's ``BIT(n)`` hold
    ``n`` bits and are a different concept, which is why those backends keep
    their own root-level class; T-SQL has exactly one ``BIT`` type and it is a
    boolean.  Two consequences follow, and both are why this class is not a
    bit-string type: a ``BIT`` column aggregates as ``0``/``1``/``NULL``, and
    SQL Server refuses any value outside that set outright rather than
    truncating it to ``n`` bits.

    Its base is :class:`BooleanType` — the concept — while
    ``format_data_type_sqlserver_bit`` and ``format_data_type_boolean`` are two
    names for one rendered word, because the framework models the concept and
    this backend's own spelling separately.  The ``spelling`` argument is the
    concept's own (``boolean`` / ``bool``), not T-SQL's ``BIT``: ``BIT`` is the
    backend's word for the type, and it belongs to this class's ``name``.
    """

    name = "sqlserver_bit"

    def __init__(self, dialect=None, *, spelling: str = "boolean"):
        super().__init__(dialect, spelling=spelling)


class SQLServerUniqueIdentifierType(UUIDType):
    """SQL Server ``UNIQUEIDENTIFIER`` — a native 16-byte GUID.

    The native storage for the UUID concept, so it derives from
    :class:`UUIDType` rather than sitting on ``DataType``: "is this a UUID
    column?" must be one question across backends, and
    ``isinstance(col.data_type, UUIDType)`` has to answer it.

    It stays a class of its own because T-SQL spells the type differently, and
    the ``sqlserver_uniqueidentifier`` name keeps the dispatch keys of this
    backend's ``format_data_type_*`` family isolated from the others'.
    ``suggested_data_types()["uuid"]`` points at it — a substitute that names a
    type this dialect really renders, which is the only kind of substitute the
    contract allows.
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
