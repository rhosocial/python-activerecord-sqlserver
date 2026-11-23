# tests/rhosocial/activerecord_sqlserver_test/feature/backend/adapters/test_neutral_adapters.py
"""DB-free coverage for SQL Server's neutral-type adapters.

These adapters bridge the core neutral types (geometry, vector, bit string,
range/multirange, MAC address, IP address) to SQL Server column representations. No live
server is involved: encoding/decoding is pure Python, and the backend inventory
is built from the adapter registry.

SQL Server spatial limitation: a ``geometry``/``geography`` column rejects a
plain VARCHAR parameter, so WKT text must be wrapped as
``geometry::STGeomFromText(?, srid)``. ``SQLServerGeometryAdapter.bind_expression``
returns that wrapper; the tests pin both the WKT encoding and the wrapper.
"""

import json
from datetime import datetime

import pytest
from rhosocial.activerecord.backend.adapters import (
    BitString,
    Geometry,
    IPAddress,
    LineString,
    MacAddress,
    Multirange,
    Point,
    Range,
    Vector,
)
from rhosocial.activerecord.backend.errors import TypeConversionError

from rhosocial.activerecord.backend.impl.sqlserver.adapters import (
    SQLServerBitStringAdapter,
    SQLServerGeometryAdapter,
    SQLServerIPAddressAdapter,
    SQLServerMacAddressAdapter,
    SQLServerRangeAdapter,
    SQLServerVectorAdapter,
)


@pytest.fixture
def geometry_adapter():
    return SQLServerGeometryAdapter()


@pytest.fixture
def vector_adapter():
    return SQLServerVectorAdapter()


@pytest.fixture
def bitstring_adapter():
    return SQLServerBitStringAdapter()


@pytest.fixture
def range_adapter():
    return SQLServerRangeAdapter()


@pytest.fixture
def mac_adapter():
    return SQLServerMacAddressAdapter()


@pytest.fixture
def ip_adapter():
    return SQLServerIPAddressAdapter()


class TestGeometryAdapter:
    def test_encode_is_wkt_text(self, geometry_adapter):
        stored = geometry_adapter.to_database(Point(1, 2), str)
        assert isinstance(stored, str)
        assert stored.startswith("POINT")

    def test_round_trip_point(self, geometry_adapter):
        result = geometry_adapter.from_database(
            geometry_adapter.to_database(Point(1, 2), str), Geometry
        )
        assert result == Point(1, 2)

    def test_round_trip_linestring(self, geometry_adapter):
        original = LineString(((0, 0), (1, 1), (2, 0)))
        result = geometry_adapter.from_database(
            geometry_adapter.to_database(original, str), Geometry
        )
        assert result == original

    def test_decode_accepts_utf8_wkt_bytes(self, geometry_adapter):
        result = geometry_adapter.from_database(b"POINT (3 4)", Geometry)
        assert result == Point(3, 4)

    def test_decode_keeps_srid_from_prefix(self, geometry_adapter):
        result = geometry_adapter.from_database("SRID=4326;POINT (1 2)", Geometry)
        assert result == Point(1, 2, srid=4326)

    def test_encoded_bytes_target(self, geometry_adapter):
        stored = geometry_adapter.to_database(Point(1, 2), bytes)
        assert isinstance(stored, bytes)

    def test_bind_expression_defaults_to_geometry_srid_zero(self, geometry_adapter):
        assert geometry_adapter.bind_expression() == "geometry::STGeomFromText(?, 0)"

    def test_bind_expression_uses_configured_srid(self):
        adapter = SQLServerGeometryAdapter(srid=4326)
        assert adapter.bind_expression(":p") == "geometry::STGeomFromText(:p, 4326)"

    def test_bind_expression_geography_defaults_to_4326(self):
        adapter = SQLServerGeometryAdapter(geography=True)
        assert adapter.kind == "geography"
        assert adapter.srid == 4326
        assert adapter.bind_expression() == "geography::STGeomFromText(?, 4326)"

    def test_negative_srid_rejected(self):
        with pytest.raises(ValueError):
            SQLServerGeometryAdapter(srid=-1)

    def test_invalid_srid_type_rejected(self):
        with pytest.raises(TypeError):
            SQLServerGeometryAdapter(srid="4326")

    def test_binary_geometry_value_is_rejected(self, geometry_adapter):
        with pytest.raises(TypeConversionError):
            geometry_adapter.from_database(b"\x00\x01\x02", Geometry)

    def test_invalid_wkt_wrapped(self, geometry_adapter):
        with pytest.raises(TypeConversionError):
            geometry_adapter.from_database("NOT A GEOMETRY", Geometry)

    def test_unsupported_input_wrapped(self, geometry_adapter):
        with pytest.raises(TypeConversionError):
            geometry_adapter.to_database(object(), str)

    def test_invalid_decode_type_wrapped(self, geometry_adapter):
        with pytest.raises(TypeConversionError):
            geometry_adapter.from_database(123, Geometry)


