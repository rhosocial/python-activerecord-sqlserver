# src/rhosocial/activerecord/backend/impl/sqlserver/expression/objects.py
"""The schema-object kinds SQL Server adds to the shared tree.

Every named object the backend touches is a
:class:`~rhosocial.activerecord.backend.expression.objects.SchemaObject`: three
fixed slots (catalog, schema, name), no rendering, no dialect. The shared tree
in ``backend.expression.objects`` already names the kinds SQL Server uses for
tables, views, indexes, sequences, types and routines. Two things are missing,
and they are defined here rather than smuggled into name strings:

:class:`SQLServerTable`
    SQL Server has no ``TEMPORARY`` keyword. A temporary table is spelled by
    prefixing the *name* with ``#``, so the prefix is part of what the table is
    called rather than a rendering decision. ``temporary`` is therefore a field
    on the object, settled once at construction, and the qualified-name renderer
    never has to ask whether it is looking at a temporary table.
:class:`PartitionFunction` / :class:`PartitionScheme`
    SQL Server's partitioning model has two named objects of its own. The
    shared tree does not name them yet; deriving them straight from
    :class:`SchemaObject` keeps them in the same tree with the same three slots
    and leaves promotion to a shared subclass for when another engine grows the
    same pair.

Because these three kinds are SQL Server's own, they declare the formatter that
renders them and the dialect implements it: ``format_table_object`` is already
core's for every table, so :class:`SQLServerTable` inherits it, while the two
partition kinds each get a small renderer on
:class:`~...mixins.partition.SQLServerPartitionMixin`.
"""

from rhosocial.activerecord.backend.expression.objects import SchemaObject, Table

__all__ = ["SQLServerTable", "PartitionFunction", "PartitionScheme"]


class SQLServerTable(Table):
    """A SQL Server table, whose ``#``-prefixed temporary form is a field.

    ``temporary`` records what the table *is*, and the ``#`` prefix is folded
    into :attr:`name` at construction. That is what keeps the qualified-name
    renderer free of a ``if temporary:`` branch: ``CREATE TABLE [#stage]`` and
    ``CREATE TABLE [stage]`` differ only in the object, not in how the object
    is rendered.
    """

    __slots__ = ("temporary",)

    def __init__(self, dialect, name: str, *, temporary: bool = False, **slots) -> None:
        """Record the table's identity.

        Args:
            dialect: The dialect that will render this table.
            name: The table's own name, without the temporary marker.
            temporary: Whether this is a ``#``-prefixed temporary table.
            **slots: ``catalog_name`` / ``schema_name`` and the three
                ``*_need_quote`` flags, passed straight through.
        """
        super().__init__(dialect, name, **slots)
        self.temporary = bool(temporary)
        if self.temporary and not self.name.startswith("#"):
            self.name = f"#{self.name}"

    def identity(self) -> tuple:
        """The comparable payload, widened with :attr:`temporary`.

        ``SQLServerTable("t", temporary=True)`` and ``SQLServerTable("#t")``
        name the same table in SQL Server but disagree about what the object
        is, so both the flag and the resulting name take part.
        """
        return super().identity() + (self.temporary,)


class PartitionFunction(SchemaObject):
    """A SQL Server ``PARTITION FUNCTION``.

    Named by ``CREATE PARTITION FUNCTION`` and referenced by name from a
    partition scheme, so it renders through the dialect's
    ``format_partition_function_object``.
    """

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this partition function."""
        return "format_partition_function_object"


class PartitionScheme(SchemaObject):
    """A SQL Server ``PARTITION SCHEME``.

    Named by ``CREATE PARTITION SCHEME`` and referenced from ``CREATE TABLE ...
    ON <scheme>``, so it renders through the dialect's
    ``format_partition_scheme_object``.
    """

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this partition scheme."""
        return "format_partition_scheme_object"