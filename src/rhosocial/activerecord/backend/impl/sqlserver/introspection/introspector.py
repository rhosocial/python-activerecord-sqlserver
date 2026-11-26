# src/rhosocial/activerecord/backend/impl/sqlserver/introspection/introspector.py
"""SQL Server concrete introspectors.

Implements AbstractIntrospector and AsyncAbstractIntrospector for SQL Server
using INFORMATION_SCHEMA and sys.* catalog views.
"""

import copy
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, FrozenSet, List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.introspection.base import (
    IntrospectorMixin,
    AbstractIntrospector,
    AsyncAbstractIntrospector,
)
from rhosocial.activerecord.backend.introspection.cache import IntrospectionCache
from rhosocial.activerecord.backend.introspection.errors import ObjectNotFoundError
from rhosocial.activerecord.backend.introspection.executor import (
    IntrospectorExecutor,
    AsyncIntrospectorExecutor,
)
from rhosocial.activerecord.backend.introspection.types import (
    ConstraintState,
    DerivedObjectState,
    IndexState,
    IntrospectionDatabaseInfo,
    IntrospectionTableInfo,
    ItemKind,
    PartitionBound,
    PartitionScheme,
    PartitionState,
    SequenceState,
    StorageOptionsState,
    TableState,
    TableType,
    IntrospectionColumnInfo,
    ColumnNullable,
    IndexInfo,
    IndexColumnInfo,
    IndexType,
    IntrospectionForeignKeyInfo,
    ReferentialAction,
    IntrospectionViewInfo,
    IntrospectionTriggerInfo,
    IntrospectionScope,
)
from .type_parser import SQLServerTypeParser

from ..mixins.introspection import DEFAULT_SCHEMA
from ..query_nodes import SQLServerNodeBuilderMixin
from .types import (
    SQLServerConstraintInfo,
    SQLServerExtendedPropertyInfo,
    SQLServerRoutineInfo,
    SQLServerSchemaInfo,
    SQLServerSequenceInfo,
    SQLServerTypeInfo,
)

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase
    from ..expression.introspection import (
        SQLServerConstraintListQueryStatement,
        SQLServerExtendedPropertyListQueryStatement,
        SQLServerPrimaryKeyQueryStatement,
        SQLServerRoutineListQueryStatement,
        SQLServerSchemaListQueryStatement,
        SQLServerSequenceListQueryStatement,
        SQLServerTemporalHistoryListQueryStatement,
        SQLServerTypeListQueryStatement,
    )
    from ..expression.partition import (
        SQLServerPartitionFunctionQueryStatement,
        SQLServerPartitionRangeQueryStatement,
        SQLServerPartitionSchemeQueryStatement,
        SQLServerPartitionTableQueryStatement,
    )

#: ``INFORMATION_SCHEMA.COLUMNS.CHARACTER_MAXIMUM_LENGTH`` reports ``-1``
#: for a MAX-capable column.  Only these three spell that marker as a length
#: argument (``(MAX)``).  ``xml`` reports ``-1`` as well but takes no length
#: argument, and the deprecated LOBs (``text``/``ntext``/``image``) report
#: their own maximum (2^31-1 / 2^30-1 / 2^31-1) rather than ``-1``, so they
#: keep the bare-word path.
_MAX_LENGTH_TYPES = frozenset({"varchar", "nvarchar", "varbinary"})

#: The three temporal types that take a fractional-seconds precision.  The
#: catalog reports it in ``DATETIME_PRECISION``, and it is the *only* place the
#: precision lives — ``NUMERIC_PRECISION`` is NULL for all three — so before it
#: was selected every ``time(3)``/``datetime2(3)``/``datetimeoffset(3)`` column
#: rebuilt to its bare word and re-read as the *default* precision: a phantom
#: diff against the declaration that produced it, and a missed change between
#: ``time(0)`` and ``time(7)``.  See the normalization note below.
#:
#: ``datetime`` (reports 3) and ``smalldatetime`` (reports 0) also carry a
#: value in ``DATETIME_PRECISION``, but those two are fixed legacy aliases
#: folded into the ``DATETIME2`` concept, so they keep the existing bare-word
#: path and are deliberately absent here.
_DATETIME_PRECISION_TYPES = frozenset({"time", "datetime2", "datetimeoffset"})

#: The fractional-seconds precision the server reports for a *bare*
#: ``time``/``datetime2``/``datetimeoffset`` declaration, and equally for an
#: explicit ``(7)`` one: the server cannot tell those two declarations apart,
#: so neither can this rebuild.  ``(n)`` is rebuilt only when ``n`` differs
#: from this default and the bare word is rebuilt at it.
#:
#: Every number above was read off a live server, identically on SQL Server
#: 2019 (15.0.4465.1), 2022 (16.0.4250.1) and 2025 (17.0.4035.5)::
#:
#:     CREATE TABLE t (t TIME, t0 TIME(0), t3 TIME(3), t7 TIME(7),
#:                     d DATETIME2, d3 DATETIME2(3), o DATETIMEOFFSET(3))
#:     -- INFORMATION_SCHEMA.COLUMNS.DATETIME_PRECISION
#:     --   t  -> 7        t0 -> 0       t3 -> 3       t7 -> 7
#:     --   d  -> 7        d3 -> 3       o3 -> 3
#:
#: The one residual this does not close: a declared explicit ``(7)`` parses to
#: a type carrying precision 7 while the rebuilt column is bare, so those two
#: still compare unequal.  Closing *that* is the server-defaults question (a
#: bare word and an explicit default name one server column), which belongs
#: with the server-defaults question rather than this catalog rebuild; it is
#: recorded here rather than silently widened.
_DATETIME_DEFAULT_PRECISION = 7

#: ``sys.objects.type`` codes for user-defined functions: scalar (``FN``),
#: inline table-valued (``IF``), multi-statement table-valued (``TF``),
#: CLR scalar (``FS``) and CLR table-valued (``FT``). ``sys.procedures``
#: covers the procedure half.
_FUNCTION_TYPE_CODES = ("FN", "IF", "TF", "FS", "FT")

#: ``sys.objects.type`` -> ``TableType``, with the two-word spellings an
#: ``INFORMATION_SCHEMA``-shaped row would carry kept beside the codes. The
#: catalogue is the only layer that distinguishes a system table from a user
#: one, so the mapping belongs here: folding ``S`` into ``BASE_TABLE`` would
#: erase the one fact the caller asked for.
_TABLE_TYPE_BY_CODE = {
    "U": TableType.BASE_TABLE,
    "BASE TABLE": TableType.BASE_TABLE,
    "V": TableType.VIEW,
    "VIEW": TableType.VIEW,
    "S": TableType.SYSTEM_TABLE,
    "SYSTEM TABLE": TableType.SYSTEM_TABLE,
}

#: SQL Server's page size, a constant of the engine with no configuration
#: switch. ``sys.dm_db_partition_stats.used_page_count`` counts 8 KiB pages,
#: so bytes are the count multiplied by this.
_PAGE_SIZE_BYTES = 8192

#: ``TableType`` -> the neutral ``TableState.kind`` vocabulary. A catalogue
#: kind with no neutral member keeps its own lower-case spelling rather than
#: being folded into ``regular``.
_TABLE_STATE_KIND = {
    TableType.BASE_TABLE: "regular",
    TableType.VIEW: "view",
    TableType.SYSTEM_TABLE: "system",
}

#: ``sys.objects.type`` constraint code -> ``ConstraintState.kind``. The
#: engine spells constraints by code, and the neutral answer is a word a
#: caller can branch on without knowing the code set.
_CONSTRAINT_STATE_KIND = {
    "PK": "primary_key",
    "UQ": "unique",
    "F": "foreign_key",
    "C": "check",
    "D": "default",
}

#: The temporal-table release: ``sys.tables.history_table_id`` and
#: ``temporal_type`` arrived with SQL Server 2016 (13.0), so a server older
#: than it cannot be asked for a history table -- it also cannot have one.
_TEMPORAL_TABLE_VERSION = (13, 0, 0)


