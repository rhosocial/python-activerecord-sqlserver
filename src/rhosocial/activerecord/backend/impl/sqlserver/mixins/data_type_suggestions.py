# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/data_type_suggestions.py
"""SQL Server's **suggested data types**: what a bare field is declared as here.

The DDL half of the type answer; :mod:`.column_type` is the operation half. A
column class says what a value can *do*, this table says what a column *is*.

Shapes this server forces:

* **text is Unicode here.** ``str`` is declared ``NVARCHAR(255)`` through this
  backend's own class, and unbounded text is ``NVARCHAR(MAX)`` -- ``TEXT`` is
  the deprecated non-Unicode type and cannot hold characters outside the
  database collation.
* **a byte string is ``VARBINARY(MAX)``.** ``BlobType`` and this backend's
  :class:`SQLServerVarBinaryMaxType` render the same declaration; the backend
  class is named because it is the one this server's adapter writes.
* **a document and the four sequence entries share ``NVARCHAR(MAX)``**:
  SQL Server has no JSON *type* on any version this backend targets. A JSON
  value is text in an ordinary column and ``OPENJSON`` / ``JSON_VALUE`` /
  ``ISJSON`` are functions over it, which is what :class:`JsonType` renders
  here; there is no array type either, so ``list``/``tuple``/``set``/
  ``frozenset`` spend the same word.
* **a UUID is native.** ``UNIQUEIDENTIFIER`` is the server's own 16-byte GUID,
  reached through :class:`SQLServerUniqueIdentifierType`; the text form
  ``CHAR(36)`` would waste width and lose the fixed-length guarantee.
* **there is no interval type.** ``DATEDIFF`` returns a count of a datepart
  rather than a value, so ``datetime.timedelta`` is carried as text, its
  neutral adapter's form.

The complex families are carried as the text their neutral adapters already
write -- WKT for ``Geometry``, a JSON array for ``Vector``, bit-string text for
``BitString``, the literal text for ``Range`` / ``Multirange``, canonical
lowercase colon text for ``MacAddress``. SQL Server does have native
``geometry`` / ``geography`` CLR types, but this backend models no ``DataType``
class for them yet, so the suggestion names the text carrier a bare field can
round-trip through; a field that wants the CLR type declares it with
``UseSqlType``. No key answers ``None``: a suggestion is what a bare field gets,
and taking the table away from the caller is not an answer.

Each call returns a **fresh dict** whose values are this module's read-only
templates; the derivation binds a dialect on a copy of the single entry it uses.
"""
from __future__ import annotations

import datetime
import decimal
import enum
import uuid
from typing import Any, Dict, Optional

from rhosocial.activerecord.backend.adapters import (
    BitString,
    Geometry,
    MacAddress,
    Multirange,
    Range,
    Vector,
)
from rhosocial.activerecord.backend.expression.types import (
    DateType,
    DecimalType,
    DoubleType,
    IntegerType,
    JsonType,
    TextType,
    TimeType,
    TimestampType,
    VarCharType,
)
from rhosocial.activerecord.backend.impl.sqlserver.expression.types import (
    SQLServerBitType,
    SQLServerNVarCharType,
    SQLServerUniqueIdentifierType,
    SQLServerVarBinaryMaxType,
)

#: SQL Server's suggested declaration per framework-modelled Python type.
SQLSERVER_DATA_TYPE_SUGGESTIONS: Dict[Any, Optional[Any]] = {
    bool: SQLServerBitType(),
    int: IntegerType(),
    float: DoubleType(),
    # A bare DECIMAL is DECIMAL(18, 0) on SQL Server: no fractional digits, so
    # a value like Decimal("10.99") would be rounded to 11 on the way in.  Give
    # the suggestion a scale so a bare ``Decimal`` field round-trips its cents.
    decimal.Decimal: DecimalType(precision=18, scale=4),
    str: SQLServerNVarCharType(length=255),
    bytes: SQLServerVarBinaryMaxType(),
    bytearray: SQLServerVarBinaryMaxType(),
    datetime.date: DateType(),
    datetime.time: TimeType(),
    # DATETIME2's default precision is 7, but anything below 6 loses the
    # microsecond part of a datetime (3 keeps only milliseconds).  Recommend 6
    # so a bare ``datetime`` field round-trips the microsecond a caller writes.
    datetime.datetime: TimestampType(precision=6),
    # SQL Server has no interval type; the value's text form is the carrier.
    datetime.timedelta: TextType(),
    uuid.UUID: SQLServerUniqueIdentifierType(),
    dict: JsonType(),
    list: JsonType(),
    tuple: JsonType(),
    set: JsonType(),
    frozenset: JsonType(),
    enum.Enum: VarCharType(length=255),
    # -- Complex families ------------------------------------------------
    # The CLR type exists, but no DataType class of this backend names it; WKT
    # text is what the adapter writes, so a bare field round-trips through it.
    Geometry: TextType(),
    # A dimension is column policy; the adapter's JSON text is the carrier.
    Vector: TextType(),
    # BIT(n) needs a width the annotation does not carry; digits as text.
    BitString: TextType(),
    # The element type is column policy; the adapter writes the literal text.
    Range: TextType(),
    Multirange: TextType(),
    MacAddress: VarCharType(length=17),
}


class SQLServerDataTypeSuggestionsMixin:
    """SQL Server's answer to "what declaration does a bare field get here"."""

    def suggested_data_types(self) -> Dict[Any, Optional[Any]]:
        return dict(SQLSERVER_DATA_TYPE_SUGGESTIONS)


__all__ = [
    "SQLSERVER_DATA_TYPE_SUGGESTIONS",
    "SQLServerDataTypeSuggestionsMixin",
]
