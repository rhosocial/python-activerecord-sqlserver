# src/rhosocial/activerecord/backend/impl/sqlserver/adapters.py
"""
SQL Server type adapters.

This module provides type adapters for converting between Python types
and SQL Server-specific data types.
"""

import json
import uuid
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from datetime import date, datetime, time, timezone
from typing import Any, Dict, List, Optional, Type, Union

from rhosocial.activerecord.backend.adapters import (
    BitString,
    BitStringAdapterBase,
    Geometry,
    GeometryAdapterBase,
    IPAddress,
    IPAddressAdapterBase,
    MacAddress,
    MacAddressAdapterBase,
    Multirange,
    Range,
    RangeAdapterBase,
    Vector,
    VectorAdapterBase,
)


def _parse_sql_datetime(value: str) -> datetime:
    """Parse a SQL Server datetime string into a timezone-aware datetime.

    ODBC/older Python runtimes deliver datetime2 values as strings without a
    ``T`` separator and often carry seven fractional digits (100ns precision),
    e.g. ``'2026-08-09 05:25:26.5205700'``. Python's ``datetime.fromisoformat``
    only accepts three or six fractional digits on Python < 3.11, so normalize
    the string first: restore the ``T`` separator and pad the fractional
    component to exactly six digits.
    """
    normalized = value.replace('Z', '+00:00')
    if 'T' not in normalized:
        head, sep, rest = normalized.partition(' ')
        if sep:
            normalized = f"{head}T{rest}"
    dot_pos = normalized.rfind('.')
    if dot_pos != -1:
        suffix = ''
        frac_end = len(normalized)
        for marker in ('+', '-'):
            idx = normalized.find(marker, dot_pos + 1)
            if idx != -1:
                frac_end = idx
                suffix = normalized[idx:]
                break
        frac = normalized[dot_pos + 1:frac_end]
        frac = frac[:6].ljust(6, '0')
        normalized = f"{normalized[:dot_pos]}.{frac}{suffix}"
    result = datetime.fromisoformat(normalized)
    if result.tzinfo is None:
        return result.replace(tzinfo=timezone.utc)
    return result


def _parse_sql_time(value: str) -> time:
    """Parse a SQL Server ``TIME`` string into a Python ``time``.

    The same wire format as ``datetime2`` applies: no ``T`` separator and
    seven fractional digits (100ns precision), e.g. ``'18:36:06.0000000'``.
    Python's ``time.fromisoformat`` only accepts three or six fractional
    digits on Python < 3.11, so trim and pad the fraction first.
    """
    normalized = value.strip().replace('Z', '+00:00')
    if 'T' in normalized:
        normalized = normalized.partition('T')[2]
    dot_pos = normalized.rfind('.')
    if dot_pos != -1:
        suffix = ''
        frac_end = len(normalized)
        for marker in ('+', '-'):
            idx = normalized.find(marker, dot_pos + 1)
            if idx != -1:
                frac_end = idx
                suffix = normalized[idx:]
                break
        frac = normalized[dot_pos + 1:frac_end][:6].ljust(6, '0')
        normalized = f"{normalized[:dot_pos]}.{frac}{suffix}"
    return time.fromisoformat(normalized)


class TypeAdapter(ABC):
    """Base class for type adapters."""
    
    @property
    @abstractmethod
    def supported_types(self) -> Dict[Type, List[str]]:
        """Return mapping of Python types to SQL Server types."""
        pass
    
    @abstractmethod
    def to_database(self, value: Any, target_type: Type = None, options: Dict = None) -> Any:
        """Convert Python value to database value."""
        pass
    
    @abstractmethod
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None, **kwargs) -> Any:
        """Convert database value to Python value."""
        pass


class SQLServerUUIDAdapter(TypeAdapter):
    """Adapter for UNIQUEIDENTIFIER type.
    
    SQL Server's UNIQUEIDENTIFIER type stores UUIDs.
    They are typically stored as strings in the format:
    XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
    """
    
    @property
    def supported_types(self) -> Dict[Type, List[str]]:
        return {
            uuid.UUID: ["uniqueidentifier"],
            str: ["uniqueidentifier"],
        }
    
    def to_database(self, value: Any, target_type: Type = None, options: Dict = None) -> Any:
        if value is None:
            return None
        
        if isinstance(value, uuid.UUID):
            return str(value)
        
        if isinstance(value, str):
            try:
                uuid.UUID(value)
                return value
            except ValueError:
                raise ValueError(f"Invalid UUID string: {value}")
        
        raise TypeError(f"Expected UUID or str, got {type(value)}")
    
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None, **kwargs) -> uuid.UUID:
        if value is None:
            return None
        
        if isinstance(value, uuid.UUID):
            return value
        
        return uuid.UUID(str(value))