class TestVectorAdapter:
    def test_encode_is_json_array(self, vector_adapter):
        stored = vector_adapter.to_database(Vector((1.5, 2)), str)
        assert json.loads(stored) == [1.5, 2]

    def test_round_trip(self, vector_adapter):
        original = Vector((1.5, -2.0, 3.25))
        result = vector_adapter.from_database(vector_adapter.to_database(original, str), Vector)
        assert result == original

    def test_round_trip_non_finite(self, vector_adapter):
        original = Vector((1.0, float("inf")), allow_non_finite=True)
        result = vector_adapter.from_database(vector_adapter.to_database(original, str), Vector)
        assert result == original

    def test_decode_accepts_bytes_and_list(self, vector_adapter):
        assert vector_adapter.from_database(b"[1, 2]", Vector) == Vector((1, 2))
        assert vector_adapter.from_database([3, 4], Vector) == Vector((3, 4))

    def test_bytes_target(self, vector_adapter):
        stored = vector_adapter.to_database(Vector((1, 2)), bytes)
        assert isinstance(stored, bytes)
        assert json.loads(stored.decode("utf-8")) == [1, 2]

    def test_invalid_json_wrapped(self, vector_adapter):
        with pytest.raises(TypeConversionError):
            vector_adapter.from_database("{nope}", Vector)

    def test_invalid_decode_type_wrapped(self, vector_adapter):
        with pytest.raises(TypeConversionError):
            vector_adapter.from_database(42, Vector)


class TestBitStringAdapter:
    def test_encode_is_varbinary_bytes(self, bitstring_adapter):
        stored = bitstring_adapter.to_database(BitString.from_bits("10101010"), bytes)
        assert stored == b"\xaa"

    def test_encode_is_bit_text_for_text_target(self, bitstring_adapter):
        stored = bitstring_adapter.to_database(BitString.from_bits("10101010"), str)
        assert stored == "10101010"

    def test_text_target_preserves_non_byte_aligned_length(self, bitstring_adapter):
        """A text carrier keeps the exact bit length binary carriers lose."""
        original = BitString.from_bits("10101")
        stored = bitstring_adapter.to_database(original, str)
        assert stored == "10101"
        assert bitstring_adapter.from_database(stored, BitString) == original

    def test_round_trip_whole_bytes(self, bitstring_adapter):
        original = BitString.from_bits("1010101011110000")
        result = bitstring_adapter.from_database(
            bitstring_adapter.to_database(original, bytes), BitString
        )
        assert result == original

    def test_decode_accepts_bit_text(self, bitstring_adapter):
        assert bitstring_adapter.from_database("10101", BitString).to_bits() == "10101"

    def test_decode_preserves_leading_zero_bytes(self, bitstring_adapter):
        # bit_length covers the whole byte string, so a leading zero byte
        # remains part of the 16-bit value.
        assert bitstring_adapter.from_database(b"\x00\x0f", BitString) == BitString.from_bytes(
            b"\x00\x0f"
        )

    def test_non_byte_aligned_length_is_not_preserved(self, bitstring_adapter):
        # Binary columns carry whole bytes; the exact bit length needs metadata.
        stored = bitstring_adapter.to_database(BitString.from_bits("10101"), bytes)
        decoded = bitstring_adapter.from_database(stored, BitString)
        assert decoded.to_bits() == "10101000"
        assert decoded.bit_length == 8

    def test_invalid_decode_type_wrapped(self, bitstring_adapter):
        with pytest.raises(TypeConversionError):
            bitstring_adapter.from_database(7, BitString)


