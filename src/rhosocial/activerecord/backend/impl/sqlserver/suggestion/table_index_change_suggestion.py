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
home in the generic ``CreateIndexStatement``). The enriched point also carries
live ``IndexDefinition`` declarations, so a change that needs one of those
values reuses the live node's own expression instead of rebuilding it from a
projection that cannot state it. Options the dialect actually spells --
CLUSTERED / NONCLUSTERED, UNIQUE and INCLUDE -- come from that node. Anything
that would require inventing SQL (``BUCKET_COUNT``, an opaque predicate, IF
NOT EXISTS or CONCURRENTLY) answers ``False``. A point with no difference
between its two sides answers ``None``.
"""
from __future__ import annotations

from typing import Any, List, Optional

from ....expression.bases import BaseExpression
from ....expression.objects import Index, Table
from ....expression.statements import CreateIndexStatement, DropIndexStatement
from ....expression.statements.ddl_table import IndexDefinition
from ....suggestion import TableIndexChangeSuggestion
from ._change_common import (
    fingerprint,
    live_by_name,
    named_values,
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
        old = named_values(point.old_indexes)
        new = named_values(point.new_indexes)
        if old is None or new is None:
            return TableIndexChangeSuggestion(operations=False)
        old_live = live_by_name(point.old_index_declarations, IndexDefinition)
        new_live = live_by_name(point.new_index_declarations, IndexDefinition)
        removed = [
            name
            for name, value in old.items()
            if name not in new
            or fingerprint(name, value, old_live) != fingerprint(name, new[name], new_live)
        ]
        added = [
            name
            for name, value in new.items()
            if name not in old
            or fingerprint(name, value, new_live) != fingerprint(name, old[name], old_live)
        ]
        if not removed and not added:
            return TableIndexChangeSuggestion(operations=None)

        table_name = point.table_name
        if not isinstance(table_name, str) or not table_name.strip():
            return TableIndexChangeSuggestion(operations=False)

        table = Table(self, table_name)
        statements: List[BaseExpression] = []
        for name in removed:
            statements.append(DropIndexStatement(self, Index(self, name), table))
        for name in added:
            declaration = new_live.get(name, new[name])
            statement = self._create_index(declaration, table)
            if statement is None:
                return TableIndexChangeSuggestion(operations=False)
            statements.append(statement)
        return TableIndexChangeSuggestion(operations=tuple(statements))

    def _create_index(
        self, projection_value: Any, table: Table
    ) -> Optional[CreateIndexStatement]:
        """Rebuild a CREATE INDEX from a projection or live node, or refuse."""
        name = projection_name(projection_value)
        columns = projection_param(projection_value, "columns")
        if name is None:
            return None
        if (
            not isinstance(columns, (list, tuple))
            or not columns
            or any(not isinstance(column, str) or not column.strip() for column in columns)
        ):
            return None

        # SQL Server has neither CREATE INDEX IF NOT EXISTS nor CONCURRENTLY.
        if projection_param(projection_value, "if_not_exists") or projection_param(
            projection_value, "concurrent"
        ):
            return None
        # A memory-optimized HASH index needs WITH (BUCKET_COUNT = ...), which
        # the generic CreateIndexStatement has no field for.
        if projection_param(projection_value, "hash_index") or projection_param(
            projection_value, "bucket_count"
        ) is not None:
            return None

        where = None
        if projection_param(projection_value, "partial_condition") is not None:
            node = projection_node(projection_value)
            where = getattr(node, "partial_condition", None) if node is not None else None
            if not isinstance(where, BaseExpression):
                # A frozen partial condition is an opaque repr; guessing a
                # predicate node would be inventing SQL.
                return None

        include = projection_param(projection_value, "include_columns")
        if include is not None and (
            not isinstance(include, (list, tuple))
            or any(not isinstance(column, str) or not column.strip() for column in include)
        ):
            return None
        index_type = projection_param(projection_value, "type")
        if index_type is not None and not isinstance(index_type, str):
            return None

        return CreateIndexStatement(
            self,
            Index(self, name),
            table,
            list(columns),
            unique=bool(projection_param(projection_value, "unique", False)),
            index_type=index_type,
            where=where,
            include=list(include) if include else None,
        )