class SQLServerDateTimeAdapter(TypeAdapter):
    """Adapter for DATETIME2 type.
    
    SQL Server DATETIME2 has better precision than DATETIME:
    - DATETIME: 3.33ms accuracy, 1753-01-01 to 9999-12-31
    - DATETIME2: 100ns accuracy, 0001-01-01 to 9999-12-31
    """
    
    @property
    def supported_types(self) -> Dict[Type, List[str]]:
        return {
            datetime: ["datetime2", "datetime", "smalldatetime"],
        }
    
    def to_database(self, value: Any, target_type: Type = None, options: Dict = None) -> Any:
        if value is None:
            return None
        
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        
        raise TypeError(f"Expected datetime, got {type(value)}")
    
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None, **kwargs) -> datetime:
        if value is None:
            return None
        
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        
        if isinstance(value, str):
            return _parse_sql_datetime(value)
        
        raise TypeError(f"Cannot convert {type(value)} to datetime")


class SQLServerDateTimeOffsetAdapter(TypeAdapter):
    """Adapter for DATETIMEOFFSET type.
    
    DATETIMEOFFSET includes timezone information:
    - Stores date, time, and timezone offset
    - Useful for applications spanning multiple timezones
    """
    
    @property
    def supported_types(self) -> Dict[Type, List[str]]:
        return {
            datetime: ["datetimeoffset"],
        }
    
    def to_database(self, value: Any, target_type: Type = None, options: Dict = None) -> Any:
        if value is None:
            return None
        
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value
        
        raise TypeError(f"Expected datetime, got {type(value)}")
    
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None, **kwargs) -> datetime:
        if value is None:
            return None
        
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, str):
            return _parse_sql_datetime(value)
        
        raise TypeError(f"Cannot convert {type(value)} to datetime")


class SQLServerDateAdapter(TypeAdapter):
    """Adapter for DATE type."""
    
    @property
    def supported_types(self) -> Dict[Type, List[str]]:
        return {
            date: ["date"],
        }
    
    def to_database(self, value: Any, target_type: Type = None, options: Dict = None) -> Any:
        if value is None:
            return None
        # datetime is an isinstance of date, so it must be checked first
        # to truncate to the date component.
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        raise TypeError(f"Expected date, got {type(value)}")
    
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None, **kwargs) -> date:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value)
        raise TypeError(f"Cannot convert {type(value)} to date")


class SQLServerTimeAdapter(TypeAdapter):
    """Adapter for TIME type."""
    
    @property
    def supported_types(self) -> Dict[Type, List[str]]:
        return {
            time: ["time"],
        }
    
    def to_database(self, value: Any, target_type: Type = None, options: Dict = None) -> Any:
        if value is None:
            return None
        if isinstance(value, time):
            return value
        if isinstance(value, datetime):
            return value.time()
        raise TypeError(f"Expected time, got {type(value)}")
    
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None, **kwargs) -> time:
        if value is None:
            return None
        if isinstance(value, time):
            return value
        if isinstance(value, datetime):
            return value.time()
        if isinstance(value, str):
            return _parse_sql_time(value)
        raise TypeError(f"Cannot convert {type(value)} to time")


class SQLServerJSONAdapter(TypeAdapter):
    """Adapter for JSON data in SQL Server 2016+.
    
    SQL Server 2016+ supports JSON functions but doesn't have
    a native JSON type. JSON data is stored as NVARCHAR(MAX).
    
    ``default`` / ``object_hook`` are forwarded to ``json.dumps`` / ``json.loads``
    so callers can plug in neutral-type codecs (see
    ``rhosocial.activerecord.backend.adapters.json_codec``) without changing the
    default behaviour: both default to ``None``, which is plain ``json``.
    """
    
    def __init__(self, default=None, object_hook=None):
        self._json_default = default
        self._json_object_hook = object_hook
    
    @property
    def supported_types(self) -> Dict[Type, List[str]]:
        return {
            dict: ["nvarchar(max)", "json"],
            list: ["nvarchar(max)", "json"],
        }
    
    def to_database(self, value: Any, target_type: Type = None, options: Dict = None) -> Any:
        if value is None:
            return None
        
        if isinstance(value, (dict, list)):
            return json.dumps(value, default=self._json_default)
        
        if isinstance(value, str):
            json.loads(value, object_hook=self._json_object_hook)
            return value
        
        raise TypeError(f"Expected dict, list, or str, got {type(value)}")
    
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None, **kwargs) -> Union[dict, list]:
        if value is None:
            return None
        
        if isinstance(value, (dict, list)):
            return value
        
        if isinstance(value, str):
            return json.loads(value, object_hook=self._json_object_hook)
        
        raise TypeError(f"Cannot convert {type(value)} to dict/list")


