# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_sqlserver_type_protocol.py
"""Tests for the SQL Server backend data-type protocol compliance.

Covers:
- format/supports 1:1 correspondence
- supports_data_types() includes sqlserver_* + core entries
- suggested_data_types() returns classes, keys disjoint from supported
- dialect_options forwarding and equality
- Precision validation
"""

import pytest
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression.types import (
    SQLServerNVarCharType,
    SQLServerNCharType,
    SQLServerNVarCharMaxType,
    SQLServerVarBinaryType,
    SQLServerVarBinaryMaxType,
    SQLServerXmlType,
    SQLServerTinyIntType,
    SQLServerBitType,
    SQLServerImageType,
)
from rhosocial.activerecord.backend.expression.types import (
    IntegerType,
    BigIntType,
    SmallIntType,
    FloatType,
    RealType,
    DoubleType,
    DecimalType,
    BooleanType,
    VarCharType,
    CharType,
    TextType,
    DateTimeType,
    DateType,
    TimeType,
    TimestampType,
    JsonType,
    BlobType,
    CustomType,
)

SQL_SERVER_2022 = (16, 0, 0)


class TestFormatSupportsCorrespondence:
    """Every format_data_type_<name> must have a matching supports_data_type_<name>."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_all_format_methods_have_supports_counterpart(self, dialect):
        import re
        format_names = set()
        for attr in dir(type(dialect)):
            m = re.match(r"^format_data_type_([a-z][a-z0-9_]*)$", attr)
            if m:
                format_names.add(m.group(1))

        supports_names = set()
        for attr in dir(type(dialect)):
            m = re.match(r"^supports_data_type_([a-z][a-z0-9_]*)$", attr)
            if m:
                supports_names.add(m.group(1))

        missing = format_names - supports_names
        assert not missing, (
            f"format_data_type_* without supports_data_type_*: {missing}"
        )

    def test_all_supports_methods_have_format_counterpart(self, dialect):
        import re
        format_names = set()
        for attr in dir(type(dialect)):
            m = re.match(r"^format_data_type_([a-z][a-z0-9_]*)$", attr)
            if m:
                format_names.add(m.group(1))

        supports_names = set()
        for attr in dir(type(dialect)):
            m = re.match(r"^supports_data_type_([a-z][a-z0-9_]*)$", attr)
            if m:
                supports_names.add(m.group(1))

        extra = supports_names - format_names
        assert not extra, (
            f"supports_data_type_* without format_data_type_*: {extra}"
        )


class TestSupportsDataTypes:
    """supports_data_types() returns sqlserver_* + core entries."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_returns_dict(self, dialect):
        result = dialect.supports_data_types()
        assert isinstance(result, dict)

    def test_includes_core_types(self, dialect):
        supported = dialect.supports_data_types()
        for name in ["integer", "int", "bigint", "smallint", "tinyint",
                      "varchar", "char", "text", "boolean", "date",
                      "datetime", "time", "timestamp", "float", "real",
                      "double", "decimal", "json", "blob", "custom"]:
            assert name in supported, f"Core type {name!r} missing from supports_data_types()"

    def test_includes_sqlserver_types(self, dialect):
        supported = dialect.supports_data_types()
        for name in ["sqlserver_nvarchar", "sqlserver_nchar",
                      "sqlserver_nvarchar_max", "sqlserver_varbinary",
                      "sqlserver_varbinary_max", "sqlserver_xml",
                      "sqlserver_tinyint", "sqlserver_bit",
                      "sqlserver_image"]:
            assert name in supported, f"SQL Server type {name!r} missing from supports_data_types()"

    def test_values_are_type_classes(self, dialect):
        supported = dialect.supports_data_types()
        for name, cls in supported.items():
            assert isinstance(cls, type), (
                f"supports_data_types()[{name!r}] = {cls!r} is not a type class"
            )


