# tests/rhosocial/activerecord_sqlserver_test/feature/backend/sqlserver/test_adapters_offline.py
"""Offline bidirectional conversion tests for ``impl/sqlserver/adapters.py``.

Every adapter is exercised for to_database / from_database round trips,
NULL semantics, empty-string semantics and error paths. No backend or
server is involved.
"""
import json
import uuid
import xml.etree.ElementTree as ET
from datetime import date, datetime, time, timezone
from decimal import Decimal

import pytest

from rhosocial.activerecord.backend.impl.sqlserver.adapters import (
    SQLServerDateAdapter,
    SQLServerDateTimeAdapter,
    SQLServerDateTimeOffsetAdapter,
    SQLServerDecimalAdapter,
    SQLServerHierarchyIdAdapter,
    SQLServerJSONAdapter,
    SQLServerSpatialAdapter,
    SQLServerTimeAdapter,
    SQLServerUUIDAdapter,
    SQLServerXMLAdapter,
    _parse_sql_datetime,
)


class TestParseSqlDatetime:
    def test_seven_digit_fraction_is_truncated_and_padded(self):
        # ODBC delivers datetime2 with 100ns precision (7 fractional digits).
        result = _parse_sql_datetime("2026-08-09 05:25:26.5205700")
        assert result == datetime(2026, 8, 9, 5, 25, 26, 520570, tzinfo=timezone.utc)

    def test_naive_value_gets_utc(self):
        assert _parse_sql_datetime("2026-08-09 05:25:26").tzinfo == timezone.utc

    def test_z_suffix_becomes_utc(self):
        result = _parse_sql_datetime("2026-08-09T05:25:26Z")
        assert result.utcoffset().total_seconds() == 0

    def test_explicit_offset_preserved(self):
        result = _parse_sql_datetime("2026-08-09T05:25:26.1234567+05:30")
        assert (result.hour, result.minute, result.second, result.microsecond) == (5, 25, 26, 123456)
        assert result.tzinfo is not None and result.utcoffset().total_seconds() == 5 * 3600 + 1800


class TestSQLServerUUIDAdapter:
    @pytest.fixture
    def adapter(self):
        return SQLServerUUIDAdapter()

    def test_supported_types(self, adapter):
        assert adapter.supported_types[uuid.UUID] == ["uniqueidentifier"]
        assert "uniqueidentifier" in adapter.supported_types[str]

    def test_uuid_to_database_renders_canonical_string(self, adapter):
        value = uuid.UUID("12345678123456781234567812345678")
        assert adapter.to_database(value) == "12345678-1234-5678-1234-567812345678"

    def test_valid_string_passthrough_keeps_case(self, adapter):
        upper = "12345678-1234-5678-1234-567812345678".upper()
        assert adapter.to_database(upper) == upper  # validated but not normalized

    def test_invalid_uuid_string_raises(self, adapter):
        with pytest.raises(ValueError, match="Invalid UUID string"):
            adapter.to_database("not-a-uuid")

    def test_unsupported_type_raises(self, adapter):
        with pytest.raises(TypeError):
            adapter.to_database(42)

    def test_from_database_roundtrip(self, adapter):
        value = uuid.uuid4()
        assert adapter.from_database(value) is value
        assert adapter.from_database(str(value).upper()) == value

    def test_null_semantics(self, adapter):
        assert adapter.to_database(None) is None
        assert adapter.from_database(None) is None


class TestSQLServerDateTimeAdapter:
    @pytest.fixture
    def adapter(self):
        return SQLServerDateTimeAdapter()

    def test_supported_types(self, adapter):
        assert set(adapter.supported_types[datetime]) == {"datetime2", "datetime", "smalldatetime"}

    def test_datetime_instance_passthrough(self, adapter):
        value = datetime(2026, 8, 9, 5, 25, 26)
        assert adapter.to_database(value) is value

    def test_iso_string_accepted(self, adapter):
        assert adapter.to_database("2026-08-09T05:25:26") == datetime(2026, 8, 9, 5, 25, 26)

    def test_epoch_number_becomes_utc_aware(self, adapter):
        result = adapter.to_database(0)
        assert (result.year, result.tzname()) in {(1970, "UTC"), (1970, "UTC+00:00")}

    def test_invalid_string_falls_through_to_type_error(self, adapter):
        with pytest.raises(TypeError):
            adapter.to_database("")  # not ISO, not numeric -> TypeError

    def test_from_database_naive_gets_utc(self, adapter):
        naive = datetime(2026, 8, 9, 5, 25, 26)
        assert adapter.from_database(naive).tzinfo == timezone.utc

    def test_from_database_string_uses_sql_parser(self, adapter):
        result = adapter.from_database("2026-08-09 05:25:26.5205700")
        assert result.microsecond == 520570

    def test_roundtrip(self, adapter):
        # Aware values survive unchanged; naive values come back UTC-qualified.
        aware = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        assert adapter.from_database(adapter.to_database(aware)) == aware
        naive = datetime(2026, 1, 2, 3, 4, 5)
        roundtripped = adapter.from_database(adapter.to_database(naive))
        assert (roundtripped.year, roundtripped.month, roundtripped.day) == (2026, 1, 2)


