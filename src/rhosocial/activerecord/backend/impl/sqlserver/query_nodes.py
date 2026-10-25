# src/rhosocial/activerecord/backend/impl/sqlserver/query_nodes.py
"""Expression-node builders for the SQL Server backend's own queries.

An introspection or probe query is a *question* about the catalogue, and this
backend used to spell it as text: f-strings, ``sql +=`` fragments and whole
``SELECT`` statements inline in the introspecter, the backend and its mixins.
A SQL string is a formatting artefact, so it belongs to the dialect formatter,
not to the layer that executes the query (org guide §16.2): the node collects
the parameters, the formatter writes the text, and the caller only constructs
and executes.

Each helper below states one construction once -- a column reference, a value,
a catalogue relation, a conjunction, a projection into a SELECT -- so the
builders read as the questions they ask instead of as the grammar they happen
to be written in. They take the dialect as their first argument because both
the introspectors and the backend classes ask these questions, and those two
families do not share a base class.
"""

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase
    from rhosocial.activerecord.backend.expression.bases import (
        BaseExpression,
        SQLPredicate,
    )
    from rhosocial.activerecord.backend.expression.sources.relation import (
        NamedRelationRef,
    )


def column(
    dialect: "SQLDialectBase",
    name: str,
    table: Optional[str] = None,
    alias: Optional[str] = None,
    name_need_quote: bool = True,
):
    """A column reference, qualified by its relation alias when given.

    ``name_need_quote=False`` is for the names that are grammar rather than
    identifiers -- ``SYSTEM_USER`` is the niladic value function the session
    query selects, and ``@@IDENTITY`` is a variable, so quoting either would
    ask the catalogue for a column of that name instead.
    """
    from rhosocial.activerecord.backend.expression import Column

    return Column(
        dialect, name, table=table, alias=alias, name_need_quote=name_need_quote
    )


def literal(dialect: "SQLDialectBase", value: Any, inline: bool = False):
    """A value in a predicate position.

    *inline* keeps the value out of the parameter tuple. Every position that
    was written into the old statement text (``'BASE TABLE'``,
    ``'PRIMARY KEY'``, ``'IsIdentity'``, a ``SERVERPROPERTY`` name) keeps it:
    those are part of what the query asks, not data it carries, and the
    callers' parameter tuples are a contract this refactor does not move.
    """
    from rhosocial.activerecord.backend.expression import Literal

    return Literal(dialect, value, inline=inline)


def relation(
    dialect: "SQLDialectBase",
    name: str,
    schema_name: Optional[str] = None,
    alias: Optional[str] = None,
) -> "NamedRelationRef":
    """A readable relation, optionally aliased."""
    from rhosocial.activerecord.backend.expression import NamedRelationRef
    from rhosocial.activerecord.backend.expression.objects import Table

    return NamedRelationRef(
        dialect, Table(dialect, name, schema_name=schema_name), alias=alias
    )


def join(dialect: "SQLDialectBase", left, right, condition=None, join_type: str = "JOIN"):
    """Join two row sources on *condition*."""
    from rhosocial.activerecord.backend.expression import JoinClause

    return JoinClause(dialect, left, right, join_type=join_type, condition=condition)


def conjunction(dialect: "SQLDialectBase", *conditions):
    """The conjunction of *conditions*, as one predicate node."""
    from rhosocial.activerecord.backend.expression import LogicalPredicate

    return LogicalPredicate(dialect, "AND", *conditions)


def compare(dialect: "SQLDialectBase", op: str, left, right):
    """A comparison between two expression nodes."""
    from rhosocial.activerecord.backend.expression import ComparisonPredicate

    return ComparisonPredicate(dialect, op, left, right)


def is_not_null(dialect: "SQLDialectBase", operand):
    """``operand IS NOT NULL``."""
    from rhosocial.activerecord.backend.expression import IsNullPredicate

    return IsNullPredicate(dialect, operand, is_not=True)


