# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/types.py
"""SQL Server DataType formatting mixin."""

from __future__ import annotations

import re
from typing import Optional, Tuple

from rhosocial.activerecord.backend.dialect.mixins import (
    DDLTypeMixin,
    DDLTypeSuggestionMixin,
)
from rhosocial.activerecord.backend.dialect.protocols import DDLTypeSupport
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BlobType,
    BooleanType,
    CharType,
    CustomType,
    DataType,
    DateType,
    DateTimeType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    JsonType,
    RealType,
    SmallIntType,
    TextType,
    TimeType,
    TimestampType,
    VarCharType,
)


class SQLServerTypeSupportMixin(DDLTypeMixin, DDLTypeSupport):

    @DDLTypeMixin.handles(IntegerType)
    def format_data_type_integer(self, data_type: IntegerType) -> Tuple[str, tuple]:
        return "INT", ()

    @DDLTypeMixin.handles(BigIntType)
    def format_data_type_bigint(self, data_type: BigIntType) -> Tuple[str, tuple]:
        return "BIGINT", ()

    @DDLTypeMixin.handles(SmallIntType)
    def format_data_type_smallint(self, data_type: SmallIntType) -> Tuple[str, tuple]:
        return "SMALLINT", ()

    @DDLTypeMixin.handles(FloatType)
    def format_data_type_float(self, data_type: FloatType) -> Tuple[str, tuple]:
        return (f"FLOAT({data_type.precision})" if data_type.precision is not None else "FLOAT"), ()

    @DDLTypeMixin.handles(RealType)
    def format_data_type_real(self, data_type: RealType) -> Tuple[str, tuple]:
        return "REAL", ()

    @DDLTypeMixin.handles(DoubleType)
    def format_data_type_double(self, data_type: DoubleType) -> Tuple[str, tuple]:
        return "FLOAT(53)", ()

    @DDLTypeMixin.handles(DecimalType)
    def format_data_type_decimal(self, data_type: DecimalType) -> Tuple[str, tuple]:
        if data_type.precision is not None and data_type.scale is not None:
            return f"DECIMAL({data_type.precision}, {data_type.scale})", ()
        if data_type.precision is not None:
            return f"DECIMAL({data_type.precision})", ()
        return "DECIMAL", ()

    @DDLTypeMixin.handles(BooleanType)
    def format_data_type_boolean(self, data_type: BooleanType) -> Tuple[str, tuple]:
        return "BIT", ()

    @DDLTypeMixin.handles(VarCharType)
    def format_data_type_varchar(self, data_type: VarCharType) -> Tuple[str, tuple]:
        return (f"VARCHAR({data_type.length})" if data_type.length is not None else "VARCHAR(255)"), ()

    @DDLTypeMixin.handles(CharType)
    def format_data_type_char(self, data_type: CharType) -> Tuple[str, tuple]:
        return (f"CHAR({data_type.length})" if data_type.length is not None else "CHAR(1)"), ()

    @DDLTypeMixin.handles(TextType)
    def format_data_type_text(self, data_type: TextType) -> Tuple[str, tuple]:
        return "NVARCHAR(MAX)", ()

    @DDLTypeMixin.handles(DateTimeType)
    def format_data_type_datetime(self, data_type: DateTimeType) -> Tuple[str, tuple]:
        return "DATETIME2", ()

    @DDLTypeMixin.handles(DateType)
    def format_data_type_date(self, data_type: DateType) -> Tuple[str, tuple]:
        return "DATE", ()

    @DDLTypeMixin.handles(TimeType)
    def format_data_type_time(self, data_type: TimeType) -> Tuple[str, tuple]:
        return "TIME", ()

    @DDLTypeMixin.handles(TimestampType)
    def format_data_type_timestamp(self, data_type: TimestampType) -> Tuple[str, tuple]:
        return "DATETIME2", ()

    @DDLTypeMixin.handles(JsonType)
    def format_data_type_json(self, data_type: JsonType) -> Tuple[str, tuple]:
        return "NVARCHAR(MAX)", ()

    @DDLTypeMixin.handles(BlobType)
    def format_data_type_blob(self, data_type: BlobType) -> Tuple[str, tuple]:
        return "VARBINARY(MAX)", ()

    @DDLTypeMixin.handles(CustomType)
    def format_data_type_custom(self, data_type: CustomType) -> Tuple[str, tuple]:
        """Render a backend-specific type verbatim (e.g. ``uniqueidentifier``)."""
        return data_type.raw, ()

    # --- Parsing ---

    def parse_type(self, raw: str) -> DataType:
        stripped = raw.strip()
        upper = stripped.upper()

        int_pattern = re.compile(r"^(?:INT|INTEGER|BIGINT|SMALLINT|TINYINT)\b", re.IGNORECASE)
        float_pattern = re.compile(r"^(?:FLOAT|REAL)\b", re.IGNORECASE)
        decimal_pattern = re.compile(r"^(?:DECIMAL|NUMERIC|MONEY|SMALLMONEY)\b", re.IGNORECASE)
        string_pattern = re.compile(r"^(?:CHAR|VARCHAR|NVARCHAR|NCHAR|TEXT|NTEXT)\b", re.IGNORECASE)
        date_pattern = re.compile(r"^(?:DATE|DATETIME|DATETIME2|SMALLDATETIME|TIMESTAMP)\b", re.IGNORECASE)
        time_pattern = re.compile(r"^(?:TIME)\b", re.IGNORECASE)
        bit_pattern = re.compile(r"^(?:BIT)\b", re.IGNORECASE)
        blob_pattern = re.compile(r"^(?:VARBINARY|IMAGE)\b", re.IGNORECASE)

        if int_pattern.match(upper):
            if upper.startswith("BIGINT"):
                return BigIntType()
            if upper.startswith("SMALLINT"):
                return SmallIntType()
            return IntegerType()

        if float_pattern.match(upper):
            if upper.startswith("REAL"):
                return RealType()
            return FloatType()

        if decimal_pattern.match(upper):
            nums = re.findall(r"\d+", stripped)
            if len(nums) >= 2:
                return DecimalType(int(nums[0]), int(nums[1]))
            if len(nums) == 1:
                return DecimalType(int(nums[0]))
            return DecimalType()

        if string_pattern.match(upper):
            if "MAX" in upper or "TEXT" in upper or "NTEXT" in upper:
                return TextType()
            length_match = re.search(r"\((\d+)", stripped)
            length = int(length_match.group(1)) if length_match else None
            if "VARCHAR" in upper or "NVARCHAR" in upper:
                return VarCharType(length or 255)
            return (CharType(length) if length_match else VarCharType(255))

        if date_pattern.match(upper):
            return DateTimeType()

        if time_pattern.match(upper):
            return TimeType()

        if bit_pattern.match(upper):
            return BooleanType()

        if blob_pattern.match(upper):
            from rhosocial.activerecord.backend.expression.types import BlobType

            return BlobType()

        return CustomType(stripped)