class TestSQLServerDateTimeOffsetAdapter:
    @pytest.fixture
    def adapter(self):
        return SQLServerDateTimeOffsetAdapter()

    def test_supported_types(self, adapter):
        assert adapter.supported_types == {datetime: ["datetimeoffset"]}

    def test_naive_input_normalized_to_utc(self, adapter):
        result = adapter.to_database(datetime(2026, 8, 9))
        assert result.tzinfo == timezone.utc

    def test_aware_input_offset_preserved(self, adapter):
        from datetime import timedelta

        aware = datetime(2026, 8, 9, tzinfo=timezone(timedelta(hours=5)))
        assert adapter.to_database(aware) is aware

    def test_non_datetime_raises(self, adapter):
        with pytest.raises(TypeError):
            adapter.to_database("2026-08-09")  # strings rejected on the way in

    def test_from_database_accepts_datetime_and_sql_strings(self, adapter):
        value = datetime(2026, 8, 9, 5, 25, 26, tzinfo=timezone.utc)
        assert adapter.from_database(value) is value
        assert adapter.from_database("2026-08-09 05:25:26.5205700").microsecond == 520570

    def test_null_semantics(self, adapter):
        assert adapter.to_database(None) is None
        assert adapter.from_database(None) is None


class TestSQLServerDateAdapter:
    @pytest.fixture
    def adapter(self):
        return SQLServerDateAdapter()

    def test_date_roundtrip(self, adapter):
        value = date(2026, 8, 9)
        assert adapter.to_database(value) is value
        assert adapter.from_database(value) is value

    def test_iso_string_parsed(self, adapter):
        assert adapter.from_database("2026-08-09") == date(2026, 8, 9)

    def test_datetime_truncated_to_date_both_directions(self, adapter):
        # datetime must be checked before date so the time component is cut.
        value = datetime(2026, 8, 9, 5)
        assert adapter.to_database(value) == date(2026, 8, 9)
        assert adapter.to_database(value) is not value
        assert adapter.from_database(value) == date(2026, 8, 9)

    def test_date_only_bidirectional_passthrough(self, adapter):
        value = date(2026, 8, 26)
        assert adapter.to_database(value) is value
        assert adapter.from_database(value) is value

    def test_error_paths(self, adapter):
        with pytest.raises(TypeError):
            adapter.to_database("2026-08-09")
        with pytest.raises(TypeError):
            adapter.from_database(12345)


class TestSQLServerTimeAdapter:
    @pytest.fixture
    def adapter(self):
        return SQLServerTimeAdapter()

    def test_time_roundtrip(self, adapter):
        value = time(5, 25, 26)
        assert adapter.to_database(value) is value
        assert adapter.from_database(value) is value

    def test_datetime_extracts_time_component(self, adapter):
        assert adapter.to_database(datetime(2026, 8, 9, 5, 25, 26)) == time(5, 25, 26)
        assert adapter.from_database(datetime(2026, 8, 9, 5, 25, 26)) == time(5, 25, 26)

    def test_iso_string_parsed(self, adapter):
        assert adapter.from_database("05:25:26") == time(5, 25, 26)

    def test_null_and_error_paths(self, adapter):
        assert adapter.to_database(None) is None
        with pytest.raises(TypeError):
            adapter.to_database(12.5)
        with pytest.raises(TypeError):
            adapter.from_database(object())


class TestSQLServerJSONAdapter:
    @pytest.fixture
    def adapter(self):
        return SQLServerJSONAdapter()

    def test_dict_and_list_serialize_to_json_text(self, adapter):
        assert adapter.to_database({"a": 1}) == '{"a": 1}'
        assert adapter.to_database([1, 2]) == "[1, 2]"

    def test_valid_json_string_passthrough_after_validation(self, adapter):
        raw = '{"a": [1, 2]}'
        assert adapter.to_database(raw) is raw

    def test_invalid_json_string_rejected(self, adapter):
        with pytest.raises(json.JSONDecodeError):
            adapter.to_database("")
        with pytest.raises(json.JSONDecodeError):
            adapter.to_database("{nope}")

    def test_from_database_parses_strings_only(self, adapter):
        assert adapter.from_database('{"a": 1}') == {"a": 1}
        assert adapter.from_database({"a": 1}) == {"a": 1}
        with pytest.raises(TypeError):
            adapter.from_database(15)

    def test_storage_target_is_nvarchar_max(self, adapter):
        # SQL Server has no native JSON type; NVARCHAR(MAX) is the storage.
        assert adapter.supported_types[dict][0] == "nvarchar(max)"

    def test_null_semantics(self, adapter):
        assert adapter.to_database(None) is None
        assert adapter.from_database(None) is None


