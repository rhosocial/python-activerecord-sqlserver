# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/table_index_change_suggestion.py
"""SQL Server's table-index-change suggestion.

On disk-based tables T-SQL has no ``ALTER TABLE ... ADD/DROP INDEX``: Microsoft
Learn (``ALTER TABLE (Transact-SQL)``, ALTER INDEX / ADD / INDEX) states that
``ALTER TABLE ... ADD``/``DROP``/``ALTER INDEX`` is "supported only for
memory-optimized tables". The honest nodes for a normal table are the
standalone ``CREATE INDEX`` / ``DROP INDEX`` statements, which this dialect
renders as ``CREATE INDEX [ix] ON [t] (...)`` and ``DROP INDEX [ix] ON [t]``.
One statement per index; the core ``AddIndexAction`` / ``DropIndexAction``
ALTER TABLE actions are deliberately not used.

A frozen index projection carries its name, columns and flags, so a plain
index can be rebuilt from it. A partial index's ``WHERE`` predicate and SQL
Server's memory-optimized ``BUCKET_COUNT`` options cannot be reconstructed from
the frozen form (the former reduces to an opaque ``repr``, the latter has no
home in the generic ``CreateIndexStatement``); when the caller hands a real
``IndexDefinition`` node those values are reused as existing expressions.
Anything that would require inventing SQL answers ``False``. A point with no
difference between its two sides answers ``None``.
"""
from __future__ import annotations

from typing import Any, List, Optional

from ....expression.bases import BaseExpression
from ....expression.objects import Index, Table
from ....expression.statements import CreateIndexStatement, DropIndexStatement
from ....suggestion import TableIndexChangeSuggestion
from ._change_common import (
    projection_name,
    projection_node,
    projection_param,
)

__all__ = ["SQLServerTableIndexChangeSuggestionMixin"]


class SQLServerTableIndexChangeSuggestionMixin:
    """Suggest one standalone CREATE/DROP INDEX statement per changed index."""

    def suggest_table_index_change(
        self, point: TableIndexChangeSuggestion
    ) -> TableIndexChangeSuggestion:
        """Drop removed indexes, then create the new ones, one per statement."""
        old = list(point.old_indexes or ())
        new = list(point.new_indexes or ())
        dropped = [projection for projection in old if projection not in new]
        added = [projection for projection in new if projection not in old]
        if not dropped and not added:
            return TableIndexChangeSuggestion(operations=None)

        table_name = point.table_name
        if not isinstance(table_name, str) or not table_name.strip():
            return TableIndexChangeSuggestion(operations=False)

        table = Table(self, table_name)
        statements: List[BaseExpression] = []
        for projection in dropped:
            name = projection_name(projection)
            if name is None:
                return TableIndexChangeSuggestion(operations=False)
            statements.append(DropIndexStatement(self, Index(self, name), table))
        for projection in added:
            statement = self._create_index(projection, table)
            if statement is None:
                return TableIndexChangeSuggestion(operations=False)
            statements.append(statement)
        return TableIndexChangeSuggestion(operations=tuple(statements))

    def _create_index(
        self, projection: Any, table: Table
    ) -> Optional[CreateIndexStatement]:
        """Rebuild a CREATE INDEX from a projection, or ``None`` to refuse."""
        name = projection_name(projection)
        columns = projection_param(projection, "columns")
        if name is None:
            return None
        if (
            not isinstance(columns, (list, tuple))
            or not columns
            or any(not isinstance(column, str) or not column.strip() for column in columns)
        ):
            return None

        # SQL Server has neither CREATE INDEX IF NOT EXISTS nor CONCURRENTLY.
        if projection_param(projection, "if_not_exists") or projection_param(
            projection, "concurrent"
        ):
            return None
        # A memory-optimized HASH index needs WITH (BUCKET_COUNT = ...), which
        # the generic CreateIndexStatement has no field for.
        if projection_param(projection, "hash_index") or projection_param(
            projection, "bucket_count"
        ) is not None:
            return None

        where = None
        if projection_param(projection, "partial_condition") is not None:
            node = projection_node(projection)
            where = getattr(node, "partial_condition", None) if node is not None else None
            if not isinstance(where, BaseExpression):
                # A frozen partial condition is an opaque repr; guessing a
                # predicate node would be inventing SQL.
                return None

        include = projection_param(projection, "include_columns")
        if include is not None and (
            not isinstance(include, (list, tuple))
            or any(not isinstance(column, str) or not column.strip() for column in include)
        ):
            return None
        index_type = projection_param(projection, "type")
        if index_type is not None and not isinstance(index_type, str):
            return None

        return CreateIndexStatement(
            self,
            Index(self, name),
            table,
            list(columns),
            unique=bool(projection_param(projection, "unique", False)),
            index_type=index_type,
            where=where,
            include=list(include) if include else None,
        )
