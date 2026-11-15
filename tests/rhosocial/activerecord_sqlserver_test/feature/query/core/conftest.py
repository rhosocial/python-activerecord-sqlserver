# tests/rhosocial/activerecord_sqlserver_test/feature/query/core/conftest.py
"""L2 backend fixtures for the SQL Server-only query "core" tests.

- ``database``: one database per directory (session scope, emptied at start);
- ``schema``: the tables this directory's files use, dropped and recreated
  for every test (function scope).

The files here assert on expression SQL (COLLATE construction) and own their
throwaway raw tables inside the test module, so no topic definition is
prepared; the database still exists because it is the directory's identity.
"""

import pytest

from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType
from rhosocial.activerecord_sqlserver_test.feature.query.conftest import *  # noqa: F401,F403

DDL = ExecutionOptions(stmt_type=StatementType.DDL)

DEFINITIONS = ()


@pytest.fixture(scope="session")
def database_config(backend_scenario):
    """The scenario, its connection configuration, and the database name."""
    name = "test_query_core"
    return backend_scenario, backend_scenario.make_config(name), name


@pytest.fixture(scope="session")
def database(database_config):
    """The directory's database, prepared once and left for later files."""
    scenario, config, name = database_config
    scenario.reset_database(name)
    backend = scenario.backend_class(connection_config=config)
    backend.connect()
    backend.introspect_and_adapt()
    yield backend
    backend.disconnect()


@pytest.fixture(scope="function", autouse=True)
def schema(database):
    """Drop and recreate the tables this directory uses, before every test."""
    fixtures = [definition(database.dialect) for definition in DEFINITIONS]
    for fixture in fixtures:
        database.execute(*fixture.create_table.to_sql(), options=DDL)
    yield
    for fixture in reversed(fixtures):
        database.execute(*fixture.drop_table.to_sql(), options=DDL)