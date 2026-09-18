# tests/rhosocial/activerecord_sqlserver_test/feature/backend/dialect/test_dql_capabilities.py
"""SQL Server DQL capability tests: WITH TIES and lock strength."""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import (
    ForUpdateClause,
    LimitOffsetClause,
    LockStrength,
)
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


@pytest.fixture
def dialect():
    return SQLServerDialect(version=(16, 0, 0))


@pytest.mark.parametrize("version", [(10, 0, 0), (11, 0, 0), (16, 0, 0), (17, 0, 0)])
def test_fetch_with_ties_unsupported(version):
    assert SQLServerDialect(version=version).supports_fetch_with_ties() is False


@pytest.mark.parametrize("version", [(10, 0, 0), (11, 0, 0), (16, 0, 0), (17, 0, 0)])
@pytest.mark.parametrize("limit, offset", [(5, None), (5, 2), (None, None)])
def test_fetch_with_ties_raises(version, limit, offset):
    dialect = SQLServerDialect(version=version)
    clause = LimitOffsetClause(dialect, limit=limit, offset=offset, with_ties=True)
    with pytest.raises(UnsupportedFeatureError, match="WITH TIES"):
        dialect.format_limit_offset_clause(clause)
    with pytest.raises(UnsupportedFeatureError, match="WITH TIES"):
        clause.to_sql()


def test_fetch_without_ties_renders_only(dialect):
    sql, _ = dialect.format_limit_offset_clause(LimitOffsetClause(dialect, limit=5))
    assert sql == "OFFSET 0 ROWS FETCH NEXT 5 ROWS ONLY"


def test_nulls_first_last_unsupported(dialect):
    assert dialect.supports_nulls_first_last() is False


def test_lock_strength_share_raises(dialect):
    with pytest.raises(Exception):
        ForUpdateClause(dialect, strength=LockStrength.SHARE).to_sql()
