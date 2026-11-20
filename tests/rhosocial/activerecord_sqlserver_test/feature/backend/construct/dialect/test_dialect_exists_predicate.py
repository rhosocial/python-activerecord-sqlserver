# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/dialect/test_dialect_exists_predicate.py
"""Offline rendering checks for T-SQL EXISTS (scalar vs boolean context).

Core's ``exists()`` turns an ``ExistsPredicate`` into an aliased scalar select
expression. T-SQL has no boolean scalar and rejects ``SELECT EXISTS (...)``, so
the SQL Server dialect renders the aliased form as ``CASE WHEN ... THEN 1 ELSE 0
END``; an unaliased EXISTS must stay a plain boolean predicate for WHERE.
"""

import pytest

from rhosocial.activerecord.backend.expression import (
    Column,
    ExistsPredicate,
    QueryStatement,
)
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.query_parts import WhereClause
from rhosocial.activerecord.backend.expression.sources import NamedRelationRef
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


@pytest.fixture
def dialect() -> SQLServerDialect:
    return SQLServerDialect((16, 0, 0))


def _subquery(dialect: SQLServerDialect) -> QueryStatement:
    return QueryStatement(
        dialect,
        select=[Column(dialect, "id")],
        from_=NamedRelationRef(dialect, Table(dialect, "users")),
    )


def test_scalar_exists_renders_case_when(dialect: SQLServerDialect) -> None:
    """An aliased (scalar) EXISTS uses the T-SQL integer-boolean form."""
    exists_expr = ExistsPredicate(dialect, _subquery(dialect))
    exists_expr.alias = "_exists"
    query = QueryStatement(
        dialect,
        select=[exists_expr],
        from_=NamedRelationRef(dialect, Table(dialect, "users")),
    )
    sql, params = query.to_sql()
    assert sql == (
        "SELECT CASE WHEN EXISTS (SELECT [id] FROM [users]) THEN 1 ELSE 0 END "
        "AS [_exists] FROM [users]"
    )
    assert params == ()


def test_where_exists_stays_boolean_predicate(dialect: SQLServerDialect) -> None:
    """An unaliased EXISTS in WHERE is left as a plain predicate."""
    query = QueryStatement(
        dialect,
        select=[Column(dialect, "id")],
        from_=NamedRelationRef(dialect, Table(dialect, "users")),
        where=WhereClause(dialect, condition=ExistsPredicate(dialect, _subquery(dialect))),
    )
    sql, params = query.to_sql()
    assert sql == "SELECT [id] FROM [users] WHERE EXISTS (SELECT [id] FROM [users])"
    assert params == ()


def test_negated_scalar_exists(dialect: SQLServerDialect) -> None:
    """NOT EXISTS keeps its negation in the CASE form."""
    exists_expr = ExistsPredicate(dialect, _subquery(dialect), is_not=True)
    exists_expr.alias = "_exists"
    query = QueryStatement(
        dialect,
        select=[exists_expr],
        from_=NamedRelationRef(dialect, Table(dialect, "users")),
    )
    sql, _ = query.to_sql()
    assert sql.startswith("SELECT CASE WHEN NOT EXISTS (")
