# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/types.py
"""SQL Server DataType formatting mixin."""

from __future__ import annotations

import re
from typing import Tuple

from rhosocial.activerecord.backend.dialect.mixins.ddl_type import DDLTypeMixin
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
    """SQL Server DataType formatting and parsing.

    Implements ``DDLTypeSupport`` so the dialect can render ``DataType``
    expressions to SQL strings and parse raw SQL type strings back into
    ``DataType`` instances.

    Formatting dispatches by the type instance's ``name`` through the
    naming-convention ``format_data_type_<name>`` methods (see
    ``DDLTypeMixin``). SQL Server-specific types carry ``sqlserver_``-prefixed
    names; core types render their real SQL Server SQL.
    """

    # --- SQL Server-specific type formatters (dispatch key = type name) ---

    def format_data_type_sqlserver_nvarchar(self, data_type: "SQLServerNVarCharType") -> Tuple[str, tuple]:
        return (f"NVARCHAR({data_type.length})" if data_type.length is not None else "NVARCHAR(255)"), ()

    def format_data_type_sqlserver_nchar(self, data_type: "SQLServerNCharType") -> Tuple[str, tuple]:
        return (f"NCHAR({data_type.length})" if data_type.length is not None else "NCHAR(1)"), ()

    def format_data_type_sqlserver_nvarchar_max(self, data_type: "SQLServerNVarCharMaxType") -> Tuple[str, tuple]:
        return "NVARCHAR(MAX)", ()

    def format_data_type_sqlserver_varbinary(self, data_type: "SQLServerVarBinaryType") -> Tuple[str, tuple]:
        if data_type.length is not None:
            return f"VARBINARY({data_type.length})", ()
        return "VARBINARY(255)", ()

    def format_data_type_sqlserver_varbinary_max(self, data_type: "SQLServerVarBinaryMaxType") -> Tuple[str, tuple]:
        return "VARBINARY(MAX)", ()

    def format_data_type_sqlserver_xml(self, data_type: "SQLServerXmlType") -> Tuple[str, tuple]:
        return "XML", ()

    def format_data_type_sqlserver_tinyint(self, data_type: "SQLServerTinyIntType") -> Tuple[str, tuple]:
        return "TINYINT", ()

    def format_data_type_sqlserver_bit(self, data_type: "SQLServerBitType") -> Tuple[str, tuple]:
        return "BIT", ()

    def format_data_type_sqlserver_image(self, data_type: "SQLServerImageType") -> Tuple[str, tuple]:
        return "IMAGE", ()

    # --- Core types (pure names) rendered to real SQL Server SQL ---

    def format_data_type_integer(self, data_type: IntegerType) -> Tuple[str, tuple]:
        return "INT", ()

    def format_data_type_int(self, data_type: IntegerType) -> Tuple[str, tuple]:
        return "INT", ()

    def format_data_type_bigint(self, data_type: BigIntType) -> Tuple[str, tuple]:
        return "BIGINT", ()

    def format_data_type_smallint(self, data_type: SmallIntType) -> Tuple[str, tuple]:
        return "SMALLINT", ()

    def format_data_type_tinyint(self, data_type: DataType) -> Tuple[str, tuple]:
        return "TINYINT", ()

    def format_data_type_float(self, data_type: FloatType) -> Tuple[str, tuple]:
        if data_type.precision is not None:
            if not (1 <= data_type.precision <= 53):
                raise ValueError(
                    f"SQL Server FLOAT precision must be 1-53, "
                    f"got {data_type.precision}"
                )
            return f"FLOAT({data_type.precision})", ()
        return "FLOAT", ()

    def format_data_type_real(self, data_type: RealType) -> Tuple[str, tuple]:
        return "REAL", ()

    def format_data_type_double(self, data_type: DoubleType) -> Tuple[str, tuple]:
        return "FLOAT(53)", ()

    def format_data_type_decimal(self, data_type: DecimalType) -> Tuple[str, tuple]:
        if data_type.precision is not None:
            if not (1 <= data_type.precision <= 38):
                raise ValueError(
                    f"SQL Server DECIMAL precision must be 1-38, "
                    f"got {data_type.precision}"
                )
        if data_type.scale is not None:
            if data_type.precision is not None and data_type.scale > data_type.precision:
                raise ValueError(
                    f"SQL Server DECIMAL scale ({data_type.scale}) "
                    f"must not exceed precision ({data_type.precision})"
                )
        if data_type.precision is not None and data_type.scale is not None:
            return f"DECIMAL({data_type.precision}, {data_type.scale})", ()
        if data_type.precision is not None:
            return f"DECIMAL({data_type.precision})", ()
        return "DECIMAL", ()

    def format_data_type_boolean(self, data_type: BooleanType) -> Tuple[str, tuple]:
        return "BIT", ()

    def format_data_type_varchar(self, data_type: VarCharType) -> Tuple[str, tuple]:
        return (f"VARCHAR({data_type.length})" if data_type.length is not None else "VARCHAR(255)"), ()

    def format_data_type_char(self, data_type: CharType) -> Tuple[str, tuple]:
        return (f"CHAR({data_type.length})" if data_type.length is not None else "CHAR(1)"), ()

    def format_data_type_text(self, data_type: TextType) -> Tuple[str, tuple]:
        return "NVARCHAR(MAX)", ()

    def format_data_type_datetime(self, data_type: DateTimeType) -> Tuple[str, tuple]:
        if data_type.precision is not None:
            if not (0 <= data_type.precision <= 7):
                raise ValueError(
                    f"SQL Server DATETIME2 fractional seconds precision "
                    f"must be 0-7, got {data_type.precision}"
                )
            return f"DATETIME2({data_type.precision})", ()
        return "DATETIME2", ()

    def format_data_type_date(self, data_type: DateType) -> Tuple[str, tuple]:
        return "DATE", ()

    def format_data_type_time(self, data_type: TimeType) -> Tuple[str, tuple]:
        if data_type.precision is not None:
            if not (0 <= data_type.precision <= 7):
                raise ValueError(
                    f"SQL Server TIME fractional seconds precision "
                    f"must be 0-7, got {data_type.precision}"
                )
            return f"TIME({data_type.precision})", ()
        return "TIME", ()

    def format_data_type_timestamp(self, data_type: TimestampType) -> Tuple[str, tuple]:
        if data_type.precision is not None:
            if not (0 <= data_type.precision <= 7):
                raise ValueError(
                    f"SQL Server DATETIME2 fractional seconds precision "
                    f"must be 0-7, got {data_type.precision}"
                )
            return f"DATETIME2({data_type.precision})", ()
        return "DATETIME2", ()

    def format_data_type_json(self, data_type: JsonType) -> Tuple[str, tuple]:
        return "NVARCHAR(MAX)", ()

    def format_data_type_blob(self, data_type: BlobType) -> Tuple[str, tuple]:
        return "VARBINARY(MAX)", ()

    def format_data_type_custom(self, data_type: CustomType) -> Tuple[str, tuple]:
        return data_type.raw, ()

    # ------------------------------------------------------------------
    # supports_data_type_<name> — 1:1 with format_data_type_<name>
    # ------------------------------------------------------------------

    def supports_data_type_sqlserver_nvarchar(self) -> bool:
        return True

    def supports_data_type_sqlserver_nchar(self) -> bool:
        return True

    def supports_data_type_sqlserver_nvarchar_max(self) -> bool:
        return True

    def supports_data_type_sqlserver_varbinary(self) -> bool:
        return True

    def supports_data_type_sqlserver_varbinary_max(self) -> bool:
        return True

    def supports_data_type_sqlserver_xml(self) -> bool:
        return True

    def supports_data_type_sqlserver_tinyint(self) -> bool:
        return True

    def supports_data_type_sqlserver_bit(self) -> bool:
        return True

    def supports_data_type_sqlserver_image(self) -> bool:
        return True

    def supports_data_type_integer(self) -> bool:
        return True

    def supports_data_type_int(self) -> bool:
        return True

    def supports_data_type_bigint(self) -> bool:
        return True

    def supports_data_type_smallint(self) -> bool:
        return True

    def supports_data_type_tinyint(self) -> bool:
        return True

    def supports_data_type_float(self) -> bool:
        return True

    def supports_data_type_real(self) -> bool:
        return True

    def supports_data_type_double(self) -> bool:
        return True

    def supports_data_type_decimal(self) -> bool:
        return True

    def supports_data_type_boolean(self) -> bool:
        return True

    def supports_data_type_varchar(self) -> bool:
        return True

    def supports_data_type_char(self) -> bool:
        return True

    def supports_data_type_text(self) -> bool:
        return True

    def supports_data_type_datetime(self) -> bool:
        return True

    def supports_data_type_date(self) -> bool:
        return True

    def supports_data_type_time(self) -> bool:
        return True

    def supports_data_type_timestamp(self) -> bool:
        return True

    def supports_data_type_json(self) -> bool:
        return True

    def supports_data_type_blob(self) -> bool:
        return True

    def supports_data_type_custom(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # DDLTypeSupport — parsing
    # ------------------------------------------------------------------

    _SQLSERVER_INTEGER_TYPES = re.compile(
        r"^(?:INT|INTEGER|BIGINT|SMALLINT|TINYINT)\b",
        re.IGNORECASE,
    )
    _SQLSERVER_FLOAT_TYPES = re.compile(
        r"^(?:FLOAT|REAL)\b",
        re.IGNORECASE,
    )
    _SQLSERVER_DECIMAL_TYPES = re.compile(
        r"^(?:DECIMAL|NUMERIC|MONEY|SMALLMONEY)\b",
        re.IGNORECASE,
    )
    _SQLSERVER_STRING_TYPES = re.compile(
        r"^(?:CHAR|VARCHAR|NVARCHAR|NCHAR|TEXT|NTEXT)\b",
        re.IGNORECASE,
    )
    _SQLSERVER_DATE_TYPES = re.compile(
        r"^(?:DATE|DATETIME|DATETIME2|SMALLDATETIME|TIMESTAMP)\b",
        re.IGNORECASE,
    )
    _SQLSERVER_TIME_TYPES = re.compile(
        r"^(?:TIME)\b",
        re.IGNORECASE,
    )
    _SQLSERVER_BIT_TYPES = re.compile(
        r"^(?:BIT)\b",
        re.IGNORECASE,
    )
    _SQLSERVER_BLOB_TYPES = re.compile(
        r"^(?:VARBINARY|IMAGE)\b",
        re.IGNORECASE,
    )

    def parse_type(self, raw: str) -> DataType:
        stripped = raw.strip()
        upper = stripped.upper()

        # BIT type
        if self._SQLSERVER_BIT_TYPES.match(upper):
            from ..expression.types import SQLServerBitType
            return SQLServerBitType(dialect=self)

        # Integer family
        if self._SQLSERVER_INTEGER_TYPES.match(upper):
            if upper.startswith("BIGINT"):
                return BigIntType(dialect=self)
            if upper.startswith("SMALLINT"):
                return SmallIntType(dialect=self)
            if upper.startswith("TINYINT"):
                from ..expression.types import SQLServerTinyIntType
                return SQLServerTinyIntType(dialect=self)
            return IntegerType(dialect=self)

        # Float family
        if self._SQLSERVER_FLOAT_TYPES.match(upper):
            if upper.startswith("REAL"):
                return RealType(dialect=self)
            nums = re.findall(r"\d+", stripped)
            precision = int(nums[0]) if nums else None
            return FloatType(dialect=self, precision=precision)

        # Decimal family
        if self._SQLSERVER_DECIMAL_TYPES.match(upper):
            nums = re.findall(r"\d+", stripped)
            if len(nums) >= 2:
                return DecimalType(dialect=self, precision=int(nums[0]), scale=int(nums[1]))
            if len(nums) == 1:
                return DecimalType(dialect=self, precision=int(nums[0]))
            return DecimalType(dialect=self)

        # String family
        if self._SQLSERVER_STRING_TYPES.match(upper):
            if "MAX" in upper or "TEXT" in upper or "NTEXT" in upper:
                return TextType(dialect=self)
            length_match = re.search(r"\((\d+)", stripped)
            length = int(length_match.group(1)) if length_match else None
            if "VARCHAR" in upper or "NVARCHAR" in upper:
                return VarCharType(dialect=self, length=length or 255)
            return (CharType(dialect=self, length=length) if length_match else VarCharType(dialect=self, length=255))

        # Date/time family
        if self._SQLSERVER_DATE_TYPES.match(upper):
            return DateTimeType(dialect=self)

        if self._SQLSERVER_TIME_TYPES.match(upper):
            return TimeType(dialect=self)

        # Blob family
        if self._SQLSERVER_BLOB_TYPES.match(upper):
            from ..expression.types import SQLServerVarBinaryType
            return SQLServerVarBinaryType(dialect=self)

        return CustomType(dialect=self, raw=stripped)