def contained_in(dialect: "SQLDialectBase", operand, values: Tuple[Any, ...]):
    """``operand IN (...)``, with the values inline as the text had them."""
    from rhosocial.activerecord.backend.expression import InPredicate

    return InPredicate(dialect, operand, literal(dialect, values, inline=True))


def call(
    dialect: "SQLDialectBase",
    name: str,
    *args,
    alias: Optional[str] = None,
    niladic: bool = False,
):
    """A function call node, optionally aliased."""
    from rhosocial.activerecord.backend.expression import FunctionCall

    return FunctionCall(dialect, name, *args, alias=alias, niladic=niladic)


def row_count(dialect: "SQLDialectBase"):
    """The ``*`` that counts rows, as ``COUNT(*)`` takes it."""
    from rhosocial.activerecord.backend.expression import RowCountWildcard

    return RowCountWildcard(dialect)


def cast(dialect: "SQLDialectBase", node, type_name: str):
    """``CAST(node AS type_name)``."""
    from rhosocial.activerecord.backend.expression.types._base import DataType

    return node.cast(DataType.parse_data_type_str(dialect, type_name))


def multiply(dialect: "SQLDialectBase", left, right):
    """``left * right`` as an arithmetic node."""
    from rhosocial.activerecord.backend.expression.operators import (
        ArithmeticOperation,
        ArithmeticOperator,
    )

    return ArithmeticOperation(dialect, ArithmeticOperator.MUL, left, right)


def add(dialect: "SQLDialectBase", left, right):
    """``left + right`` as an arithmetic node.

    SQL Server spells string concatenation with ``+`` (``||`` only from 2025),
    so joining two columns into one name is an arithmetic ``add`` here rather
    than the standard concatenation node.
    """
    from rhosocial.activerecord.backend.expression.operators import (
        ArithmeticOperation,
        ArithmeticOperator,
    )

    return ArithmeticOperation(dialect, ArithmeticOperator.ADD, left, right)


def query(
    dialect: "SQLDialectBase",
    select: List["BaseExpression"],
    from_=None,
    where: Optional["SQLPredicate"] = None,
    group_by: Optional[List["BaseExpression"]] = None,
    order_by: Optional[list] = None,
    limit: Optional[int] = None,
):
    """A ``QueryStatement`` node, ready to render or to nest.

    Args:
        dialect: The dialect the node is bound to.
        select: The projection, in order.
        from_: A relation or join node, or ``None`` for a query that asks the
            engine a question and reads no table.
        where: A predicate node, or ``None`` for no WHERE clause.
        group_by: Grouping expressions, or ``None``.
        order_by: ``(expression, direction)`` pairs, or ``None``.
        limit: A row cap, or ``None``. This is the pagination node, which SQL
            Server renders as ``OFFSET 0 ROWS FETCH NEXT n ROWS ONLY`` and
            therefore requires 2012+ and an ORDER BY.

    Returns:
        The ``QueryStatement`` node.
    """
    from rhosocial.activerecord.backend.expression import (
        GroupByHavingClause,
        LimitOffsetClause,
        OrderByClause,
        QueryStatement,
        WhereClause,
    )

    kwargs: Dict[str, Any] = {"select": select}
    if from_ is not None:
        kwargs["from_"] = from_
    if where is not None:
        kwargs["where"] = WhereClause(dialect, where)
    if group_by is not None:
        kwargs["group_by_having"] = GroupByHavingClause(dialect, group_by=group_by)
    if order_by is not None:
        kwargs["order_by"] = OrderByClause(dialect, order_by)
    if limit is not None:
        kwargs["limit_offset"] = LimitOffsetClause(dialect, limit=limit)
    return QueryStatement(dialect, **kwargs)


def subquery(
    dialect: "SQLDialectBase",
    select: List["BaseExpression"],
    from_=None,
    where: Optional["SQLPredicate"] = None,
    alias: Optional[str] = None,
):
    """A scalar subquery for a select list."""
    from rhosocial.activerecord.backend.expression import Subquery

    return Subquery(
        dialect, query(dialect, select, from_=from_, where=where), alias=alias
    )


