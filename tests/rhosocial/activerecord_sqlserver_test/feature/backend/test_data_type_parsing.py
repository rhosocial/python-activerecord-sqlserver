import pytest
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression.types import (
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
from rhosocial.activerecord.backend.expression.types._base import DataType
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BlobType,
    BooleanType,
    CharType,
    CustomType,
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
)

SQL_SERVER_2022 = (16, 0, 0)


class TestSQLServerParseType:
    """Tests for SQL Server parse_type implementation."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def _parse(self, dialect, raw: str) -> DataType:
        return DataType.parse_data_type_str(dialect, raw)

    def test_parse_integer_types(self, dialect):
        assert isinstance(self._parse(dialect, "INT"), IntegerType)
        assert isinstance(self._parse(dialect, "INTEGER"), IntegerType)
        assert isinstance(self._parse(dialect, "BIGINT"), BigIntType)
        assert isinstance(self._parse(dialect, "SMALLINT"), SmallIntType)
        # TINYINT is the 1-byte integer, not a small INTEGER: 0-255 against
        # -2147483648..2147483647. The class used to claim INTEGER.
        assert isinstance(self._parse(dialect, "TINYINT"), SQLServerTinyIntType)
        assert isinstance(self._parse(dialect, "TINYINT"), TinyIntType)
        assert not isinstance(self._parse(dialect, "TINYINT"), IntegerType)

    def test_parse_float_types(self, dialect):
        assert isinstance(self._parse(dialect, "FLOAT"), FloatType)
        assert isinstance(self._parse(dialect, "REAL"), RealType)
        assert isinstance(self._parse(dialect, "DOUBLE"), DoubleType)
        assert isinstance(self._parse(dialect, "DOUBLE PRECISION"), DoubleType)

    def test_parse_decimal_types(self, dialect):
        dt = self._parse(dialect, "DECIMAL(10,2)")
        assert isinstance(dt, DecimalType)
        assert dt.precision == 10
        assert dt.scale == 2

        dt2 = self._parse(dialect, "DECIMAL(10)")
        assert isinstance(dt2, DecimalType)
        assert dt2.precision == 10

        dt3 = self._parse(dialect, "DECIMAL")
        assert isinstance(dt3, DecimalType)

        dt4 = self._parse(dialect, "NUMERIC(18,0)")
        assert isinstance(dt4, DecimalType)
        assert dt4.precision == 18

        dt5 = self._parse(dialect, "MONEY")
        assert isinstance(dt5, DecimalType)

    def test_parse_string_types(self, dialect):
        dt = self._parse(dialect, "VARCHAR(255)")
        assert isinstance(dt, VarCharType)
        assert dt.length == 255

        dt2 = self._parse(dialect, "NVARCHAR(100)")
        assert isinstance(dt2, SQLServerNVarCharType)

        dt3 = self._parse(dialect, "CHAR(10)")
        assert isinstance(dt3, CharType)

        dt4 = self._parse(dialect, "TEXT")
        assert isinstance(dt4, TextType)

        dt5 = self._parse(dialect, "NTEXT")
        assert isinstance(dt5, TextType)

        dt6 = self._parse(dialect, "NVARCHAR(MAX)")
        assert isinstance(dt6, TextType)

    def test_char_is_fixed_length_not_variable(self, dialect):
        """The bug this parser had: ``CHAR`` yielded ``VarCharType``.

        A fixed-length character value is blank-padded to its declared width,
        which is exactly what ``VarCharType`` says it is not, so the parser was
        describing the wrong storage — and re-rendered ``CHAR(10)`` as
        ``VARCHAR(255)``.
        """
        for raw in ("CHAR", "CHAR(10)"):
            parsed = self._parse(dialect, raw)
            assert isinstance(parsed, CharType), f"{raw} -> {type(parsed).__name__}"
            assert not isinstance(parsed, VarCharType)
        assert dialect.format_data_type(self._parse(dialect, "CHAR(10)"))[0] == "CHAR(10)"

    def test_varchar_is_variable_length_not_fixed(self, dialect):
        parsed = self._parse(dialect, "VARCHAR(255)")
        assert isinstance(parsed, VarCharType)
        assert not isinstance(parsed, CharType)

    def test_nchar_is_its_own_class(self, dialect):
        """``NCHAR`` is SQL Server's own fixed-length Unicode type.

        It does not have to resolve to ``SQLServerNCharType`` for correctness —
        ``CharType`` would carry the right width — but the parser is what feeds
        a schema diff, and re-rendering an ``NCHAR`` column as ``CHAR`` would
        silently change its code page.
        """
        parsed = self._parse(dialect, "NCHAR(10)")
        assert isinstance(parsed, SQLServerNCharType)
        assert dialect.format_data_type(parsed)[0] == "NCHAR(10)"

    def test_parse_date_time_types(self, dialect):
        # DATE is its own concept: a calendar date with no time of day. It
        # yielded DateTimeType, which renders DATETIME2.
        assert isinstance(self._parse(dialect, "DATE"), DateType)
        assert isinstance(self._parse(dialect, "DATETIME"), DateTimeType)
        assert isinstance(self._parse(dialect, "DATETIME2"), DateTimeType)
        assert isinstance(self._parse(dialect, "SMALLDATETIME"), DateTimeType)
        assert isinstance(self._parse(dialect, "TIME"), TimeType)
        assert isinstance(self._parse(dialect, "DATETIMEOFFSET"), TimestampTzType)

    def test_declared_precision_survives_a_round_trip(self, dialect):
        """``DATETIME2(3)`` used to parse as a bare ``DATETIME2``.

        Precision is in the declaration and in ``PARAMETERS``, so losing it
        here made a diff report a change on a column that had not changed.
        """
        for raw, expected in (
            ("DATETIME2(3)", "DATETIME2(3)"),
            ("DATETIMEOFFSET(7)", "DATETIMEOFFSET(7)"),
            ("TIME(3)", "TIME(3)"),
            ("DECIMAL(10,2)", "DECIMAL(10, 2)"),
            ("FLOAT(24)", "FLOAT(24)"),
            ("VARBINARY(64)", "VARBINARY(64)"),
        ):
            parsed = self._parse(dialect, raw)
            assert dialect.format_data_type(parsed)[0] == expected, raw

    def test_parse_bit_type(self, dialect):
        # BIT is the boolean on SQL Server, so the parser yields the boolean
        # class rather than a bit string.
        assert isinstance(self._parse(dialect, "BIT"), SQLServerBitType)
        assert isinstance(self._parse(dialect, "BIT"), BooleanType)

    def test_parse_xml_type(self, dialect):
        """``xml`` is a binary representation on SQL Server, not a varchar."""
        parsed = self._parse(dialect, "xml")
        assert isinstance(parsed, SQLServerXmlType)
        assert dialect.format_data_type(parsed)[0] == "XML"

    def test_parse_binary_types(self, dialect):
        assert isinstance(self._parse(dialect, "VARBINARY(MAX)"), SQLServerVarBinaryMaxType)
        assert isinstance(self._parse(dialect, "VARBINARY(MAX)"), BlobType)
        assert isinstance(self._parse(dialect, "IMAGE"), SQLServerImageType)
        assert isinstance(self._parse(dialect, "VARBINARY"), SQLServerVarBinaryType)

    def test_parse_varbinary_max_is_not_a_255_byte_column(self, dialect):
        """``VARBINARY(MAX)`` used to parse as ``VARBINARY(255)``.

        Same storage, wrong declaration: the 2 GB form and the 255-byte form are
        different columns as far as a schema is concerned.
        """
        parsed = self._parse(dialect, "VARBINARY(MAX)")
        assert dialect.format_data_type(parsed)[0] == "VARBINARY(MAX)"

    def test_parse_uniqueidentifier(self, dialect):
        parsed = self._parse(dialect, "UNIQUEIDENTIFIER")
        assert isinstance(parsed, SQLServerUniqueIdentifierType)
        assert dialect.format_data_type(parsed)[0] == "UNIQUEIDENTIFIER"

    def test_parse_timestamp_is_rowversion_and_says_nothing_it_does_not_know(self, dialect):
        """T-SQL ``TIMESTAMP`` is ``ROWVERSION``, not a timestamp.

        It used to parse as ``DateTimeType``, which renders ``DATETIME2`` — an
        8-byte auto-incrementing counter turned into a date. There is no
        rowversion concept to yield, so ``CustomType`` is the honest answer and
        it round-trips exactly.
        """
        parsed = self._parse(dialect, "timestamp")
        assert isinstance(parsed, CustomType)
        assert dialect.format_data_type(parsed)[0] == "timestamp"

    def test_parse_unknown_type(self, dialect):
        result = self._parse(dialect, "GEOGRAPHY")
        assert isinstance(result, CustomType)

    def test_parse_type_case_insensitive(self, dialect):
        assert isinstance(self._parse(dialect, "int"), IntegerType)
        assert isinstance(self._parse(dialect, "VARCHAR(50)"), VarCharType)
        assert isinstance(self._parse(dialect, "decimal(8,2)"), DecimalType)

    def test_spellings_parse_to_their_own_concept(self, dialect):
        """Every concept's ``SPELLINGS`` maps back to that concept (D8).

        The failure this guards is a parser that reads ``character varying`` and
        hands back ``CharType``: one spelling in, a *different* class out, which
        is the bug ``SPELLINGS`` exists to make impossible.
        """
        cases = [
            ("integer", IntegerType, ["integer", "int"]),
            ("bigint", BigIntType, ["bigint", "int8"]),
            ("smallint", SmallIntType, ["smallint", "int2"]),
            ("tinyint", TinyIntType, ["tinyint", "int1"]),
            ("double", DoubleType, ["double", "double precision"]),
            ("decimal", DecimalType, ["decimal", "numeric", "dec"]),
            ("boolean", BooleanType, ["boolean", "bool"]),
            ("char", CharType, ["char", "character"]),
            ("varchar", VarCharType, ["varchar", "character varying"]),
            ("text", TextType, ["text", "clob"]),
            ("blob", BlobType, ["blob", "bytea"]),
        ]
        for concept, expected_cls, spellings in cases:
            for spelling in spellings:
                parsed = self._parse(dialect, spelling)
                assert isinstance(parsed, expected_cls), (
                    f"{spelling!r} parsed as {type(parsed).__name__}, "
                    f"expected {expected_cls.__name__}"
                )
                assert parsed.spelling == spelling, (
                    f"{spelling!r} lost its spelling: {parsed.spelling!r}"
                )

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("INT", "INT"),
            ("INTEGER", "INT"),
            ("INT8", "BIGINT"),
            ("INT2", "SMALLINT"),
            ("INT1", "TINYINT"),
            ("TINYINT", "TINYINT"),
            ("CHAR", "CHAR(1)"),
            ("CHAR(10)", "CHAR(10)"),
            ("CHARACTER", "CHAR(1)"),
            ("CHARACTER VARYING", "VARCHAR(255)"),
            ("CHARACTER VARYING(50)", "VARCHAR(50)"),
            ("VARCHAR", "VARCHAR(255)"),
            ("VARCHAR(255)", "VARCHAR(255)"),
            ("VARCHAR(MAX)", "NVARCHAR(MAX)"),
            ("NVARCHAR", "NVARCHAR(255)"),
            ("NVARCHAR(100)", "NVARCHAR(100)"),
            ("NVARCHAR(MAX)", "NVARCHAR(MAX)"),
            ("NCHAR", "NCHAR(1)"),
            ("NCHAR(10)", "NCHAR(10)"),
            ("TEXT", "NVARCHAR(MAX)"),
            ("NTEXT", "NVARCHAR(MAX)"),
            ("CLOB", "NVARCHAR(MAX)"),
            ("BLOB", "VARBINARY(MAX)"),
            ("BYTEA", "VARBINARY(MAX)"),
            ("BOOLEAN", "BIT"),
            ("BOOL", "BIT"),
            ("BIT", "BIT"),
            ("DOUBLE", "FLOAT(53)"),
            ("DOUBLE PRECISION", "FLOAT(53)"),
            ("DEC", "DECIMAL"),
            ("DEC(5,2)", "DECIMAL(5, 2)"),
            ("DATE", "DATE"),
            ("DATETIME", "DATETIME2"),
            ("DATETIME2", "DATETIME2"),
            ("SMALLDATETIME", "DATETIME2"),
            ("DATETIMEOFFSET", "DATETIMEOFFSET"),
            ("TIME", "TIME"),
            ("XML", "XML"),
            ("UNIQUEIDENTIFIER", "UNIQUEIDENTIFIER"),
            ("VARBINARY", "VARBINARY(255)"),
            ("VARBINARY(MAX)", "VARBINARY(MAX)"),
            ("IMAGE", "IMAGE"),
        ],
    )
    def test_parse_render_round_trip(self, dialect, raw, expected):
        """Every spelling the parser accepts renders back to stable SQL."""
        assert dialect.format_data_type(self._parse(dialect, raw))[0] == expected
