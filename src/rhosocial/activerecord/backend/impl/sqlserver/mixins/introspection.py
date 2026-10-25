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
artefact and belongs to the dialect (org guide §16.2). The introspector above
this layer constructs a statement and executes what these return, so no family
core models is spelled anywhere but in this module.
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

__all__ = ["DEFAULT_SCHEMA", "SQLServerIntrospectionMixin"]

#: The schema a name is resolved in when the caller names none. Declared once
#: so the introspector's ``default_schema`` and the statements below cannot
#: drift apart.
DEFAULT_SCHEMA = "dbo"


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

        ``include_system`` is part of the shared question but is not consulted:
        ``INFORMATION_SCHEMA.TABLES`` is scoped to the current database's
        objects, so there is no server-owned row to add or drop.
        """
        params = expr.get_params()
        target = params.get("schema") or DEFAULT_SCHEMA
        include_views = params.get("include_views", True)
        table_type = params.get("table_type")

        conditions = [self._eq(self._col("TABLE_SCHEMA"), self._lit(target))]
        if table_type:
            conditions.append(self._eq(self._col("TABLE_TYPE"), self._lit(table_type)))
        elif not include_views:
            conditions.append(
                self._eq(self._col("TABLE_TYPE"), self._lit("BASE TABLE", inline=True))
            )
        return self._select(
            [self._col("TABLE_NAME"), self._col("TABLE_TYPE")],
            from_=self._relation("TABLES", "INFORMATION_SCHEMA"),
            where=self._and(*conditions),
            order_by=[self._col("TABLE_NAME")],
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
        """
        params = expr.get_params()
        target = params.get("schema") or DEFAULT_SCHEMA
        return self._select(
            [self._col("TABLE_NAME", alias="view_name")],
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