class TestRangeAdapter:
    def test_range_round_trip(self, range_adapter):
        original = Range(1, 5, "[)")
        stored = range_adapter.to_database(original, str)
        assert json.loads(stored) == original.to_json_value()
        assert range_adapter.from_database(stored, Range) == original

    def test_empty_range_round_trip(self, range_adapter):
        original = Range(empty=True)
        assert (
            range_adapter.from_database(range_adapter.to_database(original, str), Range) == original
        )

    def test_datetime_range_round_trip(self, range_adapter):
        original = Range(datetime(2024, 1, 1, 12, 0), datetime(2024, 6, 1, 12, 0), "[)")
        assert (
            range_adapter.from_database(range_adapter.to_database(original, str), Range) == original
        )

    def test_multirange_round_trip_is_canonical(self, range_adapter):
        original = Multirange((Range(1, 5), Range(5, 9)))
        result = range_adapter.from_database(range_adapter.to_database(original, str), Multirange)
        assert result == original
        assert len(result.ranges) == 1

    def test_decode_infers_type_without_explicit_target(self, range_adapter):
        assert isinstance(
            range_adapter.from_database(
                '{"lower": 1, "upper": 2, "bounds": "[)", "empty": false, "element_type": "int"}',
                dict,
            ),
            Range,
        )
        assert isinstance(range_adapter.from_database("[]", dict), Multirange)

    def test_bytes_target(self, range_adapter):
        stored = range_adapter.to_database(Range(1, 5), bytes)
        assert isinstance(stored, bytes)

    def test_mismatched_target_wrapped(self, range_adapter):
        text = range_adapter.to_database(Range(1, 5), str)
        with pytest.raises(TypeConversionError):
            range_adapter.from_database(text, Multirange)

    def test_invalid_json_wrapped(self, range_adapter):
        with pytest.raises(TypeConversionError):
            range_adapter.from_database("{nope}", Range)


class TestMacAddressAdapter:
    def test_encode_is_canonical_text(self, mac_adapter):
        mac = MacAddress.parse("01:23:45:67:89:AB")
        assert mac_adapter.to_database(mac, str) == "01:23:45:67:89:ab"

    def test_round_trip(self, mac_adapter):
        original = MacAddress.parse("08002B010203")
        result = mac_adapter.from_database(mac_adapter.to_database(original, str), MacAddress)
        assert result == original

    def test_decode_accepts_six_raw_octets(self, mac_adapter):
        assert mac_adapter.from_database(
            b"\x01\x23\x45\x67\x89\xab", MacAddress
        ) == MacAddress.parse("01:23:45:67:89:ab")

    def test_bytes_target(self, mac_adapter):
        mac = MacAddress.parse("01:23:45:67:89:ab")
        assert mac_adapter.to_database(mac, bytes) == mac.octets

    def test_invalid_text_wrapped(self, mac_adapter):
        with pytest.raises(TypeConversionError):
            mac_adapter.from_database("not-a-mac", MacAddress)

    def test_invalid_binary_length_wrapped(self, mac_adapter):
        with pytest.raises(TypeConversionError):
            mac_adapter.from_database(b"\x01\x02\x03\x04", MacAddress)


class TestIPAddressAdapter:
    @pytest.mark.parametrize(
        "text", ["192.0.2.1", "2001:db8::1", "::1", "0.0.0.0"]
    )
    def test_encode_is_canonical_text(self, ip_adapter, text):
        ip = IPAddress.parse(text)
        assert ip_adapter.to_database(ip, str) == str(ip)

    @pytest.mark.parametrize(
        "text", ["192.0.2.1", "2001:db8::1"]
    )
    def test_round_trip(self, ip_adapter, text):
        original = IPAddress.parse(text)
        result = ip_adapter.from_database(ip_adapter.to_database(original, str), IPAddress)
        assert result == original

    def test_decode_accepts_a_stdlib_object(self, ip_adapter):
        import ipaddress

        std = ipaddress.ip_address("192.0.2.1")
        assert ip_adapter.from_database(std, IPAddress) == IPAddress.parse("192.0.2.1")

    def test_invalid_text_wrapped(self, ip_adapter):
        with pytest.raises(TypeConversionError):
            ip_adapter.from_database("not-an-ip", IPAddress)

    def test_non_text_wrapped(self, ip_adapter):
        with pytest.raises(TypeConversionError):
            ip_adapter.from_database(b"192.0.2.1", IPAddress)


@pytest.fixture(scope="module")
def backend():
    from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
    from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig

    config = SQLServerConnectionConfig(
        host="127.0.0.1",
        port=11433,
        database="master",
        username="sa",
        password="not-used-offline",
    )
    return SQLServerBackend(connection_config=config)


class TestAdapterInventory:
    """The backend's plain adapter inventory includes the neutral adapters."""

    @pytest.mark.parametrize(
        "adapter_class",
        [
            SQLServerGeometryAdapter,
            SQLServerVectorAdapter,
            SQLServerBitStringAdapter,
            SQLServerRangeAdapter,
            SQLServerMacAddressAdapter,
            SQLServerIPAddressAdapter,
        ],
    )
    def test_neutral_adapter_is_registered(self, backend, adapter_class):
        assert adapter_class in {type(adapter) for adapter in backend.get_type_adapters()}
