# SQL Server Field Types

The core library defines the portable type classes. This backend adds SQL
Server's own types where no portable spelling exists, and supplies adapters for
values the driver does not return as a native Python type. This page lists the
backend-specific side only; see the core docs for how `UseSqlType` and field
declarations work in general.

## Why backend-specific types exist

Core's string types deliberately have no character-set dimension. SQL Server's
national-character types therefore get their own classes rather than being
treated as aliases: `NVARCHAR` stores UCS-2/UTF-16, while `VARCHAR` follows the
database collation's code page. They are not interchangeable.

The SQL Server type classes live in
`rhosocial.activerecord.backend.impl.sqlserver.expression.types` and carry a
reserved `KIND_RESERVED = ("SQLServer",)` marker.

| Backend type class | SQL type | Notes |
|--------------------|----------|-------|
| `SQLServerNVarCharType` | `NVARCHAR(n)` | variable-length Unicode string |
| `SQLServerNCharType` | `NCHAR(n)` | fixed-length, blank-padded Unicode string |
| `SQLServerNVarCharMaxType` | `NVARCHAR(MAX)` | unbounded Unicode string (lifts the 8000-byte cap) |
| `SQLServerVarBinaryType` | `VARBINARY(n)` | variable-length binary |
| `SQLServerVarBinaryMaxType` | `VARBINARY(MAX)` | unbounded binary |
| `SQLServerImageType` | `IMAGE` | legacy large binary (deprecated by SQL Server) |
| `SQLServerXmlType` | `XML` | native XML, carried as text |
| `SQLServerTinyIntType` | `TINYINT` | 0–255 integer |
| `SQLServerBitType` | `BIT` | SQL Server's boolean; note it is a boolean, not a bit string |
| `SQLServerUniqueIdentifierType` | `UNIQUEIDENTIFIER` | native GUID, maps to `uuid.UUID` |

Pin a type on a field with the core `UseSqlType` annotation:

```python
from typing import Annotated, ClassVar
from rhosocial.activerecord.base import FieldProxy, UseSqlType
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.backend.impl.sqlserver.expression.types import SQLServerNVarCharType

class Article(ActiveRecord):
    c: ClassVar[FieldProxy] = FieldProxy()
    title: Annotated[str, UseSqlType(SQLServerNVarCharType(length=200))]

    @classmethod
    def table_name(cls) -> str:
        return "articles"
```

## Native types reached through adapters

Some SQL Server column families need an adapter to convert between the driver's
value and a Python type. The backend ships these in
`rhosocial.activerecord.backend.impl.sqlserver.adapters`:

| SQL Server type | Python carrier | Adapter |
|-----------------|----------------|---------|
| `MONEY`, `SMALLMONEY` | `decimal.Decimal` | default suggestion (never `float`) |
| `DATETIMEOFFSET` | `datetime.datetime` | `SQLServerDateTimeOffsetAdapter` |
| `XML` | `str` | `SQLServerXMLAdapter` |
| `HIERARCHYID` | `str` | `SQLServerHierarchyIdAdapter` |
| `GEOMETRY`, `GEOGRAPHY` | `Geometry` | `SQLServerGeometryAdapter` (`geography=True` for geography) |
| `UNIQUEIDENTIFIER` | `uuid.UUID` | default suggestion |
| `ROWVERSION` / `TIMESTAMP` | `bytes` | generated column excluded from DML |
| `JSON` | stored as `NVARCHAR(MAX)` text, carried as `dict` | default suggestion — SQL Server has no JSON type |

An adapter is pinned with `UseAdapter`:

```python
import uuid
from datetime import datetime
from typing import Annotated, ClassVar, Optional

from rhosocial.activerecord.base import FieldProxy, UseAdapter
from rhosocial.activerecord.backend.impl.sqlserver.adapters import (
    SQLServerDateTimeOffsetAdapter,
    SQLServerXMLAdapter,
)
from rhosocial.activerecord.model import ActiveRecord

class Event(ActiveRecord):
    c: ClassVar[FieldProxy] = FieldProxy()
    dto: Annotated[Optional[datetime], UseAdapter(SQLServerDateTimeOffsetAdapter(), datetime)]
    doc: Annotated[Optional[str], UseAdapter(SQLServerXMLAdapter(), str)]
    uid: Optional[uuid.UUID] = None

    @classmethod
    def table_name(cls) -> str:
        return "events"
```

> 💡 *AI prompt: "Why is money mapped to Decimal instead of float, and why does ROWVERSION appear as bytes that the backend never writes?"*

## Server-generated columns

`ROWVERSION` (and its synonym `TIMESTAMP`) is maintained by the server: SQL
Server refuses an explicit value. Declare such fields as generated so the
INSERT/UPDATE column lists skip them:

```python
class Document(ActiveRecord):
    __table_generated_columns__ = ("rv",)
    rv: Optional[bytes] = None
```

Likewise, a caller-supplied key that happens to be an `INT` (not `IDENTITY`)
must be marked as application-assigned with a `UseFieldGenerator` so core keeps
it in the INSERT rather than expecting the server to fill it.

## Type suggestion and capability probes

The dialect merges a suggestion table mapping Python types to preferred SQL
Server types, and exposes `supports_data_type_sqlserver_*` probes (for example
`supports_data_type_sqlserver_nvarchar`, `..._xml`, `..._uniqueidentifier`).
These are capability statements about the backend, useful when generating DDL
or validating a model before it reaches the server.
