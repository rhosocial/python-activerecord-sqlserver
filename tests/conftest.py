# tests/conftest.py
"""Root configuration for the SQL Server backend's test tree.

The backend knows its own classes and how a scenario maps to a connection, so
no declaration table is needed here: the scenario is exposed as a parameterized
pytest fixture that the testsuite environment consumes.

``READ_COMMITTED_SNAPSHOT`` is no longer checked here either.  Each test
directory owns a database and ``support.sqlserver`` turns the option on when it
creates that database, which is both earlier than the first test and free of
the exclusive lock a running database would need.
"""

import pytest
import support.sqlserver

_SCENARIOS = [support.sqlserver.scenario(name) for name in support.sqlserver.SCENARIOS]


@pytest.fixture(scope="session", params=_SCENARIOS, ids=lambda scenario: scenario.name)
def backend_scenario(request):
    """Return the scenario the tests run against; its id is the scenario name."""
    return request.param


def pytest_configure(config):
    """Configure custom markers for SQL Server tests."""
    config.addinivalue_line(
        "markers", "requires_sqlserver: mark test as requiring SQL Server connection"
    )
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line(
        "markers", "requires_protocol: Mark tests that require specific database protocol support"
    )
    config.addinivalue_line(
        "markers", "requires_functions: Mark tests that require specific database functions"
    )
    config.addinivalue_line(
        "markers", "requires_inner_join: Mark test as requiring INNER JOIN support"
    )
