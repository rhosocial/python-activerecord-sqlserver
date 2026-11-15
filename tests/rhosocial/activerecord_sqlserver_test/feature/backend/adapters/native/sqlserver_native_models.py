# tests/rhosocial/activerecord_sqlserver_test/feature/backend/adapters/native/sqlserver_native_models.py
"""Models for the SQL Server native-type tests.

Each model maps one Python type onto one SQL Server column family. Where the
backend's default suggestion is not the adapter under test, the field pins it
with ``UseAdapter``; otherwise the model relies on the merged suggestion table,
so the test also proves that wiring.

The tables are created from ``schema/native_types.sql``; these models never
render DDL, and ``pk_auto_generated`` is False because every primary key in
that schema is a caller-supplied ``INT``.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional

from pydantic import ConfigDict

from rhosocial.activerecord.backend.adapters.geometry import Geometry
from rhosocial.activerecord.backend.impl.sqlserver.adapters import (
    SQLServerDateTimeOffsetAdapter,
    SQLServerGeometryAdapter,
    SQLServerHierarchyIdAdapter,
    SQLServerXMLAdapter,
)
from rhosocial.activerecord.base.fields import UseAdapter
from rhosocial.activerecord.model import ActiveRecord


class _NativeRow(ActiveRecord):
    """Shared configuration for the one-table-per-family models."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def pk_auto_generated(cls) -> bool:
        return False

    id: Optional[int] = None


class MoneyRow(_NativeRow):
    """``native_money``: MONEY and SMALLMONEY, both reached through Decimal."""

    @classmethod
    def table_name(cls) -> str:
        return "native_money"

    amount: Optional[Decimal] = None
    small: Optional[Decimal] = None


class DateTimeOffsetRow(_NativeRow):
    """``native_datetimeoffset``: the offset-carrying datetime."""

    @classmethod
    def table_name(cls) -> str:
        return "native_datetimeoffset"

    dto: Annotated[
        Optional[datetime], UseAdapter(SQLServerDateTimeOffsetAdapter(), datetime)
    ] = None


class UniqueIdentifierRow(_NativeRow):
    """``native_uniqueidentifier``: the native GUID column."""

    @classmethod
    def table_name(cls) -> str:
        return "native_uniqueidentifier"

    uid: Optional[uuid.UUID] = None


class XmlRow(_NativeRow):
    """``native_xml``: the native XML column, carried as text."""

    @classmethod
    def table_name(cls) -> str:
        return "native_xml"

    doc: Annotated[Optional[str], UseAdapter(SQLServerXMLAdapter(), str)] = None


class HierarchyIdRow(_NativeRow):
    """``native_hierarchyid``: the materialised-path column."""

    @classmethod
    def table_name(cls) -> str:
        return "native_hierarchyid"

    hid: Annotated[Optional[str], UseAdapter(SQLServerHierarchyIdAdapter(), str)] = None


class BitRow(_NativeRow):
    """``native_bit``: SQL Server's native boolean, not a bit string."""

    @classmethod
    def table_name(cls) -> str:
        return "native_bit"

    flag: Optional[bool] = None


class RowVersionRow(_NativeRow):
    """``native_rowversion``: an 8-byte token the server maintains.

    ``rv`` is declared generated so the INSERT/UPDATE column lists skip it --
    SQL Server refuses an explicit value for it. The declaration is set here
    rather than derived from a model-rendered DDL because the table comes from
    ``schema/native_types.sql``.
    """

    __table_generated_columns__ = ("rv",)

    @classmethod
    def table_name(cls) -> str:
        return "native_rowversion"

    rv: Optional[bytes] = None
    note: Optional[str] = None


class TimestampRow(RowVersionRow):
    """``native_timestamp``: the synonym of ROWVERSION."""

    @classmethod
    def table_name(cls) -> str:
        return "native_timestamp"


class JsonRow(_NativeRow):
    """``native_json``: JSON kept as text, there is no JSON type."""

    @classmethod
    def table_name(cls) -> str:
        return "native_json"

    payload: Optional[dict] = None


class SpatialRow(_NativeRow):
    """``native_spatial``: the planar geometry and the earth-based geography."""

    @classmethod
    def table_name(cls) -> str:
        return "native_spatial"

    geom: Optional[Geometry] = None
    geog: Annotated[Optional[Geometry], UseAdapter(SQLServerGeometryAdapter(geography=True), str)] = None


class WktTextRow(_NativeRow):
    """``native_wkt_text``: WKT in an ordinary column, the portable carrier."""

    @classmethod
    def table_name(cls) -> str:
        return "native_wkt_text"

    shape: Annotated[Optional[Geometry], UseAdapter(SQLServerGeometryAdapter(), str)] = None
