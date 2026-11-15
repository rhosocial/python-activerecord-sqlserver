# tests/rhosocial/activerecord_sqlserver_test/feature/backend/adapters/native/test_native_rowversion.py
"""ROWVERSION / TIMESTAMP: an 8-byte concurrency token, explicitly not a time.

``timestamp`` is SQL Server's synonym of ``rowversion``. Neither is a date/time
type: the value is a server-maintained binary counter that changes whenever the
row changes, which is what the "not a time type" assertion checks. A table may
hold only one such column, so the synonym gets its own table.
"""
from datetime import date, datetime

from sqlserver_native_models import RowVersionRow, TimestampRow


def _rule_out_time_types(value):
    assert isinstance(value, bytes), f"rowversion reads as bytes, got {type(value)!r}"
    assert not isinstance(value, (date, datetime, str)), "rowversion is not a time type"
    assert len(value) == 8, "rowversion is an 8-byte counter"


def test_no_adapter_claims_the_column(native_model):
    """``bytes`` passes through: nothing converts rowversion into a time value."""
    model = native_model(RowVersionRow)
    assert model.get_field_type_adapters()["rv"] is None


def test_round_trip_s1(native_table, native_model):
    native_table("native_rowversion")
    model = native_model(RowVersionRow)

    model(id=1, note="first").save()
    found = model.find_one(1)
    _rule_out_time_types(found.rv)
    assert found.note == "first"


def test_raw_stored_form(native_table, native_io):
    native_table("native_rowversion")
    native_io.insert("native_rowversion", {"id": "1", "note": "'first'"})
    raw = native_io.raw("native_rowversion", "rv")
    _rule_out_time_types(raw)


def test_value_changes_when_the_row_changes(native_table, native_io):
    """This is what proves the column is a concurrency token, not a value."""
    native_table("native_rowversion")
    native_io.insert("native_rowversion", {"id": "1", "note": "'before'"})
    before = native_io.raw("native_rowversion", "rv")

    native_io.backend.execute("UPDATE native_rowversion SET note = 'after' WHERE id = 1", ())
    after = native_io.raw("native_rowversion", "rv")

    assert after != before
    _rule_out_time_types(after)


def test_stored_type_is_stable_s2(native_table, native_model, native_io):
    """S2 for a server-generated column: the *type* is stable, the token is new."""
    native_table("native_rowversion")
    model = native_model(RowVersionRow)

    model(id=1, note="a").save()
    model(id=2, note="a").save()
    first = model.find_one(1).rv
    second = model.find_one(2).rv

    _rule_out_time_types(first)
    _rule_out_time_types(second)
    assert first != second, "a second row gets its own token"


def test_foreign_native_value_s3(native_table, native_model, native_io):
    """A row written without the column still carries a server token."""
    native_table("native_rowversion")
    model = native_model(RowVersionRow)

    native_io.insert("native_rowversion", {"id": "9001", "note": "'native'"})
    foreign = model.find_one(9001)
    assert foreign.note == "native"
    _rule_out_time_types(foreign.rv)


def test_timestamp_is_the_synonym(native_table, native_model, native_io):
    native_table("native_timestamp")
    model = native_model(TimestampRow)

    model(id=1, note="a").save()
    first = model.find_one(1).rv
    _rule_out_time_types(first)

    native_io.insert("native_timestamp", {"id": "2", "note": "'b'"})
    second = model.find_one(2).rv
    _rule_out_time_types(second)
    assert second != first
