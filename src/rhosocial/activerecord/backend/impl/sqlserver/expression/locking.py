# src/rhosocial/activerecord/backend/impl/sqlserver/expression/locking.py
"""SQL Server table hint and locking expressions."""

from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


@dataclass
class SQLServerTableHint:
    """SQL Server table hint definition.

    A hint is a parameter of the clause that carries it, not a node of its own:
    it holds the word and nothing else. The clause's dialect formatter reads
    ``name`` and joins the words, so this value never renders SQL.

    Attributes:
        name: Hint name (e.g., 'NOLOCK', 'UPDLOCK', 'READPAST', 'HOLDLOCK')
    """
    KIND_RESERVED = ("SQLServer",)

    name: str


class SQLServerReadPastHint(SQLServerTableHint):
    """SQL Server READPAST hint - skip locked rows (2019+)."""
    KIND_RESERVED = ("SQLServer",)

    def __init__(self):
        super().__init__("READPAST")


class SQLServerTableHintClause(BaseExpression):
    """SQL Server table hint clause.

    Appends WITH (hint1, hint2, ...) after table references.

    Example:
        >>> hint = SQLServerTableHintClause(dialect, [SQLServerTableHint("NOLOCK")])
    """
    KIND_RESERVED = ("SQLServer",)

    def __init__(
        self,
        dialect: "SQLDialectBase",
        hints: Optional[List[SQLServerTableHint]] = None,
    ):
        super().__init__(dialect)
        self.hints = hints or []

    def add_hint(self, hint: SQLServerTableHint) -> "SQLServerTableHintClause":
        self.hints.append(hint)
        return self

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        for hint in self.hints:
            if not isinstance(hint, SQLServerTableHint):
                raise TypeError(f"hints must contain SQLServerTableHint, got {type(hint)}")

    @property
    def format_method(self) -> str:
        """The dialect formatter that renders this WITH (...) hint clause."""
        return "format_sqlserver_table_hint_clause"