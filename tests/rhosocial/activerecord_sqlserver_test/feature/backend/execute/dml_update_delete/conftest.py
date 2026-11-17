# tests/rhosocial/activerecord_sqlserver_test/feature/backend/execute/dml_update_delete/conftest.py
"""No directory-specific fixtures: these tests use the backend-owned fixtures."""

from rhosocial.activerecord.testsuite.pytest_plugin import Declaration

# This directory's tests use the directory-owned database (see the backend root
# conftest's ``database_for``), so they run serially on one worker per scenario.
DECLARATION = Declaration(
    parallel=True,
    purpose=(
        "Execute tests for this directory: they create and drop objects in the "
        "directory-owned database."
    ),
    passes_means="This directory's database-backed execute tests pass in isolation.",
    fails_means="A database-backed execute test failed against this directory's database.",
)
