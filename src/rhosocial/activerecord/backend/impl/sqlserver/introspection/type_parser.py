# src/rhosocial/activerecord/backend/impl/sqlserver/introspection/type_parser.py
"""SQL Server's type-spelling parser (read direction, introspection-only).

Core's ``DataType.parse_data_type_str`` degrades every spelling to ``CustomType``
and the dialect protocol no longer has a ``parse_type`` member. Parsing a
server-reported type spelling back into a ``DataType`` is a backend-local
introspection concern: this helper lives under SQL Server introspection and is
used only when reading back a column's declared type. It is NOT a dialect
protocol member and is deliberately not installed on the dialect class.

The spelling is read with character scanning (see ``.._scan``) instead of
regular expressions: a type family is the leading word of the declaration.
"""

from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BlobType,
    CustomType,
    DataType,
    DateTimeType,
    DateType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    RealType,
    SmallIntType,
    TextType,
    TimeType,
    TimestampTzType,
    TinyIntType,
    VarCharType,
    CharType,
)

from .._scan import find_argument_list, leading_word

from ..expression.types import (
    SQLServerBitType,
    SQLServerImageType,
    SQLServerNCharType,
    SQLServerNVarCharType,
    SQLServerTinyIntType,
    SQLServerUniqueIdentifierType,
    SQLServerVarBinaryMaxType,
    SQLServerVarBinaryType,
    SQLServerXmlType,
)