class TestSQLServerXMLAdapter:
    @pytest.fixture
    def adapter(self):
        return SQLServerXMLAdapter()

    def test_str_and_bytes_both_directions(self, adapter):
        assert adapter.to_database("<a/>") == "<a/>"
        assert adapter.to_database(b"<a/>") == "<a/>"
        assert adapter.from_database("<a/>") == "<a/>"
        assert adapter.from_database(b"<a/>") == "<a/>"

    def test_empty_string_is_valid_xml_document(self, adapter):
        # Empty string passes through unchanged (unlike JSON, no parse step).
        assert adapter.to_database("") == ""
        assert adapter.from_database("") == ""

    def test_unsupported_type_raises(self, adapter):
        with pytest.raises(TypeError):
            adapter.to_database(15)
        with pytest.raises(TypeError):
            adapter.from_database(15)

    def test_scalar_dict_renders_text_node(self, adapter):
        assert adapter.to_database({"a": 1}) == "<root><a>1</a></root>"

    def test_dict_roundtrip_covers_nested_list_and_text_nodes(self, adapter):
        payload = {
            "name": "users",              # text node
            "meta": {"created": "2026"},  # nested element
            "tag": ["a", "b"],            # repeated child elements
        }
        root = ET.fromstring(adapter.to_database(payload))
        assert root.tag == "root"
        assert root.findtext("name") == "users"
        assert root.find("meta").findtext("created") == "2026"
        assert [elem.text for elem in root.findall("tag")] == ["a", "b"]


class TestSQLServerSpatialAdapter:
    @pytest.fixture
    def adapter(self):
        return SQLServerSpatialAdapter()

    def test_point_wkt(self, adapter):
        assert adapter._dict_to_wkt({"type": "Point", "coordinates": [1, 2]}) == "POINT(1 2)"

    def test_linestring_separates_pairs_with_commas(self, adapter):
        assert (
            adapter._dict_to_wkt({"type": "LineString", "coordinates": [[1, 2], [3, 4]]})
            == "LINESTRING(1 2, 3 4)"
        )

    def test_polygon_wkt_single_ring(self, adapter):
        ring = [[[0, 0], [0, 1], [1, 1], [0, 0]]]
        assert (
            adapter._dict_to_wkt({"type": "Polygon", "coordinates": ring})
            == "POLYGON((0 0, 0 1, 1 1, 0 0))"
        )

    def test_unknown_geometry_type_raises(self, adapter):
        with pytest.raises(ValueError, match="Unsupported geometry type"):
            adapter._dict_to_wkt({"type": "MultiSurface"})

    def test_str_bytes_passthrough_on_the_way_in(self, adapter):
        wkt = "POINT(1 2)"
        assert adapter.to_database(wkt) is wkt
        assert adapter.to_database(b"WKB-BLOB") == b"WKB-BLOB"  # bytes kept binary

    def test_from_database_decodes_bytes(self, adapter):
        assert adapter.from_database(b"POINT(1 2)") == "POINT(1 2)"

    def test_null_semantics(self, adapter):
        assert adapter.to_database(None) is None
        assert adapter.from_database(None) is None


class TestSQLServerHierarchyIdAdapter:
    @pytest.fixture
    def adapter(self):
        return SQLServerHierarchyIdAdapter()

    def test_list_rendered_as_slash_path(self, adapter):
        assert adapter.to_database([1, 2, 3]) == "/1/2/3/"
        assert adapter.to_database([]) == "//"  # empty path still fully delimited

    def test_string_passthrough(self, adapter):
        assert adapter.to_database("/1/2/") == "/1/2/"

    def test_from_database_stringifies_anything(self, adapter):
        assert adapter.from_database(5) == "5"
        assert adapter.from_database("/1/") == "/1/"

    def test_null_semantics(self, adapter):
        assert adapter.to_database(None) is None
        assert adapter.from_database(None) is None


class TestSQLServerDecimalAdapter:
    @pytest.fixture
    def adapter(self):
        return SQLServerDecimalAdapter()

    def test_supported_types_include_money(self, adapter):
        types = adapter.supported_types
        assert types[Decimal] == ["decimal", "numeric", "money", "smallmoney"]

    def test_decimal_converted_to_float_for_driver(self, adapter):
        assert isinstance(adapter.to_database(Decimal("1.50")), float)
        assert adapter.to_database(Decimal("1.50")) == 1.5

    def test_numeric_passthrough(self, adapter):
        assert adapter.to_database(7) == 7
        assert adapter.to_database(2.5) == 2.5

    def test_string_rejected_on_the_way_in(self, adapter):
        with pytest.raises(TypeError):
            adapter.to_database("1.50")

    def test_from_database_normalizes_everything_to_decimal(self, adapter):
        assert adapter.from_database(Decimal("1.5")) == Decimal("1.5")
        assert adapter.from_database(15) == Decimal("15")
        assert adapter.from_database(1.5) == Decimal(str(1.5))
        assert adapter.from_database("2.25") == Decimal("2.25")

    def test_null_semantics(self, adapter):
        assert adapter.to_database(None) is None
        assert adapter.from_database(None) is None
