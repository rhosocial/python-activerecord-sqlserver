# src/rhosocial/activerecord/backend/impl/sqlserver/expression/dml.py
"""SQL Server-specific DML expression classes."""

from typing import TYPE_CHECKING, List, Optional

from rhosocial.activerecord.backend.expression.statements import (
    MergeExpression,
    QueryExpression,
)

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase
    from rhosocial.activerecord.backend.expression.bases import BaseExpression


class SQLServerMergeExpression(MergeExpression):
    """A SQL Server MERGE statement extending the generic one.

    SQL Server adds the ``WITH (HOLDLOCK)`` table hint and the ``OUTPUT``
    clause whose columns/action have no generic equivalent. These live here as
    typed fields and are rendered by the SQL Server ``format_merge_statement``
    override.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        target_table,
        source,
        on_condition,
        when_matched=None,
        when_not_matched=None,
        when_not_matched_by_source=None,
        *,
        output: Optional[List] = None,
        output_action: bool = False,
        holdlock: bool = False,
    ):
        super().__init__(
            dialect,
            target_table=target_table,
            source=source,
            on_condition=on_condition,
            when_matched=when_matched,
            when_not_matched=when_not_matched,
            when_not_matched_by_source=when_not_matched_by_source,
        )
        self.output = output
        self.output_action = output_action
        self.holdlock = holdlock


class SQLServerSelectIntoExpression(QueryExpression):
    """A SQL Server ``SELECT ... INTO <table>`` query.

    SQL Server's ``SELECT INTO`` creates a new table from a query result. The
    target table has no generic equivalent and lives here as a typed field; the
    SQL Server ``format_select_into_statement`` reads it.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        select: List["BaseExpression"],
        from_=None,
        where=None,
        group_by_having=None,
        order_by=None,
        qualify=None,
        limit_offset=None,
        for_update=None,
        select_modifier=None,
        *,
        select_into_table: Optional[str] = None,
    ):
        super().__init__(
            dialect,
            select=select,
            from_=from_,
            where=where,
            group_by_having=group_by_having,
            order_by=order_by,
            qualify=qualify,
            limit_offset=limit_offset,
            for_update=for_update,
            select_modifier=select_modifier,
        )
        self.select_into_table = select_into_table


__all__ = [
    "SQLServerMergeExpression",
    "SQLServerSelectIntoExpression",
]