class SQLServerXMLAdapter(TypeAdapter):
    """Adapter for XML type.
    
    SQL Server has native XML support with:
    - XML type for storage
    - XQuery for querying
    - XML indexes for performance
    """
    
    @property
    def supported_types(self) -> Dict[Type, List[str]]:
        return {
            str: ["xml"],
            bytes: ["xml"],
        }
    
    def to_database(self, value: Any, target_type: Type = None, options: Dict = None) -> Any:
        if value is None:
            return None
        
        if isinstance(value, str):
            return value
        
        if isinstance(value, bytes):
            return value.decode('utf-8')
        
        if isinstance(value, dict):
            return self._dict_to_xml(value)
        
        raise TypeError(f"Expected str, bytes, or dict, got {type(value)}")
    
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None, **kwargs) -> str:
        if value is None:
            return None
        
        if isinstance(value, str):
            return value
        
        if isinstance(value, bytes):
            return value.decode('utf-8')
        
        raise TypeError(f"Cannot convert {type(value)} to XML")
    
    def _dict_to_xml(self, data: dict, root: str = "root") -> str:
        root_elem = ET.Element(root)
        self._build_xml(root_elem, data)
        return ET.tostring(root_elem, encoding='unicode')
    
    def _build_xml(self, parent, data):
        for key, value in data.items():
            if isinstance(value, dict):
                elem = ET.SubElement(parent, key)
                self._build_xml(elem, value)
            elif isinstance(value, list):
                for item in value:
                    elem = ET.SubElement(parent, key)
                    if isinstance(item, dict):
                        self._build_xml(elem, item)
                    else:
                        elem.text = str(item)
            else:
                elem = ET.SubElement(parent, key)
                elem.text = str(value)


class SQLServerGeometryAdapter(GeometryAdapterBase):
    """WKT-text adapter for SQL Server ``GEOMETRY`` / ``GEOGRAPHY`` columns.

    The neutral :class:`~rhosocial.activerecord.backend.adapters.Geometry`
    value is encoded as plain WKT text and decoded from WKT text (or UTF-8
    bytes containing WKT). ``SRID`` is not part of plain WKT, so a decoded
    geometry always has ``srid=None``.

    **Binding limitation**: pyodbc cannot bind a SQL Server CLR spatial value,
    and a ``geometry``/``geography`` column rejects a VARCHAR/NVARCHAR parameter
    ("Implicit conversion from data type varchar to geometry is not allowed").
    SQL Server requires the parameter to be wrapped, e.g.
    ``geometry::STGeomFromText(?, 4326)``. An ORM placeholder alone is therefore
    not sufficient; call :meth:`bind_expression` to build the wrapper expression
    and bind the WKT text produced by :meth:`to_database` to it.
    """

    def __init__(self, srid: Optional[int] = None, geography: bool = False):
        super().__init__()
        if srid is not None and (isinstance(srid, bool) or not isinstance(srid, int)):
            raise TypeError(f"srid must be int, got {type(srid).__name__}")
        if srid is not None and srid < 0:
            raise ValueError(f"srid must be non-negative, got {srid}")
        if not isinstance(geography, bool):
            raise TypeError(f"geography must be bool, got {type(geography).__name__}")
        self._srid = srid if srid is not None else (4326 if geography else 0)
        self._geography = geography
        self.register_type(Geometry, str)
        self.register_type(Geometry, bytes)

    @property
    def srid(self) -> int:
        """SRID used by :meth:`bind_expression`."""
        return self._srid

    @property
    def kind(self) -> str:
        """SQL Server spatial type name: ``geometry`` or ``geography``."""
        return "geography" if self._geography else "geometry"

    def bind_expression(self, placeholder: str = "?") -> str:
        """Return the SQL expression that wraps a WKT parameter.

        Example: ``geometry::STGeomFromText(?, 4326)``. The WKT text from
        :meth:`to_database` is bound to ``placeholder``.
        """
        return f"{self.kind}::STGeomFromText({placeholder}, {self._srid})"

    def _encode(self, geometry: Geometry, target_type: Type, options: Dict = None) -> Any:
        wkt = geometry.to_wkt()
        if target_type is bytes:
            return wkt.encode("utf-8")
        return wkt

    def _decode(self, value: Any, options: Dict = None) -> Geometry:
        if isinstance(value, (bytes, bytearray)):
            try:
                value = bytes(value).decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(
                    "binary spatial values are not supported; use WKT text"
                ) from exc
        wkt = self._require_text(value)
        return Geometry.from_wkt(wkt)


