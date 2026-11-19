# tests/rhosocial/activerecord_sqlserver_test/feature/conftest.py
"""
Pytest configuration for top-level feature tests.

Provides the `fixtures` / `async_fixtures` placeholders consumed by
`test_features{,_async}.py`. The bodies of those tests are `assert True`,
and the @requires_protocol / @requires_functions markers operate on the
test's own requested fixtures (here only `fixtures`), so a stub is enough.
"""

import pytest


@pytest.fixture
def fixtures():
    """Stub fixture for the protocol/function decorator smoke tests."""
    return None


@pytest.fixture
async def async_fixtures():
    """Async stub fixture for the protocol/function decorator smoke tests."""
    return None


def pytest_collection_modifyitems(items):
    """Skip the testsuite's real-DB ``test_explain`` contracts for SQL Server.

    Those contracts execute ``.explain().aggregate()`` against a live server.
    SQL Server cannot honour that generic flow: ``SET SHOWPLAN_*`` /
    ``SET STATISTICS *`` must be the only statement in an exclusive batch, and
    with the plan flag on the driver's ``fetchall()`` reports ``No results``
    (pyodbc). Executing EXPLAIN against a connection is deliberately avoided
    for this backend -- see the local construction-level deep tests in
    ``feature/backend/construct/explain/test_sqlserver_explain_deep.py`` which
    pin the capability gates and the exact SHOWPLAN/STATISTICS SQL instead.
    """
    reason = (
        "SQL Server SHOWPLAN/STATISTICS requires an exclusive batch; real-DB "
        "EXPLAIN execution is deliberately avoided here. EXPLAIN is covered "
        "construction-level in test_sqlserver_explain_deep.py."
    )
    for item in items:
        if item.originalname == "test_explain":
            item.add_marker(pytest.mark.skip(reason=reason))
        # SQL Server trims trailing spaces from CHAR/nchar comparisons, so the
        # shared error-handling contract's exact round-trip of '   spaces   '
        # cannot hold. This is SQL Server's defined comparison semantics.
        if item.originalname == "test_special_character_full_matrix":
            item.add_marker(
                pytest.mark.skip(
                    reason="SQL Server trims trailing spaces; exact round-trip cannot hold"
                )
            )