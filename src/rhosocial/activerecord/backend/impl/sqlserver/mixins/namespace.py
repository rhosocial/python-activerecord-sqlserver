# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/namespace.py
"""SQL Server namespaces: which levels a name carries, and how it is validated.

SQL Server is the only engine in this family that renders all three namespace
slots at once -- ``[catalog].[schema].[name]`` -- so this backend is where the
schema-object layer gets exercised end to end. The rendering itself is core's:
each object kind declares a ``format_<kind>_object`` and the matching
``*NameMixin`` implements it on top of
:meth:`NamespaceMixin.format_qualified_name`.
What this mixin supplies is everything core leaves to the engine -- that a
catalog exists above the schema, that both are rendered, and that an identifier
is capped at 128 characters.

Two names exist for one object, and each is a named method rather than a string
built inside a formatter:

``<kind>Object.to_sql()``
    Bracketed: ``[catalog].[schema].[name]``. The ordinary identifier form,
    reached through the per-kind formatter.
``format_object_id_name``
    Bare: ``catalog.schema.name``. ``OBJECT_ID()`` takes a string literal
    naming an object, not a T-SQL identifier, and SQL Server does not strip
    brackets from it -- ``OBJECT_ID(N'[dbo].[t]', N'U')`` is NULL. This is the
    single deliberate exception, and it is documented at the method that
    produces it.

Core's ``NamespaceMixin`` answers two questions and keeps them apart.
``validate_namespace`` accepts or refuses the namespace levels an object
carries; ``format_qualified_name`` spells the name, joining the levels with
``separator``. SQL Server wants the default ``.`` -- the brackets come from
``format_identifier``, not from the join -- so this mixin inherits the
separator rather than restating it, and overrides only what SQL Server knows
that core does not: that both levels exist, that both are rendered, and that an
identifier is capped at 128 characters whatever level it sits at.

Core offers no third operation, and the ``OBJECT_ID`` call site needs one:
join the name *without* quoting each level. That gap is why
:attr:`object_id_separator` and :meth:`format_unquoted_qualified_name` exist
here rather than in core. The reasoning is recorded at both.

The helpers that build objects from a flat name live here too, because several
SQL Server-specific expressions (partition functions and schemes, routines,
triggers, ``NEXT VALUE FOR``) are handed their target as text rather than as an
object, and the namespace has to be read out of that text exactly once.
"""

from typing import Optional, Type

from rhosocial.activerecord.backend.dialect.mixins.schema_namespace import NamespaceMixin
from rhosocial.activerecord.backend.expression.objects import SchemaObject

from ..expression.objects import SQLServerTable

#: A qualified name has at most three parts: catalog, schema, name.
_MAX_QUALIFIED_PARTS = 3

#: SQL Server caps every identifier -- catalog, schema and name alike -- at
#: 128 characters.
_SQL_SERVER_MAX_IDENTIFIER_LENGTH = 128


