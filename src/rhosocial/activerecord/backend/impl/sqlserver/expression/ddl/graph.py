# src/rhosocial/activerecord/backend/impl/sqlserver/expression/ddl/graph.py
"""SQL Server SQL Graph DDL expressions (SQL Server 2017+).

Graph tables are ordinary tables annotated with ``AS NODE`` / ``AS EDGE``
(edge tables additionally support ``CONNECTION`` edge constraints from SQL Server 2019):

    CREATE TABLE dbo.Person (ID INT PRIMARY KEY, name VARCHAR(50)) AS NODE;
    CREATE TABLE dbo.friend (start_date DATE) AS EDGE;
    ALTER TABLE dbo.friend ADD CONSTRAINT ec_friend CONNECTION (Person TO Person);

SQL generation is delegated to the dialect's
``format_as_graph_table_expression`` / ``format_sqlserver_edge_constraint``
formatters.
"""

from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from ...dialect import SQLServerDialect


class SQLServerGraphTableKind(str, Enum):
    """Graph table kind for ``CREATE TABLE ... AS NODE | AS EDGE``.

    A member *is* the word it carries -- ``str.__str__``, not ``Enum.__str__``,
    which would win the base order otherwise -- because the member rides inside
    ``SQLServerAsGraphTableExpression``'s params and a param that travels in an
    artifact must be a JSON scalar. Plain ``Enum`` raises "not one of the value
    kinds" the moment anything serialises the node, which is how the spelling
    was settled.
    """

    __str__ = str.__str__

    NODE = "NODE"
    EDGE = "EDGE"


def _as_graph_table_kind(value: Any) -> SQLServerGraphTableKind:
    """Read a graph table kind as the member it names.

    A member and the word it carries are the same thing here -- the enum is a
    ``str`` subclass, so a word *is* the member's value -- but only the member
    answers ``.value``, and an artifact hands back the word. Normalising at
    construction keeps one spelling inside the node and lets the formatter read
    a field rather than guess what it was given.
    """
    if isinstance(value, SQLServerGraphTableKind):
        return value
    if isinstance(value, str):
        try:
            return SQLServerGraphTableKind(value.strip().upper())
        except ValueError:
            pass
    raise ValueError(f"unknown graph table kind {value!r}; use NODE or EDGE")


class SQLServerAsGraphTableExpression(BaseExpression):
    """The ``AS NODE`` / ``AS EDGE`` table-kind fragment on ``CREATE TABLE``."""
    KIND_RESERVED = ("SQLServer",)

    def __init__(self, dialect: "SQLServerDialect", kind: SQLServerGraphTableKind):
        super().__init__(dialect)
        self.kind = _as_graph_table_kind(kind)

    @property
    def format_method(self) -> str:
        return "format_as_graph_table_expression"


class SQLServerEdgeConstraint(BaseExpression):
    """A ``CONNECTION (<from> TO <to>)`` edge constraint on an edge table.

    Attributes:
        from_table: Node table the edge connects from.
        to_table: Node table the edge connects to.
        name: Optional constraint name.
    """
    KIND_RESERVED = ("SQLServer",)

    def __init__(self, dialect: "SQLServerDialect", from_table: str, to_table: str,
                 name: Optional[str] = None):
        super().__init__(dialect)
        self.from_table = from_table
        self.to_table = to_table
        self.name = name

    @property
    def format_method(self) -> str:
        return "format_sqlserver_edge_constraint"


__all__ = [
    "SQLServerGraphTableKind",
    "SQLServerAsGraphTableExpression",
    "SQLServerEdgeConstraint",
]