def select_sql(
    dialect: "SQLDialectBase",
    select: List["BaseExpression"],
    from_=None,
    where: Optional["SQLPredicate"] = None,
    group_by: Optional[List["BaseExpression"]] = None,
    order_by: Optional[list] = None,
    limit: Optional[int] = None,
) -> Tuple[str, tuple]:
    """Render one SELECT from nodes, in the dialect's own spelling."""
    return query(
        dialect,
        select,
        from_=from_,
        where=where,
        group_by=group_by,
        order_by=order_by,
        limit=limit,
    ).to_sql()


def server_property(dialect: "SQLDialectBase", name: str, alias: Optional[str] = None):
    """``SERVERPROPERTY('<name>')``, optionally aliased.

    The property name is a literal of the statement, not data, so it stays
    inline: the request carries no parameters.
    """
    node = call(dialect, "SERVERPROPERTY", literal(dialect, name, inline=True))
    return node.as_(alias) if alias else node


def identity_columns_sql(dialect: "SQLDialectBase", table_name: str) -> Tuple[str, tuple]:
    """The identity column names of one table in the default schema.

    Returned as ``(sql, params)`` because the table name is a bind position:
    it is data the query carries, not part of what it asks.
    """
    joined = join(
        dialect,
        relation(dialect, "identity_columns", "sys", alias="c"),
        relation(dialect, "tables", "sys", alias="t"),
        condition=compare(
            dialect,
            "eq",
            column(dialect, "object_id", "c"),
            column(dialect, "object_id", "t"),
        ),
    )
    return select_sql(
        dialect,
        [column(dialect, "name", "c")],
        from_=joined,
        where=conjunction(
            dialect,
            compare(
                dialect, "eq", column(dialect, "name", "t"), literal(dialect, table_name)
            ),
            compare(
                dialect,
                "eq",
                call(dialect, "SCHEMA_NAME", column(dialect, "schema_id", "t")),
                literal(dialect, "dbo", inline=True),
            ),
        ),
    )


def max_worker_threads_sql(dialect: "SQLDialectBase") -> Tuple[str, tuple]:
    """The configured ``max worker threads`` server setting."""
    return select_sql(
        dialect,
        [column(dialect, "value_in_use")],
        from_=relation(dialect, "configurations", "sys"),
        where=compare(
            dialect,
            "eq",
            column(dialect, "name"),
            literal(dialect, "max worker threads", inline=True),
        ),
    )


def server_property_value_sql(
    dialect: "SQLDialectBase", name: str
) -> Tuple[str, tuple]:
    """One ``SERVERPROPERTY`` value, uncast.

    The property name is part of what the query asks, so it stays inline and
    the request carries no parameters -- which is what the raw driver call
    this replaces did.
    """
    return select_sql(dialect, [server_property(dialect, name)])


def session_identity_sql(dialect: "SQLDialectBase") -> Tuple[str, tuple]:
    """The ``@@IDENTITY`` variable: the last identity value this session made."""
    return select_sql(dialect, [column(dialect, "@@IDENTITY", name_need_quote=False)])


def scope_identity_value_sql(dialect: "SQLDialectBase") -> Tuple[str, tuple]:
    """Alias kept for readability at the call sites that want the variable."""
    return session_identity_sql(dialect)


def identity_current_sql(dialect: "SQLDialectBase", table: str) -> Tuple[str, tuple]:
    """``IDENT_CURRENT(<table>)``; the table name is a bind position."""
    return select_sql(dialect, [call(dialect, "IDENT_CURRENT", literal(dialect, table))])


def health_check_sql(dialect: "SQLDialectBase") -> Tuple[str, tuple]:
    """The cheapest statement that proves the connection answers."""
    return select_sql(dialect, [literal(dialect, 1, inline=True)])


