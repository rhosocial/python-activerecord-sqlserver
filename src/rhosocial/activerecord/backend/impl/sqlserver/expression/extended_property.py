# src/rhosocial/activerecord/backend/impl/sqlserver/expression/extended_property.py
"""SQL Server extended-property write statements.

Microsoft Learn documents three system procedures for writing the catalogue
rows that ``sys.extended_properties`` reads (the read side already has
``SQLServerExtendedPropertyListQueryStatement`` in this package):

``sys.sp_addextendedproperty``
    ``@name``, ``@value``, ``@level0type`` / ``@level0name``, ``@level1type`` /
    ``@level1name``, ``@level2type`` / ``@level2name``.
``sys.sp_updateextendedproperty``
    The same eight arguments; ``@name`` is mandatory and ``@value`` defaults to
    ``NULL``.
``sys.sp_dropextendedproperty``
    ``@name`` plus the six level arguments; there is **no** ``@value``.

All three take the identical object address: level 0 (database-scoped object,
e.g. ``SCHEMA``) owns level 1 (e.g. ``TABLE``) which owns level 2 (e.g.
``COLUMN``). Omitting every level addresses the database itself.

One node, one formatter
=======================

The three operations differ only in the procedure name and in whether a value
is sent. The first eight parameter slots are the same contract, so they are
one expression carrying its operation as a word, rendered by one public
``format_extended_property_write_statement``. Three classes pointing at one
formatter would break the backend's one-to-one node/formatter rule; three
copies of the same argument list in three formatters would be the price of
avoiding a shared private renderer. The word on the node is the identity the
formatter needs, so it belongs on the node (formal spec §3.1, absent-expression
case: SQL Server owns this vocabulary, core does not).

Core has no counterpart: ``CommentOnStatement`` is a read-side analogue at
best, and this backend deliberately declines to render it (``COMMENT ON`` is
not T-SQL). Nothing here is re-exported from core.
"""

from typing import Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from ..dialect import SQLServerDialect


#: The words this node accepts, spelled as the operations Microsoft documents.
#: Kept as data on the expression, not as an enum: an artifact carries a plain
#: string and a reader must be able to rebuild the same node from it.
EXTENDED_PROPERTY_OPERATIONS = ("ADD", "UPDATE", "DROP")


class SQLServerExtendedPropertyWriteStatement(BaseExpression):
    """Add, update or drop one extended property, by procedure call.

    Args:
        dialect: The dialect this statement is bound to; ``None`` is accepted
            at construction and bound later through :attr:`dialect`.
        operation: ``"ADD"``, ``"UPDATE"`` or ``"DROP"``. The formatter
            validates the word and chooses the procedure.
        name: ``@name``; a ``sysname`` and mandatory on every operation.
        value: ``@value`` for ADD / UPDATE; ``None`` writes ``NULL``. Must be
            left unset for DROP, which has no such argument.
        level0type: ``@level0type``, e.g. ``SCHEMA``.
        level0name: ``@level0name``, e.g. ``dbo``.
        level1type: ``@level1type``, e.g. ``TABLE``.
        level1name: ``@level1name``, e.g. ``T1``.
        level2type: ``@level2type``, e.g. ``COLUMN``.
        level2name: ``@level2name``, e.g. ``id``.

    Example:
        >>> expr = SQLServerExtendedPropertyWriteStatement(
        ...     dialect, "ADD", "MS_Description", value="O'Brien",
        ...     level0type="SCHEMA", level0name="dbo",
        ...     level1type="TABLE", level1name="T1",
        ... )
        >>> sql, params = expr.to_sql()
        >>> assert "N'O''Brien'" in sql
    """

    KIND_RESERVED = ("SQLServer",)

    def __init__(
        self,
        dialect: Optional["SQLServerDialect"],
        operation: str,
        name: str,
        *,
        value: Optional[str] = None,
        level0type: Optional[str] = None,
        level0name: Optional[str] = None,
        level1type: Optional[str] = None,
        level1name: Optional[str] = None,
        level2type: Optional[str] = None,
        level2name: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.operation = operation
        self.name = name
        self.value = value
        self.level0type = level0type
        self.level0name = level0name
        self.level1type = level1type
        self.level1name = level1name
        self.level2type = level2type
        self.level2name = level2name

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this procedure call."""
        return "format_extended_property_write_statement"