class SQLServerTypeSuggestionMixin(DDLTypeSuggestionMixin):
    """SQL Server ``suggest_column_type()``.

    SQL Server reuses the core generic ``DataType`` classes (rendered by
    ``SQLServerTypeSupportMixin``); suggestions therefore map to core types:

    - ``uuid.UUID`` → ``CustomType("uniqueidentifier")`` (native SQL Server
      UUID type; the default value adapter already round-trips via str).
    - ``dict`` / ``list`` → ``JsonType`` (SQL Server has no native JSON type;
      rendered as ``NVARCHAR(MAX)`` and handled by ``SQLServerJSONAdapter``).
    - ``str`` → ``VarCharType(255)`` (``VARCHAR`` in the base dialect,
      ``NVARCHAR`` under ``SQLServerUnicodeDialect``).

    All common types are stable across supported SQL Server versions, so no
    version gating applies (unlike MySQL's 5.7 JSON threshold).
    """

    def suggest_column_type(
        self, python_type: type, version: "Optional[Tuple[int, int, int]]" = None
    ) -> "Optional[DataType]":
        import datetime as _dt
        import decimal as _dec
        import enum as _enum
        import uuid as _uuid

        mapping = {
            str: VarCharType,
            int: IntegerType,
            bool: BooleanType,
            float: DoubleType,
            bytes: BlobType,
            _dt.datetime: DateTimeType,
            _dt.date: DateType,
            _dt.time: TimeType,
            _dec.Decimal: DecimalType,
            dict: JsonType,
            list: JsonType,
            _enum.Enum: VarCharType,
        }
        if python_type is _uuid.UUID:
            return CustomType("uniqueidentifier")
        factory = mapping.get(python_type)
        if factory is not None:
            if python_type is _enum.Enum:
                return VarCharType(64)
            if python_type is str:
                return VarCharType(255)
            return factory()

        return super().suggest_column_type(python_type, version)
