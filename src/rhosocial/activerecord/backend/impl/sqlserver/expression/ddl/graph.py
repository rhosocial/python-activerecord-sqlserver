# src/rhosocial/activerecord/backend/impl/sqlserver/expression/ddl/graph.py
"""SQL Server SQL Graph DDL expressions (SQL Server 2017+).

Graph tables are ordinary tables annotated with ``AS NODE`` / ``AS EDGE``
(edge tables additionally support ``CONNECTION`` edge constraints from SQL Server 2019):

    CREATE TABLE dbo.Person (ID INT PRIMARY KEY, name VARCHAR(50)) AS NODE;
    CREATE TABLE dbo.friend (start_date DATE) AS EDGE;
    ALTER TABLE dbo.friend ADD CONSTRAINT ec_friend CONNECTION (Person TO Person);

SQL generation is delegated to the dialect's
``format_sqlserver_graph_table_kind`` / ``format_sqlserver_edge_constraint``
formatters.
"""

from enum import Enum
from typing import Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from ...dialect import SQLServerDialect


class SQLServerGraphTableKind(Enum):
    """Graph table kind for ``CREATE TABLE ... AS NODE | AS EDGE``."""

    NODE = "NODE"
    EDGE = "EDGE"


class SQLServerAsGraphTableExpression(BaseExpression):
    """The ``AS NODE`` / ``AS EDGE`` table-kind fragment on ``CREATE TABLE``."""

    def __init__(self, dialect: "SQLServerDialect", kind: SQLServerGraphTableKind):
        super().__init__(dialect)
        self.kind = kind

    @property
    def format_method(self) -> str:
        return "format_sqlserver_graph_table_kind"


class SQLServerEdgeConstraint(BaseExpression):
    """A ``CONNECTION (<from> TO <to>)`` edge constraint on an edge table.

    Attributes:
        from_table: Node table the edge connects from.
        to_table: Node table the edge connects to.
        name: Optional constraint name.
    """

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