class SQLServerIntrospectorMixin(SQLServerNodeBuilderMixin, IntrospectorMixin):
    """Shared non-I/O logic for SQL Server introspectors."""

    #: Shared-object kinds this engine does not have at all. Answering these
    #: ``False`` is a definite "there is none", not "cannot tell".
    #:
    #: ``DOMAIN`` is SQL-standard vocabulary SQL Server never adopted: its
    #: user-defined data types are ``TYPE`` objects and carry no domain
    #: defaults or checks. ``EXTENSION`` is equally absent -- features arrive
    #: with the server itself, and the dialect's ``supports_extensions()``
    #: keeps the default ``False``.
    ITEM_KINDS_ABSENT: FrozenSet[ItemKind] = frozenset({
        ItemKind.DOMAIN,
        ItemKind.EXTENSION,
    })

    #: Shared-object kinds this engine has objects of, but with no catalogue
    #: query behind :meth:`item_exists`. These refuse rather than answer
    #: ``False``: an implementation gap that reads as absence would teach a
    #: migration plan the wrong thing.
    #:
    #: ``INDEX`` is here because an index name alone is not an address in
    #: SQL Server -- an index belongs to a table, and this method is given
    #: none. ``FULLTEXT_CATALOG`` is here because the catalogue views have no
    #: listing here. ``TABLESPACE`` is here because the engine's placement
    #: objects are filegroups (partition schemes name them), and they have no
    #: query yet.
    ITEM_KINDS_UNQUERIED: FrozenSet[ItemKind] = frozenset({
        ItemKind.INDEX,
        ItemKind.FULLTEXT_CATALOG,
        ItemKind.TABLESPACE,
    })

    #: Shared-object kinds answered by a catalogue query in
    #: :meth:`item_exists`.
    ITEM_KINDS_QUERIED: FrozenSet[ItemKind] = frozenset({
        ItemKind.SCHEMA,
        ItemKind.TABLE,
        ItemKind.SEQUENCE,
        ItemKind.TYPE,
        ItemKind.FUNCTION,
        ItemKind.PARTITION_FUNCTION,
        ItemKind.PARTITION_SCHEME,
    })

    @property
    def default_schema(self) -> str:
        return DEFAULT_SCHEMA

    @property
    def _node_dialect(self) -> "SQLDialectBase":
        """The dialect the node builders bind their trees to."""
        return self.dialect

    def _get_version(self) -> tuple:
        return getattr(self._backend, '_version', (15, 0, 0))

    # ------------------------------------------------------------------
    # Backend-specific statement factories
    #
    # Every family core models is a statement its dialect renders; this
    # layer constructs it and executes what comes back. The families core has
    # no statement for are SQL Server's own -- the primary key, schemas,
    # extended properties, routines and sequences -- and each gets a factory
    # here returning the statement object. Each collects every parameter at
    # construction (keyword-only: a question is asked once and never edited),
    # the dialect renders it, and each carries the family name into its cache
    # key (see the managers below) so two families never answer each other's
    # question.
    #
    # Nothing here renders: a SQL string is the dialect formatter's, so a
    # factory below names a statement and stops.
    # ------------------------------------------------------------------

    def primary_key_statement(
        self, *, table_name: str, schema: str
    ) -> "SQLServerPrimaryKeyQueryStatement":
        """Return the statement that lists one table's primary-key columns."""
        from ..expression.introspection import SQLServerPrimaryKeyQueryStatement

        return SQLServerPrimaryKeyQueryStatement(self.dialect, table_name=table_name, schema=schema)

    def schema_list_statement(self) -> "SQLServerSchemaListQueryStatement":
        """Return the statement that lists this database's schemas."""
        from ..expression.introspection import SQLServerSchemaListQueryStatement

        return SQLServerSchemaListQueryStatement(self.dialect)

    def extended_property_list_statement(
        self,
        *,
        major_id: Optional[int] = None,
        table_name: Optional[str] = None,
        minor_id: Optional[int] = None,
        class_name: str = "OBJECT_OR_COLUMN",
        schema: Optional[str] = None,
    ) -> "SQLServerExtendedPropertyListQueryStatement":
        """Return the statement that reads one object's extended properties.

        The object is named by ``major_id`` -- the object id for
        ``OBJECT_OR_COLUMN`` (class 1) and the id in the family's own space for
        the other classes -- or by ``table_name``, which the statement resolves
        through ``sys.tables``. The statement takes exactly one of the two;
        ``minor_id`` narrows to one column's properties. ``schema`` only means
        something for the object-scoped classes, and the formatter refuses it
        for a family that has none rather than returning nothing.
        """
        from ..expression.introspection import (
            SQLServerExtendedPropertyListQueryStatement,
        )

        return SQLServerExtendedPropertyListQueryStatement(
            self.dialect,
            major_id=major_id,
            table_name=table_name,
            minor_id=minor_id,
            class_name=class_name,
            schema=schema,
        )

    def routine_list_statement(
        self, *, type_codes: Tuple[str, ...], schema: Optional[str]
    ) -> "SQLServerRoutineListQueryStatement":
        """Return the statement that lists the routines with these type codes.

        One statement class for both routine families -- what separates a
        procedure from a function is the ``sys.objects.type`` code set.
        """
        from ..expression.introspection import SQLServerRoutineListQueryStatement

        return SQLServerRoutineListQueryStatement(
            self.dialect, type_codes=type_codes, schema=schema
        )

    def procedure_list_statement(
        self, *, schema: Optional[str]
    ) -> "SQLServerRoutineListQueryStatement":
        """Return the statement that lists procedures (types ``P``/``PC``)."""
        return self.routine_list_statement(type_codes=("P", "PC"), schema=schema)

    def function_list_statement(
        self, *, schema: Optional[str]
    ) -> "SQLServerRoutineListQueryStatement":
        """Return the statement that lists user-defined functions."""
        return self.routine_list_statement(type_codes=_FUNCTION_TYPE_CODES, schema=schema)

    def sequence_list_statement(
        self, *, schema: Optional[str]
    ) -> "SQLServerSequenceListQueryStatement":
        """Return the statement that lists this database's sequences."""
        from ..expression.introspection import SQLServerSequenceListQueryStatement

        return SQLServerSequenceListQueryStatement(self.dialect, schema=schema)

    def partition_table_statement(
        self, *, table_name: str, schema: Optional[str] = None
    ) -> "SQLServerPartitionTableQueryStatement":
        """Return the statement that reads one table's partition scheme.

        The question answers the scheme name, the function behind it, the
        partitioning column and the function's partition count in one row --
        the three facts ``get_partition_state`` needs before it can ask for
        bounds.
        """
        from ..expression.partition import SQLServerPartitionTableQueryStatement

        return SQLServerPartitionTableQueryStatement(
            self.dialect, table_name=table_name, schema=schema
        )

    def partition_function_statement(
        self, *, function_name: str
    ) -> "SQLServerPartitionFunctionQueryStatement":
        """Return the statement that reads one function's direction and bounds.

        One row per boundary, with the direction on every row: the boundaries
        are ``sql_variant`` and cast to text by the statement, and the
        direction says which side of each boundary belongs to the upper
        partition.
        """
        from ..expression.partition import SQLServerPartitionFunctionQueryStatement

        return SQLServerPartitionFunctionQueryStatement(
            self.dialect, function_name=function_name
        )

    def partition_scheme_statement(
        self, *, scheme_name: str
    ) -> "SQLServerPartitionSchemeQueryStatement":
        """Return the statement that reads one partition scheme by name."""
        from ..expression.partition import SQLServerPartitionSchemeQueryStatement

        return SQLServerPartitionSchemeQueryStatement(
            self.dialect, scheme_name=scheme_name
        )

    def partition_range_statement(
        self, *, table_name: str, schema: Optional[str] = None
    ) -> "SQLServerPartitionRangeQueryStatement":
        """Return the statement that reads one table's partitions *and their
        statistics*.

        The single statement returns the partition number, row count, used
        pages and the two boundary values, so an answer that asks for
        statistics gets bounds and measurements from one read. It is never
        rendered when ``include_stats`` is false: ``get_partition_state``
        builds bounds from the function's boundary rows in that case, and
        nothing touches ``sys.dm_db_partition_stats``.
        """
        from ..expression.partition import SQLServerPartitionRangeQueryStatement

        return SQLServerPartitionRangeQueryStatement(
            self.dialect, table_name=table_name, schema=schema
        )

    def temporal_history_list_statement(
        self, *, table_name: str, schema: Optional[str] = None
    ) -> "SQLServerTemporalHistoryListQueryStatement":
        """Return the statement that reads a table's temporal history table."""
        from ..expression.introspection import (
            SQLServerTemporalHistoryListQueryStatement,
        )

        return SQLServerTemporalHistoryListQueryStatement(
            self.dialect, table_name=table_name, schema=schema
        )

    def type_list_statement(
        self, *, schema: Optional[str] = None
    ) -> "SQLServerTypeListQueryStatement":
        """Return the statement that lists one schema's user-defined types."""
        from ..expression.introspection import SQLServerTypeListQueryStatement

        return SQLServerTypeListQueryStatement(self.dialect, schema=schema)

    def constraint_list_statement(
        self, *, table_name: Optional[str] = None, schema: Optional[str] = None
    ) -> "SQLServerConstraintListQueryStatement":
        """Return the statement that lists one schema's or table's constraints."""
        from ..expression.introspection import SQLServerConstraintListQueryStatement

        return SQLServerConstraintListQueryStatement(
            self.dialect, table_name=table_name, schema=schema
        )

    # ------------------------------------------------------------------
    # Parse methods — pure Python, no I/O
    # ------------------------------------------------------------------

    def parse_database_info(self, rows: List[Dict[str, Any]]) -> IntrospectionDatabaseInfo:
        """Read the database row, taking the version from the server.

        ``server_version`` is the version the dialect was adapted to, or the
        one the backend cached from its last handshake; reading it never
        raises. The row's own ``version`` is the fallback, and ``"unknown"``
        with ``(0, 0, 0)`` is the answer when nothing knows -- rather than the
        strict ``dialect.version``, which would refuse to report a database
        just because nothing had adapted yet.

        The statement answers only these three facts, so ``table_count`` and
        ``size_bytes`` stay ``None``: they are questions of their own and this
        parser does not ask them on the side.
        """
        row = rows[0] if rows else {}
        version_tuple = self.server_version
        if version_tuple is not None:
            version_str = ".".join(str(part) for part in version_tuple)
        else:
            version_str = str(row.get("version") or "unknown")
            version_tuple = self.parse_version_tuple(version_str)
        return IntrospectionDatabaseInfo(
            name=row.get("db_name", ""),
            version=version_str,
            version_tuple=version_tuple,
            vendor="SQL Server",
            encoding=None,
            collation=row.get("collation"),
        )

    @staticmethod
    def parse_version_tuple(version_str: str) -> Tuple[int, int, int]:
        """Read up to three numeric components, ``(0, 0, 0)`` when unreadable."""
        parts = version_str.split(".")
        try:
            parsed = tuple(int(part) for part in parts[:3])
        except (ValueError, TypeError):
            return (0, 0, 0)
        return parsed + (0,) * (3 - len(parsed))

    def parse_tables(
        self, rows: List[Dict[str, Any]], schema: Optional[str]
    ) -> List[IntrospectionTableInfo]:
        """Map ``sys.objects.type`` onto the shared table-kind vocabulary.

        ``U`` is a base table, ``V`` a view and ``S`` a system table; the
        two-word spellings are accepted too, so a row that came from an
        ``INFORMATION_SCHEMA``-shaped question still parses. An unknown code
        reads as a base table, which is the least surprising answer for a
        relation this backend listed as one.

        The three storage slots arrive as the subqueries
        ``_partition_stats_bytes`` projected. A subquery that found no
        partition rows -- a view has none -- answers ``NULL``, which the
        driver returns as ``None``, so "storage this engine does not track
        for this object" stays ``None`` rather than being written as zero.
        ``row_count`` is deliberately not answered: an exact count is a scan,
        and an estimate is a table the engine keeps no estimate in, so the
        slot says so instead of guessing.
        """
        target = schema or self.default_schema
        return [
            IntrospectionTableInfo(
                name=row["TABLE_NAME"],
                schema=target,
                table_type=_TABLE_TYPE_BY_CODE.get(
                    str(row.get("TABLE_TYPE") or "").strip().upper(),
                    TableType.BASE_TABLE,
                ),
                comment=row.get("table_comment"),
                size_bytes=row.get("size_bytes"),
                data_size_bytes=row.get("data_size_bytes"),
                index_size_bytes=row.get("index_size_bytes"),
            )
            for row in rows
        ]

    def parse_columns(
        self, rows: List[Dict[str, Any]], table_name: str, schema: str,
        primary_keys: Optional[List[str]] = None,
    ) -> List[IntrospectionColumnInfo]:
        pk_set = set(primary_keys or [])
        columns: List[IntrospectionColumnInfo] = []
        for row in rows:
            data_type = (row.get("DATA_TYPE") or "").lower()
            max_len = row.get("CHARACTER_MAXIMUM_LENGTH")
            precision = row.get("NUMERIC_PRECISION")
            scale = row.get("NUMERIC_SCALE")
            dt_precision = row.get("DATETIME_PRECISION")

            if max_len == -1 and data_type in _MAX_LENGTH_TYPES:
                # Rebuild the ``(MAX)`` spelling the catalog marker stands
                # for; the introspection type parser reads it as the documented widening
                # (``TextType`` for the character pair,
                # ``SQLServerVarBinaryMaxType`` for ``varbinary``).  Dropping
                # the marker rebuilt a bare word, which re-read as the
                # declared default width (``nvarchar`` -> 255) — a MAX
                # column then compared equal to a 255 one, and against a
                # declared ``NVARCHAR(MAX)`` it produced a phantom diff.
                full_type = f"{data_type}(MAX)"
            elif data_type in _DATETIME_PRECISION_TYPES:
                # Rebuild the fractional-seconds precision the column was
                # declared with, except at the server default: a bare word
                # and ``(7)`` are the same column to the server, so the bare
                # word is what the default rebuilds to and ``(n)`` appears
                # only where the declaration was genuinely narrower.  Before
                # ``DATETIME_PRECISION`` was read at all, a ``time(3)``
                # column came back bare and re-read as the default
                # (``TimeType(None)`` vs the declared ``TimeType(3)``), while
                # ``time(0)`` and ``time(7)`` both folded to the same bare
                # type and could not be told apart.  The measured rows and
                # the explicit-``(7)`` residual are written down on
                # ``_DATETIME_DEFAULT_PRECISION``.
                if (dt_precision is not None
                        and dt_precision != _DATETIME_DEFAULT_PRECISION):
                    full_type = f"{data_type}({dt_precision})"
                else:
                    full_type = data_type
            elif max_len and max_len > 0:
                full_type = f"{data_type}({max_len})"
            elif precision is not None:
                if scale:
                    full_type = f"{data_type}({precision},{scale})"
                else:
                    full_type = f"{data_type}({precision})"
            else:
                full_type = data_type

            col_name = row.get("COLUMN_NAME", "")

            parsed = None
            try:
                parsed = SQLServerTypeParser(self._backend.dialect).parse(full_type)
            except Exception:
                pass

            columns.append(IntrospectionColumnInfo(
                name=col_name,
                table_name=table_name,
                schema=schema,
                ordinal_position=row.get("ORDINAL_POSITION", 0),
                data_type=data_type,
                data_type_full=full_type,
                parsed_data_type=parsed,
                nullable=(
                    ColumnNullable.NULLABLE
                    if row.get("IS_NULLABLE") == "YES"
                    else ColumnNullable.NOT_NULL
                ),
                default_value=row.get("COLUMN_DEFAULT"),
                is_primary_key=col_name in pk_set,
                is_unique=False,
                # ``COLUMNPROPERTY(..., 'IsIdentity')`` answers 1/0 or NULL;
                # ``_as_flag`` keeps a text "0" from reading as truthy.
                is_auto_increment=bool(self._as_flag(row.get("IS_IDENTITY"))),
                comment=row.get("column_comment"),
                character_maximum_length=max_len,
                numeric_precision=precision,
                numeric_scale=scale,
                charset=None,
            ))
        return columns

    def parse_indexes(
        self, rows: List[Dict[str, Any]], table_name: str, schema: str
    ) -> List[IndexInfo]:
        """Fold the one-row-per-column answer into one record per index.

        ``extra`` carries the three facts core's ``IndexInfo`` has no slot
        for: the catalogue's own ``type_desc`` spelling, and the two flags
        that decide whether the engine still treats the index as usable
        (``is_disabled`` and ``is_hypothetical``). ``filter_definition``
        lands on the declared ``filter_condition`` slot.
        """
        type_map = {
            "CLUSTERED": IndexType.BTREE,
            "NONCLUSTERED": IndexType.BTREE,
            "HEAP": IndexType.BTREE,
        }
        index_map: Dict[str, IndexInfo] = {}
        for row in rows:
            idx_name = row.get("index_name", "")
            if idx_name not in index_map:
                idx_type_str = (row.get("index_type") or "").upper()
                index_map[idx_name] = IndexInfo(
                    name=idx_name,
                    table_name=table_name,
                    schema=schema,
                    is_unique=bool(row.get("is_unique")),
                    is_primary=bool(row.get("is_primary_key")),
                    index_type=type_map.get(idx_type_str, IndexType.BTREE),
                    filter_condition=row.get("filter_definition"),
                    columns=[],
                    extra={
                        "index_type": idx_type_str,
                        "is_disabled": self._as_flag(row.get("is_disabled")),
                        "is_hypothetical": self._as_flag(
                            row.get("is_hypothetical")
                        ),
                        "has_filter": self._as_flag(row.get("has_filter")),
                    },
                )
            index_map[idx_name].columns.append(IndexColumnInfo(
                name=row.get("column_name", ""),
                ordinal_position=int(row.get("column_position", 1)),
                is_descending=bool(row.get("is_descending_key")),
            ))
        return list(index_map.values())

    def parse_foreign_keys(
        self, rows: List[Dict[str, Any]], table_name: str, schema: str
    ) -> List[IntrospectionForeignKeyInfo]:
        action_map = {
            "NO_ACTION": ReferentialAction.NO_ACTION,
            "CASCADE": ReferentialAction.CASCADE,
            "SET_NULL": ReferentialAction.SET_NULL,
            "SET_DEFAULT": ReferentialAction.SET_DEFAULT,
        }
        fk_map: Dict[str, IntrospectionForeignKeyInfo] = {}
        for row in rows:
            fk_name = row.get("fk_name", "")
            if fk_name not in fk_map:
                on_del = (row.get("on_delete") or "NO_ACTION").upper()
                on_upd = (row.get("on_update") or "NO_ACTION").upper()
                fk_map[fk_name] = IntrospectionForeignKeyInfo(
                    name=fk_name,
                    table_name=table_name,
                    schema=schema,
                    referenced_table=row.get("ref_table", ""),
                    on_delete=action_map.get(
                        on_del, ReferentialAction.NO_ACTION
                    ),
                    on_update=action_map.get(
                        on_upd, ReferentialAction.NO_ACTION
                    ),
                    columns=[],
                    referenced_columns=[],
                )
            fk_map[fk_name].columns.append(row.get("col_name", ""))
            fk_map[fk_name].referenced_columns.append(
                row.get("ref_col", "")
            )
        return list(fk_map.values())

    def parse_views(
        self, rows: List[Dict[str, Any]], schema: str
    ) -> List[IntrospectionViewInfo]:
        """Read the list rows into view info, definition included.

        The list statement projects ``VIEW_DEFINITION`` and ``IS_UPDATABLE``
        (see ``format_view_list_query_statement``), so the two facts the
        single-view question answers are on every row here as well.
        ``definition`` stays ``None`` only when the server withheld it -- a view
        whose text the caller may not read answers with ``NULL``, which is a
        different thing from a parser that never selected the column.
        """
        return [
            IntrospectionViewInfo(
                name=row.get("view_name", ""),
                schema=schema,
                definition=row.get("definition"),
                is_updatable=row.get("IS_UPDATABLE") == "YES",
            )
            for row in rows
        ]

    def parse_view_info(
        self, rows: List[Dict[str, Any]], view_name: str, schema: str
    ) -> Optional[IntrospectionViewInfo]:
        if not rows:
            return None
        row = rows[0]
        return IntrospectionViewInfo(
            name=row.get("view_name", view_name),
            schema=schema,
            definition=row.get("definition"),
            is_updatable=row.get("IS_UPDATABLE") == "YES",
        )

    def parse_triggers(
        self, rows: List[Dict[str, Any]], schema: str
    ) -> List[IntrospectionTriggerInfo]:
        """Fold the one-row-per-event answer back into one row per trigger.

        The list statement joins ``sys.trigger_events``, so a trigger that
        fires on ``INSERT`` and ``UPDATE`` arrives twice. Each row's
        ``is_disabled`` and ``definition`` are the trigger's, repeated per
        event; ``status`` is read from the first instead of being written as
        ``ENABLED`` for every trigger, which is what the hard-coded default
        amounted to.
        """
        triggers: Dict[str, IntrospectionTriggerInfo] = {}
        for row in rows:
            name = row.get("trigger_name", "")
            trigger = triggers.get(name)
            if trigger is None:
                trigger = IntrospectionTriggerInfo(
                    name=name,
                    table_name=row.get("table_name", ""),
                    schema=schema,
                    timing=(
                        "INSTEAD OF" if row.get("is_instead_of_trigger")
                        else "AFTER"
                    ),
                    events=[],
                    definition=row.get("definition"),
                    status="DISABLED" if row.get("is_disabled") else "ENABLED",
                )
                triggers[name] = trigger
            event = row.get("event")
            # A LEFT JOIN row for a trigger with no event of its own carries a
            # NULL, which is the absence of an event rather than one.
            if event and event not in trigger.events:
                trigger.events.append(event)
        return list(triggers.values())

    # ------------------------------------------------------------------
    # Backend-specific parsers
    # ------------------------------------------------------------------

    def parse_schemas(
        self, rows: List[Dict[str, Any]]
    ) -> List[SQLServerSchemaInfo]:
        return [
            SQLServerSchemaInfo(
                name=row.get("schema_name", ""),
                schema_id=int(row.get("schema_id") or 0),
                owner=row.get("owner"),
            )
            for row in rows
        ]

    def parse_extended_properties(
        self, rows: List[Dict[str, Any]]
    ) -> List[SQLServerExtendedPropertyInfo]:
        properties: List[SQLServerExtendedPropertyInfo] = []
        for row in rows:
            value = row.get("property_value")
            properties.append(
                SQLServerExtendedPropertyInfo(
                    name=row.get("property_name", ""),
                    # The cast widened a sql_variant to text; a NULL value is
                    # a property that was set to NULL, not a missing property,
                    # so it stays None rather than becoming "".
                    value=None if value is None else str(value),
                    class_id=int(row.get("class_id") or 0),
                    class_name=row.get("class_name") or "",
                    major_id=int(row.get("major_id") or 0),
                    minor_id=int(row.get("minor_id") or 0),
                )
            )
        return properties

    def parse_routines(
        self, rows: List[Dict[str, Any]]
    ) -> List[SQLServerRoutineInfo]:
        return [
            SQLServerRoutineInfo(
                name=row.get("routine_name", ""),
                schema=row.get("schema_name"),
                type_code=(row.get("type_code") or "").strip(),
                type_desc=row.get("type_desc") or "",
                created_at=row.get("created_at"),
                modified_at=row.get("modified_at"),
                is_ms_shipped=bool(row.get("is_ms_shipped")),
            )
            for row in rows
        ]

    def parse_sequences(
        self, rows: List[Dict[str, Any]]
    ) -> List[SQLServerSequenceInfo]:
        sequences: List[SQLServerSequenceInfo] = []
        for row in rows:
            cache_size = row.get("cache_size")
            sequences.append(
                SQLServerSequenceInfo(
                    name=row.get("sequence_name", ""),
                    schema=row.get("schema_name"),
                    data_type=row.get("data_type"),
                    start_value=self._as_decimal(row.get("start_value")),
                    increment=self._as_decimal(row.get("increment")),
                    minimum_value=self._as_decimal(row.get("minimum_value")),
                    maximum_value=self._as_decimal(row.get("maximum_value")),
                    current_value=self._as_decimal(row.get("current_value")),
                    is_cycling=bool(row.get("is_cycling")),
                    is_cached=bool(row.get("is_cached")),
                    cache_size=int(cache_size) if cache_size is not None else None,
                )
            )
        return sequences

    def parse_sequence_states(
        self, sequences: List[SQLServerSequenceInfo]
    ) -> List[SequenceState]:
        """Project this engine's complete sequence records onto core's state.

        T-SQL has no ``OWNED BY``: a sequence is a schema object that a
        column's *default* may reference, not one it owns, so ``owned_by``
        stays ``None``. ``start`` and ``increment`` are the catalogue's own
        values through ``to_core``, the one exact-numeric projection this
        backend already owns; the engine-specific remainder (the declared
        type, the current value and the cache flag) rides ``raw``.
        """
        states: List[SequenceState] = []
        for sequence in sequences:
            core = sequence.to_core()
            states.append(
                SequenceState(
                    name=sequence.name,
                    schema=sequence.schema,
                    start=core.start_value,
                    increment=core.increment,
                    raw={
                        "data_type": sequence.data_type,
                        "current_value": sequence.current_value,
                        "is_cached": sequence.is_cached,
                    },
                )
            )
        return states

    @staticmethod
    def _as_decimal(value: Any) -> Optional[Decimal]:
        """Read a cast-to-text sequence value back as an exact number.

        ``None`` means the server reported NULL (an unstarted sequence has no
        ``current_value``); unparseable text also degrades to ``None`` rather
        than aborting the whole listing, matching the contract
        ``parsed_data_type`` follows for columns.
        """
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _as_int(value: Any) -> Optional[int]:
        """Read a catalogue count back as an int, ``None`` when it is absent."""
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def parse_partition_state(
        self,
        table_rows: List[Dict[str, Any]],
        function_rows: List[Dict[str, Any]],
        range_rows: List[Dict[str, Any]],
        *,
        include_stats: bool,
    ) -> Optional[PartitionState]:
        """Fold the partition catalogue rows into the neutral partition state.

        Returns ``None`` when the table is not partitioned, which is core's
        single neutral answer for that -- whatever the engine's own spelling
        is. SQL Server only partitions by range, so the scheme is always
        ``PartitionScheme.RANGE``; the engine's scheme *name*, its partition
        function and the boundary direction are spelling this engine owns
        and ride ``raw``.

        ``upper`` is the partition's high boundary as the server spells it,
        and the last partition's ``None`` is its unbounded top -- the same
        fact a ``MAXVALUE`` partition records elsewhere. Partitions have no
        names in this engine, so ``name`` is the catalogue's partition
        number under a ``p`` prefix.

        With ``include_stats`` the bounds carry ``row_count`` and
        ``size_bytes`` from ``sys.dm_db_partition_stats`` (``used_page_count``
        multiplied by the engine's 8 KiB page). Without it both stay ``None``,
        and the caller's rows never touched that view.
        """
        if not table_rows:
            return None

        row = table_rows[0]
        scheme_name = row.get("scheme_name")
        function_name = row.get("function_name")
        column = row.get("partition_column")

        direction = "RIGHT"
        fanout = self._as_int(row.get("partition_count")) or 0
        boundaries: List[str] = []
        for function_row in function_rows:
            flag = self._as_flag(function_row.get("boundary_value_on_right"))
            if flag is not None:
                direction = "RIGHT" if flag else "LEFT"
            count = self._as_int(function_row.get("partition_count"))
            if count:
                fanout = max(fanout, count)
            value = function_row.get("boundary_value")
            if value is not None:
                boundaries.append(str(value))

        bounds: List[PartitionBound] = []
        if include_stats and range_rows:
            for index, range_row in enumerate(range_rows, start=1):
                number = self._as_int(range_row.get("partition_number"))
                label = number if number is not None else index
                used_pages = self._as_int(range_row.get("used_page_count"))
                bounds.append(
                    PartitionBound(
                        name=f"p{label}",
                        upper=range_row.get("high_boundary"),
                        is_maxvalue=range_row.get("high_boundary") is None,
                        row_count=self._as_int(range_row.get("row_count")),
                        size_bytes=(
                            used_pages * _PAGE_SIZE_BYTES
                            if used_pages is not None
                            else None
                        ),
                    )
                )
        else:
            # The boundary rows are the partition function's own, one per
            # SPLIT RANGE value; N values divide the domain into N + 1
            # partitions. The first partition's lower side and the last
            # partition's upper side are unbounded, so the high boundary of
            # partition k is the k-th value (absent for the last).
            count = fanout or len(boundaries) + 1
            for number in range(1, count + 1):
                upper = boundaries[number - 1] if number <= len(boundaries) else None
                bounds.append(
                    PartitionBound(
                        name=f"p{number}",
                        upper=upper,
                        is_maxvalue=upper is None,
                    )
                )

        return PartitionState(
            scheme=PartitionScheme.RANGE,
            # SQL Server partitions a table on exactly one column, recorded by
            # ``sys.index_columns.partition_ordinal = 1``; the column is the
            # key expression and the key column at once.
            key_expression=column or "",
            key_columns=(column,) if column else (),
            has_default=False,
            auto_extend=False,
            bounds=tuple(bounds),
            raw={
                "scheme_name": scheme_name,
                "function_name": function_name,
                "range_direction": direction,
                "partition_column": column,
                "partition_count": fanout,
            },
        )

    def parse_types(self, rows: List[Dict[str, Any]]) -> List[SQLServerTypeInfo]:
        """Read ``sys.types`` rows into user-defined type records.

        ``kind`` is derived from the catalogue flags, never from the name: a
        table type is ``TABLE_TYPE``, a CLR type ``CLR_TYPE`` and the rest
        ``ALIAS_TYPE``. ``column_count`` is meaningful only for a table type;
        the subquery answers 0 for an alias type whose ``type_table_object_id``
        is NULL, and that zero is not a count of columns the type has.
        """
        types: List[SQLServerTypeInfo] = []
        for row in rows:
            is_table_type = bool(row.get("is_table_type"))
            is_assembly_type = bool(row.get("is_assembly_type"))
            if is_table_type:
                kind = "TABLE_TYPE"
            elif is_assembly_type:
                kind = "CLR_TYPE"
            else:
                kind = "ALIAS_TYPE"
            types.append(
                SQLServerTypeInfo(
                    name=row.get("type_name", ""),
                    schema=row.get("schema_name"),
                    kind=kind,
                    base_type=row.get("base_type"),
                    max_length=self._as_int(row.get("max_length")),
                    precision=self._as_int(row.get("precision")),
                    scale=self._as_int(row.get("scale")),
                    collation=row.get("collation"),
                    is_nullable=bool(row.get("is_nullable")),
                    is_user_defined=bool(row.get("is_user_defined")),
                    is_table_type=is_table_type,
                    is_assembly_type=is_assembly_type,
                    column_count=(
                        self._as_int(row.get("column_count"))
                        if is_table_type
                        else None
                    ),
                    default_object_id=int(row.get("default_object_id") or 0),
                    rule_object_id=int(row.get("rule_object_id") or 0),
                    comment=row.get("type_comment"),
                )
            )
        return types

    def parse_constraints(
        self, rows: List[Dict[str, Any]]
    ) -> List[SQLServerConstraintInfo]:
        """Fold one-row-per-constraint (or per foreign-key column) rows.

        A primary key, unique constraint or foreign key is one row per key
        column; a check or default constraint is one row carrying its
        expression. The columns and the ordinal that orders them are chosen
        by constraint type, so a foreign key's columns never land in the
        primary key's list merely because both catalogue views were joined.
        """
        records: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        for row in rows:
            name = row.get("constraint_name", "")
            schema = row.get("schema_name")
            table = row.get("table_name")
            key = (schema or "", table or "", name)
            record = records.get(key)
            if record is None:
                record = {
                    "name": name,
                    "schema": schema,
                    "table": table,
                    "constraint_type": (row.get("constraint_type") or "").strip(),
                    "constraint_type_desc": row.get("constraint_type_desc") or "",
                    "columns": [],
                    "referenced_schema": None,
                    "referenced_table": None,
                    "referenced_columns": [],
                    "definition": None,
                    "is_disabled": None,
                    "is_not_trusted": None,
                    "is_system_named": None,
                    "delete_action": None,
                    "update_action": None,
                }
                records[key] = record

            constraint_type = (row.get("constraint_type") or "").strip()
            ordinal = self._as_int(row.get("fk_ordinal"))
            if ordinal is None:
                ordinal = self._as_int(row.get("key_ordinal"))
            ordinal = ordinal or 0

            if constraint_type == "F":
                column = row.get("fk_column")
                referenced = row.get("fk_referenced_column")
                record["referenced_schema"] = row.get("referenced_schema")
                record["referenced_table"] = row.get("referenced_table")
                record["delete_action"] = row.get("on_delete")
                record["update_action"] = row.get("on_update")
                record["is_disabled"] = self._as_flag(row.get("fk_disabled"))
                record["is_not_trusted"] = self._as_flag(
                    row.get("fk_not_trusted")
                )
            elif constraint_type in ("PK", "UQ"):
                column = row.get("key_column")
                referenced = None
            elif constraint_type == "C":
                column = row.get("check_column")
                referenced = None
                record["definition"] = row.get("check_definition")
                record["is_disabled"] = self._as_flag(row.get("check_disabled"))
                record["is_not_trusted"] = self._as_flag(
                    row.get("check_not_trusted")
                )
            elif constraint_type == "D":
                column = row.get("default_column")
                referenced = None
                record["definition"] = row.get("default_definition")
                record["is_system_named"] = self._as_flag(
                    row.get("default_system_named")
                )
            else:
                column = None
                referenced = None

            if column and column not in [item[1] for item in record["columns"]]:
                record["columns"].append((ordinal, column))
            if referenced and referenced not in [
                item[1] for item in record["referenced_columns"]
            ]:
                record["referenced_columns"].append((ordinal, referenced))

        constraints: List[SQLServerConstraintInfo] = []
        for record in records.values():
            record["columns"] = tuple(
                column for _ordinal, column in sorted(record["columns"])
            )
            record["referenced_columns"] = tuple(
                column
                for _ordinal, column in sorted(record["referenced_columns"])
            )
            constraints.append(SQLServerConstraintInfo(**record))
        return sorted(
            constraints,
            key=lambda constraint: (
                constraint.schema or "",
                constraint.table or "",
                constraint.name,
            ),
        )

    @staticmethod
    def _as_flag(value: Any) -> Optional[bool]:
        """Read a catalogue bit as a tri-state, ``None`` when absent.

        The driver normally hands back ``0``/``1``, but a text row -- a test
        double or a driver conversion -- can hand back ``"0"``, and
        ``bool("0")`` is ``True``. The string branch closes that trap before
        it can turn an identity or trust flag on.
        """
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes")
        return bool(value)


