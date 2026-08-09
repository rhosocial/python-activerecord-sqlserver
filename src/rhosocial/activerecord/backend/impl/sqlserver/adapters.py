# src/rhosocial/activerecord/backend/impl/sqlserver/adapters.py
"""
SQL Server type adapters.

This module provides type adapters for converting between Python types
and SQL Server-specific data types.
"""

import json
import uuid
from abc import ABC, abstractmethod
from datetime import date, datetime, time, timezone
from typing import Any, Dict, List, Type, Union


def _parse_sql_datetime(value: str) -> datetime:
    """Parse a SQL Server datetime string into a timezone-aware datetime.

    ODBC/older Python runtimes deliver datetime2 values as strings without a
    ``T`` separator and often carry seven fractional digits (100ns precision),
    e.g. ``'2026-08-09 05:25:26.5205700'``. Python's ``datetime.fromisoformat``
    rejects values with more than six fractional digits on Python < 3.13, so
    normalize the string first: normalize the separator, then drop any
    fractional component beyond six digits.
    """
    normalized = value.replace('Z', '+00:00')
    if 'T' not in normalized:
        head, sep, rest = normalized.partition(' ')
        if sep:
            normalized = f"{head}T{rest}"
    if '.' in normalized:
        head, sep, frac = normalized.rpartition('.')
        frac = frac.rstrip('0')[:6]
        if frac:
            normalized = f"{head}.{frac}"
    result = datetime.fromisoformat(normalized)
    if result.tzinfo is None:
        return result.replace(tzinfo=timezone.utc)
    return result


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
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None) -> Any:
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
    
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None) -> uuid.UUID:
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
    
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None) -> datetime:
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
    
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None) -> datetime:
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
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        raise TypeError(f"Expected date, got {type(value)}")
    
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None) -> date:
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
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
    
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None) -> time:
        if value is None:
            return None
        if isinstance(value, time):
            return value
        if isinstance(value, datetime):
            return value.time()
        if isinstance(value, str):
            return time.fromisoformat(value)
        raise TypeError(f"Cannot convert {type(value)} to time")


class SQLServerJSONAdapter(TypeAdapter):
    """Adapter for JSON data in SQL Server 2016+.
    
    SQL Server 2016+ supports JSON functions but doesn't have
    a native JSON type. JSON data is stored as NVARCHAR(MAX).
    """
    
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
            return json.dumps(value)
        
        if isinstance(value, str):
            json.loads(value)
            return value
        
        raise TypeError(f"Expected dict, list, or str, got {type(value)}")
    
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None) -> Union[dict, list]:
        if value is None:
            return None
        
        if isinstance(value, (dict, list)):
            return value
        
        if isinstance(value, str):
            return json.loads(value)
        
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
    
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None) -> str:
        if value is None:
            return None
        
        if isinstance(value, str):
            return value
        
        if isinstance(value, bytes):
            return value.decode('utf-8')
        
        raise TypeError(f"Cannot convert {type(value)} to XML")
    
    def _dict_to_xml(self, data: dict, root: str = "root") -> str:
        import xml.etree.ElementTree as ET
        
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


class SQLServerSpatialAdapter(TypeAdapter):
    """Adapter for GEOGRAPHY and GEOMETRY types.
    
    SQL Server supports spatial data through:
    - geography: For earth-based coordinates (lat/lon)
    - geometry: For planar coordinates
    
    Uses Well-Known Text (WKT) or Well-Known Binary (WKB) format.
    """
    
    @property
    def supported_types(self) -> Dict[Type, List[str]]:
        return {
            str: ["geography", "geometry"],
            bytes: ["geography", "geometry"],
        }
    
    def to_database(self, value: Any, target_type: Type = None, options: Dict = None) -> Any:
        if value is None:
            return None
        
        if isinstance(value, str):
            return value
        
        if isinstance(value, bytes):
            return value
        
        if isinstance(value, dict):
            return self._dict_to_wkt(value)
        
        raise TypeError(f"Expected str, bytes, or dict, got {type(value)}")
    
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None) -> str:
        if value is None:
            return None
        
        if isinstance(value, str):
            return value
        
        if isinstance(value, bytes):
            return value.decode('utf-8')
        
        raise TypeError(f"Cannot convert {type(value)} to spatial type")
    
    def _dict_to_wkt(self, data: dict) -> str:
        geom_type = data.get('type', 'Point')
        
        if geom_type == 'Point':
            coords = data.get('coordinates', [0, 0])
            return f"POINT({coords[0]} {coords[1]})"
        
        elif geom_type == 'LineString':
            coords = data.get('coordinates', [])
            points = " ".join(f"{c[0]} {c[1]}" for c in coords)
            return f"LINESTRING({points})"
        
        elif geom_type == 'Polygon':
            coords = data.get('coordinates', [[]])
            rings = []
            for ring in coords:
                points = " ".join(f"{c[0]} {c[1]}" for c in ring)
                rings.append(f"({points})")
            return f"POLYGON({','.join(rings)})"
        
        raise ValueError(f"Unsupported geometry type: {geom_type}")


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
    
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None) -> str:
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
    
    def from_database(self, value: Any, target_type: Type = None, options: Dict = None):
        from decimal import Decimal
        
        if value is None:
            return None
        
        if isinstance(value, Decimal):
            return value
        
        if isinstance(value, (int, float, str)):
            return Decimal(str(value))
        
        raise TypeError(f"Cannot convert {type(value)} to Decimal")
