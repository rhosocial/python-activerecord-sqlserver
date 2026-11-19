# tests/rhosocial/activerecord_sqlserver_test/feature/cli_contracts/conftest.py
"""Bridge the shared ``feature/cli`` contracts with a dedicated database.

The testsuite ``feature/cli`` conftest hardcodes the database name ``test_cli``;
this backend's own ``feature/cli`` also uses that shared fixture. To keep the
two directories' parallel subsets isolated, override the database name here
with a unique one derived from this directory.
"""
from rhosocial.activerecord.testsuite.feature.cli.conftest import *  # noqa: F401,F403
import pytest


@pytest.fixture(scope="session")
def database_config(backend_scenario):
    name = "test_cli_contracts"
    return backend_scenario, backend_scenario.make_config(name), name
