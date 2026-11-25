# src/rhosocial/activerecord/backend/impl/sqlserver/expression/constraint_state.py
"""SQL Server ``CHECK`` / ``NOCHECK CONSTRAINT`` state statements.

Microsoft Learn, `ALTER TABLE (Transact-SQL)
<https://learn.microsoft.com/en-us/sql/t-sql/statements/alter-table-transact-sql>`_,
disk-based table syntax::

    [ WITH { CHECK | NOCHECK } ] { CHECK | NOCHECK } CONSTRAINT
        { ALL | constraint_name [ ,...n ] }

The spelling has **two** keyword positions, which is why the obvious guess --
``ALTER TABLE t WITH CHECK CONSTRAINT c`` -- is wrong: ``WITH { CHECK |
NOCHECK }`` belongs to ``ADD`` / to a re-enable, and the state change itself
still needs the second ``CHECK`` or ``NOCHECK``. The canonical re-validation
form quoted by that page is ``ALTER TABLE table WITH CHECK CHECK CONSTRAINT
ALL``.

The two state verbs are different operations, not a boolean on one node:

* ``NOCHECK CONSTRAINT`` disables the constraint (``is_disabled = 1``) and
  leaves it untrusted;
* ``CHECK CONSTRAINT`` re-enables it, and with the default ``WITH NOCHECK``
  on a re-enable it does not re-validate existing rows. Adding ``WITH CHECK``
  is what re-validates and clears ``is_not_trusted``.

Both are measured on SQL Server 2019 (15.0.4465.1, Developer Edition) as
accepted, and both work on CHECK and FOREIGN KEY constraints; see
``mixins/constraint.py``. Core has no node for this state vocabulary, so these
are backend-proprietary expressions: one node per state verb, one formatter
each, nothing re-exported from core.
"""

from typing import Optional, Sequence, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from ..dialect import SQLServerDialect


class SQLServerCheckConstraintStatement(BaseExpression):
    """``ALTER TABLE ... [WITH CHECK|NOCHECK] CHECK CONSTRAINT ...``.

    Parameters are collected only; the dialect formatter owns every check
    (mutually exclusive switches, a usable table name, a non-empty address).

    Args:
        dialect: The dialect this statement is bound to; ``None`` is accepted
            at construction and bound later through :attr:`dialect`.
        table_name: Target table, optionally schema-qualified (``dbo.t``).
        constraint_names: Named constraints; mutually exclusive with
            ``all_constraints``.
        all_constraints: ``ALL`` instead of a name list. ``ALL`` reaches every
            CHECK and FOREIGN KEY constraint on the table.
        with_check: Emit ``WITH CHECK`` before ``CHECK CONSTRAINT``; this is
            the re-validating form. Mutually exclusive with ``with_nocheck``.
        with_nocheck: Emit ``WITH NOCHECK`` before ``CHECK CONSTRAINT``.

    Example:
        >>> expr = SQLServerCheckConstraintStatement(
        ...     dialect, "dbo.t", constraint_names=["ck_a"], with_check=True
        ... )
        >>> sql, params = expr.to_sql()
        >>> assert sql == "ALTER TABLE [dbo].[t] WITH CHECK CHECK CONSTRAINT [ck_a]"
    """

    KIND_RESERVED = ("SQLServer",)

    def __init__(
        self,
        dialect: Optional["SQLServerDialect"],
        table_name: str,
        *,
        constraint_names: Sequence[str] = (),
        all_constraints: bool = False,
        with_check: bool = False,
        with_nocheck: bool = False,
    ):
        super().__init__(dialect)
        self.table_name = table_name
        self.constraint_names = list(constraint_names)
        self.all_constraints = all_constraints
        self.with_check = with_check
        self.with_nocheck = with_nocheck

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this CHECK statement."""
        return "format_check_constraint_statement"


class SQLServerNocheckConstraintStatement(BaseExpression):
    """``ALTER TABLE ... [WITH CHECK|NOCHECK] NOCHECK CONSTRAINT ...``.

    The disable half of the state vocabulary. It is a distinct kind from
    :class:`SQLServerCheckConstraintStatement` because the two verbs change
    state in opposite directions; a single class with a boolean would put two
    different statements behind one formatter.

    Args:
        dialect: The dialect this statement is bound to; ``None`` is accepted
            at construction and bound later through :attr:`dialect`.
        table_name: Target table, optionally schema-qualified (``dbo.t``).
        constraint_names: Named constraints; mutually exclusive with
            ``all_constraints``.
        all_constraints: ``ALL`` instead of a name list.
        with_check: Emit ``WITH CHECK`` before ``NOCHECK CONSTRAINT``. It is
            syntactically legal but does not validate anything while the
            constraint is disabled.
        with_nocheck: Emit ``WITH NOCHECK`` before ``NOCHECK CONSTRAINT``;
            mutually exclusive with ``with_check``.

    Example:
        >>> expr = SQLServerNocheckConstraintStatement(dialect, "t", all_constraints=True)
        >>> sql, params = expr.to_sql()
        >>> assert sql == "ALTER TABLE [t] NOCHECK CONSTRAINT ALL"
    """

    KIND_RESERVED = ("SQLServer",)

    def __init__(
        self,
        dialect: Optional["SQLServerDialect"],
        table_name: str,
        *,
        constraint_names: Sequence[str] = (),
        all_constraints: bool = False,
        with_check: bool = False,
        with_nocheck: bool = False,
    ):
        super().__init__(dialect)
        self.table_name = table_name
        self.constraint_names = list(constraint_names)
        self.all_constraints = all_constraints
        self.with_check = with_check
        self.with_nocheck = with_nocheck

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this NOCHECK statement."""
        return "format_nocheck_constraint_statement"
