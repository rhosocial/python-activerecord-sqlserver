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

Partition state is *not* among them: core's ``PartitionState`` /
``PartitionBound`` is the one answer to "which partitions does this table
have", and this backend folds its catalogue rows into it. The database-wide
partition listing that used to live here had no neutral shape, and the state
answer replaced it.

Every field is populated from a catalogue column this backend selected
explicitly; nothing is inferred, and a value the server reports as NULL stays
``None``. Numeric sequence values are :class:`~decimal.Decimal` because a
sequence can be declared on any exact numeric type, and turning one into a
``float`` here would silently round every value read back.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple, TYPE_CHECKING

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


@dataclass
class SQLServerTypeInfo:
    """One user-defined type: an alias type, a table type or a CLR type.

    ``kind`` is derived from the catalogue flags rather than guessed from the
    name: ``TABLE_TYPE`` when ``is_table_type`` is set, ``CLR_TYPE`` when
    ``is_assembly_type`` is set, and ``ALIAS_TYPE`` otherwise. ``base_type``
    is the system type an alias type is declared on, read through
    ``sys.types.system_type_id`` and ``TYPE_NAME``. ``max_length``
    is the catalogue's byte length, so an ``nvarchar(20)`` alias reports 40.
    ``column_count`` is filled for table types only; the table type's
    ``type_table_object_id`` is the object whose columns are counted.
    """

    name: str
    schema: Optional[str] = None
    kind: str = "ALIAS_TYPE"
    base_type: Optional[str] = None
    max_length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    collation: Optional[str] = None
    is_nullable: bool = True
    is_user_defined: bool = True
    is_table_type: bool = False
    is_assembly_type: bool = False
    column_count: Optional[int] = None
    default_object_id: int = 0
    rule_object_id: int = 0
    comment: Optional[str] = None


@dataclass
class SQLServerConstraintInfo:
    """One constraint object from ``sys.objects``.

    ``constraint_type`` is the two-character ``sys.objects.type`` spelling:
    ``PK`` primary key, ``UQ`` unique, ``F`` foreign key, ``C`` check and
    ``D`` default. The primary-key, unique and foreign-key families are also
    reachable through the index and foreign-key introspection explicitly;
    this record is the uniform view of the constraint object, and the check
    and default constraints are the two no other family answers.

    ``definition`` carries the check predicate or the default expression, and
    ``is_disabled``/``is_not_trusted`` are the engine's own flags for the
    constraint kinds that have them (check and foreign key). ``is_system_named``
    is the flag the default-constraint catalogue keeps: ``True`` for a name the
    engine generated, ``False`` for one the declaration gave. A system-named
    default is recreated from the column's declaration, so only a named one is
    a derived object a plan can refer to (``list_derived_objects``).
    """

    name: str
    schema: Optional[str] = None
    table: Optional[str] = None
    constraint_type: str = ""
    constraint_type_desc: str = ""
    columns: Tuple[str, ...] = ()
    referenced_schema: Optional[str] = None
    referenced_table: Optional[str] = None
    referenced_columns: Tuple[str, ...] = ()
    definition: Optional[str] = None
    is_disabled: Optional[bool] = None
    is_not_trusted: Optional[bool] = None
    is_system_named: Optional[bool] = None
    delete_action: Optional[str] = None
    update_action: Optional[str] = None


__all__ = [
    "SQLServerConstraintInfo",
    "SQLServerExtendedPropertyInfo",
    "SQLServerRoutineInfo",
    "SQLServerSchemaInfo",
    "SQLServerSequenceInfo",
    "SQLServerTypeInfo",
]
