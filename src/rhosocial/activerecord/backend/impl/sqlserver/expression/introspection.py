# src/rhosocial/activerecord/backend/impl/sqlserver/expression/introspection.py
"""SQL Server's own introspection questions.

Core's statement classes cover the catalogue questions every backend asks:
tables, their columns, indexes, foreign keys, views and triggers. Five families
have no core entry point and are SQL Server's own:

* **the primary key** -- core reads the column list and asks the backend to
  resolve which of those columns the key is made of;
* **schemas** -- ``sys.schemas`` with the owning principal, a namespace level
  core models only optionally;
* **extended properties** -- the ``MS_Description`` family, which lives in a
  catalogue shared by objects, columns, indexes and more;
* **routines** -- stored procedures and user-defined functions, which this
  engine keeps in one relation and separates by ``sys.objects.type``;
* **sequences** -- ``sys.sequences``, whose values are ``sql_variant`` and
  must be cast to text before the driver can fetch them.

Each class collects all its parameters at construction -- keyword-only, since
the question is asked once and never edited -- and names, through
``format_method``, the one dialect formatter that renders it. The SQL lives on
the dialect (``SQLServerIntrospectionMixin`` in ``mixins/introspection.py``);
this module only carries the question.

Example:
    >>> expr = SQLServerPrimaryKeyQueryStatement(
    ...     dialect, table_name="users", schema="dbo"
    ... )
    >>> sql, params = expr.to_sql()
"""

from typing import Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.introspection import (
    IntrospectionExpression,
)

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase

__all__ = [
    "SQLServerExtendedPropertyListQueryStatement",
    "SQLServerPrimaryKeyQueryStatement",
    "SQLServerRoutineListQueryStatement",
    "SQLServerSchemaListQueryStatement",
    "SQLServerSequenceListQueryStatement",
]


class SQLServerPrimaryKeyQueryStatement(IntrospectionExpression):
    """Ask which columns make up one table's primary key.

    Args:
        dialect: The dialect the statement is bound to.
        table_name: The table whose key columns are wanted.
        schema: The schema the table is resolved in.
    """

    KIND_RESERVED = ("SQLServer",)

    def __init__(self, dialect: "SQLDialectBase", *, table_name: str, schema: str):
        super().__init__(dialect, schema=schema)
        self.table_name: str = table_name

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_primary_key_query_statement"

    def __repr__(self) -> str:
        return (
            f"SQLServerPrimaryKeyQueryStatement("
            f"table_name={self.table_name!r}, schema={self.schema!r})"
        )


class SQLServerSchemaListQueryStatement(IntrospectionExpression):
    """Ask for this database's schemas and their owning principals.

    The question has no parameters beyond the dialect: ``sys.schemas`` is
    scoped to the current database, so there is nothing to narrow.

    Args:
        dialect: The dialect the statement is bound to.
    """

    KIND_RESERVED = ("SQLServer",)

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_schema_list_query_statement"

    def __repr__(self) -> str:
        return "SQLServerSchemaListQueryStatement()"


class SQLServerExtendedPropertyListQueryStatement(IntrospectionExpression):
    """Ask for ``sys.extended_properties`` rows of one catalogue object.

    The object is named one of two ways, and exactly one of them:

    * ``major_id`` -- its catalogue id, when the caller already has it. The id
      means something different in each ``class_desc`` family;
    * ``table_name`` -- a table's name, which the dialect resolves through
      ``sys.tables``/``sys.schemas`` in the same query. It is the way a caller
      who only has a name can ask, and it costs one round trip rather than
      two.

    Naming both (or neither) is a malformed question, refused at construction
    rather than answered by guessing which one was meant.

    Args:
        dialect: The dialect the statement is bound to.
        major_id: The object id for ``OBJECT_OR_COLUMN`` (class 1), or the id
            in the family's own space for another class.
        table_name: The table whose properties are wanted. Only
            ``OBJECT_OR_COLUMN`` has a table, and the dialect refuses any other
            class rather than returning nothing.
        minor_id: ``None`` for every row of the object, or the exact
            ``minor_id`` -- ``0`` for an object-level property, a
            ``column_id`` for a column-level one.
        class_name: The ``class_desc`` family. The dialect refuses a name
            outside SQL Server's documented set, and refuses a schema on a
            family that has none.
        schema: Restrict to objects in this schema, or ``None``.
    """

    KIND_RESERVED = ("SQLServer",)

    def __init__(
        self,
        dialect: "SQLDialectBase",
        *,
        major_id: Optional[int] = None,
        table_name: Optional[str] = None,
        minor_id: Optional[int] = None,
        class_name: str = "OBJECT_OR_COLUMN",
        schema: Optional[str] = None,
    ):
        if (major_id is None) == (table_name is None):
            raise ValueError(
                "an extended-property question takes exactly one of "
                "major_id or table_name"
            )
        super().__init__(dialect, schema=schema)
        self.major_id: Optional[int] = major_id
        self.table_name: Optional[str] = table_name
        self.minor_id: Optional[int] = minor_id
        self.class_name: str = class_name

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_extended_property_list_query_statement"

    def __repr__(self) -> str:
        return (
            f"SQLServerExtendedPropertyListQueryStatement("
            f"major_id={self.major_id!r}, table_name={self.table_name!r}, "
            f"minor_id={self.minor_id!r}, class_name={self.class_name!r}, "
            f"schema={self.schema!r})"
        )


class SQLServerRoutineListQueryStatement(IntrospectionExpression):
    """Ask for the routines of one schema, by ``sys.objects.type`` code.

    One class for both families: a procedure is a routine whose type is
    ``P``/``PC`` and a function is one of the ``FN``/``IF``/``TF``/``FS``/
    ``FT`` codes, so the only difference between the two questions is the
    code set.

    Args:
        dialect: The dialect the statement is bound to.
        type_codes: The ``sys.objects.type`` codes this question admits.
        schema: The schema to read, or ``None`` for the default schema.
    """

    KIND_RESERVED = ("SQLServer",)

    def __init__(
        self,
        dialect: "SQLDialectBase",
        *,
        type_codes: Tuple[str, ...],
        schema: Optional[str],
    ):
        super().__init__(dialect, schema=schema)
        self.type_codes: Tuple[str, ...] = type_codes

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_routine_list_query_statement"

    def __repr__(self) -> str:
        return (
            f"SQLServerRoutineListQueryStatement("
            f"type_codes={self.type_codes!r}, schema={self.schema!r})"
        )


class SQLServerSequenceListQueryStatement(IntrospectionExpression):
    """Ask for this database's sequences in one schema.

    Args:
        dialect: The dialect the statement is bound to.
        schema: The schema to read, or ``None`` for the default schema.
    """

    KIND_RESERVED = ("SQLServer",)

    def __init__(self, dialect: "SQLDialectBase", *, schema: Optional[str]):
        super().__init__(dialect, schema=schema)

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this statement."""
        return "format_sequence_list_query_statement"

    def __repr__(self) -> str:
        return f"SQLServerSequenceListQueryStatement(schema={self.schema!r})"