class SQLServerIntrospector(
    SQLServerIntrospectorMixin, AbstractIntrospector
):
    """Synchronous introspector for SQL Server backends."""

    def __init__(
        self,
        backend: Any,
        executor: IntrospectorExecutor,
        cache: Optional[IntrospectionCache] = None,
    ) -> None:
        super().__init__(backend, executor, cache)

    def get_table_info(
        self, table_name: str, schema: Optional[str] = None
    ) -> Optional[IntrospectionTableInfo]:
        key = self._cache.key(
            IntrospectionScope.TABLE, table_name, schema=schema
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        tables = self.list_tables(schema)
        table = next(
            (t for t in tables if t.name == table_name), None
        )
        if table is None:
            return None

        table = copy.copy(table)
        table.columns = self.list_columns(table_name, schema)
        table.indexes = self.list_indexes(table_name, schema)
        table.foreign_keys = self.list_foreign_keys(table_name, schema)
        self._cache.set(key, table)
        return table

    def list_columns(
        self, table_name: str, schema: Optional[str] = None
    ) -> List[IntrospectionColumnInfo]:
        target = schema if schema is not None else self.default_schema
        key = self._cache.key(
            IntrospectionScope.COLUMN, table_name, schema=target
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        pk_sql, pk_params = self.primary_key_statement(
            table_name=table_name, schema=target
        ).to_sql()
        pk_rows = self._executor.execute(pk_sql, pk_params)
        primary_keys = [r.get("COLUMN_NAME") for r in pk_rows]

        sql, params = self.column_info_statement(
            table_name=table_name, schema=schema
        ).to_sql()
        rows = self._executor.execute(sql, params)
        columns = self.parse_columns(
            rows, table_name, target, primary_keys
        )
        self._cache.set(key, columns)
        return columns

    # ------------------------------------------------------------------
    # Backend-specific questions (sync)
    #
    # The cache keys follow the same discipline as core's shared methods:
    # the scope comes from IntrospectionScope, the schema rides the
    # dedicated argument, and a family that shares a scope with another
    # family names itself in ``extra``. Comparison is by scope value and
    # schema, so ``list_procedures(schema="dbo")`` and
    # ``list_functions(schema="dbo")`` never answer each other.
    # ------------------------------------------------------------------

    def list_schema_infos(self) -> List[SQLServerSchemaInfo]:
        """List the database's schemas with their owning principal."""
        key = self._cache.key(IntrospectionScope.SCHEMA, extra="schema_infos")
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.schema_list_statement().to_sql()
        schemas = self.parse_schemas(self._executor.execute(sql, params))
        self._cache.set(key, schemas)
        return schemas

    def list_schemas(self) -> List[str]:
        """List the schema names the server exposes.

        Core's neutral answer is the names alone; the owner and schema id
        this engine also reports stay on :meth:`list_schema_infos`, which
        is the backend's own complete answer beside it.
        """
        return [schema.name for schema in self.list_schema_infos()]

    def list_extended_properties(
        self,
        major_id: Optional[int] = None,
        *,
        table_name: Optional[str] = None,
        minor_id: Optional[int] = None,
        class_name: str = "OBJECT_OR_COLUMN",
        schema: Optional[str] = None,
    ) -> List[SQLServerExtendedPropertyInfo]:
        """List ``sys.extended_properties`` rows for one catalogue object.

        The object is named by id or by table name, and exactly one of the
        two: ``major_id`` when the caller has the object id, ``table_name``
        when all it has is the name -- the statement resolves that name
        through ``sys.tables`` itself, so it is one query rather than a lookup
        followed by a read.

        Args:
            major_id: The object id for ``OBJECT_OR_COLUMN`` (class 1), or the
                id in the family's own space for other classes.
            table_name: The table whose properties are wanted. Only
                ``OBJECT_OR_COLUMN`` has a table, and the statement refuses any
                other class rather than returning nothing.
            minor_id: ``None`` for every row of the object (the object's own
                properties plus its columns'), or the exact ``minor_id`` --
                ``0`` for an object-level property, a ``column_id`` for a
                column-level one.
            class_name: The ``class_desc`` family, ``OBJECT_OR_COLUMN`` by
                default -- the family ``MS_Description`` normally lives in.
            schema: Restrict to objects in this schema. Only meaningful for
                the object-scoped classes; asking for a schema on a family
                that has none raises ``ValueError`` instead of returning
                nothing.

        The cache entry is keyed on whichever name was given, so
        ``invalidate_cache(TABLE, "<table>")`` drops the one asked by table
        name but not the one asked by id; clear the scope for the latter.
        """
        key = self._cache.key(
            IntrospectionScope.TABLE,
            table_name if table_name is not None else str(major_id),
            schema=schema,
            extra=f"extended_properties:{class_name}:{minor_id}",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.extended_property_list_statement(
            major_id=major_id,
            table_name=table_name,
            minor_id=minor_id,
            class_name=class_name,
            schema=schema,
        ).to_sql()
        properties = self.parse_extended_properties(
            self._executor.execute(sql, params)
        )
        self._cache.set(key, properties)
        return properties

    def list_procedures(
        self, schema: Optional[str] = None
    ) -> List[SQLServerRoutineInfo]:
        """List stored procedures in *schema* (``sys.objects`` types P/PC)."""
        key = self._cache.key(
            IntrospectionScope.TABLE, schema=schema, extra="procedures"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.procedure_list_statement(schema=schema).to_sql()
        procedures = self.parse_routines(self._executor.execute(sql, params))
        self._cache.set(key, procedures)
        return procedures

    def list_functions(
        self, schema: Optional[str] = None
    ) -> List[SQLServerRoutineInfo]:
        """List user-defined functions in *schema*."""
        key = self._cache.key(
            IntrospectionScope.TABLE, schema=schema, extra="functions"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.function_list_statement(schema=schema).to_sql()
        functions = self.parse_routines(self._executor.execute(sql, params))
        self._cache.set(key, functions)
        return functions

    def list_sequences(
        self, schema: Optional[str] = None
    ) -> List[SQLServerSequenceInfo]:
        """List sequences in *schema* (``sys.sequences``)."""
        key = self._cache.key(IntrospectionScope.SEQUENCE, schema=schema)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.sequence_list_statement(schema=schema).to_sql()
        sequences = self.parse_sequences(self._executor.execute(sql, params))
        self._cache.set(key, sequences)
        return sequences

    def list_types(self, schema: Optional[str] = None) -> List[SQLServerTypeInfo]:
        """List one schema's user-defined alias, table and CLR types."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA, schema=schema, extra="types"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.type_list_statement(schema=schema).to_sql()
        types = self.parse_types(self._executor.execute(sql, params))
        self._cache.set(key, types)
        return types

    def get_type_info(
        self, type_name: str, schema: Optional[str] = None
    ) -> Optional[SQLServerTypeInfo]:
        """Return one user-defined type, or ``None`` when it is not there."""
        return next(
            (type_ for type_ in self.list_types(schema) if type_.name == type_name),
            None,
        )

    def list_constraints(
        self,
        table_name: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> List[SQLServerConstraintInfo]:
        """List constraint objects, for one table or one schema.

        The families cover primary keys, unique constraints, foreign keys,
        check constraints and default constraints. The first three are also
        reachable through the index and foreign-key questions; the check and
        default constraints are the two no other family answers.
        """
        key = self._cache.key(
            IntrospectionScope.TABLE,
            table_name or "*",
            schema=schema,
            extra="constraints",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.constraint_list_statement(
            table_name=table_name, schema=schema
        ).to_sql()
        constraints = self.parse_constraints(self._executor.execute(sql, params))
        self._cache.set(key, constraints)
        return constraints

    # ------------------------------------------------------------------
    # Neutral object state (sync)
    # ------------------------------------------------------------------
    #
    # These answer core's object-state contract in core's own dataclasses.
    # Where the engine has no neutral slot for a fact it owns -- the
    # partition scheme's name, its function, the boundary direction -- the
    # fact rides ``raw``, which is what that channel is for. A family the
    # engine cannot answer is not overridden and stays refused.

    def get_table_state(
        self, table_name: str, schema: Optional[str] = None
    ) -> TableState:
        """Read the table's kind, comment and partition scheme.

        The partitioning member is :meth:`get_partition_state`'s answer, so
        ``partitioning`` is ``None`` exactly when the table is unpartitioned.
        A table that is not there raises ``ObjectNotFoundError`` rather than
        answering with a default state, because "no such table" and "a table
        with no storage options" are not the same answer.
        """
        target = schema if schema is not None else self.default_schema
        key = self._cache.key(
            IntrospectionScope.TABLE, table_name, schema=target, extra="state"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        table = next(
            (
                candidate
                for candidate in self.list_tables(target, include_system=True)
                if candidate.name == table_name
            ),
            None,
        )
        if table is None:
            raise ObjectNotFoundError("Table", table_name, target)

        state = TableState(
            name=table_name,
            schema=target,
            kind=_TABLE_STATE_KIND.get(table.table_type, "regular"),
            # SQL Server has no table-level engine, charset, collation or
            # tablespace declaration: the storage a table has is its
            # filegroup and compression, neither of which this neutral
            # record models. The dataclass default is the honest answer.
            storage=StorageOptionsState(),
            comment=table.comment,
            partitioning=self.get_partition_state(table_name, target),
            raw={"table_type": table.table_type.value},
        )
        self._cache.set(key, state)
        return state

    def get_partition_state(
        self,
        table_name: str,
        schema: Optional[str] = None,
        include_stats: bool = False,
    ) -> Optional[PartitionState]:
        """Read one table's partition scheme, bounds and optional statistics.

        ``None`` is the neutral answer for "this table is not partitioned";
        the partition-table question returns no row for an unpartitioned
        table, so nothing else is asked.

        ``include_stats`` decides whether ``sys.dm_db_partition_stats`` is
        read at all. Without it the bounds come from the function's own
        boundary rows and every bound's ``row_count``/``size_bytes`` stays
        ``None``; with it the range question returns numbers and pages
        beside each boundary and they fill the bounds.
        """
        target = schema if schema is not None else self.default_schema
        key = self._cache.key(
            IntrospectionScope.PARTITION,
            table_name,
            schema=target,
            extra=f"state:stats={include_stats}",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.partition_table_statement(
            table_name=table_name, schema=target
        ).to_sql()
        table_rows = self._executor.execute(sql, params)
        if not table_rows:
            return None

        function_rows: List[Dict[str, Any]] = []
        function_name = table_rows[0].get("function_name")
        if function_name:
            sql, params = self.partition_function_statement(
                function_name=function_name
            ).to_sql()
            function_rows = self._executor.execute(sql, params)

        range_rows: List[Dict[str, Any]] = []
        if include_stats:
            sql, params = self.partition_range_statement(
                table_name=table_name, schema=target
            ).to_sql()
            range_rows = self._executor.execute(sql, params)

        state = self.parse_partition_state(
            table_rows, function_rows, range_rows, include_stats=include_stats
        )
        self._cache.set(key, state)
        return state

    def list_index_states(
        self, table_name: str, schema: Optional[str] = None
    ) -> List[IndexState]:
        """Read every index on the table, with usability and its predicate.

        ``usable`` is false for an index the engine reports disabled or
        hypothetical: both are catalogue rows that will not serve a query.
        SQL Server has no invisible index, so ``visible`` stays true.
        """
        target = schema if schema is not None else self.default_schema
        states: List[IndexState] = []
        for index in self.list_indexes(table_name, target):
            extra = index.extra or {}
            disabled = self._as_flag(extra.get("is_disabled")) is True
            hypothetical = self._as_flag(extra.get("is_hypothetical")) is True
            states.append(
                IndexState(
                    name=index.name,
                    table=index.table_name,
                    schema=index.schema if index.schema is not None else target,
                    unique=index.is_unique,
                    method=extra.get("index_type") or None,
                    predicate=index.filter_condition,
                    visible=True,
                    usable=not (disabled or hypothetical),
                    raw={
                        "is_primary": index.is_primary,
                        "is_disabled": disabled,
                        "is_hypothetical": hypothetical,
                    },
                )
            )
        return states

    def list_constraint_states(
        self, table_name: str, schema: Optional[str] = None
    ) -> List[ConstraintState]:
        """Read every constraint on the table, including its trust state.

        ``validated`` is the inverse of ``is_not_trusted`` and ``enforced``
        the inverse of ``is_disabled`` -- the two flags ``NOCHECK`` clears.
        SQL Server has no deferred constraints, so ``deferred`` is false.
        """
        target = schema if schema is not None else self.default_schema
        states: List[ConstraintState] = []
        for constraint in self.list_constraints(table_name, target):
            disabled = self._as_flag(constraint.is_disabled) is True
            states.append(
                ConstraintState(
                    name=constraint.name,
                    table=constraint.table or table_name,
                    kind=_CONSTRAINT_STATE_KIND.get(
                        constraint.constraint_type,
                        constraint.constraint_type.lower() or "constraint",
                    ),
                    schema=constraint.schema if constraint.schema is not None else target,
                    validated=self._as_flag(constraint.is_not_trusted) is not True,
                    enforced=not disabled,
                    deferred=False,
                    disabled=disabled,
                    raw={
                        "constraint_type": constraint.constraint_type,
                        "constraint_type_desc": constraint.constraint_type_desc,
                        "columns": constraint.columns,
                        "definition": constraint.definition,
                        "referenced_table": constraint.referenced_table,
                        "is_system_named": constraint.is_system_named,
                    },
                )
            )
        return states

    def list_sequence_states(
        self, schema: Optional[str] = None
    ) -> List[SequenceState]:
        """Read this schema's sequences as core's neutral state."""
        return self.parse_sequence_states(self.list_sequences(schema))

    def list_derived_objects(
        self, table_name: str, schema: Optional[str] = None
    ) -> List[DerivedObjectState]:
        """Read the objects this table's declarations caused the engine to make.

        Two kinds exist here: an explicitly *named* default constraint, whose
        name a plan must know before it can drop it, and a temporal history
        table, which the engine creates for a ``SYSTEM_VERSIONING``
        declaration. A system-named default is excluded: the engine generated
        its name from the column, so it is recreated from the declaration and
        is not a separate object a caller refers to.

        The history question is asked only from SQL Server 2016 (13.0), the
        release that added ``history_table_id``; an older server cannot have
        a temporal table at all, so there is nothing to miss.
        """
        target = schema if schema is not None else self.default_schema
        key = self._cache.key(
            IntrospectionScope.TABLE,
            table_name,
            schema=target,
            extra="derived_objects",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        objects: List[DerivedObjectState] = []
        for constraint in self.list_constraints(table_name, target):
            if constraint.constraint_type == "D" and not constraint.is_system_named:
                objects.append(
                    DerivedObjectState(
                        kind="named_default",
                        name=constraint.name,
                        owned_by=(
                            constraint.columns[0] if constraint.columns else None
                        ),
                        raw={
                            "definition": constraint.definition,
                            "is_system_named": constraint.is_system_named,
                        },
                    )
                )

        if self._get_version() >= _TEMPORAL_TABLE_VERSION:
            sql, params = self.temporal_history_list_statement(
                table_name=table_name, schema=target
            ).to_sql()
            for row in self._executor.execute(sql, params):
                history = row.get("history_table")
                if history:
                    objects.append(
                        DerivedObjectState(
                            kind="history_table",
                            name=history,
                            owned_by=table_name,
                            raw={
                                "schema": row.get("history_schema"),
                                "temporal_type": self._as_int(
                                    row.get("temporal_type")
                                ),
                            },
                        )
                    )

        objects.sort(key=lambda item: (item.kind, item.name))
        self._cache.set(key, objects)
        return objects

    def item_exists(
        self, kind: ItemKind, name: str, schema: Optional[str] = None
    ) -> bool:
        """Whether a shared object of this kind exists.

        Answer for every kind, with core's one rule: a kind this engine does
        not have at all answers ``False``; a kind it has and this backend
        queries answers from the catalogue; a kind it has but this backend
        cannot query is refused, because an implementation gap must not read
        as absence. :attr:`ITEM_KINDS_ABSENT` and :attr:`ITEM_KINDS_QUERIED`
        declare the two answer sets; everything else is
        :attr:`ITEM_KINDS_UNQUERIED` and refuses.

        A partition function or scheme is database-scoped, so ``schema``
        means nothing for those two and is not forwarded.
        """
        if not isinstance(kind, ItemKind):
            try:
                kind = ItemKind(kind)
            except ValueError:
                self._refuse("StructureIntrospectionSupport", "item_exists")

        if kind in self.ITEM_KINDS_ABSENT:
            return False
        if kind not in self.ITEM_KINDS_QUERIED:
            self._refuse("StructureIntrospectionSupport", "item_exists")
            return False

        if kind is ItemKind.SCHEMA:
            return name in self.list_schemas()
        if kind is ItemKind.TABLE:
            return self.table_exists(name, schema)
        if kind is ItemKind.SEQUENCE:
            return any(sequence.name == name for sequence in self.list_sequences(schema))
        if kind is ItemKind.TYPE:
            return self.get_type_info(name, schema) is not None
        if kind is ItemKind.FUNCTION:
            return any(
                routine.name == name for routine in self.list_functions(schema)
            )
        if kind is ItemKind.PARTITION_FUNCTION:
            statement = self.partition_function_statement(function_name=name)
        else:
            statement = self.partition_scheme_statement(scheme_name=name)

        cache_key = self._cache.key(
            IntrospectionScope.PARTITION, name, extra=f"exists:{kind.value}"
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        sql, params = statement.to_sql()
        exists = bool(self._executor.execute(sql, params))
        self._cache.set(cache_key, exists)
        return exists


class AsyncSQLServerIntrospector(
    SQLServerIntrospectorMixin, AsyncAbstractIntrospector
):
    """Asynchronous introspector for SQL Server backends."""

    def __init__(
        self,
        backend: Any,
        executor: AsyncIntrospectorExecutor,
        cache: Optional[IntrospectionCache] = None,
    ) -> None:
        super().__init__(backend, executor, cache)

    async def get_table_info(
        self, table_name: str, schema: Optional[str] = None
    ) -> Optional[IntrospectionTableInfo]:
        key = self._cache.key(
            IntrospectionScope.TABLE, table_name, schema=schema
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        tables = await self.list_tables(schema)
        table = next(
            (t for t in tables if t.name == table_name), None
        )
        if table is None:
            return None

        table = copy.copy(table)
        table.columns = await self.list_columns(table_name, schema)
        table.indexes = await self.list_indexes(table_name, schema)
        table.foreign_keys = await self.list_foreign_keys(
            table_name, schema
        )
        self._cache.set(key, table)
        return table

    async def list_columns(
        self, table_name: str, schema: Optional[str] = None
    ) -> List[IntrospectionColumnInfo]:
        target = schema if schema is not None else self.default_schema
        key = self._cache.key(
            IntrospectionScope.COLUMN, table_name, schema=target
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        pk_sql, pk_params = self.primary_key_statement(
            table_name=table_name, schema=target
        ).to_sql()
        pk_rows = await self._executor.execute(pk_sql, pk_params)
        primary_keys = [r.get("COLUMN_NAME") for r in pk_rows]

        sql, params = self.column_info_statement(
            table_name=table_name, schema=schema
        ).to_sql()
        rows = await self._executor.execute(sql, params)
        columns = self.parse_columns(
            rows, table_name, target, primary_keys
        )
        self._cache.set(key, columns)
        return columns

    # ------------------------------------------------------------------
    # Backend-specific questions (async)
    #
    # Same signatures as the sync manager, same cache keys, same parsers;
    # only the executor is awaited.
    # ------------------------------------------------------------------

    async def list_schema_infos(self) -> List[SQLServerSchemaInfo]:
        """List the database's schemas with their owning principal."""
        key = self._cache.key(IntrospectionScope.SCHEMA, extra="schema_infos")
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.schema_list_statement().to_sql()
        schemas = self.parse_schemas(await self._executor.execute(sql, params))
        self._cache.set(key, schemas)
        return schemas

    async def list_schemas(self) -> List[str]:
        """List the schema names the server exposes."""
        return [schema.name for schema in await self.list_schema_infos()]

    async def list_extended_properties(
        self,
        major_id: Optional[int] = None,
        *,
        table_name: Optional[str] = None,
        minor_id: Optional[int] = None,
        class_name: str = "OBJECT_OR_COLUMN",
        schema: Optional[str] = None,
    ) -> List[SQLServerExtendedPropertyInfo]:
        """List ``sys.extended_properties`` rows for one catalogue object.

        Same signature and same cache key as the synchronous manager: the
        object is named by id or by table name, and exactly one of the two.
        """
        key = self._cache.key(
            IntrospectionScope.TABLE,
            table_name if table_name is not None else str(major_id),
            schema=schema,
            extra=f"extended_properties:{class_name}:{minor_id}",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.extended_property_list_statement(
            major_id=major_id,
            table_name=table_name,
            minor_id=minor_id,
            class_name=class_name,
            schema=schema,
        ).to_sql()
        properties = self.parse_extended_properties(
            await self._executor.execute(sql, params)
        )
        self._cache.set(key, properties)
        return properties

    async def list_procedures(
        self, schema: Optional[str] = None
    ) -> List[SQLServerRoutineInfo]:
        """List stored procedures in *schema* (``sys.objects`` types P/PC)."""
        key = self._cache.key(
            IntrospectionScope.TABLE, schema=schema, extra="procedures"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.procedure_list_statement(schema=schema).to_sql()
        procedures = self.parse_routines(
            await self._executor.execute(sql, params)
        )
        self._cache.set(key, procedures)
        return procedures

    async def list_functions(
        self, schema: Optional[str] = None
    ) -> List[SQLServerRoutineInfo]:
        """List user-defined functions in *schema*."""
        key = self._cache.key(
            IntrospectionScope.TABLE, schema=schema, extra="functions"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.function_list_statement(schema=schema).to_sql()
        functions = self.parse_routines(
            await self._executor.execute(sql, params)
        )
        self._cache.set(key, functions)
        return functions

    async def list_sequences(
        self, schema: Optional[str] = None
    ) -> List[SQLServerSequenceInfo]:
        """List sequences in *schema* (``sys.sequences``)."""
        key = self._cache.key(IntrospectionScope.SEQUENCE, schema=schema)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.sequence_list_statement(schema=schema).to_sql()
        sequences = self.parse_sequences(
            await self._executor.execute(sql, params)
        )
        self._cache.set(key, sequences)
        return sequences

    async def list_types(
        self, schema: Optional[str] = None
    ) -> List[SQLServerTypeInfo]:
        """List one schema's user-defined alias, table and CLR types."""
        key = self._cache.key(
            IntrospectionScope.SCHEMA, schema=schema, extra="types"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.type_list_statement(schema=schema).to_sql()
        types = self.parse_types(await self._executor.execute(sql, params))
        self._cache.set(key, types)
        return types

    async def get_type_info(
        self, type_name: str, schema: Optional[str] = None
    ) -> Optional[SQLServerTypeInfo]:
        """Return one user-defined type asynchronously, or ``None``."""
        types = await self.list_types(schema)
        return next((type_ for type_ in types if type_.name == type_name), None)

    async def list_constraints(
        self,
        table_name: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> List[SQLServerConstraintInfo]:
        """List constraint objects asynchronously, for one table or schema."""
        key = self._cache.key(
            IntrospectionScope.TABLE,
            table_name or "*",
            schema=schema,
            extra="constraints",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.constraint_list_statement(
            table_name=table_name, schema=schema
        ).to_sql()
        constraints = self.parse_constraints(
            await self._executor.execute(sql, params)
        )
        self._cache.set(key, constraints)
        return constraints

    # ------------------------------------------------------------------
    # Neutral object state (async)
    #
    # Same signatures, cache keys, parsers and answers as the synchronous
    # manager; only the executor is awaited.
    # ------------------------------------------------------------------

    async def get_table_state(
        self, table_name: str, schema: Optional[str] = None
    ) -> TableState:
        """Read the table's kind, comment and partition scheme."""
        target = schema if schema is not None else self.default_schema
        key = self._cache.key(
            IntrospectionScope.TABLE, table_name, schema=target, extra="state"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        table = next(
            (
                candidate
                for candidate in await self.list_tables(target, include_system=True)
                if candidate.name == table_name
            ),
            None,
        )
        if table is None:
            raise ObjectNotFoundError("Table", table_name, target)

        state = TableState(
            name=table_name,
            schema=target,
            kind=_TABLE_STATE_KIND.get(table.table_type, "regular"),
            storage=StorageOptionsState(),
            comment=table.comment,
            partitioning=await self.get_partition_state(table_name, target),
            raw={"table_type": table.table_type.value},
        )
        self._cache.set(key, state)
        return state

    async def get_partition_state(
        self,
        table_name: str,
        schema: Optional[str] = None,
        include_stats: bool = False,
    ) -> Optional[PartitionState]:
        """Read one table's partition scheme, bounds and optional statistics."""
        target = schema if schema is not None else self.default_schema
        key = self._cache.key(
            IntrospectionScope.PARTITION,
            table_name,
            schema=target,
            extra=f"state:stats={include_stats}",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sql, params = self.partition_table_statement(
            table_name=table_name, schema=target
        ).to_sql()
        table_rows = await self._executor.execute(sql, params)
        if not table_rows:
            return None

        function_rows: List[Dict[str, Any]] = []
        function_name = table_rows[0].get("function_name")
        if function_name:
            sql, params = self.partition_function_statement(
                function_name=function_name
            ).to_sql()
            function_rows = await self._executor.execute(sql, params)

        range_rows: List[Dict[str, Any]] = []
        if include_stats:
            sql, params = self.partition_range_statement(
                table_name=table_name, schema=target
            ).to_sql()
            range_rows = await self._executor.execute(sql, params)

        state = self.parse_partition_state(
            table_rows, function_rows, range_rows, include_stats=include_stats
        )
        self._cache.set(key, state)
        return state

    async def list_index_states(
        self, table_name: str, schema: Optional[str] = None
    ) -> List[IndexState]:
        """Read every index on the table, with usability and its predicate."""
        target = schema if schema is not None else self.default_schema
        states: List[IndexState] = []
        for index in await self.list_indexes(table_name, target):
            extra = index.extra or {}
            disabled = self._as_flag(extra.get("is_disabled")) is True
            hypothetical = self._as_flag(extra.get("is_hypothetical")) is True
            states.append(
                IndexState(
                    name=index.name,
                    table=index.table_name,
                    schema=index.schema if index.schema is not None else target,
                    unique=index.is_unique,
                    method=extra.get("index_type") or None,
                    predicate=index.filter_condition,
                    visible=True,
                    usable=not (disabled or hypothetical),
                    raw={
                        "is_primary": index.is_primary,
                        "is_disabled": disabled,
                        "is_hypothetical": hypothetical,
                    },
                )
            )
        return states

    async def list_constraint_states(
        self, table_name: str, schema: Optional[str] = None
    ) -> List[ConstraintState]:
        """Read every constraint on the table, including its trust state."""
        target = schema if schema is not None else self.default_schema
        states: List[ConstraintState] = []
        for constraint in await self.list_constraints(table_name, target):
            disabled = self._as_flag(constraint.is_disabled) is True
            states.append(
                ConstraintState(
                    name=constraint.name,
                    table=constraint.table or table_name,
                    kind=_CONSTRAINT_STATE_KIND.get(
                        constraint.constraint_type,
                        constraint.constraint_type.lower() or "constraint",
                    ),
                    schema=constraint.schema if constraint.schema is not None else target,
                    validated=self._as_flag(constraint.is_not_trusted) is not True,
                    enforced=not disabled,
                    deferred=False,
                    disabled=disabled,
                    raw={
                        "constraint_type": constraint.constraint_type,
                        "constraint_type_desc": constraint.constraint_type_desc,
                        "columns": constraint.columns,
                        "definition": constraint.definition,
                        "referenced_table": constraint.referenced_table,
                        "is_system_named": constraint.is_system_named,
                    },
                )
            )
        return states

    async def list_sequence_states(
        self, schema: Optional[str] = None
    ) -> List[SequenceState]:
        """Read this schema's sequences as core's neutral state."""
        return self.parse_sequence_states(await self.list_sequences(schema))

    async def list_derived_objects(
        self, table_name: str, schema: Optional[str] = None
    ) -> List[DerivedObjectState]:
        """Read the objects this table's declarations caused the engine to make."""
        target = schema if schema is not None else self.default_schema
        key = self._cache.key(
            IntrospectionScope.TABLE,
            table_name,
            schema=target,
            extra="derived_objects",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        objects: List[DerivedObjectState] = []
        for constraint in await self.list_constraints(table_name, target):
            if constraint.constraint_type == "D" and not constraint.is_system_named:
                objects.append(
                    DerivedObjectState(
                        kind="named_default",
                        name=constraint.name,
                        owned_by=(
                            constraint.columns[0] if constraint.columns else None
                        ),
                        raw={
                            "definition": constraint.definition,
                            "is_system_named": constraint.is_system_named,
                        },
                    )
                )

        if self._get_version() >= _TEMPORAL_TABLE_VERSION:
            sql, params = self.temporal_history_list_statement(
                table_name=table_name, schema=target
            ).to_sql()
            for row in await self._executor.execute(sql, params):
                history = row.get("history_table")
                if history:
                    objects.append(
                        DerivedObjectState(
                            kind="history_table",
                            name=history,
                            owned_by=table_name,
                            raw={
                                "schema": row.get("history_schema"),
                                "temporal_type": self._as_int(
                                    row.get("temporal_type")
                                ),
                            },
                        )
                    )

        objects.sort(key=lambda item: (item.kind, item.name))
        self._cache.set(key, objects)
        return objects

    async def item_exists(
        self, kind: ItemKind, name: str, schema: Optional[str] = None
    ) -> bool:
        """Whether a shared object of this kind exists.

        The async twin of the sync rule: a kind this engine does not have at
        all answers ``False``; a queried kind answers from the catalogue; a
        kind it has but this backend cannot query is refused.
        """
        if not isinstance(kind, ItemKind):
            try:
                kind = ItemKind(kind)
            except ValueError:
                self._refuse("StructureIntrospectionSupport", "item_exists")

        if kind in self.ITEM_KINDS_ABSENT:
            return False
        if kind not in self.ITEM_KINDS_QUERIED:
            self._refuse("StructureIntrospectionSupport", "item_exists")
            return False

        if kind is ItemKind.SCHEMA:
            return name in await self.list_schemas()
        if kind is ItemKind.TABLE:
            return await self.table_exists(name, schema)
        if kind is ItemKind.SEQUENCE:
            return any(
                sequence.name == name
                for sequence in await self.list_sequences(schema)
            )
        if kind is ItemKind.TYPE:
            return await self.get_type_info(name, schema) is not None
        if kind is ItemKind.FUNCTION:
            return any(
                routine.name == name
                for routine in await self.list_functions(schema)
            )
        if kind is ItemKind.PARTITION_FUNCTION:
            statement = self.partition_function_statement(function_name=name)
        else:
            statement = self.partition_scheme_statement(scheme_name=name)

        cache_key = self._cache.key(
            IntrospectionScope.PARTITION, name, extra=f"exists:{kind.value}"
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        sql, params = statement.to_sql()
        exists = bool(await self._executor.execute(sql, params))
        self._cache.set(cache_key, exists)
        return exists

