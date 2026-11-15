# tests/rhosocial/activerecord_sqlserver_test/feature/backend/adapters/native/test_native_uniqueidentifier.py
"""UNIQUEIDENTIFIER: SQL Server's native 16-byte GUID.

The adapter writes the canonical string form and reads back ``uuid.UUID``.
pyodbc returns the column as text, which is why the stored-form assertion is
``CONVERT(varchar(36), uid)``; the server renders it in upper case.
"""
import uuid

from sqlserver_native_models import UniqueIdentifierRow

UID = uuid.UUID("0f8fad5b-d9cb-469f-a165-70867728950e")
STORED_TEXT = "0F8FAD5B-D9CB-469F-A165-70867728950E"


def _stored(native_io, row_id=1):
    return native_io.raw("native_uniqueidentifier", "CONVERT(varchar(36), uid)", row_id)


def test_adapter_semantic_round_trip(native_io):
    """S1 without a server: the registered adapter writes and reads a UUID."""
    adapter = native_io.adapter(uuid.UUID, str)
    assert adapter is not None, "UUID -> str is the backend's suggestion for UUID"

    wire = adapter.to_database(UID, str, None)
    assert isinstance(wire, str)
    assert adapter.from_database(wire, uuid.UUID) == UID


def test_round_trip_s1(native_table, native_model):
    native_table("native_uniqueidentifier")
    model = native_model(UniqueIdentifierRow)

    model(id=1, uid=UID).save()
    found = model.find_one(1)
    assert found.uid == UID
    assert isinstance(found.uid, uuid.UUID)


def test_raw_stored_form(native_table, native_io):
    """The column stores the canonical GUID, upper case on this server."""
    native_table("native_uniqueidentifier")
    native_io.insert("native_uniqueidentifier", {"id": "1", "uid": f"'{UID}'"})
    assert _stored(native_io) == STORED_TEXT


def test_stored_form_is_stable_s2(native_table, native_model, native_io):
    native_table("native_uniqueidentifier")
    model = native_model(UniqueIdentifierRow)

    model(id=1, uid=UID).save()
    read_back = model.find_one(1)
    model(id=2, uid=read_back.uid).save()
    assert _stored(native_io, 1) == _stored(native_io, 2)


def test_foreign_native_value_s3(native_table, native_model, native_io):
    """A lower-case literal reads back as a UUID and re-writes canonically."""
    native_table("native_uniqueidentifier")
    model = native_model(UniqueIdentifierRow)

    native_io.insert(
        "native_uniqueidentifier", {"id": "9001", "uid": "'0f8fad5b-d9cb-469f-a165-70867728950e'"}
    )
    foreign = model.find_one(9001)
    assert foreign.uid == UID

    model(id=9002, uid=foreign.uid).save()
    assert _stored(native_io, 9001) == _stored(native_io, 9002) == STORED_TEXT


def test_nil_uuid_round_trip(native_table, native_model):
    """The all-zero GUID is a value, not a NULL."""
    native_table("native_uniqueidentifier")
    model = native_model(UniqueIdentifierRow)

    nil = uuid.UUID(int=0)
    model(id=1, uid=nil).save()
    assert model.find_one(1).uid == nil
