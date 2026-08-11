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