class TestSuggestedDataTypes:
    """suggested_data_types() returns classes, keys disjoint from supported."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_returns_dict(self, dialect):
        result = dialect.suggested_data_types()
        assert isinstance(result, dict)

    def test_values_are_type_classes(self, dialect):
        suggested = dialect.suggested_data_types()
        for name, cls in suggested.items():
            assert isinstance(cls, type), (
                f"suggested_data_types()[{name!r}] = {cls!r} is not a type class"
            )

    def test_keys_disjoint_from_supported(self, dialect):
        supported = set(dialect.supports_data_types().keys())
        suggested = set(dialect.suggested_data_types().keys())
        overlap = supported & suggested
        assert not overlap, (
            f"Keys appear in both supports and suggested: {overlap}"
        )

    def test_suggests_unsupported_core_types(self, dialect):
        suggested = dialect.suggested_data_types()
        # SQL Server doesn't natively support these core types
        for name in ["uuid", "interval", "array", "enum", "jsonb",
                      "timestamptz", "timetz"]:
            assert name in suggested, (
                f"Expected suggestion for {name!r} in suggested_data_types()"
            )


class TestDialectOptionsForwarding:
    """dialect_options are forwarded through __init__ and participate in equality."""

    def test_nvarchar_forwarding(self):
        t1 = SQLServerNVarCharType(length=100, dialect_options={"foo": "bar"})
        assert t1.dialect_options == {"foo": "bar"}

    def test_nvarchar_equality_with_options(self):
        t1 = SQLServerNVarCharType(length=100, dialect_options={"foo": "bar"})
        t2 = SQLServerNVarCharType(length=100, dialect_options={"foo": "bar"})
        t3 = SQLServerNVarCharType(length=100, dialect_options={"foo": "baz"})
        assert t1 == t2
        assert t1 != t3

    def test_nvarchar_hash_ignores_options(self):
        t1 = SQLServerNVarCharType(length=100, dialect_options={"foo": "bar"})
        t2 = SQLServerNVarCharType(length=100, dialect_options={"foo": "baz"})
        assert hash(t1) == hash(t2)

    def test_varbinary_type_params(self):
        t = SQLServerVarBinaryType(length=512)
        assert t._type_params() == (512,)

    def test_varbinary_equality(self):
        t1 = SQLServerVarBinaryType(length=512)
        t2 = SQLServerVarBinaryType(length=512)
        t3 = SQLServerVarBinaryType(length=1024)
        assert t1 == t2
        assert t1 != t3

    def test_decimal_type_params(self):
        t = DecimalType(precision=10, scale=2)
        assert t._type_params() == (10, 2)

    def test_float_type_params(self):
        t = FloatType(precision=24)
        assert t._type_params() == (24,)

    def test_datetime_type_params(self):
        t = DateTimeType(precision=3)
        assert t._type_params() == (3,)


class TestPrecisionValidation:
    """Precision parameters are validated per SQL Server rules."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_decimal_precision_too_high(self, dialect):
        with pytest.raises(ValueError, match="precision must be 1-38"):
            dialect.format_data_type(DecimalType(precision=39, scale=0))

    def test_decimal_scale_exceeds_precision(self, dialect):
        with pytest.raises(ValueError, match="scale.*must not exceed precision"):
            dialect.format_data_type(DecimalType(precision=5, scale=10))

    def test_decimal_valid(self, dialect):
        sql, _ = dialect.format_data_type(DecimalType(precision=38, scale=38))
        assert sql == "DECIMAL(38, 38)"

    def test_float_precision_too_high(self, dialect):
        with pytest.raises(ValueError, match="precision must be 1-53"):
            dialect.format_data_type(FloatType(precision=54))

    def test_float_precision_zero(self, dialect):
        with pytest.raises(ValueError, match="precision must be 1-53"):
            dialect.format_data_type(FloatType(precision=0))

    def test_float_valid(self, dialect):
        sql, _ = dialect.format_data_type(FloatType(precision=53))
        assert sql == "FLOAT(53)"

    def test_datetime_precision_too_high(self, dialect):
        with pytest.raises(ValueError, match="precision.*must be 0-7"):
            dialect.format_data_type(DateTimeType(precision=8))

    def test_datetime_precision_negative(self, dialect):
        with pytest.raises(ValueError, match="precision.*must be 0-7"):
            dialect.format_data_type(DateTimeType(precision=-1))

    def test_datetime_valid(self, dialect):
        sql, _ = dialect.format_data_type(DateTimeType(precision=7))
        assert sql == "DATETIME2(7)"

    def test_time_precision_too_high(self, dialect):
        with pytest.raises(ValueError, match="precision.*must be 0-7"):
            dialect.format_data_type(TimeType(precision=8))

    def test_time_valid(self, dialect):
        sql, _ = dialect.format_data_type(TimeType(precision=3))
        assert sql == "TIME(3)"

    def test_timestamp_precision_validation(self, dialect):
        with pytest.raises(ValueError, match="precision.*must be 0-7"):
            dialect.format_data_type(TimestampType(precision=8))
