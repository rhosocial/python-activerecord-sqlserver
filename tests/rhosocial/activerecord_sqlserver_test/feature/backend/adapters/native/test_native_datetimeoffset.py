# tests/rhosocial/activerecord_sqlserver_test/feature/backend/adapters/native/test_native_datetimeoffset.py
"""DATETIMEOFFSET: a datetime that carries its UTC offset.

Two environment limits decide the shape of these tests, and both are asserted
rather than worked around:

* **write** -- a value carried by a bare ``?`` loses its offset: the ODBC layer
  sends a timestamp and SQL Server applies the session offset (``+00:00``).
  Preserving ``+08:00`` needs ``CONVERT(datetimeoffset(7), ?)``, and the
  execution layer does not render that wrapper (testing plan §4.7, §7.3).
* **read** -- pyodbc 5.5.0 rejects ODBC type ``-155``
  (``SQL_SS_TIMESTAMPOFFSET``), so the column cannot be fetched as a Python
  value at all. The stored form is read through
  ``CONVERT(varchar(60), dto, 121)`` and decoded by the adapter.
"""
from datetime import datetime, timedelta, timezone

import pytest

from rhosocial.activerecord.backend.impl.sqlserver.adapters import (
    SQLServerDateTimeOffsetAdapter,
)
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType
from sqlserver_native_models import DateTimeOffsetRow

DML = ExecutionOptions(stmt_type=StatementType.DML)

OFFSET = timezone(timedelta(hours=8))
VALUE = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=OFFSET)
STORED_TEXT = "2026-01-02 03:04:05.1234567 +08:00"
WRAPPED_INSERT = (
    "INSERT INTO native_datetimeoffset (id, dto) VALUES (?, CONVERT(datetimeoffset(7), ?))"
)


def _offset_text(value):
    """Render the ``+HH:MM`` suffix Python's ``isoformat`` cannot always give."""
    offset = value.utcoffset()
    sign = "+" if offset >= timedelta(0) else "-"
    minutes = abs(int(offset.total_seconds())) // 60
    return f"{sign}{minutes // 60:02d}:{minutes % 60:02d}"


def _stored(native_io, row_id=1):
    return native_io.raw("native_datetimeoffset", "CONVERT(varchar(60), dto, 121)", row_id)


def test_model_declares_the_offset_adapter(native_model):
    """The field pins the offset adapter, not the plain DATETIME2 one."""
    model = native_model(DateTimeOffsetRow)
    adapter, target = model.get_field_type_adapters()["dto"]
    assert isinstance(adapter, SQLServerDateTimeOffsetAdapter)
    assert target is datetime


def test_adapter_semantic_round_trip(native_io):
    """S1 without a server: text carrying ``+08:00`` decodes with that offset."""
    adapter = SQLServerDateTimeOffsetAdapter()

    wire = adapter.to_database(VALUE, datetime, None)
    assert wire is VALUE, "the driver target is the datetime itself"

    decoded = adapter.from_database(STORED_TEXT, datetime)
    assert decoded == VALUE
    assert decoded.utcoffset() == timedelta(hours=8)


def test_round_trip_preserves_the_offset_s1(native_table, native_io):
    """S1 on the server, through the wrapper the execution layer does not render."""
    native_table("native_datetimeoffset")
    native_io.backend.execute(WRAPPED_INSERT, (1, STORED_TEXT), options=DML)

    assert _stored(native_io) == STORED_TEXT
    assert native_io.raw("native_datetimeoffset", "DATEPART(TZOFFSET, dto)") == 480

    decoded = SQLServerDateTimeOffsetAdapter().from_database(_stored(native_io), datetime)
    assert decoded.utcoffset() == timedelta(hours=8)


