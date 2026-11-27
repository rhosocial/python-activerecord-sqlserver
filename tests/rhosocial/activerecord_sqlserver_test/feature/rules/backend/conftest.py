# tests/rhosocial/activerecord_sqlserver_test/feature/rules/backend/conftest.py
"""Fixtures for the SQL Server backend's own rule suite.

SQL Server is a standalone backend repository, not part of core's generic
rules. Every path is derived from the installed packages, never from a
hardcoded worktree path. The shared rule library supplies the assertions;
this conftest selects the subject: exactly one source root, the installed
``backend/impl/sqlserver`` tree of this repository.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import List, Tuple

import pytest

from rhosocial.activerecord.testsuite.feature.rules.backend.conftest import *  # noqa: F401,F403
from rhosocial.activerecord.testsuite.feature.rules.backend.conftest import python_files_in
from rhosocial.activerecord.testsuite.pytest_plugin import Declaration

DECLARATION = Declaration(
    uses_database=False,
    parallel=False,
    purpose="Executable assertions of the SQL Server backend's formal constraints",
    passes_means="SQL Server source obeys the mechanical and structural rule",
    fails_means="SQL Server source introduces a forbidden construct or dependency",
)


def sqlserver_expression_package() -> object:
    """The installed SQL Server expression package."""
    return importlib.import_module("rhosocial.activerecord.backend.impl.sqlserver.expression")


def sqlserver_impl_root() -> Path:
    """The installed ``backend/impl/sqlserver`` directory."""
    package = sqlserver_expression_package()
    for search_path in vars(package).get("__path__", ()):
        current = Path(search_path).resolve()
        for candidate in [current] + list(current.parents):
            if candidate.name == "impl" and candidate.parent.name == "backend":
                return candidate / current.relative_to(candidate).parts[0]
    pytest.skip("SQL Server impl root is not discoverable from the installed package")


def sqlserver_project_root() -> Path:
    """Project root inferred from the installed SQL Server package layout."""
    root = sqlserver_impl_root()
    for candidate in [root] + list(root.parents):
        if (candidate / "tests").is_dir() and (candidate / "src").is_dir():
            return candidate
    pytest.skip("SQL Server project root is not discoverable from the installed package")


@pytest.fixture
def backend_expression_package() -> object:
    """SQL Server's expression package."""
    return sqlserver_expression_package()


@pytest.fixture
def backend_dialect() -> object:
    """An instantiated SQL Server dialect."""
    from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

    return SQLServerDialect()


@pytest.fixture
def backend_prefix() -> str:
    """SQL Server's own naming prefix."""
    return "SQLServer"


@pytest.fixture
def backend_impl_root() -> Path:
    """The SQL Server ``impl`` root used by the file-driven shared rules."""
    return sqlserver_impl_root()


@pytest.fixture
def source_roots() -> List[Tuple[str, Path]]:
    """One root only: this backend's implementation tree, never core or a peer."""
    return [("sqlserver", sqlserver_impl_root())]


@pytest.fixture
def backend_project_root() -> Path:
    """Project root for SQL Server's tests."""
    return sqlserver_project_root()


@pytest.fixture
def backend_test_files(backend_project_root) -> List[Path]:
    """Every Python test file in this backend's project."""
    files = list(python_files_in(backend_project_root / "tests"))
    assert files, f"no test files under {backend_project_root / 'tests'}"
    return files


@pytest.fixture
def backend_matrix_files(backend_test_files) -> List[Path]:
    """Round-trip matrices that declare an UNCONSTRUCTIBLE list."""
    return [
        path for path in backend_test_files
        if "UNCONSTRUCTIBLE" in path.read_text(encoding="utf-8")
    ]