class SQLServerNodeBuilderMixin:
    """The node builders above, bound to the object that owns the spelling.

    Two families ask these questions. The introspectors reach their dialect
    through the core introspector mixin; the dialect itself is the spelling.
    They share no base class, so the binding is asked for once -- here, under
    :attr:`_node_dialect` -- and every builder below reads it from there.
    """

    #: The dialect an introspector reaches through core's introspector mixin.
    #: A dialect that uses these builders overrides ``_node_dialect`` instead.
    dialect: "SQLDialectBase"

    @property
    def _node_dialect(self) -> "SQLDialectBase":
        """The dialect every node built here is bound to."""
        return self.dialect

    def _col(self, name: str, table: Optional[str] = None, alias: Optional[str] = None):
        """A column reference, qualified by its relation alias when given."""
        return column(self._node_dialect, name, table=table, alias=alias)

    def _lit(self, value: Any, inline: bool = False):
        """A value in a predicate position; *inline* keeps it out of params."""
        return literal(self._node_dialect, value, inline=inline)

    def _relation(
        self, name: str, schema_name: Optional[str] = None, alias: Optional[str] = None
    ) -> "NamedRelationRef":
        """A readable relation, optionally aliased."""
        return relation(self._node_dialect, name, schema_name=schema_name, alias=alias)

    def _join(self, left, right, condition=None, join_type: str = "JOIN"):
        """Join two row sources on *condition*."""
        return join(self._node_dialect, left, right, condition=condition, join_type=join_type)

    def _and(self, *conditions):
        """The conjunction of *conditions*, as one predicate node."""
        return conjunction(self._node_dialect, *conditions)

    def _eq(self, left, right):
        """Equality between two expression nodes."""
        return compare(self._node_dialect, "eq", left, right)

    def _gt(self, left, right):
        """``left > right`` between two expression nodes."""
        return compare(self._node_dialect, "gt", left, right)

    def _in(self, operand, values: Tuple[Any, ...]):
        """``operand IN (...)``, with the values inline as the text had them."""
        return contained_in(self._node_dialect, operand, values)

    def _is_not_null(self, operand):
        """``operand IS NOT NULL``."""
        return is_not_null(self._node_dialect, operand)

    def _fn(self, name: str, *args, alias: Optional[str] = None, niladic: bool = False):
        """A function call node, optionally aliased."""
        return call(self._node_dialect, name, *args, alias=alias, niladic=niladic)

    def _cast(self, node, type_name: str):
        """``CAST(node AS type_name)``."""
        return cast(self._node_dialect, node, type_name)

    def _mul(self, left, right):
        """``left * right`` as an arithmetic node."""
        return multiply(self._node_dialect, left, right)

    def _add(self, left, right):
        """``left + right`` as an arithmetic node (SQL Server's concatenation)."""
        return add(self._node_dialect, left, right)

    def _row_count_wildcard(self):
        """The ``*`` that counts rows, as ``COUNT(*)`` takes it."""
        return row_count(self._node_dialect)

    def _subquery(self, select, from_=None, where=None, alias=None):
        """A scalar subquery in a select list."""
        return subquery(self._node_dialect, select, from_=from_, where=where, alias=alias)

    def _query(self, select, from_=None, where=None, group_by=None, order_by=None, limit=None):
        """A ``QueryStatement`` node, ready to render or to nest."""
        return query(
            self._node_dialect,
            select,
            from_=from_,
            where=where,
            group_by=group_by,
            order_by=order_by,
            limit=limit,
        )

    def _select(self, select, from_=None, where=None, group_by=None, order_by=None, limit=None):
        """Render one SELECT from nodes, in the dialect's own spelling."""
        return select_sql(
            self._node_dialect,
            select,
            from_=from_,
            where=where,
            group_by=group_by,
            order_by=order_by,
            limit=limit,
        )


__all__ = [
    "SQLServerNodeBuilderMixin",
    "add",
    "call",
    "cast",
    "column",
    "compare",
    "conjunction",
    "contained_in",
    "health_check_sql",
    "identity_columns_sql",
    "identity_current_sql",
    "is_not_null",
    "join",
    "literal",
    "max_worker_threads_sql",
    "multiply",
    "query",
    "relation",
    "row_count",
    "scope_identity_value_sql",
    "select_sql",
    "server_property",
    "server_property_value_sql",
    "session_identity_sql",
    "subquery",
]
