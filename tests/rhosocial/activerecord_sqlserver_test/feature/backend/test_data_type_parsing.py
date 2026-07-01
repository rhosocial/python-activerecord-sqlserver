import pytest
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.expression.types._base import DataType
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BooleanType,
    CharType,
    CustomType,
    DateTimeType,
    DecimalType,
    FloatType,
    IntegerType,
    RealType,
    SmallIntType,
    TextType,
    TimeType,
    VarCharType,
)
from rhosocial.activerecord.backend.expression.types import BlobType

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
        assert isinstance(self._parse(dialect, "TINYINT"), IntegerType)

    def test_parse_float_types(self, dialect):
        assert isinstance(self._parse(dialect, "FLOAT"), FloatType)
        assert isinstance(self._parse(dialect, "REAL"), RealType)

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
        assert isinstance(dt2, VarCharType)

        dt3 = self._parse(dialect, "CHAR(10)")
        assert isinstance(dt3, CharType)

        dt4 = self._parse(dialect, "TEXT")
        assert isinstance(dt4, TextType)

        dt5 = self._parse(dialect, "NTEXT")
        assert isinstance(dt5, TextType)

        dt6 = self._parse(dialect, "NVARCHAR(MAX)")
        assert isinstance(dt6, TextType)

    def test_parse_date_time_types(self, dialect):
        assert isinstance(self._parse(dialect, "DATE"), DateTimeType)
        assert isinstance(self._parse(dialect, "DATETIME"), DateTimeType)
        assert isinstance(self._parse(dialect, "DATETIME2"), DateTimeType)
        assert isinstance(self._parse(dialect, "SMALLDATETIME"), DateTimeType)
        assert isinstance(self._parse(dialect, "TIME"), TimeType)

    def test_parse_bit_type(self, dialect):
        assert isinstance(self._parse(dialect, "BIT"), BooleanType)

    def test_parse_binary_types(self, dialect):
        assert isinstance(self._parse(dialect, "VARBINARY(MAX)"), BlobType)
        assert isinstance(self._parse(dialect, "IMAGE"), BlobType)

    def test_parse_unknown_type(self, dialect):
        result = self._parse(dialect, "GEOGRAPHY")
        assert isinstance(result, CustomType)

    def test_parse_type_case_insensitive(self, dialect):
        assert isinstance(self._parse(dialect, "int"), IntegerType)
        assert isinstance(self._parse(dialect, "VARCHAR(50)"), VarCharType)
        assert isinstance(self._parse(dialect, "decimal(8,2)"), DecimalType)
