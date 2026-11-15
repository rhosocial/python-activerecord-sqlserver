# tests/rhosocial/activerecord_sqlserver_test/feature/backend/adapters/native/test_native_json.py
"""JSON kept as text in ``NVARCHAR(MAX)``.

SQL Server has no JSON type. The column is text, the server validates it with
``ISJSON()``, and the core ``JSONAdapter`` is the carrier (``dict -> str``).
That is also why ``SELECT`` returns text and the read side has to call
``json.loads`` -- the "driver pre-decodes nothing" hook surface of testing plan
§3.5.
"""
import json

import pytest
from pydantic import ValidationError

from sqlserver_native_models import JsonRow

PAYLOAD = {"a": 1, "b": [1, None, "x"], "unicode": "测试", "big": 2**53 + 1}
STORED_TEXT = json.dumps(PAYLOAD)


def _stored(native_io, row_id=1):
    return native_io.raw("native_json", "payload", row_id)


def test_column_is_text_not_a_json_type(native_table, native_io):
    native_table("native_json")
    assert native_io.column_type("native_json", "payload") == "nvarchar"


def test_round_trip_s1(native_table, native_model):
    native_table("native_json")
    model = native_model(JsonRow)

    model(id=1, payload=PAYLOAD).save()
    found = model.find_one(1)
    assert found.payload == PAYLOAD


def test_raw_stored_form(native_table, native_io):
    """The stored text is valid JSON, which the server confirms itself."""
    native_table("native_json")
    native_io.insert("native_json", {"id": "1", "payload": f"'{STORED_TEXT}'"})

    assert _stored(native_io) == STORED_TEXT
    assert native_io.raw("native_json", "ISJSON(payload)") == 1
    assert native_io.raw("native_json", "JSON_VALUE(payload, '$.a')") == "1"


def test_stored_form_is_stable_s2(native_table, native_model, native_io):
    """No double encoding: the rewrite produces byte-identical text."""
    native_table("native_json")
    model = native_model(JsonRow)

    model(id=1, payload=PAYLOAD).save()
    read_back = model.find_one(1)
    model(id=2, payload=read_back.payload).save()

    assert _stored(native_io, 1) == _stored(native_io, 2) == STORED_TEXT


def test_foreign_native_value_s3(native_table, native_model, native_io):
    """Text another writer produced reads back as a dict and re-writes as-is."""
    native_table("native_json")
    model = native_model(JsonRow)

    native_io.insert("native_json", {"id": "9001", "payload": "'{\"k\": \"v\"}'"})
    foreign = model.find_one(9001)
    assert foreign.payload == {"k": "v"}

    model(id=9002, payload=foreign.payload).save()
    assert _stored(native_io, 9001) == _stored(native_io, 9002) == '{"k": "v"}'


def test_twice_serialized_text_is_detected(native_table, native_model, native_io):
    """A payload stored as an already-encoded string is detected, not decoded twice.

    This is the shape a double encoding produces (``"{\\"a\\": 1}"``): the column
    holds one JSON document whose value is text. The adapter runs ``json.loads``
    exactly once, so the decoded value is a ``str`` and the model's ``dict`` field
    refuses the row instead of silently returning the inner document.
    """
    native_table("native_json")
    model = native_model(JsonRow)

    double_encoded = json.dumps(json.dumps({"a": 1}))
    native_io.insert("native_json", {"id": "1", "payload": f"N'{double_encoded}'"})
    assert _stored(native_io) == double_encoded

    with pytest.raises(ValidationError, match="valid dictionary"):
        model.find_one(1)
