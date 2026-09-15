# tests/rhosocial/activerecord_sqlserver_test/feature/backend/dialect/test_dql_capabilities.py
"""SQL Server DQL capability tests: WITH TIES and lock strength."""

import pytest

from rhosocial.activerecord.backend.expression import (
    ForUpdateClause,
    LimitOffsetClause,
    LockStrength,
)
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


@pytest.fixture
def dialect():
    return SQLServerDialect(version=(16, 0, 0))


def test_fetch_with_ties_supported(dialect):
    assert dialect.supports_fetch_with_ties() is True


def test_fetch_with_ties_renders(dialect):
    sql, _ = dialect.format_limit_offset_clause(LimitOffsetClause(dialect, limit=5, with_ties=True))
    assert sql == "OFFSET 0 ROWS FETCH NEXT 5 ROWS WITH TIES"


def test_fetch_without_ties_renders_only(dialect):
    sql, _ = dialect.format_limit_offset_clause(LimitOffsetClause(dialect, limit=5))
    assert sql == "OFFSET 0 ROWS FETCH NEXT 5 ROWS ONLY"


def test_nulls_first_last_unsupported(dialect):
    assert dialect.supports_nulls_first_last() is False


def test_lock_strength_share_raises(dialect):
    with pytest.raises(Exception):
        ForUpdateClause(dialect, strength=LockStrength.SHARE).to_sql()
