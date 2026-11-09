# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/introspection.py
"""Which catalogue questions SQL Server can answer, and how it writes them.

This backend introspects fully -- catalog views, ``sys.tables``/``sys.columns``/
``sys.indexes``, ``OBJECT_DEFINITION`` for routine bodies, and the live CLI is
covered by tests against a real server. It nevertheless reported
``supports_introspection() = False`` and every per-kind answer with it, because
it never declared them and inherited core's default of ``False``.

That default is conservative on purpose: a backend that cannot answer says so,
and a caller gating on the switch is not misled. The cost is the opposite error
-- a backend that *can* answer but says it cannot, which is what happened here.
A caller gating on these switches would have concluded SQL Server has no
introspection at all, while its CLI offered twelve types.

So the switches are declared, one per family, and each says what SQL Server
actually answers. They are placed in a mixin of their own, because this
backend keeps its capability answers next to the concern they describe, and
because a caller should be able to find "what can I ask" in one place.

The mixin precedes the core bundle it overrides in ``SQLServerDialect``'s base
list; see the comment there for why the position matters.

The questions themselves are expression trees, and the text they render is
written here too, in ``format_*_query_statement``: a SQL string is a formatting
artefact and belongs to the dialect (org guide §16.2). That covers the families
core models *and* the ones only SQL Server has -- the primary key, schemas,
extended properties, routines and sequences -- whose statements live in
``expression/introspection.py``. The introspector above this layer constructs a
statement and executes what these return, so no family is spelled anywhere but
in this module.
"""

from typing import List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.introspection.types import ProfileSource

from ..query_nodes import SQLServerNodeBuilderMixin

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase
    from rhosocial.activerecord.backend.introspection.types import IntrospectionScope
    from rhosocial.activerecord.backend.expression.introspection import (
        ColumnDataProfileQueryStatement,
        ColumnInfoQueryStatement,
        ColumnValueSampleQueryStatement,
        DatabaseInfoQueryStatement,
        ForeignKeyQueryStatement,
        IndexInfoQueryStatement,
        JoinCoverageQueryStatement,
        TableListQueryStatement,
        TriggerListQueryStatement,
        ViewInfoQueryStatement,
        ViewListQueryStatement,
        UnusedIndexesQueryStatement,
        IndexUsageStatsQueryStatement,
        RuntimeMetricsQueryStatement,
        ObjectDependencyQueryStatement,
    )
    from ..expression.introspection import (
        SQLServerConstraintListQueryStatement,
        SQLServerExtendedPropertyListQueryStatement,
        SQLServerPartitionAlignedIndexListQueryStatement,
        SQLServerPartitionBoundaryListQueryStatement,
        SQLServerPartitionFunctionListQueryStatement,
        SQLServerPartitionSchemeListQueryStatement,
        SQLServerPrimaryKeyQueryStatement,
        SQLServerRoutineListQueryStatement,
        SQLServerSchemaListQueryStatement,
        SQLServerSequenceListQueryStatement,
        SQLServerTypeListQueryStatement,
    )

__all__ = ["DEFAULT_SCHEMA", "SQLServerIntrospectionMixin"]

#: The schema a name is resolved in when the caller names none. Declared once
#: so the introspector's ``default_schema`` and the statements below cannot
#: drift apart.
DEFAULT_SCHEMA = "dbo"

#: The ``sys.extended_properties.class_desc`` values SQL Server documents.
#: The property table is shared by objects, columns, schemas, indexes,
#: parameters and so on, and ``major_id``/``minor_id`` mean something
#: different for each; accepting a name outside this set would silently
#: return nothing instead of saying the family is unknown.
_EXTENDED_PROPERTY_CLASSES = frozenset(
    {
        "DATABASE",
        "OBJECT_OR_COLUMN",
        "PARAMETER",
        "SCHEMA",
        "DATABASE_PRINCIPAL",
        "ASSEMBLY",
        "TYPE",
        "INDEX",
        "XML_SCHEMA_COLLECTION",
        "XML_SCHEMA_NAMESPACE",
        "TYPE_SCHEMA",
        "XML_INDEX",
        "PLAN_GUIDE",
    }
)

#: The extended-property classes whose ``major_id`` is an object id, and which
#: therefore have a schema the ``sys.objects``/``sys.schemas`` join can narrow.
#: Every other class names an id in its own space, so a schema filter would be
#: a silent "no rows" rather than a contradiction -- refused before the query
#: is built, below.
_OBJECT_SCOPED_PROPERTY_CLASSES = frozenset({"OBJECT_OR_COLUMN", "INDEX"})

#: ``sys.objects.type`` codes the table question admits, and the spellings a
#: caller can name a kind with. ``U`` is a user table, ``V`` a view and ``S``
#: a system table; ``INFORMATION_SCHEMA.TABLES`` would have said "BASE TABLE"
#: or "VIEW" and dropped the ``S`` rows altogether, which is why the table
#: list reads ``sys.objects`` instead. See ``format_table_list_query_statement``.
_TABLE_KIND_CODES = {
    "TABLE": ("U",),
    "BASE TABLE": ("U",),
    "VIEW": ("V",),
    "SYSTEM TABLE": ("S",),
    "SYSTEM_TABLE": ("S",),
}

#: ``sys.sequences`` stores these as ``sql_variant``. The ODBC driver refuses
#: to fetch that type (``HY106``), so every one of them is cast to text in the
#: statement. Keeping the list in one place is what stops a later column from
#: being added to the projection without its cast.
_SEQUENCE_NUMERIC_COLUMNS = (
    "start_value",
    "increment",
    "minimum_value",
    "maximum_value",
    "current_value",
)