class SQLServerVectorAdapter(VectorAdapterBase):
    """JSON-text adapter for SQL Server vector columns.

    SQL Server before version 2025 has no native ``VECTOR`` type, so a vector
    is carried as JSON text in ``NVARCHAR``/``VARCHAR`` (``NVARCHAR(MAX)`` when
    the dimension is not fixed). The adapter encodes the neutral
    :class:`~rhosocial.activerecord.backend.adapters.Vector` as a JSON array and
    decodes JSON text, UTF-8 bytes, or an already-decoded list/tuple. Non-finite
    components use the neutral JSON spellings (``"NaN"``, ``"Infinity"``,
    ``"-Infinity"``). If a deployment does provide a native vector type, this
    text adapter is still the neutral representation; a native adapter would be
    a separate implementation.
    """

    def __init__(self):
        super().__init__()
        self.register_type(Vector, str)
        self.register_type(Vector, bytes)

    def _encode(self, vector: Vector, target_type: Type, options: Dict = None) -> Any:
        text = json.dumps(vector.to_json_value(), ensure_ascii=False)
        if target_type is bytes:
            return text.encode("utf-8")
        return text

    def _decode(self, value: Any, options: Dict = None) -> Vector:
        if isinstance(value, (list, tuple)):
            return Vector.from_json_value(value)
        if isinstance(value, (bytes, bytearray)):
            value = bytes(value).decode("utf-8")
        if not isinstance(value, str):
            raise TypeError(f"expected JSON array text or a list, got {type(value).__name__}")
        return Vector.from_json_value(json.loads(value))


class SQLServerBitStringAdapter(BitStringAdapterBase):
    """Adapter for neutral bit strings carried as ``VARBINARY`` or text.

    SQL Server's own ``BIT`` type is a boolean and is not a bit string; bit
    strings are carried in ``BINARY``/``VARBINARY`` columns or in text columns
    (``VARCHAR``/``NVARCHAR``). Raw bytes can only represent whole bytes, so a
    bit string whose ``bit_length`` is not a multiple of 8 loses its exact
    length in the binary representation. The text target keeps the exact
    length: :meth:`BitString.to_bits` renders the significant bits (including
    leading zeros), and :meth:`_decode` accepts that form unchanged.
    """

    def __init__(self):
        super().__init__()
        self.register_type(BitString, str)
        self.register_type(BitString, bytes)

    def _encode(self, bits: BitString, target_type: Type, options: Dict = None) -> Any:
        if target_type is str:
            return bits.to_bits()
        return bits.data

    def _decode(self, value: Any, options: Dict = None) -> BitString:
        if isinstance(value, (bytes, bytearray)):
            return BitString.from_bytes(bytes(value))
        if isinstance(value, str):
            return BitString.from_bits(value)
        raise TypeError(f"expected bytes or a bit-string text, got {type(value).__name__}")


class SQLServerRangeAdapter(RangeAdapterBase):
    """JSON-text adapter for neutral ranges stored in text columns.

    SQL Server has no range/multirange type. Ranges are stored as JSON text
    (``NVARCHAR``/``VARCHAR``) using the neutral canonical representation from
    :meth:`Range.to_json_value` / :meth:`Multirange.to_json_value`.
    """

    def __init__(self):
        super().__init__()
        self.register_type(Range, str)
        self.register_type(Multirange, str)
        self.register_type(Range, bytes)
        self.register_type(Multirange, bytes)

    def _encode(self, value: Any, target_type: Type, options: Dict = None) -> Any:
        text = json.dumps(value.to_json_value(), ensure_ascii=False)
        if target_type is bytes:
            return text.encode("utf-8")
        return text

    def _decode(self, value: Any, target_type: Type, options: Dict = None) -> Any:
        if isinstance(value, (bytes, bytearray)):
            value = bytes(value).decode("utf-8")
        if not isinstance(value, str):
            raise TypeError(f"expected JSON text, got {type(value).__name__}")
        payload = json.loads(value)
        if target_type is Multirange:
            return Multirange.from_json_value(payload)
        if target_type is Range:
            return Range.from_json_value(payload)
        if isinstance(payload, list):
            return Multirange.from_json_value(payload)
        return Range.from_json_value(payload)


