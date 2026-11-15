# tests/rhosocial/activerecord_sqlserver_test/feature/backend/adapters/native/test_native_bit.py
"""BIT: SQL Server's native boolean.

The column must not be reached through the core ``bool -> int`` default: the
backend merges ``(bool, bool)`` into the suggestion table, so the adapter's
target is the Python ``bool`` itself. The stored form is still ``0``/``1``
because that is how SQL Server spells a boolean; the assertion is about the
value crossing the driver, not about the column's internal representation.
"""
from sqlserver_native_models import BitRow


def _stored(native_io, row_id=1):
    return native_io.raw("native_bit", "CAST(flag AS int)", row_id)


def test_model_target_is_bool_not_int(native_model):
    """The suggestion table resolves BIT to the Python bool, not to int."""
    model = native_model(BitRow)
    _, target = model.get_field_type_adapters()["flag"]
    assert target is bool, "BIT must not go through the bool -> int default"


def test_adapter_does_not_convert_bool_to_int(native_io):
    """``to_database`` is the identity for the bool target and int for int."""
    adapter = native_io.adapter(bool, bool)
    assert adapter is not None

    wire = adapter.to_database(True, bool, None)
    assert wire is True
    assert isinstance(wire, bool), "the value crossing the driver is a bool"

    # The conversion this backend deliberately avoids for BIT still exists for
    # integer columns, so the two targets are genuinely different.
    assert adapter.to_database(True, int, None) == 1


def test_round_trip_s1(native_table, native_model):
    native_table("native_bit")
    model = native_model(BitRow)

    model(id=1, flag=True).save()
    model(id=2, flag=False).save()

    assert model.find_one(1).flag is True
    assert model.find_one(2).flag is False
    assert isinstance(model.find_one(1).flag, bool)


def test_raw_stored_form(native_table, native_io):
    native_table("native_bit")
    native_io.insert("native_bit", {"id": "1", "flag": "1"})
    native_io.insert("native_bit", {"id": "2", "flag": "0"})
    assert _stored(native_io, 1) == 1
    assert _stored(native_io, 2) == 0


def test_stored_form_is_stable_s2(native_table, native_model, native_io):
    native_table("native_bit")
    model = native_model(BitRow)

    model(id=1, flag=True).save()
    model(id=2, flag=model.find_one(1).flag).save()
    assert _stored(native_io, 1) == _stored(native_io, 2)


def test_foreign_native_value_s3(native_table, native_model, native_io):
    """A native ``1`` decodes to True and re-writes as ``1``."""
    native_table("native_bit")
    model = native_model(BitRow)

    native_io.insert("native_bit", {"id": "9001", "flag": "1"})
    foreign = model.find_one(9001)
    assert foreign.flag is True

    model(id=9002, flag=foreign.flag).save()
    assert _stored(native_io, 9001) == _stored(native_io, 9002)


def test_null_bit_round_trip(native_table, native_model):
    native_table("native_bit")
    model = native_model(BitRow)

    model(id=1, flag=None).save()
    assert model.find_one(1).flag is None