def test_stored_form_is_stable_s2(native_table, native_io):
    """S2: the value read back renders to the identical stored text."""
    native_table("native_datetimeoffset")
    adapter = SQLServerDateTimeOffsetAdapter()

    native_io.backend.execute(WRAPPED_INSERT, (1, STORED_TEXT), options=DML)
    read_back = adapter.from_database(_stored(native_io), datetime)
    # ``isoformat`` on an aware datetime already appends the UTC offset, so the
    # naive wall-clock is rendered and the offset is spelled once, after it.
    naive_text = read_back.replace(tzinfo=None).isoformat(
        sep=" ", timespec="microseconds"
    )
    wire_text = naive_text + " " + _offset_text(read_back)

    native_io.backend.execute(WRAPPED_INSERT, (2, wire_text), options=DML)
    # The server keeps 100 ns precision and the driver target (datetime) carries
    # microseconds, so stability is asserted at the precision the adapter
    # claims rather than the storage text's seventh digit.
    stored_1 = adapter.from_database(_stored(native_io, 1), datetime)
    stored_2 = adapter.from_database(_stored(native_io, 2), datetime)
    assert stored_2 == stored_1
    assert stored_2.utcoffset() == stored_1.utcoffset() == timedelta(hours=8)


def test_foreign_native_value_s3(native_table, native_io):
    """S3: a literal the server wrote itself decodes and re-writes unchanged."""
    native_table("native_datetimeoffset")

    native_io.insert("native_datetimeoffset", {"id": "9001", "dto": f"'{STORED_TEXT}'"})
    assert _stored(native_io, 9001) == STORED_TEXT

    adapter = SQLServerDateTimeOffsetAdapter()
    decoded = adapter.from_database(_stored(native_io, 9001), datetime)
    # ``isoformat`` on an aware datetime already appends the UTC offset, so the
    # naive wall-clock is rendered and the offset is spelled once, after it.
    naive_text = decoded.replace(tzinfo=None).isoformat(
        sep=" ", timespec="microseconds"
    )
    wire_text = naive_text + " " + _offset_text(decoded)
    native_io.backend.execute(WRAPPED_INSERT, (9002, wire_text), options=DML)

    decoded_2 = adapter.from_database(_stored(native_io, 9002), datetime)
    assert decoded_2 == decoded
    assert decoded_2.utcoffset() == decoded.utcoffset() == timedelta(hours=8)
    # The server keeps 100 ns precision; the driver target carries
    # microseconds, so the seventh digit is not claimed.


def test_zero_and_negative_offsets(native_table, native_io):
    """Two more offsets, so the claim is about the offset, not one literal."""
    native_table("native_datetimeoffset")
    cases = {
        1: "2026-01-02 03:04:05.0000000 +00:00",
        2: "2026-01-02 03:04:05.0000000 -05:00",
    }
    for row_id, text in cases.items():
        native_io.insert("native_datetimeoffset", {"id": str(row_id), "dto": f"'{text}'"})
        assert _stored(native_io, row_id) == text

    adapter = SQLServerDateTimeOffsetAdapter()
    assert adapter.from_database(cases[1], datetime).utcoffset() == timedelta(0)
    assert adapter.from_database(cases[2], datetime).utcoffset() == timedelta(hours=-5)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "DATETIMEOFFSET cannot round-trip through the ORM yet: a bare '?' carries "
        "the value as a timestamp, so SQL Server stores the session offset "
        "(+00:00), and pyodbc 5.5.0 rejects ODBC type -155 (SQL_SS_TIMESTAMPOFFSET) "
        "on read. Both need work outside this adapter: execution-layer parameter "
        "wrapping (testing plan §4.7 and the §8 item 'execution layer supports "
        "bind_expression'; §7.3) plus a driver that returns the type."
    ),
)
def test_orm_round_trip_preserves_the_offset(native_table, native_model):
    native_table("native_datetimeoffset")
    model = native_model(DateTimeOffsetRow)

    model(id=1, dto=VALUE).save()
    found = model.find_one(1)
    assert found.dto.utcoffset() == timedelta(hours=8)