class SQLServerTypeParser:
    """Parse a raw SQL Server type spelling into a DataType, bound to a dialect."""

    _SQLSERVER_INTEGER_TYPES = frozenset({
        "INT8", "BIGINT", "SMALLINT", "INT2", "TINYINT", "INT1", "INTEGER", "INT",
    })
    _SQLSERVER_FLOAT_TYPES = frozenset({"FLOAT", "REAL", "DOUBLE"})
    _SQLSERVER_DECIMAL_TYPES = frozenset({
        "DECIMAL", "NUMERIC", "DEC", "MONEY", "SMALLMONEY",
    })
    _SQLSERVER_STRING_TYPES = frozenset({
        "CHARACTER", "NCHAR", "VARCHAR", "NVARCHAR", "CHAR", "CLOB", "NTEXT", "TEXT",
    })
    _SQLSERVER_DATE_TYPES = frozenset({
        "DATETIMEOFFSET", "DATETIME2", "SMALLDATETIME", "DATETIME", "DATE",
    })
    #: The plain calendar date, separated from the datetimes that share its
    #: letters. ``startswith("DATE")`` cannot tell them apart, so the leading
    #: word has to equal ``DATE`` exactly.
    _SQLSERVER_DATE_ONLY_TYPES = frozenset({"DATE"})
    _SQLSERVER_TIME_TYPES = frozenset({"TIME"})
    _SQLSERVER_BIT_TYPES = frozenset({"BIT", "BOOL", "BOOLEAN"})
    _SQLSERVER_BLOB_TYPES = frozenset({"VARBINARY", "IMAGE", "BLOB", "BYTEA"})
    _SQLSERVER_XML_TYPES = frozenset({"XML"})

    def __init__(self, dialect):
        self.dialect = dialect

    def parse(self, raw: str) -> DataType:
        dialect = self.dialect
        stripped = raw.strip()
        upper = stripped.upper()
        word = leading_word(upper)
        arguments = find_argument_list(stripped)
        length = arguments[0] if arguments else None
        scale = arguments[1] if arguments else None

        # BIT — the boolean, not MySQL/PostgreSQL's bit string. The spelling
        # recorded is the concept's own, so ``BOOLEAN`` and ``BOOL`` survive the
        # round trip. T-SQL refuses a width on ``bit`` (error 2716), so a
        # parenthesised form is answered with ValueError rather than silently
        # dropping the width or escaping as a bare KeyError.
        if word in self._SQLSERVER_BIT_TYPES:
            spelling = {"BIT": "boolean", "BOOL": "bool",
                        "BOOLEAN": "boolean"}.get(upper)
            if spelling is None:
                raise ValueError(
                    f"{stripped!r} is not a declaration this server accepts: "
                    f"T-SQL's ``bit`` takes no width, and SQL Server refuses "
                    f"one with error 2716, 'Cannot specify a column width on "
                    f"data type bit.' (measured live on SQL Server 2019 "
                    f"(15.0.4465.1), 2022 (16.0.4250.1) and 2025 "
                    f"(17.0.4035.5)). Declare the bare word — ``bit``, or its "
                    f"accepted spellings ``bool`` and ``boolean`` — without "
                    f"parentheses."
                )
            return SQLServerBitType(dialect=dialect, spelling=spelling)

        # UNIQUEIDENTIFIER — the native GUID.
        if upper.startswith("UNIQUEIDENTIFIER"):
            return SQLServerUniqueIdentifierType(dialect=dialect)

        # XML — a binary XML representation, not a varchar (checked before the
        # string family because ``XML`` shares no prefix with any of it).
        if word in self._SQLSERVER_XML_TYPES:
            return SQLServerXmlType(dialect=dialect)

        # Integer family: one class per width, and the spelling preserved.
        if word in self._SQLSERVER_INTEGER_TYPES:
            if upper.startswith("INT8"):
                return BigIntType(dialect=dialect, spelling="int8")
            if upper.startswith("BIGINT"):
                return BigIntType(dialect=dialect, spelling="bigint")
            if upper.startswith("INT2"):
                return SmallIntType(dialect=dialect, spelling="int2")
            if upper.startswith("SMALLINT"):
                return SmallIntType(dialect=dialect, spelling="smallint")
            if upper.startswith("INT1"):
                return TinyIntType(dialect=dialect, spelling="int1")
            if upper.startswith("TINYINT"):
                return SQLServerTinyIntType(dialect=dialect)
            spelling = "integer" if upper.startswith("INTEGER") else "int"
            return IntegerType(dialect=dialect, spelling=spelling)

        # Float family. ``DOUBLE`` / ``DOUBLE PRECISION`` is the concept SQL
        # names for 8-byte floating point, which T-SQL spells ``FLOAT(53)``.
        if word in self._SQLSERVER_FLOAT_TYPES:
            if upper.startswith("DOUBLE"):
                spelling = "double precision" if "PRECISION" in upper else "double"
                return DoubleType(dialect=dialect, spelling=spelling)
            if upper.startswith("REAL"):
                return RealType(dialect=dialect)
            return FloatType(dialect=dialect, precision=length)

        # Decimal family. ``MONEY`` / ``SMALLMONEY`` carry a fixed scale of 4
        # and a currency-formatted result the schema does not record, so they
        # stay a plain DecimalType rather than a distinct concept.
        if word in self._SQLSERVER_DECIMAL_TYPES:
            if upper.startswith("MONEY") or upper.startswith("SMALLMONEY"):
                return DecimalType(dialect=dialect)
            if upper.startswith("NUMERIC"):
                spelling = "numeric"
            elif upper.startswith("DECIMAL"):
                spelling = "decimal"
            else:
                spelling = "dec"
            return DecimalType(dialect=dialect, precision=length, scale=scale,
                               spelling=spelling)

        # String family. Fixed length and variable length are different
        # concepts, so ``CHAR`` never yields a VarCharType and ``VARCHAR`` never
        # yields a CharType. An unsized word is completed from the same literal
        # the formatters use: 1 for the fixed forms, 255 for the variable ones.
        if word in self._SQLSERVER_STRING_TYPES:
            # ``(MAX)`` lifts the length cap rather than setting one, in either
            # character set, so it is unbounded text and not a 255-char column.
            unbounded = arguments is None and "MAX" in upper
            if upper.startswith("NCHAR"):
                return SQLServerNCharType(dialect=dialect, length=length or 1)
            if upper.startswith("NVARCHAR"):
                if unbounded:
                    return TextType(dialect=dialect)
                return SQLServerNVarCharType(dialect=dialect, length=length or 255)
            if upper.startswith("VARCHAR"):
                if unbounded:
                    return TextType(dialect=dialect)
                return VarCharType(dialect=dialect, length=length or 255)
            if upper.startswith("CHARACTER VARYING"):
                return VarCharType(dialect=dialect, length=length,
                                   spelling="character varying")
            if upper.startswith("CHARACTER"):
                return CharType(dialect=dialect, length=length, spelling="character")
            if upper.startswith("CHAR"):
                return CharType(dialect=dialect, length=length)
            # ``CLOB`` / ``TEXT`` / ``NTEXT`` are all unbounded text: the first
            # is the portable spelling, the other two the deprecated T-SQL
            # ones, and all three render ``NVARCHAR(MAX)``.
            spelling = "clob" if upper.startswith("CLOB") else "text"
            return TextType(dialect=dialect, spelling=spelling)

        # Date/time family. ``DATE`` is its own concept — a calendar date with
        # no time of day — and T-SQL ``TIMESTAMP`` is ``ROWVERSION``, an
        # 8-byte auto-incrementing counter that is *not* a timestamp; with no
        # rowversion concept to declare, that name falls through to
        # ``CustomType`` rather than being filed under datetime.
        if word in self._SQLSERVER_DATE_TYPES:
            if upper.startswith("DATETIMEOFFSET"):
                return TimestampTzType(dialect=dialect, precision=length)
            if word in self._SQLSERVER_DATE_ONLY_TYPES:
                return DateType(dialect=dialect)
            return DateTimeType(dialect=dialect, precision=length)

        if word in self._SQLSERVER_TIME_TYPES:
            return TimeType(dialect=dialect, precision=length)

        # Byte-string family. ``VARBINARY(MAX)`` is the unbounded declaration
        # and not a 255-byte one, so it gets its own class.
        if word in self._SQLSERVER_BLOB_TYPES:
            if upper.startswith("VARBINARY"):
                if arguments is None and "MAX" in upper:
                    return SQLServerVarBinaryMaxType(dialect=dialect)
                return SQLServerVarBinaryType(dialect=dialect, length=length)
            if upper.startswith("IMAGE"):
                return SQLServerImageType(dialect=dialect)
            spelling = "bytea" if upper.startswith("BYTEA") else "blob"
            return BlobType(dialect=dialect, spelling=spelling)

        return CustomType(dialect=dialect, raw=stripped)


__all__ = ["SQLServerTypeParser"]