class SQLServerIntrospectionMixin(SQLServerNodeBuilderMixin):
    """SQL Server's answers to the shared catalogue capability questions.

    Each ``supports_*`` says which catalogue view answers the family; each
    ``format_*_query_statement`` renders the question from the nodes the
    statement carries.
    """

    @property
    def _node_dialect(self) -> "SQLDialectBase":
        """This object *is* the dialect, so nodes bind straight to it."""
        return self

    def supports_introspection(self) -> bool:
        """SQL Server introspects through its catalog views."""
        return True

    def supports_database_info(self) -> bool:
        """``sys.databases`` and ``@@VERSION`` answer for the instance."""
        return True

    def supports_table_introspection(self) -> bool:
        """``sys.tables`` joined to ``sys.schemas``."""
        return True

    def supports_column_introspection(self) -> bool:
        """``sys.columns``, which also carries identity and nullable."""
        return True

    def supports_index_introspection(self) -> bool:
        """``sys.indexes`` with ``sys.index_columns`` for the ordering."""
        return True

    def supports_foreign_key_introspection(self) -> bool:
        """``sys.foreign_keys`` and ``sys.foreign_key_columns``."""
        return True

    def supports_view_introspection(self) -> bool:
        """``sys.views``, with the definition from ``OBJECT_DEFINITION``."""
        return True

    def supports_trigger_introspection(self) -> bool:
        """``sys.triggers``, which also distinguishes INSTEAD OF."""
        return True

    def supports_extended_property_introspection(self) -> bool:
        """``sys.extended_properties``, where ``MS_Description`` lives.

        Declared as its own family rather than folded into
        ``supports_table_introspection``: "can this server list and describe
        tables" and "can it read the properties hanging off their objects" are
        two questions, and a caller gating on the first would be told nothing
        about the second.
        """
        return True

    def supports_table_storage_introspection(self) -> bool:
        """``sys.dm_db_partition_stats`` answers per-table storage.

        SQL Server's storage is row-plus-index shaped -- a heap or clustered
        index holds the rows, nonclustered indexes hold the rest -- so all
        four narrow slots of ``IntrospectionTableInfo`` can be answered from
        one partition-stats read per table: ``size_bytes`` the total,
        ``data_size_bytes`` the table's own partitions and
        ``index_size_bytes`` the nonclustered ones' pages. Before this was
        declared, the listing left every slot ``None`` while the engine was
        able to answer; a caller gating on the switch now learns that.
        """
        return True

    def supports_partition_info(self) -> bool:
        """``sys.partition_*`` answers partition functions, schemes and indexes.

        This is core's name for the family; the backend-local spelling is
        ``supports_partition_metadata_introspection`` on the partition mixin.
        Both answer the same engine question, so a caller may gate on either.
        """
        return self.version_at_least((10, 0, 0))

    def supports_type_introspection(self) -> bool:
        """``sys.types``/``sys.table_types`` answer user-defined types.

        The family covers alias types, table types and CLR types; system
        types are deliberately not listed because a model never has to map
        one back to a declaration. The 2008 (10.0) floor is where
        ``sys.table_types`` -- and the ``is_table_type`` flag on
        ``sys.types`` -- arrived, so a server older than it cannot answer the
        question this family asks.
        """
        return self.version_at_least((10, 0, 0))

    def supports_constraint_introspection(self) -> bool:
        """``sys.objects`` and the constraint views answer constraint objects.

        A constraint is one object with one row in ``sys.objects``, and the
        check and default constraints have no other family: the index family
        answers primary and unique keys, the foreign-key family answers
        foreign keys, but neither answers the two constraints that carry an
        expression.
        """
        return True

    def get_supported_introspection_scopes(self) -> List["IntrospectionScope"]:
        """The catalogue families this dialect answers, as core names them.

        Core's default is the empty list -- the right answer for a backend that
        cannot introspect, and the same wrong answer the switches above were
        declared to stop giving here: a caller asking "what can I introspect"
        was told "nothing" by a server that answers eleven families.
        ``SEQUENCE`` is included because ``IntrospectionScope`` has it and
        ``sys.sequences`` answers it.
        """
        from rhosocial.activerecord.backend.introspection.types import (
            IntrospectionScope,
        )

        return [
            IntrospectionScope.DATABASE,
            IntrospectionScope.TABLE,
            IntrospectionScope.COLUMN,
            IntrospectionScope.INDEX,
            IntrospectionScope.FOREIGN_KEY,
            IntrospectionScope.VIEW,
            IntrospectionScope.TRIGGER,
            IntrospectionScope.SEQUENCE,
        ]

    # ========== Query Formatting ==========
    #
    # The parameter positions are the ones the concatenated form used: a
    # schema or table name the caller supplied stays bound, and a value that
    # is part of the question (``'BASE TABLE'``, ``'PRIMARY KEY'``,
    # ``'IsIdentity'``) stays an inline literal, so every caller keeps the
    # parameter tuple it already had.

    def _cast_server_property(self, name: str, alias: Optional[str] = None):
        """``CAST(SERVERPROPERTY('<name>') AS NVARCHAR(128))``, optionally aliased.

        The property name is a literal of the statement, not data, so it stays
        inline: the request carries no parameters.
        """
        from rhosocial.activerecord.backend.expression import FunctionCall
        from ..expression.types import SQLServerNVarCharType

        node = FunctionCall(
            self._node_dialect, "SERVERPROPERTY", self._lit(name, inline=True)
        ).cast(SQLServerNVarCharType(self._node_dialect, 128))
        return node.as_(alias) if alias else node

    def _partition_stats_bytes(self, alias: str, *, heap: bool = False, nonclustered: bool = False):
        """One storage slot, read from ``sys.dm_db_partition_stats``.

        The view counts one row per partition of one index, which is where
        SQL Server answers "how much space does this table occupy": the
        partitions of ``index_id`` 0 (a heap) or 1 (a clustered index) are
        the table's own storage, and everything above 1 is a nonclustered
        index's. Which bucket *alias* asks for is the two flags; with
        neither, every partition of the object is summed -- the total.

        A view has no partition rows at all, so the scalar subquery answers
        NULL and the slot stays ``None``: an object whose storage is not a
        question the engine answers for it is a different answer from zero
        bytes, and claiming the zero would describe storage it does not have.

        The page size is a constant of this engine -- SQL Server pages are
        8 KiB with no configuration switch, unlike PostgreSQL's or Oracle's
        -- so the multiplication is a fact of the engine rather than a read
        that could come back unknown.
        """
        bucket = None
        if heap:
            bucket = self._in(self._col("index_id", "ps"), (0, 1))
        elif nonclustered:
            bucket = self._gt(
                self._col("index_id", "ps"), self._lit(1, inline=True)
            )
        conditions = [
            self._eq(self._col("object_id", "ps"), self._col("object_id", "o")),
        ]
        if bucket is not None:
            conditions.append(bucket)
        return self._mul(
            self._subquery(
                [self._fn("SUM", self._col("used_page_count", "ps"))],
                from_=self._relation("dm_db_partition_stats", "sys", alias="ps"),
                where=self._and(*conditions),
            ),
            self._lit(8192, inline=True),
        ).as_(alias)

    def format_database_info_query_statement(
        self, expr: "DatabaseInfoQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format the database information query.

        Args:
            expr: The statement; SQL Server identifies itself, so no
                parameter of it is consulted.

        Returns:
            Tuple of (SQL string, parameters tuple).
        """
        from rhosocial.activerecord.backend.expression import FunctionCall

        # No FROM: this query reads no table, it asks the engine a question.
        return self._select(
            [
                FunctionCall(self._node_dialect, "DB_NAME", alias="db_name"),
                self._cast_server_property("ProductVersion", "version"),
                self._cast_server_property("Collation", "collation"),
                self._cast_server_property("Edition", "edition"),
            ]
        )

    def format_table_list_query_statement(
        self, expr: "TableListQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format the table list query.

        ``sys.objects`` is read rather than ``INFORMATION_SCHEMA.TABLES``
        because the information-schema view folds the object kinds into two
        two-word spellings and omits every ``is_ms_shipped`` row: the one row
        that says "this is a system table" never reached the parser, so a
        caller asking for system tables got a shorter list with no word about
        it. The catalogue view carries ``sys.objects.type`` (``U`` user
        table, ``V`` view, ``S`` system table) and ``is_ms_shipped``, which
        are the two facts the question is about.

        ``include_system`` is therefore honoured here: adopting ``S`` and
        dropping the ``is_ms_shipped`` filter is what makes the CLI's
        ``--include-system`` flag change the answer instead of being ignored.
        An explicit ``table_type`` narrows the admitted codes and, when it
        names system tables, implies ``include_system`` for that query.

        ``MS_Description`` is joined in as ``table_comment``: SQL Server has no
        ``COMMENT`` clause, and ``sys.extended_properties`` is the only place a
        table's comment lives. Without the join ``TableInfo.comment`` was
        permanently ``None`` -- a declared field no backend could fill. The
        join is a ``LEFT JOIN`` on the object-level property alone
        (``minor_id = 0``), so a table without a comment still row-appears and a
        column-level description cannot be mistaken for the table's.

        The storage slots ride the same listing as three scalar subqueries
        rather than a join: ``sys.dm_db_partition_stats`` holds one row per
        partition per index, and a GROUP BY over it would fold the object
        kinds -- a view, which has no partitions, would vanish from the
        listing instead of answering ``None`` for its storage. A subquery per
        slot keeps every row and says plainly which slots a view cannot
        answer; see :meth:`_partition_stats_bytes`.
        """
        params = expr.get_params()
        target = params.get("schema") or DEFAULT_SCHEMA
        include_views = params.get("include_views", True)
        include_system = params.get("include_system", False)
        table_type = params.get("table_type")

        if table_type:
            codes = _TABLE_KIND_CODES.get(
                str(table_type).upper(), (str(table_type),)
            )
        else:
            codes = ("U", "V") if include_views else ("U",)
            if include_system:
                codes = codes + ("S",)

        conditions = [self._eq(self._col("name", "s"), self._lit(target))]
        conditions.append(self._in(self._col("type", "o"), codes))
        if not include_system and "S" not in codes:
            # A system table is an ``is_ms_shipped`` object; without this the
            # flag would still be ignored for the kinds a caller named.
            conditions.append(
                self._eq(self._col("is_ms_shipped", "o"), self._lit(0, inline=True))
            )

        joined = self._join(
            self._join(
                self._relation("objects", "sys", alias="o"),
                self._relation("schemas", "sys", alias="s"),
                condition=self._eq(
                    self._col("schema_id", "o"), self._col("schema_id", "s")
                ),
            ),
            self._relation("extended_properties", "sys", alias="ep"),
            join_type="LEFT JOIN",
            condition=self._and(
                self._eq(self._col("major_id", "ep"), self._col("object_id", "o")),
                self._eq(self._col("minor_id", "ep"), self._lit(0, inline=True)),
                self._eq(self._col("class", "ep"), self._lit(1, inline=True)),
                self._eq(
                    self._col("name", "ep"),
                    self._lit("MS_Description", inline=True),
                ),
            ),
        )
        return self._select(
            [
                self._col("name", "o", alias="TABLE_NAME"),
                self._col("type", "o", alias="TABLE_TYPE"),
                self._cast(self._col("value", "ep"), "NVARCHAR(4000)").as_(
                    "table_comment"
                ),
                self._partition_stats_bytes("size_bytes"),
                self._partition_stats_bytes("data_size_bytes", heap=True),
                self._partition_stats_bytes("index_size_bytes", nonclustered=True),
            ],
            from_=joined,
            where=self._and(*conditions),
            order_by=[self._col("name", "o")],
        )

    def format_column_info_query_statement(
        self, expr: "ColumnInfoQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format the column information query.

        ``DATETIME_PRECISION`` is projected because it is the only place the
        fractional-seconds precision of ``time``/``datetime2``/
        ``datetimeoffset`` lives. ``include_hidden`` is part of the shared
        question; SQL Server's catalog reports no hidden columns.

        ``MS_Description`` is joined in as ``column_comment``, the second half
        of the comment story the table list tells: the property is keyed by the
        object id the column belongs to and the column's own id, neither of
        which ``INFORMATION_SCHEMA.COLUMNS`` carries, so ``sys.columns`` is
        joined to reach them. ``OBJECT_ID`` is evaluated on the qualified name
        this statement already builds, and the join is a ``LEFT JOIN`` so a
        column without a description keeps its row.
        """
        from rhosocial.activerecord.backend.expression import FunctionCall, JoinClause
        from rhosocial.activerecord.backend.expression.operators import (
            ArithmeticOperation,
            ArithmeticOperator,
        )

        params = expr.get_params()
        table_name = params.get("table_name")
        target = params.get("schema") or DEFAULT_SCHEMA

        # OBJECT_ID takes the qualified object name as one string. SQL Server
        # spells string concatenation with ``+`` (``||`` only from 2025), so
        # this is the arithmetic ``add`` node, not the standard concatenation.
        qualified_name = ArithmeticOperation(
            self._node_dialect,
            ArithmeticOperator.ADD,
            ArithmeticOperation(
                self._node_dialect,
                ArithmeticOperator.ADD,
                self._col("TABLE_SCHEMA", "c"),
                self._lit(".", inline=True),
            ),
            self._col("TABLE_NAME", "c"),
        )
        object_id = FunctionCall(self._node_dialect, "OBJECT_ID", qualified_name)
        is_identity = FunctionCall(
            self._node_dialect,
            "COLUMNPROPERTY",
            object_id,
            self._col("COLUMN_NAME", "c"),
            self._lit("IsIdentity", inline=True),
            alias="IS_IDENTITY",
        )
        joined = JoinClause(
            self._node_dialect,
            JoinClause(
                self._node_dialect,
                self._relation("COLUMNS", "INFORMATION_SCHEMA", alias="c"),
                self._relation("columns", "sys", alias="sc"),
                join_type="LEFT JOIN",
                condition=self._and(
                    self._eq(self._col("object_id", "sc"), object_id),
                    self._eq(self._col("name", "sc"), self._col("COLUMN_NAME", "c")),
                ),
            ),
            self._relation("extended_properties", "sys", alias="epc"),
            join_type="LEFT JOIN",
            condition=self._and(
                self._eq(self._col("class", "epc"), self._lit(1, inline=True)),
                self._eq(self._col("major_id", "epc"), self._col("object_id", "sc")),
                self._eq(self._col("minor_id", "epc"), self._col("column_id", "sc")),
                self._eq(
                    self._col("name", "epc"),
                    self._lit("MS_Description", inline=True),
                ),
            ),
        )
        return self._select(
            [
                self._col("COLUMN_NAME", "c"),
                self._col("DATA_TYPE", "c"),
                self._col("IS_NULLABLE", "c"),
                self._col("COLUMN_DEFAULT", "c"),
                self._col("CHARACTER_MAXIMUM_LENGTH", "c"),
                self._col("NUMERIC_PRECISION", "c"),
                self._col("NUMERIC_SCALE", "c"),
                self._col("DATETIME_PRECISION", "c"),
                self._col("ORDINAL_POSITION", "c"),
                self._col("COLLATION_NAME", "c"),
                is_identity,
                self._cast(self._col("value", "epc"), "NVARCHAR(4000)").as_(
                    "column_comment"
                ),
            ],
            from_=joined,
            where=self._and(
                self._eq(self._col("TABLE_SCHEMA", "c"), self._lit(target)),
                self._eq(self._col("TABLE_NAME", "c"), self._lit(table_name)),
            ),
            order_by=[self._col("ORDINAL_POSITION", "c")],
        )

    def format_index_info_query_statement(
        self, expr: "IndexInfoQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format the index information query."""
        from rhosocial.activerecord.backend.expression import IsNullPredicate, JoinClause

        params = expr.get_params()
        table_name = params.get("table_name")
        target = params.get("schema") or DEFAULT_SCHEMA

        joins = JoinClause(
            self._node_dialect,
            JoinClause(
                self._node_dialect,
                JoinClause(
                    self._node_dialect,
                    JoinClause(
                        self._node_dialect,
                        self._relation("indexes", "sys", alias="i"),
                        self._relation("tables", "sys", alias="t"),
                        join_type="JOIN",
                        condition=self._eq(
                            self._col("object_id", "i"), self._col("object_id", "t")
                        ),
                    ),
                    self._relation("schemas", "sys", alias="s"),
                    join_type="JOIN",
                    condition=self._eq(
                        self._col("schema_id", "t"), self._col("schema_id", "s")
                    ),
                ),
                self._relation("index_columns", "sys", alias="ic"),
                join_type="JOIN",
                condition=self._and(
                    self._eq(self._col("object_id", "i"), self._col("object_id", "ic")),
                    self._eq(self._col("index_id", "i"), self._col("index_id", "ic")),
                ),
            ),
            self._relation("columns", "sys", alias="c"),
            join_type="JOIN",
            condition=self._and(
                self._eq(self._col("object_id", "ic"), self._col("object_id", "c")),
                self._eq(self._col("column_id", "ic"), self._col("column_id", "c")),
            ),
        )
        return self._select(
            [
                self._col("name", "i", alias="index_name"),
                self._col("is_unique", "i"),
                self._col("is_primary_key", "i"),
                self._col("type_desc", "i", alias="index_type"),
                self._col("name", "c", alias="column_name"),
                self._col("key_ordinal", "ic", alias="column_position"),
                self._col("is_descending_key", "ic"),
            ],
            from_=joins,
            where=self._and(
                self._eq(self._col("name", "s"), self._lit(target)),
                self._eq(self._col("name", "t"), self._lit(table_name)),
                IsNullPredicate(self._node_dialect, self._col("name", "i"), is_not=True),
            ),
            order_by=[self._col("name", "i"), self._col("key_ordinal", "ic")],
        )

    def format_foreign_key_query_statement(
        self, expr: "ForeignKeyQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format the foreign key information query."""
        from rhosocial.activerecord.backend.expression import FunctionCall, JoinClause

        params = expr.get_params()
        table_name = params.get("table_name")
        target = params.get("schema") or DEFAULT_SCHEMA

        joins = JoinClause(
            self._node_dialect,
            JoinClause(
                self._node_dialect,
                JoinClause(
                    self._node_dialect,
                    self._relation("foreign_keys", "sys", alias="fk"),
                    self._relation("foreign_key_columns", "sys", alias="fc"),
                    join_type="JOIN",
                    condition=self._eq(
                        self._col("object_id", "fk"),
                        self._col("constraint_object_id", "fc"),
                    ),
                ),
                self._relation("tables", "sys", alias="t"),
                join_type="JOIN",
                condition=self._eq(
                    self._col("parent_object_id", "fk"), self._col("object_id", "t")
                ),
            ),
            self._relation("schemas", "sys", alias="s"),
            join_type="JOIN",
            condition=self._eq(
                self._col("schema_id", "t"), self._col("schema_id", "s")
            ),
        )
        return self._select(
            [
                self._col("name", "fk", alias="fk_name"),
                FunctionCall(
                    self._node_dialect,
                    "COL_NAME",
                    self._col("parent_object_id", "fc"),
                    self._col("parent_column_id", "fc"),
                    alias="col_name",
                ),
                FunctionCall(
                    self._node_dialect,
                    "OBJECT_NAME",
                    self._col("referenced_object_id", "fk"),
                    alias="ref_table",
                ),
                FunctionCall(
                    self._node_dialect,
                    "COL_NAME",
                    self._col("referenced_object_id", "fc"),
                    self._col("referenced_column_id", "fc"),
                    alias="ref_col",
                ),
                self._col("delete_referential_action_desc", "fk", alias="on_delete"),
                self._col("update_referential_action_desc", "fk", alias="on_update"),
                self._col("constraint_column_id", "fc", alias="col_position"),
            ],
            from_=joins,
            where=self._and(
                self._eq(self._col("name", "s"), self._lit(target)),
                self._eq(self._col("name", "t"), self._lit(table_name)),
            ),
            order_by=[
                self._col("name", "fk"),
                self._col("constraint_column_id", "fc"),
            ],
        )

    def format_view_list_query_statement(
        self, expr: "ViewListQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format the view list query.

        ``include_system`` is not consulted for the same reason as in the table
        list: ``INFORMATION_SCHEMA.VIEWS`` holds no server-owned row here.

        The definition is read here, not only in the single-view query: the
        list used to project ``TABLE_NAME`` alone, so every row of ``introspect
        views`` carried ``definition = null`` although the single-view question
        right below had always projected it. Both read ``VIEW_DEFINITION`` from
        the same ``INFORMATION_SCHEMA.VIEWS`` row, so the list and the
        single-view answer cannot disagree.

        ``VIEW_DEFINITION`` is ``NULL`` for a view whose text the caller may not
        read -- unlike ``OBJECT_DEFINITION()``, which returns the text to a
        caller holding ``VIEW DEFINITION``. Keeping both questions on the
        information-schema view is deliberate: one source, one visibility rule.
        """
        params = expr.get_params()
        target = params.get("schema") or DEFAULT_SCHEMA
        return self._select(
            [
                self._col("TABLE_NAME", alias="view_name"),
                self._col("VIEW_DEFINITION", alias="definition"),
                self._col("IS_UPDATABLE"),
            ],
            from_=self._relation("VIEWS", "INFORMATION_SCHEMA"),
            where=self._eq(self._col("TABLE_SCHEMA"), self._lit(target)),
            order_by=[self._col("TABLE_NAME")],
        )

    def format_view_info_query_statement(
        self, expr: "ViewInfoQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format the single-view query.

        ``include_columns`` is part of the shared question; the columns of a
        view are read through the column statement, so this one always returns
        the view's own row.
        """
        params = expr.get_params()
        view_name = params.get("view_name")
        target = params.get("schema") or DEFAULT_SCHEMA
        return self._select(
            [
                self._col("TABLE_NAME", alias="view_name"),
                self._col("VIEW_DEFINITION", alias="definition"),
                self._col("IS_UPDATABLE"),
            ],
            from_=self._relation("VIEWS", "INFORMATION_SCHEMA"),
            where=self._and(
                self._eq(self._col("TABLE_SCHEMA"), self._lit(target)),
                self._eq(self._col("TABLE_NAME"), self._lit(view_name)),
            ),
        )

    def format_trigger_list_query_statement(
        self, expr: "TriggerListQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format the trigger list query, optionally for one table.

        The firing events are not a column of ``sys.triggers``: they live one
        table over, in ``sys.trigger_events``, one row per event
        (``INSERT``/``UPDATE``/``DELETE``). Joining it is what makes ``events``
        answerable at all -- the parser used to write ``[]`` for every trigger
        because nothing selected the events. The join is a ``LEFT JOIN``: a
        trigger row with no event of its own is still a trigger, and dropping it
        would trade an empty list for a missing trigger.

        One trigger now answers with one row per event, so the rows of a
        trigger are contiguous (the list is ordered by trigger name, then by
        event) and the parser folds them back together.
        """
        from rhosocial.activerecord.backend.expression import FunctionCall, JoinClause

        params = expr.get_params()
        table_name = params.get("table_name")
        target = params.get("schema") or DEFAULT_SCHEMA

        joins = JoinClause(
            self._node_dialect,
            JoinClause(
                self._node_dialect,
                JoinClause(
                    self._node_dialect,
                    self._relation("triggers", "sys", alias="tr"),
                    self._relation("trigger_events", "sys", alias="te"),
                    join_type="LEFT JOIN",
                    condition=self._eq(
                        self._col("object_id", "te"), self._col("object_id", "tr")
                    ),
                ),
                self._relation("tables", "sys", alias="t"),
                join_type="JOIN",
                condition=self._eq(
                    self._col("parent_id", "tr"), self._col("object_id", "t")
                ),
            ),
            self._relation("schemas", "sys", alias="s"),
            join_type="JOIN",
            condition=self._eq(
                self._col("schema_id", "t"), self._col("schema_id", "s")
            ),
        )
        conditions = [self._eq(self._col("name", "s"), self._lit(target))]
        if table_name:
            conditions.append(self._eq(self._col("name", "t"), self._lit(table_name)))
        return self._select(
            [
                self._col("name", "tr", alias="trigger_name"),
                self._col("name", "t", alias="table_name"),
                self._col("is_disabled", "tr"),
                self._col("is_instead_of_trigger", "tr"),
                self._col("type_desc", "te", alias="event"),
                FunctionCall(
                    self._node_dialect,
                    "OBJECT_DEFINITION",
                    self._col("object_id", "tr"),
                    alias="definition",
                ),
            ],
            from_=joins,
            where=self._and(*conditions),
            order_by=[self._col("name", "tr"), self._col("type_desc", "te")],
        )

    # ------------------------------------------------------------------ #
    # SQL Server's own object families
    #
    # The primary key, schemas, extended properties, routines and sequences
    # have no core statement class: the question is this backend's own. Each
    # formatter below renders one of those statements from the nodes, and the
    # construction lives here because the SQL is the dialect's -- the
    # introspector only constructs the statement and executes what comes back.
    # ------------------------------------------------------------------ #

    def format_primary_key_query_statement(
        self, expr: "SQLServerPrimaryKeyQueryStatement"
    ) -> Tuple[str, tuple]:
        """Render the primary-key column list of one table.

        The two catalogue views are joined on the constraint name *and* the
        schema, so a same-named constraint in another schema cannot contribute
        a column to this table's key.
        """
        from rhosocial.activerecord.backend.expression import JoinClause

        params = expr.get_params()
        table_name = params.get("table_name")
        target = params.get("schema")

        join = JoinClause(
            self._node_dialect,
            self._relation("TABLE_CONSTRAINTS", "INFORMATION_SCHEMA", alias="tc"),
            self._relation("CONSTRAINT_COLUMN_USAGE", "INFORMATION_SCHEMA", alias="ccu"),
            join_type="JOIN",
            condition=self._and(
                self._eq(
                    self._col("CONSTRAINT_NAME", "tc"),
                    self._col("CONSTRAINT_NAME", "ccu"),
                ),
                self._eq(
                    self._col("TABLE_SCHEMA", "tc"), self._col("TABLE_SCHEMA", "ccu")
                ),
            ),
        )
        return self._select(
            [self._col("COLUMN_NAME", "ccu")],
            from_=join,
            where=self._and(
                self._eq(self._col("TABLE_SCHEMA", "tc"), self._lit(target)),
                self._eq(self._col("TABLE_NAME", "tc"), self._lit(table_name)),
                self._eq(
                    self._col("CONSTRAINT_TYPE", "tc"),
                    self._lit("PRIMARY KEY", inline=True),
                ),
            ),
        )

    def format_schema_list_query_statement(
        self, expr: "SQLServerSchemaListQueryStatement"
    ) -> Tuple[str, tuple]:
        """Render ``sys.schemas`` with the owning principal's name.

        ``sys.schemas`` is joined to ``sys.database_principals`` on
        ``principal_id`` -- not on ``name`` -- because a schema and its owner
        need not share a name. The join is a ``LEFT JOIN``: the catalogue
        keeps a schema after its owning principal is dropped, leaving
        ``principal_id`` dangling, and that row is still a schema.
        """
        joined = self._join(
            self._relation("schemas", "sys", alias="s"),
            self._relation("database_principals", "sys", alias="p"),
            join_type="LEFT JOIN",
            condition=self._eq(
                self._col("principal_id", "s"), self._col("principal_id", "p")
            ),
        )
        return self._select(
            [
                self._col("schema_id", "s"),
                self._col("name", "s", alias="schema_name"),
                self._col("name", "p", alias="owner"),
            ],
            from_=joined,
            order_by=[self._col("name", "s")],
        )

    def format_extended_property_list_query_statement(
        self, expr: "SQLServerExtendedPropertyListQueryStatement"
    ) -> Tuple[str, tuple]:
        """Render ``sys.extended_properties`` for one object, optionally one column.

        Two ways to name the object, one query each: by ``major_id`` when the
        caller already has the id, or by ``table_name`` when all it has is a
        name. The named form joins ``sys.tables`` and ``sys.schemas`` -- the
        one place a table's name resolves to an id -- so the caller needs no
        first round trip to turn a name into a ``major_id``.

        ``value`` is ``sql_variant`` and the driver cannot fetch it, so it is
        cast to ``NVARCHAR(4000)`` in the statement: the property text is what
        a caller wants, and truncation beyond 4000 characters is impossible to
        avoid without a second round trip.

        The schema filter is the one part that is not a column of
        ``sys.extended_properties``: it resolves ``major_id`` through
        ``sys.objects`` and ``sys.schemas``. That join only means something
        for the object-scoped classes (``OBJECT_OR_COLUMN`` above all), so
        asking for a schema while listing, say, ``DATABASE`` properties is a
        contradiction rather than an empty answer -- refused before the query
        is built.

        A ``table_name`` narrows the question even further: only
        ``OBJECT_OR_COLUMN`` properties hang off a table, so any other class
        asked by table name is refused rather than answered with no rows. The
        named selection can only reach what ``sys.tables`` holds -- base tables.
        A view's properties have no row there and are reachable through the
        ``major_id`` selection only.
        """
        params = expr.get_params()
        major_id = params.get("major_id")
        table_name = params.get("table_name")
        minor_id = params.get("minor_id")
        class_name = params.get("class_name")
        schema = params.get("schema")

        if class_name not in _EXTENDED_PROPERTY_CLASSES:
            raise ValueError(
                f"unknown extended-property class {class_name!r}; "
                f"expected one of {sorted(_EXTENDED_PROPERTY_CLASSES)}"
            )
        if schema is not None and class_name not in _OBJECT_SCOPED_PROPERTY_CLASSES:
            raise ValueError(
                f"a schema can only narrow object-scoped extended properties; "
                f"{class_name!r} has no schema"
            )

        if table_name is not None:
            if class_name != "OBJECT_OR_COLUMN":
                raise ValueError(
                    f"a table name only names OBJECT_OR_COLUMN properties; "
                    f"{class_name!r} keeps its objects in another catalogue"
                )
            target = schema or DEFAULT_SCHEMA
            joined = self._join(
                self._join(
                    self._relation("extended_properties", "sys", alias="ep"),
                    self._relation("tables", "sys", alias="t"),
                    join_type="JOIN",
                    condition=self._eq(
                        self._col("major_id", "ep"), self._col("object_id", "t")
                    ),
                ),
                self._relation("schemas", "sys", alias="s"),
                join_type="JOIN",
                condition=self._eq(
                    self._col("schema_id", "t"), self._col("schema_id", "s")
                ),
            )
            conditions = [
                self._eq(self._col("class_desc", "ep"), self._lit(class_name)),
                self._eq(self._col("name", "t"), self._lit(table_name)),
                self._eq(self._col("name", "s"), self._lit(target)),
            ]
            if minor_id is not None:
                conditions.append(
                    self._eq(self._col("minor_id", "ep"), self._lit(minor_id))
                )
            return self._select(
                self._extended_property_projection(),
                from_=joined,
                where=self._and(*conditions),
                order_by=[self._col("minor_id", "ep"), self._col("name", "ep")],
            )

        joined = self._join(
            self._relation("extended_properties", "sys", alias="ep"),
            self._relation("objects", "sys", alias="o"),
            join_type="LEFT JOIN",
            condition=self._eq(
                self._col("major_id", "ep"), self._col("object_id", "o")
            ),
        )
        joined = self._join(
            joined,
            self._relation("schemas", "sys", alias="s"),
            join_type="LEFT JOIN",
            condition=self._eq(
                self._col("schema_id", "o"), self._col("schema_id", "s")
            ),
        )

        conditions = [
            self._eq(self._col("major_id", "ep"), self._lit(major_id)),
            self._eq(self._col("class_desc", "ep"), self._lit(class_name)),
        ]
        if minor_id is not None:
            conditions.append(
                self._eq(self._col("minor_id", "ep"), self._lit(minor_id))
            )
        if schema is not None:
            conditions.append(self._eq(self._col("name", "s"), self._lit(schema)))

        return self._select(
            self._extended_property_projection(),
            from_=joined,
            where=self._and(*conditions),
            order_by=[self._col("minor_id", "ep"), self._col("name", "ep")],
        )

    def _extended_property_projection(self) -> list:

        """The extended-property columns both selections of that family project."""
        return [
            self._col("class", "ep", alias="class_id"),
            self._col("class_desc", "ep", alias="class_name"),
            self._col("major_id", "ep", alias="major_id"),
            self._col("minor_id", "ep", alias="minor_id"),
            self._col("name", "ep", alias="property_name"),
            self._cast(self._col("value", "ep"), "NVARCHAR(4000)").as_(
                "property_value"
            ),
        ]

    def format_routine_list_query_statement(
        self, expr: "SQLServerRoutineListQueryStatement"
    ) -> Tuple[str, tuple]:
        """Render the schema-scoped routines of the admitted ``sys.objects.type`` codes.

        One formatter for both families: a procedure is a routine whose
        ``sys.objects.type`` is ``P``/``PC`` and a function is one of the
        ``FN``/``IF``/``TF``/``FS``/``FT`` codes. What differs is the code
        set, and that is the parameter the statement carries.
        """
        params = expr.get_params()
        type_codes = params.get("type_codes")
        target = params.get("schema") or DEFAULT_SCHEMA

        joined = self._join(
            self._relation("objects", "sys", alias="o"),
            self._relation("schemas", "sys", alias="s"),
            join_type="JOIN",
            condition=self._eq(
                self._col("schema_id", "o"), self._col("schema_id", "s")
            ),
        )
        return self._select(
            [
                self._col("name", "o", alias="routine_name"),
                self._col("name", "s", alias="schema_name"),
                self._col("type", "o", alias="type_code"),
                self._col("type_desc", "o"),
                self._col("create_date", "o", alias="created_at"),
                self._col("modify_date", "o", alias="modified_at"),
                self._col("is_ms_shipped", "o"),
            ],
            from_=joined,
            where=self._and(
                self._in(self._col("type", "o"), type_codes),
                self._eq(self._col("name", "s"), self._lit(target)),
            ),
            order_by=[self._col("name", "o")],
        )

    def format_sequence_list_query_statement(
        self, expr: "SQLServerSequenceListQueryStatement"
    ) -> Tuple[str, tuple]:
        """Render ``sys.sequences`` with every ``sql_variant`` value cast to text.

        ``start_value``/``increment``/``minimum_value``/``maximum_value``/
        ``current_value`` are ``sql_variant``. pyodbc raises
        ``ODBC SQL type -25 is not yet supported`` on the very first of them,
        so a projection that selected them raw could not be fetched at all --
        which is why the cast is in the statement rather than the parser.
        """
        params = expr.get_params()
        target = params.get("schema") or DEFAULT_SCHEMA
        joined = self._join(
            self._relation("sequences", "sys", alias="q"),
            self._relation("schemas", "sys", alias="s"),
            join_type="JOIN",
            condition=self._eq(
                self._col("schema_id", "q"), self._col("schema_id", "s")
            ),
        )
        projection = [
            self._col("name", "q", alias="sequence_name"),
            self._col("name", "s", alias="schema_name"),
            self._fn(
                "TYPE_NAME", self._col("user_type_id", "q"), alias="data_type"
            ),
        ]
        for column in _SEQUENCE_NUMERIC_COLUMNS:
            projection.append(
                self._cast(
                    self._col(column, "q"), "NVARCHAR(64)"
                ).as_(column)
            )
        projection.extend(
            [
                self._col("is_cycling", "q"),
                self._col("is_cached", "q"),
                self._cast(self._col("cache_size", "q"), "BIGINT").as_(
                    "cache_size"
                ),
            ]
        )
        return self._select(
            projection,
            from_=joined,
            where=self._eq(self._col("name", "s"), self._lit(target)),
            order_by=[self._col("name", "q")],
        )

    # ------------------------------------------------------------------ #
    # Partitions, user-defined types and constraints
    #
    # These three families have no core statement class either. Partitions
    # are three catalogue questions because SQL Server's model has three
    # levels -- function, scheme and the index whose ``data_space_id`` is a
    # scheme -- and each is rendered here rather than folded into one join
    # that would multiply boundaries by destinations by indexes.
    # ------------------------------------------------------------------ #

    def format_partition_function_list_query_statement(
        self, expr: "SQLServerPartitionFunctionListQueryStatement"
    ) -> Tuple[str, tuple]:
        """Render ``sys.partition_functions`` with its parameter type.

        ``sys.partition_parameters`` carries the declared type: the
        function view itself does not. ``TYPE_NAME`` is asked twice, once for
        the user type and once for its system base, so an alias-typed function
        keeps both names. The parameter rows are folded into one function
        record by the parser.
        """
        joined = self._join(
            self._relation("partition_functions", "sys", alias="pf"),
            self._relation("partition_parameters", "sys", alias="pp"),
            join_type="LEFT JOIN",
            condition=self._eq(
                self._col("function_id", "pf"), self._col("function_id", "pp")
            ),
        )
        return self._select(
            [
                self._col("name", "pf", alias="partition_function"),
                self._col("function_id", "pf"),
                self._col("type", "pf", alias="function_type"),
                self._col("type_desc", "pf", alias="function_type_desc"),
                self._col("fanout", "pf"),
                self._col("boundary_value_on_right", "pf"),
                self._fn(
                    "TYPE_NAME", self._col("user_type_id", "pp"), alias="data_type"
                ),
                self._fn(
                    "TYPE_NAME", self._col("system_type_id", "pp"), alias="base_type"
                ),
                self._col("max_length", "pp"),
                self._col("precision", "pp"),
                self._col("scale", "pp"),
                self._col("collation_name", "pp", alias="collation"),
                self._col("parameter_id", "pp"),
            ],
            from_=joined,
            order_by=[
                self._col("name", "pf"),
                self._col("parameter_id", "pp"),
            ],
        )

    def format_partition_boundary_list_query_statement(
        self, expr: "SQLServerPartitionBoundaryListQueryStatement"
    ) -> Tuple[str, tuple]:
        """Render ``sys.partition_range_values`` with the value cast to text.

        ``value`` is ``sql_variant``; pyodbc raises on that type before a
        row reaches the parser, which is why the cast is in the statement.
        The cast is wide enough for a boundary on a long character type and
        the boundary id orders a function's values.
        """
        return self._select(
            [
                self._col("function_id", "prv"),
                self._col("boundary_id", "prv"),
                self._col("parameter_id", "prv"),
                self._cast(
                    self._col("value", "prv"), "NVARCHAR(4000)"
                ).as_("boundary_value"),
            ],
            from_=self._relation("partition_range_values", "sys", alias="prv"),
            order_by=[
                self._col("function_id", "prv"),
                self._col("boundary_id", "prv"),
                self._col("parameter_id", "prv"),
            ],
        )

    def format_partition_scheme_list_query_statement(
        self, expr: "SQLServerPartitionSchemeListQueryStatement"
    ) -> Tuple[str, tuple]:
        """Render ``sys.partition_schemes`` with each destination's filegroup.

        ``sys.partition_schemes`` inherits ``sys.data_spaces``; its
        ``data_space_id`` is the scheme id the indexes point at.
        ``sys.destination_data_spaces`` maps one destination to one data
        space, and ``sys.data_spaces`` is where that space's filegroup name
        lives. The joins are LEFT so a scheme with no destination rows is
        still a scheme.
        """
        joined = self._join(
            self._relation("partition_schemes", "sys", alias="ps"),
            self._relation("destination_data_spaces", "sys", alias="dds"),
            join_type="LEFT JOIN",
            condition=self._eq(
                self._col("data_space_id", "ps"),
                self._col("partition_scheme_id", "dds"),
            ),
        )
        joined = self._join(
            joined,
            self._relation("data_spaces", "sys", alias="ds"),
            join_type="LEFT JOIN",
            condition=self._eq(
                self._col("data_space_id", "dds"), self._col("data_space_id", "ds")
            ),
        )
        return self._select(
            [
                self._col("name", "ps", alias="scheme_name"),
                self._col("data_space_id", "ps", alias="scheme_id"),
                self._col("function_id", "ps"),
                self._col("destination_id", "dds"),
                self._col(
                    "data_space_id", "dds", alias="destination_data_space_id"
                ),
                self._col("name", "ds", alias="filegroup_name"),
            ],
            from_=joined,
            order_by=[
                self._col("name", "ps"),
                self._col("destination_id", "dds"),
            ],
        )

    def format_partition_aligned_index_list_query_statement(
        self, expr: "SQLServerPartitionAlignedIndexListQueryStatement"
    ) -> Tuple[str, tuple]:
        """Render the indexes whose ``data_space_id`` is a partition scheme.

        An index is aligned when its ``data_space_id`` is the scheme's -- no
        separate flag records it. The partitioning columns are the
        ``sys.index_columns`` rows with a non-zero ``partition_ordinal``, and
        the row and byte counts are this index's own partitions from
        ``sys.dm_db_partition_stats``: measured per index rather than summed
        across indexes, because a nonclustered index repeats the table's
        rows and a sum would count every row twice.
        """
        params = expr.get_params()
        table_name = params.get("table_name")
        schema = params.get("schema")

        joined = self._join(
            self._join(
                self._join(
                    self._join(
                        self._relation("indexes", "sys", alias="i"),
                        self._relation("partition_schemes", "sys", alias="ps"),
                        join_type="JOIN",
                        condition=self._eq(
                            self._col("data_space_id", "i"),
                            self._col("data_space_id", "ps"),
                        ),
                    ),
                    self._relation("objects", "sys", alias="o"),
                    join_type="JOIN",
                    condition=self._eq(
                        self._col("object_id", "i"), self._col("object_id", "o")
                    ),
                ),
                self._relation("schemas", "sys", alias="s"),
                join_type="JOIN",
                condition=self._eq(
                    self._col("schema_id", "o"), self._col("schema_id", "s")
                ),
            ),
            self._relation("index_columns", "sys", alias="ic"),
            join_type="LEFT JOIN",
            condition=self._and(
                self._eq(self._col("object_id", "i"), self._col("object_id", "ic")),
                self._eq(self._col("index_id", "i"), self._col("index_id", "ic")),
                self._gt(
                    self._col("partition_ordinal", "ic"),
                    self._lit(0, inline=True),
                ),
            ),
        )
        joined = self._join(
            joined,
            self._relation("columns", "sys", alias="c"),
            join_type="LEFT JOIN",
            condition=self._and(
                self._eq(self._col("object_id", "c"), self._col("object_id", "ic")),
                self._eq(self._col("column_id", "c"), self._col("column_id", "ic")),
            ),
        )

        stats_conditions = self._and(
            self._eq(self._col("object_id", "st"), self._col("object_id", "i")),
            self._eq(self._col("index_id", "st"), self._col("index_id", "i")),
        )
        row_count = self._subquery(
            [self._fn("SUM", self._col("row_count", "st"))],
            from_=self._relation("dm_db_partition_stats", "sys", alias="st"),
            where=stats_conditions,
            alias="row_count",
        )
        size_bytes = self._mul(
            self._subquery(
                [self._fn("SUM", self._col("used_page_count", "st"))],
                from_=self._relation("dm_db_partition_stats", "sys", alias="st"),
                where=stats_conditions,
            ),
            self._lit(8192, inline=True),
        ).as_("size_bytes")

        conditions = []
        if table_name is not None:
            conditions.append(
                self._eq(
                    self._col("name", "s"),
                    self._lit(schema or DEFAULT_SCHEMA),
                )
            )
            conditions.append(
                self._eq(self._col("name", "o"), self._lit(table_name))
            )
        elif schema is not None:
            conditions.append(self._eq(self._col("name", "s"), self._lit(schema)))

        return self._select(
            [
                self._col("name", "ps", alias="scheme_name"),
                self._col("function_id", "ps"),
                self._col("name", "s", alias="schema_name"),
                self._col("name", "o", alias="table_name"),
                self._col("name", "i", alias="index_name"),
                self._col("index_id", "i"),
                self._col("type_desc", "i", alias="index_type"),
                self._col("is_unique", "i"),
                self._col("is_primary_key", "i"),
                self._col("name", "c", alias="partition_column"),
                self._col("partition_ordinal", "ic"),
                row_count,
                size_bytes,
            ],
            from_=joined,
            where=self._and(*conditions) if conditions else None,
            order_by=[
                self._col("name", "ps"),
                self._col("name", "s"),
                self._col("name", "o"),
                self._col("index_id", "i"),
                self._col("partition_ordinal", "ic"),
            ],
        )

    def format_type_list_query_statement(
        self, expr: "SQLServerTypeListQueryStatement"
    ) -> Tuple[str, tuple]:
        """Render ``sys.types`` for one schema's user-defined types.

        ``sys.table_types`` inherits ``sys.types`` and adds the object id
        whose columns a table type declares, so it is a LEFT JOIN keyed on
        the shared ``user_type_id``. ``MS_Description`` lives in
        ``sys.extended_properties`` under ``class_desc = 'TYPE'`` and
        ``major_id = user_type_id``; the join is LEFT so a type without a
        description keeps its row.
        """
        params = expr.get_params()
        target = params.get("schema") or DEFAULT_SCHEMA

        joined = self._join(
            self._join(
                self._relation("types", "sys", alias="t"),
                self._relation("schemas", "sys", alias="s"),
                join_type="JOIN",
                condition=self._eq(
                    self._col("schema_id", "t"), self._col("schema_id", "s")
                ),
            ),
            self._relation("table_types", "sys", alias="tt"),
            join_type="LEFT JOIN",
            condition=self._eq(
                self._col("user_type_id", "tt"), self._col("user_type_id", "t")
            ),
        )
        joined = self._join(
            joined,
            self._relation("extended_properties", "sys", alias="ep"),
            join_type="LEFT JOIN",
            condition=self._and(
                self._eq(self._col("class_desc", "ep"), self._lit("TYPE", inline=True)),
                self._eq(self._col("major_id", "ep"), self._col("user_type_id", "t")),
                self._eq(self._col("minor_id", "ep"), self._lit(0, inline=True)),
                self._eq(
                    self._col("name", "ep"),
                    self._lit("MS_Description", inline=True),
                ),
            ),
        )
        return self._select(
            [
                self._col("name", "t", alias="type_name"),
                self._col("name", "s", alias="schema_name"),
                self._col("user_type_id", "t"),
                self._col("system_type_id", "t"),
                self._fn(
                    "TYPE_NAME", self._col("system_type_id", "t"), alias="base_type"
                ),
                self._col("max_length", "t"),
                self._col("precision", "t"),
                self._col("scale", "t"),
                self._col("collation_name", "t", alias="collation"),
                self._col("is_nullable", "t"),
                self._col("is_user_defined", "t"),
                self._col("is_table_type", "t"),
                self._col("is_assembly_type", "t"),
                self._col("default_object_id", "t"),
                self._col("rule_object_id", "t"),
                self._col("type_table_object_id", "tt"),
                self._subquery(
                    [self._fn("COUNT", self._row_count_wildcard())],
                    from_=self._relation("columns", "sys", alias="c"),
                    where=self._eq(
                        self._col("object_id", "c"),
                        self._col("type_table_object_id", "tt"),
                    ),
                    alias="column_count",
                ),
                self._cast(self._col("value", "ep"), "NVARCHAR(4000)").as_(
                    "type_comment"
                ),
            ],
            from_=joined,
            where=self._and(
                self._eq(self._col("is_user_defined", "t"), self._lit(1, inline=True)),
                self._eq(self._col("name", "s"), self._lit(target)),
            ),
            order_by=[self._col("name", "t")],
        )

    def format_constraint_list_query_statement(
        self, expr: "SQLServerConstraintListQueryStatement"
    ) -> Tuple[str, tuple]:
        """Render the constraint objects of one table or one schema.

        One ``sys.objects`` row per constraint, with the family's own view
        joined by ``object_id``: ``sys.key_constraints`` for ``PK``/``UQ``,
        ``sys.foreign_keys``/``sys.foreign_key_columns`` for ``F``,
        ``sys.check_constraints`` for ``C`` and ``sys.default_constraints``
        for ``D``. The column joins are LEFT and each matches only the family
        that owns the constraint, so a primary key does not acquire a foreign
        key's columns merely because both views are present.
        """
        params = expr.get_params()
        table_name = params.get("table_name")
        target = params.get("schema") or DEFAULT_SCHEMA

        joined = self._join(
            self._relation("objects", "sys", alias="o"),
            self._relation("schemas", "sys", alias="s"),
            join_type="JOIN",
            condition=self._eq(
                self._col("schema_id", "o"), self._col("schema_id", "s")
            ),
        )
        joined = self._join(
            joined,
            self._relation("tables", "sys", alias="t"),
            join_type="LEFT JOIN",
            condition=self._eq(
                self._col("parent_object_id", "o"), self._col("object_id", "t")
            ),
        )
        joined = self._join(
            joined,
            self._relation("check_constraints", "sys", alias="cc"),
            join_type="LEFT JOIN",
            condition=self._eq(self._col("object_id", "cc"), self._col("object_id", "o")),
        )
        joined = self._join(
            joined,
            self._relation("default_constraints", "sys", alias="dc"),
            join_type="LEFT JOIN",
            condition=self._eq(self._col("object_id", "dc"), self._col("object_id", "o")),
        )
        joined = self._join(
            joined,
            self._relation("foreign_keys", "sys", alias="fk"),
            join_type="LEFT JOIN",
            condition=self._eq(self._col("object_id", "fk"), self._col("object_id", "o")),
        )
        joined = self._join(
            joined,
            self._relation("key_constraints", "sys", alias="kc"),
            join_type="LEFT JOIN",
            condition=self._eq(self._col("object_id", "kc"), self._col("object_id", "o")),
        )
        joined = self._join(
            joined,
            self._relation("tables", "sys", alias="rt"),
            join_type="LEFT JOIN",
            condition=self._eq(
                self._col("referenced_object_id", "fk"), self._col("object_id", "rt")
            ),
        )
        joined = self._join(
            joined,
            self._relation("schemas", "sys", alias="rs"),
            join_type="LEFT JOIN",
            condition=self._eq(
                self._col("schema_id", "rt"), self._col("schema_id", "rs")
            ),
        )
        joined = self._join(
            joined,
            self._relation("foreign_key_columns", "sys", alias="fkc"),
            join_type="LEFT JOIN",
            condition=self._eq(
                self._col("constraint_object_id", "fkc"), self._col("object_id", "o")
            ),
        )
        joined = self._join(
            joined,
            self._relation("columns", "sys", alias="cf"),
            join_type="LEFT JOIN",
            condition=self._and(
                self._eq(self._col("object_id", "cf"), self._col("parent_object_id", "fkc")),
                self._eq(self._col("column_id", "cf"), self._col("parent_column_id", "fkc")),
            ),
        )
        joined = self._join(
            joined,
            self._relation("columns", "sys", alias="cr"),
            join_type="LEFT JOIN",
            condition=self._and(
                self._eq(
                    self._col("object_id", "cr"),
                    self._col("referenced_object_id", "fkc"),
                ),
                self._eq(
                    self._col("column_id", "cr"),
                    self._col("referenced_column_id", "fkc"),
                ),
            ),
        )
        joined = self._join(
            joined,
            self._relation("index_columns", "sys", alias="ic"),
            join_type="LEFT JOIN",
            condition=self._and(
                self._eq(self._col("object_id", "ic"), self._col("parent_object_id", "kc")),
                self._eq(self._col("index_id", "ic"), self._col("unique_index_id", "kc")),
                self._gt(self._col("key_ordinal", "ic"), self._lit(0, inline=True)),
            ),
        )
        joined = self._join(
            joined,
            self._relation("columns", "sys", alias="ck"),
            join_type="LEFT JOIN",
            condition=self._and(
                self._eq(self._col("object_id", "ck"), self._col("object_id", "ic")),
                self._eq(self._col("column_id", "ck"), self._col("column_id", "ic")),
            ),
        )
        joined = self._join(
            joined,
            self._relation("columns", "sys", alias="cchk"),
            join_type="LEFT JOIN",
            condition=self._and(
                self._eq(self._col("object_id", "cchk"), self._col("parent_object_id", "cc")),
                self._eq(self._col("column_id", "cchk"), self._col("parent_column_id", "cc")),
            ),
        )
        joined = self._join(
            joined,
            self._relation("columns", "sys", alias="cd"),
            join_type="LEFT JOIN",
            condition=self._and(
                self._eq(self._col("object_id", "cd"), self._col("parent_object_id", "dc")),
                self._eq(self._col("column_id", "cd"), self._col("parent_column_id", "dc")),
            ),
        )

        conditions = [
            self._in(
                self._col("type", "o"),
                ("PK", "UQ", "F", "C", "D"),
            ),
            self._eq(self._col("is_ms_shipped", "o"), self._lit(0, inline=True)),
            self._eq(self._col("name", "s"), self._lit(target)),
        ]
        if table_name is not None:
            conditions.append(self._eq(self._col("name", "t"), self._lit(table_name)))

        return self._select(
            [
                self._col("name", "o", alias="constraint_name"),
                self._col("name", "s", alias="schema_name"),
                self._col("name", "t", alias="table_name"),
                self._col("type", "o", alias="constraint_type"),
                self._col("type_desc", "o", alias="constraint_type_desc"),
                self._col("constraint_column_id", "fkc", alias="fk_ordinal"),
                self._col("name", "cf", alias="fk_column"),
                self._col("name", "cr", alias="fk_referenced_column"),
                self._col("name", "rt", alias="referenced_table"),
                self._col("name", "rs", alias="referenced_schema"),
                self._col(
                    "delete_referential_action_desc", "fk", alias="on_delete"
                ),
                self._col(
                    "update_referential_action_desc", "fk", alias="on_update"
                ),
                self._col("unique_index_id", "kc"),
                self._col("key_ordinal", "ic"),
                self._col("name", "ck", alias="key_column"),
                self._col("parent_column_id", "cc", alias="check_column_id"),
                self._col("definition", "cc", alias="check_definition"),
                self._col("is_disabled", "cc", alias="check_disabled"),
                self._col("is_not_trusted", "cc", alias="check_not_trusted"),
                self._col("name", "cchk", alias="check_column"),
                self._col("parent_column_id", "dc", alias="default_column_id"),
                self._col("definition", "dc", alias="default_definition"),
                self._col("name", "cd", alias="default_column"),
                self._col("is_disabled", "fk", alias="fk_disabled"),
                self._col("is_not_trusted", "fk", alias="fk_not_trusted"),
            ],
            from_=joined,
            where=self._and(*conditions),
            order_by=[
                self._col("name", "s"),
                self._col("name", "t"),
                self._col("name", "o"),
                self._col("constraint_column_id", "fkc"),
                self._col("key_ordinal", "ic"),
            ],
        )

    # ========== Operational families ==========

    def supports_unused_indexes_detection(self) -> bool:
        """SQL Server answers from ``sys.dm_db_index_usage_stats``, 2005 on.

        The dynamic management views are a live-instance view rather than a
        schema-scoped catalogue, which is the dependency this round recorded
        as pending. It is carried: the join through ``sys.objects`` and
        ``sys.schemas`` applies the schema filter the statement needs, the
        way the per-table storage read already reaches
        ``sys.dm_db_partition_stats`` -- one construct, the same shape as the
        catalogue questions this module already asks.

        The counters are *since the view was last flushed*, which is the
        engine's own window and not a resettable one: ``DBCC
        SQLPERF('sys.dm_os_wait_stats',CLEAR)`` clears some counters and the
        index usage view flushes on its own schedule after a restart. An index
        absent from the answer is absence of evidence, never proof of use, and
        the DMV only reports the indexes it knows about.

        Reading the DMV needs ``VIEW DATABASE STATE`` (or ``VIEW SERVER
        STATE``); without it the view returns only the objects the caller
        owns. A caller with less privilege gets a shorter list, not an error,
        which is why the privilege is stated here rather than turned into a
        probe: the probe can ask a version, not a grant, and a short list is
        an answer about what the caller may see.
        """
        return self.version_at_least((9, 0, 0))

    def supports_index_stats(self) -> bool:
        """SQL Server answers per-index counters from the same DMV, 2005 on.

        ``user_seeks``/``user_scans``/``user_lookups`` are the three read
        shapes and their sum is what ``scans`` answers; ``user_updates`` rides
        the row into ``extra``. There is no per-index "rows read" counter in
        this view, so ``rows_read`` and ``rows_fetched`` stay ``None`` rather
        than being filled with a seek or a scan count -- an operation is not a
        row and the two must not be merged into one slot.

        The privilege and the window are the ones
        :meth:`supports_unused_indexes_detection` states, because it is the
        same view.
        """
        return self.version_at_least((9, 0, 0))

    def supports_table_stats(self) -> bool:
        """SQL Server keeps no per-table usage counter, so the probe refuses.

        The inquiry covered every release in the matrix (2017, 2019 and
        2022). The engine's counters are per *index*:
        ``sys.dm_db_index_usage_stats`` rows are keyed by object and index,
        and summing them per table would be an aggregate wearing the shape of
        a measured counter -- a reader asking "how many scans did this table
        take" would receive a number no engine ever counted, and the family's
        promise is that each figure is the engine's own.

        Two of the slots the family names are not tracked at all. Sequential
        scans are not distinguishable from indexed ones at the table level,
        and inserts and deletes are recorded nowhere -- ``user_updates`` is
        the only write shape the DMV carries, and it counts writes of every
        kind. So the honest answer is that the engine does not measure this,
        and the probe says so rather than projecting a derived figure.

        The row estimate is a different source again:
        ``sys.dm_db_partition_stats`` keeps an in-memory count whose refresh
        is the engine's own, so it stays where it already is -- on the table
        listing's ``row_count`` slot -- rather than being copied beside
        counters it has nothing to do with.
        """
        return False

    def supports_runtime_stats(self) -> bool:
        """SQL Server answers runtime measurements from its performance counters.

        ``sys.dm_os_performance_counters`` names what is actually being
        counted on this instance -- one row per counter, grouped by the
        object that owns it -- which makes it the honest source for a "what is
        alive" listing: a counter not being maintained produces no row, and
        therefore no number, rather than a zero that would read as "idle".
        ``cntr_type`` carries the engine's own classification and rides the
        row as ``kind``; the counter's owning object is projected as
        ``source``, because these figures are since the view was last flushed
        and the window is the engine's to name.

        Reading it needs ``VIEW SERVER STATE``; without that grant the view
        answers nothing, and a listing that silently loses every row there is
        a privilege statement rather than a measurement. The probe cannot ask
        a grant -- only a version -- so the privilege is stated here and the
        version floor is the one the view needs.
        """
        return self.version_at_least((9, 0, 0))

    def supports_object_dependencies(self) -> bool:
        """SQL Server answers the object dependency graph, 2008 on.

        ``sys.sql_expression_dependencies`` records, per reference, which
        object depends on which *named* entity -- a view on a table, a
        procedure on a table, a function used by a trigger. It is a real graph
        and a partial one: by-name references resolve only to objects the
        caller can see, and the view is scoped to the database, so a
        cross-database reference names an entity rather than an object.

        It does not record every other kind of coupling -- a foreign key is
        not a row here, and an object bound through ``sp_depends``-style
        dynamic SQL is invisible to it. A caller asking "what breaks if I drop
        this" gets the referential half plus the resolved-name half, and the
        docstring says which half.
        """
        return self.version_at_least((10, 0, 0))

    def supports_ddl_extraction(self) -> bool:
        """SQL Server will not hand back the DDL that recreates an object.

        The engine has no per-object DDL retrieval call of the kind
        PostgreSQL's ``DBMS_METADATA`` and MySQL's ``SHOW CREATE TABLE`` are.
        ``OBJECT_DEFINITION`` and ``sys.sql_modules`` hold the *body* of a
        routine, a view or a trigger -- text the engine stores because it
        executes it -- and a table's columns, constraints, indexes and
        storage are recorded as rows across ``sys.columns``,
        ``sys.indexes``, ``sys.default_constraints`` and more. Reassembling a
        ``CREATE TABLE`` from them is a reconstruction, and this family's rule
        is that a reconstruction is not an answer: ``DDLStatement.native``
        exists to say which of the two a caller is looking at, and an
        assembly that used it would be claiming the engine said something it
        did not.

        So the probe answers ``False`` and the CLI refuses the question at the
        capability gate rather than rendering a partial text. The four
        operational families this round *does* answer are listed above; this
        one stays a declared gap, and the roundtrip matrix in this repository
        keeps its pin for ``DDLStatementQueryStatement`` with this reason.
        """
        return False

    def _usage_stats_source(self, with_indexes: bool):
        """The per-index DMV joined to the catalogue that names its objects.

        ``sys.dm_db_index_usage_stats`` addresses everything by id --
        ``database_id``, ``object_id``, ``index_id`` -- and carries no name
        and no schema. The join through ``sys.objects`` and ``sys.schemas``
        is what turns those ids into the address a caller reads, and it is
        also where the schema filter is applied: the DMV covers every
        database on the instance, so a caller asking about one schema must
        not be handed every schema's indexes.

        ``sys.indexes`` is joined as well when the caller reads the index's
        *name*: the DMV has no ``index_id``-to-name mapping of its own, and
        the heap's ``index_id`` 0 has no row there at all.

        The database is *not* filtered here, and that is deliberate. The DMV
        keeps one row per index of the connected database, and a
        ``database_id`` filter would have to name it -- either through
        ``DB_ID()``, whose value the statement would then depend on, or
        through a second read. The join to ``sys.schemas`` already narrows to
        one schema of this database, which is the narrowing the statement was
        asked for.
        """
        usage = self._relation("dm_db_index_usage_stats", "sys", alias="u")
        joined = self._join(
            self._join(
                usage,
                self._relation("objects", "sys", alias="o"),
                condition=self._eq(
                    self._col("object_id", "u"), self._col("object_id", "o")
                ),
            ),
            self._relation("schemas", "sys", alias="s"),
            condition=self._eq(
                self._col("schema_id", "o"), self._col("schema_id", "s")
            ),
        )
        if with_indexes:
            joined = self._join(
                joined,
                self._relation("indexes", "sys", alias="i"),
                condition=self._and(
                    self._eq(self._col("object_id", "u"), self._col("object_id", "i")),
                    self._eq(self._col("index_id", "u"), self._col("index_id", "i")),
                ),
            )
        return joined

    def _read_counter_sum(self):
        """The three read shapes added: seeks, scans and lookups.

        One ``scans`` figure, because the engine's own counters are three
        columns of the same event and the family names one slot. Adding them
        is not a derived measurement; it is the same counter, spelled in three
        parts, and the docstring of the family that reads it says which parts.
        """
        return self._add(
            self._add(self._col("user_seeks", "u"), self._col("user_scans", "u")),
            self._col("user_lookups", "u"),
        )

    def format_unused_indexes_query_statement(
        self, expr: "UnusedIndexesQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format the unused-indexes listing from the index usage DMV.

        The predicates are the answer to "unused" as this engine means it:
        ``index_id > 0`` excludes a heap's row (``index_id`` 0 is not an index
        and never appears in ``sys.indexes``), and the sum of the three read
        counters being zero says no query the engine counted has used it.

        The name of the index is read through ``sys.indexes`` rather than
        reconstructed from the DMV's ids, and the object and schema through
        the join above. See :meth:`_usage_stats_source`.
        """
        params = expr.get_params()
        target = params.get("schema") or DEFAULT_SCHEMA

        return self._select(
            [
                self._col("name", "s", alias="schema_name"),
                self._col("name", "o", alias="table_name"),
                self._col("name", "i", alias="index_name"),
            ],
            from_=self._usage_stats_source(with_indexes=True),
            where=self._and(
                self._eq(self._col("name", "s"), self._lit(target)),
                self._gt(self._col("index_id", "u"), self._lit(0, inline=True)),
                self._eq(self._read_counter_sum(), self._lit(0, inline=True)),
            ),
            order_by=[
                self._col("name", "s"),
                self._col("name", "o"),
                self._col("name", "i"),
            ],
        )

    def format_index_usage_stats_query_statement(
        self, expr: "IndexUsageStatsQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format per-index counters from the same DMV.

        ``scans`` is the shared slot the three read columns sum into, and
        ``user_updates`` rides the row into ``extra`` under its own name --
        an update is not a scan, and the two are not interchangeable. The
        engine keeps no per-index row counter, so ``rows_read`` and
        ``rows_fetched`` are simply not projected and stay ``None``; see
        :meth:`supports_index_stats`.
        """
        params = expr.get_params()
        target = params.get("schema") or DEFAULT_SCHEMA

        return self._select(
            [
                self._col("name", "s", alias="schema_name"),
                self._col("name", "o", alias="table_name"),
                self._col("name", "i", alias="index_name"),
                self._read_counter_sum().as_("scans"),
                self._col("user_updates", "u", alias="writes"),
            ],
            from_=self._usage_stats_source(with_indexes=True),
            where=self._and(
                self._eq(self._col("name", "s"), self._lit(target)),
                self._gt(self._col("index_id", "u"), self._lit(0, inline=True)),
            ),
            order_by=[
                self._col("name", "s"),
                self._col("name", "o"),
                self._col("name", "i"),
            ],
        )

    def format_runtime_metrics_query_statement(
        self, expr: "RuntimeMetricsQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format the runtime listing from the instance's performance counters.

        No schema filter: the counters describe a running instance and carry
        no schema column, so a filter here would refuse a correct query for a
        nonsensical reason -- the same reasoning the storage slots use when
        they leave a view's storage unmeasured.

        ``cntr_value`` is the number and ``cntr_type`` the engine's
        classification of it, projected as ``kind`` so a caller can group
        without learning the DMV's vocabulary. ``object_name`` is the counter
        group that owns it (``SQLServer:Buffer Manager`` and friends) and is
        projected as ``source``; ``instance_name`` -- the per-node or per-lru
        split that makes two rows of the same counter distinguishable -- is
        projected under its own name and travels in ``extra``.
        """
        return self._select(
            [
                self._col("counter_name", alias="name"),
                self._col("cntr_value", alias="value"),
                self._col("cntr_type", alias="kind"),
                self._col("object_name", alias="source"),
                self._col("instance_name"),
            ],
            from_=self._relation("dm_os_performance_counters", "sys"),
            order_by=[self._col("object_name"), self._col("counter_name")],
        )

    def format_object_dependency_query_statement(
        self, expr: "ObjectDependencyQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format the dependency graph from by-name entity references.

        ``referencing_id`` is the object that depends and
        ``referenced_entity_name`` is the entity it names, so the two sides
        come from different columns of the same row -- which is why the join
        is on the referencing object rather than on the referenced one: the
        referenced thing is a *name*, not an id, and a second join would have
        to resolve it.

        ``referenced_class_desc`` says what kind of thing was named (OBJECT,
        COLUMN, TYPE) and rides the row as ``kind``. A ``referenced_server_name``
        or ``referenced_database_name`` other than this one means the referenc
        leaves the database; those rows are kept and their names travel in
        ``extra``, because dropping an object with a cross-database
        dependant is exactly the case the graph exists to show.

        """
        params = expr.get_params()
        target = params.get("schema") or DEFAULT_SCHEMA
        object_name = params.get("object_name")

        joined = self._join(
            self._relation("sql_expression_dependencies", "sys", alias="d"),
            self._relation("objects", "sys", alias="o"),
            condition=self._eq(
                self._col("referencing_id", "d"), self._col("object_id", "o")
            ),
        )
        joined = self._join(
            joined,
            self._relation("schemas", "sys", alias="s"),
            condition=self._eq(
                self._col("schema_id", "o"), self._col("schema_id", "s")
            ),
        )

        conditions = [self._eq(self._col("name", "s"), self._lit(target))]
        if object_name:
            conditions.append(
                self._eq(self._col("name", "o"), self._lit(object_name))
            )

        return self._select(
            [
                self._col("name", "s", alias="schema_name"),
                self._col("name", "o", alias="dependent"),
                self._col("referenced_entity_name", "d", alias="referenced"),
                self._col("type_desc", "o", alias="dependent_type"),
                self._col("referenced_class_desc", "d", alias="kind"),
            ],
            from_=joined,
            where=self._and(*conditions),
            order_by=[
                self._col("name", "s"),
                self._col("name", "o"),
                self._col("referenced_entity_name", "d"),
            ],
        )

    # ========== Data Profiles (row-shaped answers) ==========

    def supports_column_data_profile(self) -> bool:
        """SQL Server answers a column data profile by aggregating the rows.

        SQL Server publishes statistics, and they are the reason this probe is
        worth a paragraph rather than a sentence: ``sys.stats`` names a
        statistics object, ``sys.stats_columns`` maps that object to one or
        more columns, and ``sys.dm_db_stats_properties`` reports what the last
        update of *that object* measured -- ``rows``, ``rows_sampled``,
        ``steps``, ``modification_counter``, ``last_updated`` and
        ``persisted_sample_percent``. The key is the object, not the column. A
        single-column statistics object is a fair proxy for its column, but a
        two-column one describes the pair's leading prefix, and the same column
        can appear in several objects with different samples, so summing or
        picking one would invent a per-column fact the catalogue does not hold.

        What is missing is sharper than what is keyed oddly. There is no
        per-column null count anywhere in the catalogue -- nullability is a
        *declaration* in ``sys.columns``, never a measurement -- and no
        per-column distinct count either; ``sys.dm_db_stats_histogram``
        (2016+) reports ``range_high_key``/``equal_rows``/``distinct_range_rows``
        per step of one object, which is a bucket summary for that object's
        leading column, not a count of the values in a column. The one figure
        the catalogue could contribute, ``last_updated``, would be the vintage
        of a statistics object, not of the profile -- and this family's rule is
        that a figure travels with the source and vintage that produced it.

        So all five figures come from one place, and it is the rows: exact,
        and paid for in time. The label is ``aggregate``, projected into each
        row rather than stamped onto the result, so nothing here can be
        mistaken for an estimate of somebody's last sample.
        """
        return True

    def supports_column_value_sample(self) -> bool:
        """SQL Server answers a value listing by aggregating with a limit.

        The nearest catalogue answer is ``sys.dm_db_stats_histogram``, and it
        answers a different question: a histogram step's ``equal_rows`` counts
        the rows equal to that step's ``range_high_key``, so the list it could
        produce would be bucket boundaries with estimated weights -- only for
        the leading column of a statistics object, and only for the values
        whose boundaries survived bucketing. A ``GROUP BY`` answers what the
        caller asked for, exactly, at the cost of a grouped scan.

        The cap rides the dialect's pagination clause, ``OFFSET 0 ROWS FETCH
        NEXT n ROWS ONLY``, which the engine parses only from 2012 on. That
        floor is asked of the version accessor rather than left to a runtime
        syntax error: a server below it is refused at the capability question
        with "cannot answer", which is a different and truer answer than a
        query that fails to parse. Every release this repository tests
        against (2017, 2019, 2022 and 2025) is well past it, so the gate
        changes nothing there and keeps an older server from an execution
        error.
        """
        return self.version_at_least((11, 0, 0))

    def supports_join_coverage(self) -> bool:
        """SQL Server answers overlap by counting distinct values on both sides.

        Exact: two ``COUNT(DISTINCT ...)`` denominators and one intersection,
        with ``NULL`` excluded on both sides because a NULL is not a value that
        could ever join. Answering ``True`` is right because the probe asks
        whether the engine *can* answer, not whether it can answer cheaply --
        the cost, two scans of each column, belongs in the docstring.
        """
        return True

    def _user_relation(self, table_name: str, target: str, alias: Optional[str] = None):
        """A user table as a FROM source, named in *target*'s schema.

        The opposite of the ``sys`` relations above: this one is whatever its
        owner declared, and it lives in a caller-named schema, so both parts go
        through the dialect's identifier renderer. ``target`` is never empty --
        the formatters below fall back to :data:`DEFAULT_SCHEMA` the same way
        every other statement in this module does.

        ``alias`` is what tells the two sides of a coverage measurement apart;
        it is quoted like every other identifier.
        """
        return self._relation(table_name, target, alias=alias)

    def _profile_cast(self, node, type_name: str, alias: Optional[str] = None):
        """``CAST(node AS type_name)`` for a node that is not a column.

        :meth:`_cast` asks the node to cast *itself*, which only a reference
        carrying a declared type can do; a literal, a ``CASE`` and a function
        call are values, so the cast is built around them instead. The type is
        parsed by the dialect's own parser, so the spelling in the statement is
        the one this backend uses everywhere else.
        """
        from rhosocial.activerecord.backend.expression.core import CastExpression
        from rhosocial.activerecord.backend.expression.types._base import DataType

        dialect = self._node_dialect
        return CastExpression(
            dialect, node, DataType.parse_data_type_str(dialect, type_name), alias=alias
        )

    def _data_profile_label(self, text: Optional[str], alias: str):
        """A constant label as a named select-list entry.

        ``Literal`` is deliberately unaliasable -- a value has nothing to name
        (see :class:`~...expression.core.Literal`) -- so the constant is cast
        to text, which is the smallest node in the tree that produces a named
        result. The cast is not there for its type: it is there so the label
        can be called ``source``, which is what the parser reads. The width is
        stated because SQL Server's ``CHAR`` and ``NVARCHAR`` default to length
        1 in a ``CAST``, which would truncate the word to its first character.
        """
        return self._profile_cast(
            self._lit(text, inline=True), "NVARCHAR(128)", alias
        )

    def _profile_arm(self, table_name: str, target: str, column_name: str):
        """One column's arm of the profile, as a query node.

        The seven entries are the family's contract: the column's own name, the
        null count, the distinct count, the two endpoints, the row count the
        parser divides by, and the provenance.

        Three type decisions are written into this projection rather than left
        to the reader. The null flag is cast to ``BIGINT`` before it is summed,
        and the row count is ``COUNT_BIG(*)`` rather than ``COUNT(*)``, because
        SQL Server's ``SUM`` and ``COUNT`` return ``INT``: a table with more
        than 2,147,483,647 rows -- exactly the table worth profiling -- would
        overflow the very counts the profile exists to report. The two
        endpoints are cast to ``NVARCHAR(MAX)`` for a reason that belongs to
        the union rather than to this arm, and is stated at
        :meth:`format_column_data_profile_query_statement`.
        """
        from rhosocial.activerecord.backend.expression import (
            CaseExpression,
            CountFunction,
        )

        column = self._col(column_name)
        null_flag = CaseExpression(
            self._node_dialect,
            cases=[(column.is_null(), self._lit(1, inline=True))],
            else_result=self._lit(0, inline=True),
        )
        return self._query(
            [
                # The name is bound rather than written into the statement: it
                # is a value, and a non-prefixed literal would be typed with
                # the database's code page, so an identifier outside that page
                # would arrive as question marks. A parameter is typed Unicode
                # by the driver, and it keeps the caller's text out of the SQL.
                self._profile_cast(
                    self._lit(column_name), "NVARCHAR(128)", "column_name"
                ),
                self._fn(
                    "SUM", self._profile_cast(null_flag, "BIGINT")
                ).as_("null_count"),
                CountFunction(self._node_dialect, column, distinct=True).as_(
                    "distinct_count"
                ),
                self._profile_cast(
                    self._fn("MIN", column), "NVARCHAR(MAX)", "min_value"
                ),
                self._profile_cast(
                    self._fn("MAX", column), "NVARCHAR(MAX)", "max_value"
                ),
                self._fn("COUNT_BIG", self._row_count_wildcard()).as_("row_count"),
                self._data_profile_label(ProfileSource.AGGREGATE.value, "source"),
            ],
            from_=self._user_relation(table_name, target),
        )

    def format_column_data_profile_query_statement(
        self, expr: "ColumnDataProfileQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format a per-column profile by aggregating the rows themselves.

        The catalogue was audited and refused -- see
        :meth:`supports_column_data_profile` for what is keyed by statistics
        object and what is simply absent -- so every figure is counted and the
        row says so. The ``aggregate`` label is projected *into* each row
        rather than stamped onto the result afterwards: a consumer comparing a
        SQL Server profile with a PostgreSQL estimate can tell the two apart
        without knowing which engine it asked.

        One arm per column, over the column list the expression carries: SQL
        cannot pivot ``SUM(CASE WHEN col IS NULL ...)`` across columns it was
        never told about, so an aggregating dialect genuinely needs that list
        where a catalogue-based one does not.

        The one place in this module where a set operator is written as text.
        Every arm is a real :class:`~...expression.statements.dql.QueryStatement`
        -- the renderer owns its projection, its identifiers and its relation
        -- because a ``UNION ALL`` over a column list known only at run time
        has no node to represent it: the column list is a tuple on the
        expression, not an operand in the tree. So each arm is rendered on its
        own, its parameters are concatenated in arm order, and the rendered
        arms are joined by the set operator's word. Nothing else here is text.

        Why the endpoints are cast to text, which is the one place this differs
        from the MySQL-family implementation. A union resolves *one* result type
        per column position by data-type precedence and implicitly converts the
        other arms to it, so the ``min_value`` slot would have to hold an
        ``int`` from one arm and a ``varchar`` from another: ``int`` wins, and
        the text value is converted to a number, which fails. A ``decimal``
        beside a ``datetime`` fails the same way in the other direction.
        Nothing in the formatter knows a column's declared type, so there is no
        per-type cast to choose; text is the one target every scalar column
        converts to, and the endpoints arrive as the engine's default rendering
        of the value. The figures are exact; the Python types are the union's,
        and a ``datetime`` endpoint renders without its sub-minute part because
        that is what SQL Server's style-free conversion produces.

        ``null_count`` rather than a fraction: dividing by a row count that may
        legitimately be zero belongs in the parser, not in a SQL expression
        that would then have to guard against it. ``SUM`` over no rows is NULL,
        so an empty table answers "not measured" for the fraction rather than
        ``0.0``, which would claim a measurement nobody made.

        A table holding an ``xml``, ``text``/``ntext``/``image`` or CLR-typed
        column cannot be profiled this way at all: SQL Server refuses ``MIN``
        and ``MAX`` on those types, and the statement fails rather than
        answering a partial profile. That is the honest limit of an aggregate,
        and it is stated here rather than discovered as a server error.

        An empty column list answers with no rows. That case cannot arise from
        a real table -- SQL Server requires at least one column -- but the
        branch has to render, so it is a statement that selects no rows rather
        than a special-case string.
        """
        params = expr.get_params()
        target = params.get("schema") or DEFAULT_SCHEMA

        arms = []
        parameters: "list" = []
        for name in expr.columns:
            sql, arm_parameters = self._profile_arm(
                params.get("table_name"), target, name
            ).to_sql()
            arms.append(sql)
            parameters.extend(arm_parameters)

        if not arms:
            return self._query(
                [self._data_profile_label(None, "column_name")],
                where=self._eq(
                    self._lit(0, inline=True), self._lit(1, inline=True)
                ),
            ).to_sql()

        return " UNION ALL ".join(arms), tuple(parameters)

    def format_column_value_sample_query_statement(
        self, expr: "ColumnValueSampleQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format a most-frequent-values listing with a grouped scan.

        Nothing usable is precomputed -- see
        :meth:`supports_column_value_sample` for what a histogram step does and
        does not answer -- so this costs a ``GROUP BY`` over the column plus a
        sort of the groups: the same order as the profile itself, which is why
        the two are separate probes rather than one call that would make the
        cheap half pay for the dear one.

        ``ORDER BY COUNT_BIG(*) DESC`` is what makes the answer "the most
        frequent values" rather than "the first values". ``COUNT_BIG`` rather
        than ``COUNT`` for the same reason as the profile: the count of a
        value's rows can pass 2,147,483,647 on a large table, and an overflow
        there would be reported as an error rather than read as a large group.
        Ties break by the value so two runs of the same query agree.

        The cap rides the dialect's pagination clause, ``OFFSET 0 ROWS FETCH
        NEXT n ROWS ONLY``, which is SQL Server 2012+ syntax; ``n`` is an
        ``int`` the statement carries, so no caller text is spliced into the
        statement.
        """
        params = expr.get_params()
        target = params.get("schema") or DEFAULT_SCHEMA
        column_name = expr.column_name
        counts = self._fn("COUNT_BIG", self._row_count_wildcard())

        return self._select(
            [
                self._col(column_name).as_("value"),
                counts.as_("count"),
            ],
            from_=self._user_relation(expr.table_name, target),
            group_by=[self._col(column_name)],
            order_by=[
                (self._fn("COUNT_BIG", self._row_count_wildcard()), "DESC"),
                (self._col(column_name), "ASC"),
            ],
            limit=int(expr.limit),
        )

    def _coverage_fraction(self, column, source, other_column, other_source):
        """One side of the overlap: the share of *column* the other side holds.

        The numerator counts the *distinct* values of *column* that also occur
        in *other_column*, as a ``COUNT(*)`` over a derived table of those
        distinct values; the denominator counts *column*'s distinct non-NULL
        values. Distinct on both sides is what makes the figure a coverage of
        values rather than of rows -- a key repeated a thousand times that
        matches once would otherwise read as well covered.

        ``IS NOT NULL`` is written on both halves rather than relied upon. In
        the numerator it is load-bearing: a DISTINCT treats a NULL as one
        value, so counting it would credit the tested side with a match it does
        not have. In the divisor ``COUNT(DISTINCT ...)`` skips NULLs on its
        own, but the statement says so explicitly, because the share is of the
        values that could join and that is the fact being measured.
        ``NULLIF(..., 0)`` then makes a column with no value at all answer NULL
        rather than 0, which the parser reads as "no fraction": the difference
        between "nothing matched" and "nothing to match" survives to the caller.

        The numerator is multiplied by ``1.0`` before it is divided, and that
        is not decoration: SQL Server divides two integers with integer
        division, so ``COUNT(*) / COUNT(DISTINCT ...)`` would answer 0 or 1 and
        lose every fraction between them. The multiplier makes the division
        decimal, which is exact for these counts rather than approximate.
        """
        from rhosocial.activerecord.backend.expression import (
            FunctionCall,
            InPredicate,
            QueryStatement,
            SelectModifier,
            Subquery,
            WhereClause,
        )
        from rhosocial.activerecord.backend.expression.functions import (
            CountFunction,
        )
        from rhosocial.activerecord.backend.expression.operators import (
            ArithmeticOperation,
            ArithmeticOperator,
        )
        from rhosocial.activerecord.backend.expression.sources import (
            DerivedTableSource,
        )

        dialect = self._node_dialect
        # ``DISTINCT`` is a statement modifier rather than a predicate, so the
        # overlap is built as a statement rather than through ``self._query``:
        # a node carries every parameter it was given at construction and is
        # never edited afterwards.
        overlap = QueryStatement(
            dialect,
            select=[column],
            from_=source,
            where=WhereClause(
                dialect,
                self._and(
                    self._is_not_null(column),
                    InPredicate(
                        dialect,
                        column,
                        Subquery(
                            dialect,
                            self._query(
                                [other_column],
                                from_=other_source,
                                where=self._is_not_null(other_column),
                            ),
                        ),
                    ),
                ),
            ),
            select_modifier=SelectModifier.DISTINCT,
        )
        covered = self._subquery(
            [self._fn("COUNT_BIG", self._row_count_wildcard())],
            from_=DerivedTableSource(dialect, overlap, alias="covered"),
        )
        total = self._subquery(
            [
                FunctionCall(
                    dialect,
                    "NULLIF",
                    CountFunction(dialect, column, distinct=True),
                    self._lit(0, inline=True),
                )
            ],
            from_=source,
            where=self._is_not_null(column),
        )
        scaled = ArithmeticOperation(
            dialect,
            ArithmeticOperator.MUL,
            covered,
            self._lit(1.0, inline=True),
        )
        return ArithmeticOperation(
            dialect, ArithmeticOperator.DIV, scaled, total
        )

    def format_join_coverage_query_statement(
        self, expr: "JoinCoverageQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format a two-sided measurement of two columns' value domains.

        Unlike every other statement in this module, this one names two user
        tables rather than one catalogue relation: the question is a relation
        between two objects, so both sides are carried explicitly and their
        identifiers are the dialect's to quote (see :meth:`_user_relation`).
        The aliases ``l`` and ``r`` are what keep the two columns apart in the
        rendered statement, and they are quoted like every other identifier.

        The row carries both fractions because neither is meaningful alone. A
        left share of 1.0 beside a right share of 0.2 says every tested value
        exists on the other side while most of that other domain is
        unaccounted for; a single similarity score would average the two and
        describe neither. A caller deciding whether a join is worth writing
        needs to know which direction is incomplete.

        Both figures are counted over *distinct* values, with NULLs excluded
        from the numerators and the denominators alike -- see
        :meth:`_coverage_fraction` for both rules and for the ``1.0`` that
        keeps SQL Server from answering an integer division.

        The cost is the two sides read for their distinct domains plus an
        intersection of the two -- a double scan, and the reason the probe
        belongs behind an explicit call rather than in any automatic pass.

        Collations are not reconciled. SQL Server compares the two columns
        under whichever collation applies to the comparison, so values the
        database would treat as equal may be counted as distinct here, and the
        fractions are a *lower* bound across mismatched collations -- never an
        upper one.
        """
        params = expr.get_params()
        target = params.get("schema") or DEFAULT_SCHEMA

        left_source = self._user_relation(params.get("left_table"), target, "l")
        right_source = self._user_relation(params.get("right_table"), target, "r")
        left_column = self._col(params.get("left_column"), "l")
        right_column = self._col(params.get("right_column"), "r")

        return self._select(
            [
                self._coverage_fraction(
                    left_column, left_source, right_column, right_source
                ).as_("left_coverage"),
                self._coverage_fraction(
                    right_column, right_source, left_column, left_source
                ).as_("right_coverage"),
            ]
        )

