# tests/rhosocial/activerecord_sqlserver_test/feature/backend/adapters/native/test_native_money.py
"""MONEY / SMALLMONEY on a live SQL Server.

The column is fixed-point with four decimal places, and the backend reaches it
through the ``Decimal`` suggestion. The assertions follow testing plan §3.1
(Python value, wire target, stored text) and §3.4 (S1/S2/S3).
"""
from decimal import Decimal

from rhosocial.activerecord.backend.impl.sqlserver.adapters import SQLServerDecimalAdapter
from sqlserver_native_models import MoneyRow

AMOUNT = Decimal("1234.5678")
SMALL = Decimal("-12.3456")


def _amount(native_io, row_id=1):
    return native_io.raw("native_money", "CONVERT(varchar(40), amount, 2)", row_id)


def _small(native_io, row_id=1):
    return native_io.raw("native_money", "CONVERT(varchar(40), small, 2)", row_id)


def test_adapter_semantic_round_trip(native_io):
    """S1 without a server: the registered Decimal adapter is the carrier."""
    adapter = native_io.adapter(Decimal, Decimal)
    assert isinstance(adapter, SQLServerDecimalAdapter)

    wire = adapter.to_database(AMOUNT, Decimal, None)
    assert isinstance(wire, float), "the documented driver target for Decimal is float"
    assert adapter.from_database(wire, Decimal) == AMOUNT


def test_round_trip_s1(native_table, native_model):
    """S1 on the server: a Decimal written to MONEY reads back unchanged."""
    native_table("native_money")
    model = native_model(MoneyRow)

    model(id=1, amount=AMOUNT, small=SMALL).save()
    found = model.find_one(1)
    assert found.amount == AMOUNT
    assert found.small == SMALL


def test_raw_stored_form(native_table, native_io):
    """The column holds a fixed-point value, not a float or a string."""
    native_table("native_money")
    native_io.insert("native_money", {"id": "1", "amount": "1234.5678", "small": "-12.3456"})

    # Style 2 is the locale-independent four-decimal form.
    assert _amount(native_io) == "1234.5678"
    assert _small(native_io) == "-12.3456"
    # The default style keeps MONEY's two-decimal display form.
    assert native_io.raw("native_money", "CONVERT(varchar(40), amount)") == "1234.57"


def test_stored_form_is_stable_s2(native_table, native_model, native_io):
    """S2: writing the value read back produces the same stored text."""
    native_table("native_money")
    model = native_model(MoneyRow)

    model(id=1, amount=AMOUNT, small=SMALL).save()
    read_back = model.find_one(1)
    model(id=2, amount=read_back.amount, small=read_back.small).save()

    assert _amount(native_io, 1) == _amount(native_io, 2)
    assert _small(native_io, 1) == _small(native_io, 2)


def test_foreign_native_value_s3(native_table, native_model, native_io):
    """S3: a value written as native SQL decodes and re-writes canonically."""
    native_table("native_money")
    model = native_model(MoneyRow)

    native_io.insert("native_money", {"id": "9001", "amount": "1234.5678", "small": "-12.3456"})
    foreign = model.find_one(9001)
    assert foreign.amount == AMOUNT
    assert foreign.small == SMALL

    model(id=9002, amount=foreign.amount, small=foreign.small).save()
    assert _amount(native_io, 9001) == _amount(native_io, 9002)


def test_smallmoney_bounds_round_trip(native_table, native_model, native_io):
    """SMALLMONEY's documented range survives the round trip."""
    native_table("native_money")
    model = native_model(MoneyRow)

    values = (Decimal("214748.3647"), Decimal("-214748.3648"), Decimal("0.0001"))
    for row_id, value in enumerate(values, start=1):
        model(id=row_id, small=value).save()

    for row_id, value in enumerate(values, start=1):
        assert model.find_one(row_id).small == value
        assert _small(native_io, row_id) == str(value)
