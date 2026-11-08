# src/rhosocial/activerecord/backend/impl/sqlserver/introspection/types.py
"""Result types for this backend's own introspection questions.

Core's ``rhosocial.activerecord.backend.introspection.types`` describes the
objects every backend has: databases, tables, columns, indexes, foreign keys,
views, triggers. SQL Server's catalogue also answers questions core has no
shape for -- which schemas exist and who owns them, which documentation
properties (``MS_Description`` and friends) an object carries, which stored
procedures and user-defined functions live in a schema, and which sequences
are declared. Those answers get their own types here rather than being
crammed into ``extra`` dictionaries: a caller that wants the owner of a
schema should read an attribute, not a string key.

Every field is populated from a catalogue column this backend selected
explicitly; nothing is inferred, and a value the server reports as NULL stays
``None``. Numeric sequence values are :class:`~decimal.Decimal` because a
sequence can be declared on any exact numeric type, and turning one into a
``float`` here would silently round every value read back.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.introspection import SequenceInfo


@dataclass
class SQLServerSchemaInfo:
    """One row of ``sys.schemas``, with its owning principal.

    ``owner`` is the *database principal* name resolved through
    ``sys.schemas.principal_id``. It is ``None`` when the principal has been
    dropped while the schema remains, which the catalogue permits.
    """

    name: str
    schema_id: int = 0
    owner: Optional[str] = None


@dataclass
class SQLServerExtendedPropertyInfo:
    """One row of ``sys.extended_properties``.

    ``class_id``/``class_name`` say what ``major_id`` identifies: for
    ``OBJECT_OR_COLUMN`` (class 1) ``major_id`` is an ``object_id`` and
    ``minor_id`` is 0 for the object itself or the ``column_id`` for a
    column. ``value`` is read through a ``CAST(... AS NVARCHAR)`` because the
    catalogue stores it as ``sql_variant``, which the driver cannot fetch;
    the cast is why a value always arrives as text.
    """

    name: str
    value: Optional[str] = None
    class_id: int = 1
    class_name: str = "OBJECT_OR_COLUMN"
    major_id: int = 0
    minor_id: int = 0


@dataclass
class SQLServerRoutineInfo:
    """One stored procedure or user-defined function.

    ``type_code`` is the two-character ``sys.objects.type`` spelling
    (``P``/``PC`` for procedures, ``FN``/``IF``/``TF``/``FS``/``FT`` for
    functions) and ``type_desc`` its long form. Both are kept because the
    short code is what T-SQL scripts branch on and the description is what a
    person reads.
    """

    name: str
    schema: Optional[str] = None
    type_code: str = ""
    type_desc: str = ""
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    is_ms_shipped: bool = False


@dataclass
class SQLServerSequenceInfo:
    """One row of ``sys.sequences``.

    Every numeric field arrives through a ``CAST(... AS NVARCHAR)`` as well:
    ``start_value``, ``increment``, ``minimum_value``, ``maximum_value`` and
    ``current_value`` are ``sql_variant``, which the driver refuses to fetch.
    They are parsed back into :class:`~decimal.Decimal` here rather than
    returned as the catalog's text, so a caller comparing an increment with
    a bound does arithmetic, not string comparison.
    """

    name: str
    schema: Optional[str] = None
    data_type: Optional[str] = None
    start_value: Optional[Decimal] = None
    increment: Optional[Decimal] = None
    minimum_value: Optional[Decimal] = None
    maximum_value: Optional[Decimal] = None
    current_value: Optional[Decimal] = None
    is_cycling: bool = False
    is_cached: bool = False
    cache_size: Optional[int] = None

    def to_core(self) -> "SequenceInfo":
        """The cross-dialect minimum this answer carries.

        Core's ``SequenceInfo`` names the smallest shape every engine with
        sequences answers, and this is the projection onto it: the fields
        with a one-to-one reading are copied, ``current_value`` lands on
        ``last_value`` and ``is_cycling`` on ``cycle``. A catalog value that
        is not integral stays ``None`` here and complete on this class --
        SQL Server permits a sequence declared on ``decimal(10,2)``, whose
        increment cannot be an integer, and the common minimum does not
        widen to hold one engine's non-integral sequence. ``is_cached`` and
        the exact numeric type stay on this side too: caching is a storage
        detail the minimum has no field for
        (``.claude/rules/introspection.md`` section 5).
        """
        from rhosocial.activerecord.backend.introspection import SequenceInfo

        def as_int(value: Optional[Decimal]) -> Optional[int]:
            if value is None:
                return None
            integral = value.to_integral_value()
            return int(integral) if integral == value else None

        return SequenceInfo(
            name=self.name,
            schema=self.schema,
            data_type=self.data_type,
            start_value=as_int(self.start_value),
            minimum_value=as_int(self.minimum_value),
            maximum_value=as_int(self.maximum_value),
            increment=as_int(self.increment),
            cycle=self.is_cycling,
            cache_size=self.cache_size,
            last_value=as_int(self.current_value),
        )


__all__ = [
    "SQLServerExtendedPropertyInfo",
    "SQLServerRoutineInfo",
    "SQLServerSchemaInfo",
    "SQLServerSequenceInfo",
]