class SQLServerNamespaceMixin(NamespaceMixin):
    """SQL Server's answer to which namespace levels a name may carry."""

    #: What goes between the levels of the bare name ``OBJECT_ID`` reads.
    #:
    #: ``NamespaceMixin.separator`` governs *T-SQL identifiers*, where the
    #: character between ``[catalog]`` and ``[schema]`` is a period. It is not
    #: the right source for this, because ``OBJECT_ID`` is handed a string
    #: literal rather than an identifier and SQL Server does not treat the
    #: period as T-SQL syntax there -- it parses the literal's text into
    #: namespace parts. The character happens to be a period in both places,
    #: and it is kept separate on purpose so that a future dialect which spells
    #: identifiers with a different join cannot silently change the shape of a
    #: string literal, and so that no one reads ``separator`` as the reason
    #: ``OBJECT_ID`` cannot have brackets.
    object_id_separator: str = "."

    # ------------------------------------------------------------------
    # NamespaceSupport
    # ------------------------------------------------------------------

    def supports_catalog(self) -> bool:
        """SQL Server models a catalog above the schema (the database)."""
        return True

    def supports_catalog_qualification(self) -> bool:
        """SQL Server renders the catalog when a name carries one."""
        return True

    def supports_schema_qualification(self) -> bool:
        """SQL Server renders the schema when a name carries one.

        Distinct from :meth:`supports_schema`, which asks whether the engine has
        schemas at all -- ``dbo`` does, and ``CREATE SCHEMA`` is spelled. This
        one asks the naming question, and SQL Server qualifies with the schema
        whether or not the caller supplies one: ``[catalog].[schema].[name]`` is
        the shape every object name takes.
        """
        return True

    def validate_catalog_name(self, obj: object) -> None:
        """Accept or reject the catalog ``obj`` carries.

        SQL Server caps every identifier at 128 characters, and a catalog is an
        ordinary identifier as far as that limit is concerned. ``tempdb``-style
        names are fine; nothing about the outer namespace is special, so no
        other rule is applied here.
        """
        self._validate_identifier_length(getattr(obj, "catalog_name", None), "catalog_name")

    def validate_schema_name(self, obj: object) -> None:
        """Accept or reject the schema ``obj`` carries.

        The same 128-character cap applies; the inner namespace is no more
        exempt than the outer one.
        """
        self._validate_identifier_length(getattr(obj, "schema_name", None), "schema_name")

    @staticmethod
    def _validate_identifier_length(value: Optional[str], field_name: str) -> None:
        """Reject a namespace part SQL Server could not store."""
        if value is not None and len(value) > _SQL_SERVER_MAX_IDENTIFIER_LENGTH:
            raise ValueError(
                f"SQL Server identifiers are limited to "
                f"{_SQL_SERVER_MAX_IDENTIFIER_LENGTH} characters; "
                f"{field_name} is {len(value)} characters"
            )

    # ------------------------------------------------------------------
    # Building objects out of a flat name
    # ------------------------------------------------------------------

    def schema_object(
        self,
        kind: Type[SchemaObject],
        name: str,
        *,
        catalog_name: Optional[str] = None,
        schema_name: Optional[str] = None,
        catalog_need_quote: bool = True,
        schema_need_quote: bool = True,
        name_need_quote: bool = True,
        temporary: bool = False,
    ) -> SchemaObject:
        """The ``kind`` object called ``name`` in the given namespaces.

        The dialect is the object's first constructor argument, as on every
        other expression, so this helper supplies it.

        Args:
            kind: The object class naming *what* this is: ``Table``,
                ``View``, ``Index``, ``Sequence``, ``Type``, ``Procedure``,
                ``Function``, ``SQLServerTable``, ...
            name: The object's own name, unqualified.
            catalog_name: Outer namespace, or ``None`` for the current
                database.
            schema_name: Inner namespace, or ``None`` for the default schema.
            catalog_need_quote: Whether the catalog is quoted when rendered.
            schema_need_quote: Whether the schema is quoted when rendered.
            name_need_quote: Whether the name is quoted when rendered.
            temporary: Whether the table is a ``#``-prefixed temporary. Only
                :class:`SQLServerTable` can be temporary, and asking any other
                kind is an error rather than a silently ignored flag.

        Returns:
            The schema object; it carries no SQL.

        Raises:
            TypeError: ``temporary`` was requested for a kind that has no such
                notion.
            ValueError: A slot is present but not a usable identifier.
        """
        if temporary and kind is not SQLServerTable:
            raise TypeError(
                f"temporary=True is only meaningful for SQLServerTable, "
                f"not for {kind.__name__}"
            )
        slots = {
            "catalog_name": catalog_name,
            "schema_name": schema_name,
            "catalog_need_quote": catalog_need_quote,
            "schema_need_quote": schema_need_quote,
            "name_need_quote": name_need_quote,
        }
        if temporary:
            return kind(self, name, temporary=True, **slots)
        return kind(self, name, **slots)

    def qualified_object_name(
        self,
        kind: Type[SchemaObject],
        name: str,
        **slots,
    ) -> str:
        """The bracketed SQL name of the ``kind`` object called ``name``.

        This is the bridge for the SQL Server-specific expressions that are
        handed their target as text: the object is built, then rendered through
        its own ``format_<kind>_object``, which is the same path a statement
        takes for an object it was given directly. ``slots`` are the keyword
        arguments of :meth:`schema_object`.
        """
        return self.schema_object(kind, name, **slots).to_sql()[0]

    def qualified_object_name_from_dotted(
        self,
        kind: Type[SchemaObject],
        name: str,
        *,
        catalog_name: Optional[str] = None,
        schema_name: Optional[str] = None,
        **slots,
    ) -> str:
        """The bracketed SQL name of a flat name that may carry its namespace.

        Several SQL Server-specific expressions accept the namespace written
        inline -- ``"dbo.pf_sales"`` is a documented way to spell a
        schema-qualified partition function. This is the one place a namespace
        is read back out of text: the parts fill the object's fixed slots from
        the right, and the object is then rendered like every other name.

        Args:
            kind: The object class naming what the name refers to.
            name: One, two or three dot-separated parts.
            catalog_name: Outer namespace, when the caller supplies it
                separately.
            schema_name: Inner namespace, when the caller supplies it
                separately.
            **slots: Remaining :meth:`schema_object` keyword arguments.

        Raises:
            ValueError: The name has more than three parts, has an empty part,
                or supplies a namespace slot the caller also passed
                differently. A name that resolves two ways is reported rather
                than resolved one way or the other.
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")
        parts = name.split(".")
        if len(parts) > _MAX_QUALIFIED_PARTS:
            raise ValueError(
                f"{name!r} has {len(parts)} qualified parts; SQL Server has at "
                f"most {_MAX_QUALIFIED_PARTS} (catalog, schema, name)"
            )
        if any(not part.strip() for part in parts):
            raise ValueError(f"{name!r} must contain non-empty qualified parts")
        dotted_catalog = dotted_schema = None
        if len(parts) == _MAX_QUALIFIED_PARTS:
            dotted_catalog, dotted_schema, name = parts
        elif len(parts) == 2:
            dotted_schema, name = parts
        if dotted_catalog is not None:
            if catalog_name is not None and catalog_name != dotted_catalog:
                raise ValueError(
                    f"catalog_name={catalog_name!r} disagrees with the "
                    f"catalog {dotted_catalog!r} in the name"
                )
            catalog_name = dotted_catalog
        if dotted_schema is not None:
            if schema_name is not None and schema_name != dotted_schema:
                raise ValueError(
                    f"schema_name={schema_name!r} disagrees with the schema "
                    f"{dotted_schema!r} in the name"
                )
            schema_name = dotted_schema
        return self.qualified_object_name(
            kind, name, catalog_name=catalog_name, schema_name=schema_name, **slots
        )

    # ------------------------------------------------------------------
    # The one unbracketed shape
    # ------------------------------------------------------------------
    #
    # The decision this section records, and why the obvious answers are wrong.
    #
    # Core, before ``separator`` existed, spelled a qualified name with a period
    # hard-coded in the middle of one method that also did all the checking.
    # ``format_object_id_name`` could not use that method, because it needs a
    # name with no brackets, and it worked around the exclusion by joining the
    # slots itself: ``".".join(...)``, bypassing the rendering *and* the
    # checks. That is a policy leak with a live failure mode -- if the join were
    # ever lost, or if a slot were added, ``OBJECT_ID`` would return NULL for a
    # table that plainly exists, no test would notice, and no statement would
    # run.
    #
    # With L3 that is no longer the only two-way door, but the obvious repair is
    # still wrong. Deleting the method and calling
    # ``format_qualified_name(expr)`` looks right and is not: that method quotes
    # every level, so ``OBJECT_ID(N'[dbo].[t]')`` comes straight back -- the
    # exact NULL the method exists to prevent. So the requirement is a third
    # operation, not one of the existing two.
    #
    # It belongs to the dialect rather than to core, for two reasons. Core's two
    # operations are about SQL text, and neither has a use for a bare name; this
    # is the only call site in the tree that wants one, and it is SQL Server's
    # ``OBJECT_ID`` that imposes it. Putting it in core would give nine dialects
    # a method none of them calls -- the same "declared but never dispatched"
    # shape core already retired twice. Declaring it here keeps the knowledge
    # with the engine that has it, and gives the conformance tests somewhere to
    # point.
    #
    # What the method deliberately does *not* do is skip the check.
    # ``validate_namespace`` runs first, so an object carrying a level SQL
    # Server cannot express is refused rather than quietly spelled without it.

    def format_unquoted_qualified_name(self, obj: SchemaObject) -> str:
        """*obj*'s qualified name as bare text, with no level quoted.

        The third operation, and the one ``OBJECT_ID`` needs: the same levels
        and the same order as :meth:`~.NamespaceMixin.format_qualified_name`,
        joined by :attr:`object_id_separator` and with each part emitted
        verbatim.

        Args:
            obj: The object being named.

        Returns:
            The bare name, e.g. ``"dbo.t"`` or ``"sales.dbo.t"``. ``params`` is
            absent because this is text, not SQL.
        """
        parts = [part for part in (obj.catalog_name, obj.schema_name, obj.name) if part]
        return self.object_id_separator.join(parts)

    def format_object_id_name(self, obj: SchemaObject) -> str:
        """The ``OBJECT_ID()`` argument naming ``obj``: ``catalog.schema.name``.

        ``OBJECT_ID`` does not take an identifier. It takes a string literal
        naming an object, and SQL Server compares it literally, so brackets
        inside the literal stop it resolving -- ``IF OBJECT_ID(N'[dbo].[t]',
        N'U') IS NULL`` is true for a table that plainly exists. This method
        therefore renders the same object's slots as bare text, and it is the
        only place in the backend that does so.

        It does not build the text itself: the spelling is
        :meth:`format_unquoted_qualified_name`, and the checks are core's
        :meth:`~.NamespaceMixin.validate_namespace`. Both used to be bypassed
        here, which is what made a regression in either invisible.

        The ``OBJECT_ID`` caller is responsible for escaping the result as an
        SQL string literal; this method produces the name, not the literal.
        """
        self.validate_namespace(obj)
        return self.format_unquoted_qualified_name(obj)


__all__ = ["SQLServerNamespaceMixin"]