class SQLServerMacAddressAdapter(MacAddressAdapterBase):
    """Canonical-text adapter for MAC addresses.

    SQL Server has no MAC address type; the value is stored in ``VARCHAR``/
    ``CHAR`` as the canonical lowercase colon-separated text
    (``01:23:45:67:89:ab``). ``BINARY``/``VARBINARY`` columns are also accepted
    when the raw value is exactly 6 or 8 octets.
    """

    def __init__(self):
        super().__init__()
        self.register_type(MacAddress, str)
        self.register_type(MacAddress, bytes)

    def _encode(self, mac: MacAddress, target_type: Type, options: Dict = None) -> Any:
        if target_type is bytes:
            return mac.octets
        return str(mac)

    def _decode(self, value: Any, options: Dict = None) -> MacAddress:
        if isinstance(value, bytearray):
            value = bytes(value)
        if isinstance(value, bytes) and len(value) not in (6, 8):
            try:
                value = value.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("MAC address bytes must be 6 or 8 octets") from exc
        return MacAddress.parse(value)


class SQLServerIPAddressAdapter(IPAddressAdapterBase):
    """Canonical-text adapter for IP addresses.

    SQL Server has no IP address type; the value is stored in ``VARCHAR``/``NVARCHAR``
    as the canonical compressed text (``192.0.2.1`` / ``2001:db8::1``), which is
    what the neutral :class:`IPAddress` renders and parses. The base class supplies
    the three conversion methods; only the two hooks below are backend-specific.
    """

    def __init__(self):
        super().__init__()
        self.register_type(IPAddress, str)

    def _encode(
        self, ip_addr: IPAddress, target_type: Type, options: Dict = None
    ) -> str:
        return str(ip_addr)

    def _decode(self, value: Any, options: Dict = None) -> IPAddress:
        return IPAddress.parse(value)


class SQLServerHierarchyIdAdapter(TypeAdapter):
    """Adapter for HIERARCHYID type.
    
    HIERARCHYID is a CLR type in SQL Server for representing
    hierarchical data (organizational charts, file systems, etc.).
    """
    
    @property
    def supported_types(self) -> Dict[Type, List[str]]:
        return {
            str: ["hierarchyid"],
            list: ["hierarchyid"],
        }
    
    def to_database(self, value: Any, target_type: Type = None, options: Dict = None) -> Any:
        if value is None:
            return None
        
        if isinstance(value, str):
            return value
        
        if isinstance(value, list):
            return "/" + "/".join(str(x) for x in value) + "/"
        
        raise TypeError(f"Expected str or list, got {type(value)}")
    
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None, **kwargs) -> str:
        if value is None:
            return None
        
        return str(value)


class SQLServerDecimalAdapter(TypeAdapter):
    """Adapter for DECIMAL/NUMERIC type."""
    
    @property
    def supported_types(self) -> Dict[Type, List[str]]:
        from decimal import Decimal
        return {
            Decimal: ["decimal", "numeric", "money", "smallmoney"],
            float: ["decimal", "numeric"],
            int: ["decimal", "numeric"],
        }
    
    def to_database(self, value: Any, target_type: Type = None, options: Dict = None) -> Any:
        if value is None:
            return None
        
        from decimal import Decimal
        if isinstance(value, Decimal):
            return float(value)
        
        if isinstance(value, (int, float)):
            return value
        
        raise TypeError(f"Expected Decimal, int, or float, got {type(value)}")
    
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None, **kwargs):
        from decimal import Decimal
        
        if value is None:
            return None
        
        if isinstance(value, Decimal):
            return value
        
        if isinstance(value, (int, float, str)):
            return Decimal(str(value))
        
        raise TypeError(f"Cannot convert {type(value)} to Decimal")
