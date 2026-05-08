# src/rhosocial/activerecord/backend/impl/sqlserver/expression/locking.py
"""SQL Server table hint and locking expressions."""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


@dataclass
class SQLServerTableHint:
    """SQL Server table hint definition.

    Attributes:
        name: Hint name (e.g., 'NOLOCK', 'UPDLOCK', 'READPAST', 'HOLDLOCK')
    """
    name: str

    def to_sql(self) -> str:
        return self.name


class SQLServerReadPastHint(SQLServerTableHint):
    """SQL Server READPAST hint - skip locked rows (2019+)."""

    def __init__(self):
        super().__init__("READPAST")


class SQLServerTableHintClause(BaseExpression):
    """SQL Server table hint clause.

    Appends WITH (hint1, hint2, ...) after table references.

    Example:
        >>> hint = SQLServerTableHintClause(dialect, [SQLServerTableHint("NOLOCK")])
    """

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

    def to_sql(self) -> SQLQueryAndParams:
        if not self.hints:
            return "", ()
        hint_strs = [h.to_sql() for h in self.hints]
        return f"WITH ({', '.join(hint_strs)})", ()