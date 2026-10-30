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

from typing import Optional, Tuple, TYPE_CHECKING

from ..query_nodes import SQLServerNodeBuilderMixin

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase
    from rhosocial.activerecord.backend.expression.introspection import (
        ColumnInfoQueryStatement,
        DatabaseInfoQueryStatement,
        ForeignKeyQueryStatement,
        IndexInfoQueryStatement,
        TableListQueryStatement,
        TriggerListQueryStatement,
        ViewInfoQueryStatement,
        ViewListQueryStatement,
    )
    from ..expression.introspection import (
        SQLServerExtendedPropertyListQueryStatement,
        SQLServerPrimaryKeyQueryStatement,
        SQLServerRoutineListQueryStatement,
        SQLServerSchemaListQueryStatement,
        SQLServerSequenceListQueryStatement,
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
            self._relation("objects", "sys", alias="o"),
            self._relation("schemas", "sys", alias="s"),
            condition=self._eq(
                self._col("schema_id", "o"), self._col("schema_id", "s")
            ),
        )
        return self._select(
            [
                self._col("name", "o", alias="TABLE_NAME"),
                self._col("type", "o", alias="TABLE_TYPE"),
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
        """
        from rhosocial.activerecord.backend.expression import FunctionCall
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
        is_identity = FunctionCall(
            self._node_dialect,
            "COLUMNPROPERTY",
            FunctionCall(self._node_dialect, "OBJECT_ID", qualified_name),
            self._col("COLUMN_NAME", "c"),
            self._lit("IsIdentity", inline=True),
            alias="IS_IDENTITY",
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
            ],
            from_=self._relation("COLUMNS", "INFORMATION_SCHEMA", alias="c"),
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
        """Format the trigger list query, optionally for one table."""
        from rhosocial.activerecord.backend.expression import FunctionCall, JoinClause

        params = expr.get_params()
        table_name = params.get("table_name")
        target = params.get("schema") or DEFAULT_SCHEMA

        joins = JoinClause(
            self._node_dialect,
            JoinClause(
                self._node_dialect,
                self._relation("triggers", "sys", alias="tr"),
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
                FunctionCall(
                    self._node_dialect,
                    "OBJECT_DEFINITION",
                    self._col("object_id", "tr"),
                    alias="definition",
                ),
            ],
            from_=joins,
            where=self._and(*conditions),
            order_by=[self._col("name", "tr")],
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
        """
        params = expr.get_params()
        major_id = params.get("major_id")
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
            [
                self._col("class", "ep", alias="class_id"),
                self._col("class_desc", "ep", alias="class_name"),
                self._col("major_id", "ep", alias="major_id"),
                self._col("minor_id", "ep", alias="minor_id"),
                self._col("name", "ep", alias="property_name"),
                self._cast(
                    self._col("value", "ep"), "NVARCHAR(4000)"
                ).as_("property_value"),
            ],
            from_=joined,
            where=self._and(*conditions),
            order_by=[self._col("minor_id", "ep"), self._col("name", "ep")],
        )

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
