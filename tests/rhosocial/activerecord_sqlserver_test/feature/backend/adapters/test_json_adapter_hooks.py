# tests/rhosocial/activerecord_sqlserver_test/feature/backend/adapters/test_json_adapter_hooks.py
"""DB-free tests for ``SQLServerJSONAdapter``'s optional ``default`` / ``object_hook``.

The hooks are forwarded to ``json.dumps`` / ``json.loads``; passing neither
keeps plain ``json`` behaviour, which the no-hook cases pin down.
"""

import json
from typing import Any

import pytest
from rhosocial.activerecord.backend.adapters.json_codec import (
    AdapterJSONCodec,
    register_type,
    unregister_type,
)

from rhosocial.activerecord.backend.impl.sqlserver.adapters import SQLServerJSONAdapter


class _Point:
    """Minimal neutral type used to prove the hooks reach ``json``."""

    json_type_tag = "demo_point_sqlserver"

    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    def to_json_value(self) -> Any:
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_json_value(cls, value: Any) -> "_Point":
        return cls(int(value["x"]), int(value["y"]))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Point) and (self.x, self.y) == (other.x, other.y)


class _Opaque:
    """Not JSON serializable by plain ``json.dumps``."""

    def __str__(self) -> str:
        return "opaque"


class TestNoHooks:
    """``default=None`` / ``object_hook=None`` reproduce the historical behaviour."""

    @pytest.fixture
    def adapter(self):
        return SQLServerJSONAdapter()

    def test_dict_and_list_serialize_to_json_text(self, adapter):
        assert adapter.to_database({"a": 1}) == '{"a": 1}'
        assert adapter.to_database([1, 2]) == "[1, 2]"

    def test_valid_json_string_still_passes_through_after_validation(self, adapter):
        raw = '{"a": [1, 2]}'
        assert adapter.to_database(raw) is raw

    def test_invalid_json_string_still_rejected(self, adapter):
        with pytest.raises(json.JSONDecodeError):
            adapter.to_database("{nope}")

    def test_plain_dict_and_list_decode_unchanged(self, adapter):
        payload = {"a": [1, {"b": 2}]}
        assert adapter.from_database('{"a": [1, {"b": 2}]}') == payload
        assert adapter.from_database(payload) is payload
        assert adapter.from_database([1, 2]) == [1, 2]

    def test_unsupported_object_still_raises_without_default(self, adapter):
        with pytest.raises(TypeError):
            adapter.to_database({"o": _Opaque()})

    def test_null_semantics(self, adapter):
        assert adapter.to_database(None) is None
        assert adapter.from_database(None) is None

    def test_supported_types_unchanged(self, adapter):
        assert adapter.supported_types[dict] == ["nvarchar(max)", "json"]
        assert adapter.supported_types[list] == ["nvarchar(max)", "json"]

    def test_unsupported_scalar_still_raises(self, adapter):
        with pytest.raises(TypeError):
            adapter.from_database(15)


class TestCustomDefault:
    def test_default_is_used_for_unsupported_objects(self):
        adapter = SQLServerJSONAdapter(default=lambda obj: str(obj))
        assert adapter.to_database({"o": _Opaque()}) == '{"o": "opaque"}'

    def test_default_does_not_affect_json_native_values(self):
        adapter = SQLServerJSONAdapter(default=lambda obj: "unused")
        assert adapter.to_database({"a": [1, None, True]}) == '{"a": [1, null, true]}'

    def test_default_does_not_change_string_validation(self):
        adapter = SQLServerJSONAdapter(default=lambda obj: "unused")
        raw = '{"a": 1}'
        assert adapter.to_database(raw) is raw


class TestObjectHook:
    def test_object_hook_decodes_matching_dicts(self):
        def hook(value):
            if set(value) == {"x", "y"}:
                return _Point(value["x"], value["y"])
            return value

        adapter = SQLServerJSONAdapter(object_hook=hook)
        decoded = adapter.from_database('{"p": {"x": 1, "y": 2}}')
        assert decoded == {"p": _Point(1, 2)}
        assert isinstance(decoded["p"], _Point)

    def test_object_hook_leaves_other_dicts_untouched(self):
        adapter = SQLServerJSONAdapter(
            object_hook=lambda value: _Point(0, 0) if "x" in value else value
        )
        assert adapter.from_database('{"a": 1, "b": [1, 2]}') == {"a": 1, "b": [1, 2]}

    def test_object_hook_is_not_applied_to_dict_input(self):
        adapter = SQLServerJSONAdapter(object_hook=lambda value: _Point(0, 0))
        payload = {"x": 1, "y": 2}
        assert adapter.from_database(payload) is payload

    def test_matching_encode_and_decode_round_trip(self):
        def default(obj):
            if isinstance(obj, _Point):
                return obj.to_json_value()
            raise TypeError(f"not serializable: {type(obj).__name__}")

        def hook(value):
            return _Point(value["x"], value["y"]) if set(value) == {"x", "y"} else value

        adapter = SQLServerJSONAdapter(default=default, object_hook=hook)
        stored = adapter.to_database({"p": _Point(1, 2)})
        assert stored == '{"p": {"x": 1, "y": 2}}'
        assert adapter.from_database(stored) == {"p": _Point(1, 2)}


class TestAdapterJSONCodecInterop:
    def test_tagged_codec_round_trips_through_the_adapter(self):
        register_type("demo_point_sqlserver", _Point)
        try:
            codec = AdapterJSONCodec(tagged=True)
            adapter = SQLServerJSONAdapter(default=codec.default, object_hook=codec.object_hook)

            stored = adapter.to_database({"p": _Point(1, 2)})
            assert json.loads(stored) == {"p": {"x": 1, "y": 2, "__type__": "demo_point_sqlserver"}}

            decoded = adapter.from_database(stored)
            assert isinstance(decoded["p"], _Point)
            assert decoded["p"] == _Point(1, 2)
        finally:
            unregister_type("demo_point_sqlserver")
