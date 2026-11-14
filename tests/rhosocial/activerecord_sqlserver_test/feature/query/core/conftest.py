# tests/rhosocial/activerecord_sqlserver_test/feature/query/core/conftest.py
"""The SQL Server-only query tests that belong to no shared subdirectory.

These tests build their own table through the backend-local fixture, so the
directory declares an empty fixture group.  The contract is what pins the
directory -- and its own logical database -- instead of letting these tests
fall back to the ``query`` database their sibling directories share.
"""


def ensure_database(environment):
    """Create the directory's database, or clear it when it already exists."""
    environment.reset_database()


def prepare(environment):
    """Nothing to create: each test creates the tables it needs."""


def teardown(environment):
    """Nothing to drop: each test drops the tables it created."""
