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
from typing import Dict, List, Tuple

import pytest
from rhosocial.activerecord.testsuite.feature.rules.backend import (
    test_no_raw_sql_in_src as raw_sql_rules,
)
from rhosocial.activerecord.testsuite.feature.rules.backend import (
    test_no_reflection_in_expression_layer as reflection_rules,
)
from rhosocial.activerecord.testsuite.feature.rules.backend import (
    test_no_string_sql_manipulation_in_formatters as formatter_rules,
)
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


# Reason-bearing entries for SQL Server's own source. Core's entries stay in the
# merged fixtures below because the shared rule modules probe them with synthetic
# sources labelled "core"; nothing here weakens an assertion.
SQLSERVER_REFLECTION_ALLOWLIST: Dict[Tuple[str, str, str, str], Tuple[int, str]] = {
    ("sqlserver", "alter_table_modifier.py", "SQLServerAlterColumnModifierMixin", "getattr"): (
        13,
        "legacy ALTER COLUMN modifier probes optional flags on non-expression action nodes",
    ),
    ("sqlserver", "alter_table_modifier.py", "SQLServerAlterColumnModifierMixin", "hasattr"): (
        1,
        "legacy ALTER COLUMN modifier probes optional flags on non-expression action nodes",
    ),
    ("sqlserver", "async_transaction.py", "AsyncSQLServerTransactionManager", "getattr"): (
        1,
        "transaction manager reads an optional driver/config attribute on a non-expression object",
    ),
    ("sqlserver", "backend/async_backend.py", "AsyncSQLServerBackend", "getattr"): (
        2,
        "connection/driver optional attribute read on a non-expression backend object",
    ),
    ("sqlserver", "backend/backend.py", "SQLServerBackend", "getattr"): (
        2,
        "connection/driver optional attribute read on a non-expression backend object",
    ),
    ("sqlserver", "backend/backend.py", "SQLServerBackend", "hasattr"): (
        1,
        "connection/driver optional attribute read on a non-expression backend object",
    ),
    ("sqlserver", "cli/connection.py", "resolve_connection_config_from_args", "getattr"): (
        7,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/info.py", "handle", "getattr"): (
        1,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/introspect.py", "_handle_introspect_async", "getattr"): (
        1,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/introspect.py", "_handle_introspect_sync", "getattr"): (
        1,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/introspect.py", "_missing_from", "getattr"): (
        1,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/introspect.py", "_require_capability", "getattr"): (
        2,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/introspect.py", "_serialize_for_output", "hasattr"): (
        1,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/introspect.py", "_steps", "getattr"): (
        2,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/introspect.py", "_validate_options", "getattr"): (
        2,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/introspect.py", "_value_sample_arguments", "getattr"): (
        1,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/introspect.py", "handle", "getattr"): (
        1,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/named_expression.py", "_get_requested_version", "getattr"): (
        1,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/named_expression.py", "handle", "getattr"): (
        1,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/named_migration.py", "disconnect", "getattr"): (
        1,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/named_migration.py", "disconnect_async", "getattr"): (
        1,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/named_migration.py", "handle", "getattr"): (
        1,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/named_procedure.py", "handle", "getattr"): (
        1,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/named_procedure_graph.py", "handle", "getattr"): (
        1,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/query.py", "handle", "getattr"): (
        1,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/status.py", "_display_status_rich", "hasattr"): (
        2,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/status.py", "_serialize_for_output", "hasattr"): (
        1,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "cli/status.py", "handle", "getattr"): (
        1,
        "CLI reads argparse/config attributes, not expression fields",
    ),
    ("sqlserver", "dialect.py", "SQLServerDialect", "getattr"): (
        6,
        "dialect formatter reads optional flags on legacy non-expression nodes",
    ),
    ("sqlserver", "dialect.py", "SQLServerDialect", "hasattr"): (
        1,
        "dialect formatter reads optional flags on legacy non-expression nodes",
    ),
    ("sqlserver", "dialect.py", "_register_partition_formatters", "getattr"): (
        1,
        "registry copies declared members between mixin and dialect classes",
    ),
    ("sqlserver", "dialect.py", "_register_partition_formatters", "setattr"): (
        1,
        "registry copies declared members between mixin and dialect classes",
    ),
    ("sqlserver", "dialect.py", "_register_type_formatters", "getattr"): (
        2,
        "registry copies declared members between mixin and dialect classes",
    ),
    ("sqlserver", "dialect.py", "_register_type_formatters", "setattr"): (
        2,
        "registry copies declared members between mixin and dialect classes",
    ),
    ("sqlserver", "error_mapping.py", "extract_driver_code", "getattr"): (
        1,
        "driver exception object exposes optional attributes; no declared attribute exists",
    ),
    ("sqlserver", "introspection/introspector.py", "SQLServerIntrospectorMixin", "getattr"): (
        1,
        "introspection client object optional attribute; not an expression field",
    ),
    ("sqlserver", "mixins/backend_mixin.py", "SQLServerBackendMixin", "getattr"): (
        6,
        "optional cursor/config attribute on non-expression backend objects",
    ),
    ("sqlserver", "mixins/backend_mixin.py", "SQLServerBackendMixin", "hasattr"): (
        1,
        "optional cursor/config attribute on non-expression backend objects",
    ),
    ("sqlserver", "mixins/collation.py", "SQLServerCollationMixin", "getattr"): (
        1,
        "legacy formatter reads declared node/option attributes; no declared accessor for all variants",
    ),
    ("sqlserver", "mixins/concurrency.py", "SQLServerConcurrencyMixin", "getattr"): (
        1,
        "legacy formatter reads declared node/option attributes; no declared accessor for all variants",
    ),
    ("sqlserver", "mixins/ddl_type.py", "SQLServerTypeDDLMixin", "getattr"): (
        7,
        "legacy formatter reads declared node/option attributes; no declared accessor for all variants",
    ),
    ("sqlserver", "mixins/explain.py", "SQLServerExplainMixin", "getattr"): (
        9,
        "legacy formatter reads declared node/option attributes; no declared accessor for all variants",
    ),
    ("sqlserver", "mixins/function.py", "SQLServerFunctionMixin", "getattr"): (
        1,
        "legacy formatter reads declared node/option attributes; no declared accessor for all variants",
    ),
    ("sqlserver", "mixins/namespace.py", "SQLServerNamespaceMixin", "getattr"): (
        2,
        "legacy formatter reads declared node/option attributes; no declared accessor for all variants",
    ),
    ("sqlserver", "mixins/partition.py", "SQLServerPartitionMixin", "getattr"): (
        1,
        "legacy formatter reads declared node/option attributes; no declared accessor for all variants",
    ),
    ("sqlserver", "mixins/pivot.py", "SQLServerPivotMixin", "hasattr"): (
        1,
        "legacy formatter reads declared node/option attributes; no declared accessor for all variants",
    ),
    ("sqlserver", "mixins/returning.py", "SQLServerReturningMixin", "getattr"): (
        1,
        "legacy formatter reads declared node/option attributes; no declared accessor for all variants",
    ),
    ("sqlserver", "show/functionality.py", "SQLServerShowFunctionality", "getattr"): (
        1,
        "SHOW capability object reads declared attributes on non-expression objects",
    ),
    ("sqlserver", "suggestion/_change_common.py", "ChangeProjection", "getattr"): (
        1,
        "schema-change projection snapshots optional declared attributes of non-expression objects",
    ),
    ("sqlserver", "suggestion/_change_common.py", "_params_of", "getattr"): (
        1,
        "schema-change projection snapshots optional declared attributes of non-expression objects",
    ),
    ("sqlserver", "suggestion/_change_common.py", "fingerprint", "getattr"): (
        1,
        "schema-change projection snapshots optional declared attributes of non-expression objects",
    ),
    ("sqlserver", "suggestion/_change_common.py", "live_by_name", "getattr"): (
        1,
        "schema-change projection snapshots optional declared attributes of non-expression objects",
    ),
    ("sqlserver", "suggestion/_change_common.py", "projection", "getattr"): (
        1,
        "schema-change projection snapshots optional declared attributes of non-expression objects",
    ),
    ("sqlserver", "suggestion/_common.py", "_get", "getattr"): (
        1,
        "schema-change projection snapshots optional declared attributes of non-expression objects",
    ),
    ("sqlserver", "suggestion/_common.py", "_word", "getattr"): (
        3,
        "schema-change projection snapshots optional declared attributes of non-expression objects",
    ),
    (
        "sqlserver",
        "suggestion/table_constraint_change_suggestion.py",
        "_spellable_constraint",
        "getattr",
    ): (
        3,
        "schema-change projection snapshots optional declared attributes of non-expression objects",
    ),
    (
        "sqlserver",
        "suggestion/table_constraint_change_suggestion.py",
        "_spellable_constraint",
        "hasattr",
    ): (
        1,
        "schema-change projection snapshots optional declared attributes of non-expression objects",
    ),
    (
        "sqlserver",
        "suggestion/table_index_change_suggestion.py",
        "SQLServerTableIndexChangeSuggestionMixin",
        "getattr",
    ): (
        1,
        "schema-change projection snapshots optional declared attributes of non-expression objects",
    ),
}

SQLSERVER_FORMATTER_ALLOWLIST: Dict[Tuple[str, str, str, str, str], Tuple[int, str]] = {
    ("sqlserver", "alter_table_modifier.py", "format_add_masked_action", "replace", "call:str"): (
        1,
        "escapes the declared masked-function value atom before concatenating ALTER COLUMN text",
    ),
    (
        "sqlserver",
        "dialect.py",
        "format_create_table_statement",
        "replace",
        "call:render_object_id_name",
    ): (
        1,
        "escapes a developer-supplied object-name atom from the declared table name",
    ),
    ("sqlserver", "dialect.py", "format_fulltext_match", "replace", "name:search_term"): (
        1,
        "escapes the declared full-text search term atom, not assembled SQL",
    ),
    (
        "sqlserver",
        "mixins/ddl_extras.py",
        "format_add_default_constraint_action",
        "replace",
        "attr:value",
    ): (
        1,
        "escapes the declared default value atom",
    ),
    (
        "sqlserver",
        "mixins/extended_property.py",
        "format_extended_property_write_statement",
        "replace",
        "name:value",
    ): (
        1,
        "escapes the declared extended-property value atom",
    ),
    ("sqlserver", "mixins/identifier.py", "format_identifier", "replace", "name:identifier"): (
        1,
        "escapes a developer-supplied identifier atom",
    ),
    (
        "sqlserver",
        "mixins/protocol_support.py",
        "format_select_into_statement",
        "startswith",
        "name:full_sql",
    ): (
        1,
        "splits a rendered SELECT at the declared head; does not inspect arbitrary SQL",
    ),
    (
        "sqlserver",
        "mixins/protocol_support.py",
        "format_sqlserver_contains_predicate",
        "replace",
        "attr:search_string",
    ): (
        1,
        "escapes the declared CONTAINS search-string atom",
    ),
    (
        "sqlserver",
        "mixins/protocol_support.py",
        "format_sqlserver_freetext_predicate",
        "replace",
        "attr:search_string",
    ): (
        1,
        "escapes the declared FREETEXT search-string atom",
    ),
}

SQLSERVER_RAW_SQL_ALLOWLIST: Dict[Tuple[str, str], Tuple[int, str]] = {
    ("sqlserver", "mixins/returning.py", "RawSQL"): (
        1,
        "OUTPUT-clause returning has no expression kind; RawSQL is an explicitly vouched list item",
    ),
}

SQLSERVER_EXEC_ALLOWLIST: Dict[Tuple[str, str, str, str], Tuple[int, str]] = {
    (
        "sqlserver",
        "examples/insert/output.py",
        "cleanup",
        "execute",
        "DROP TABLE IF EXISTS output_test",
    ): (1, "caller-vouched static DDL literal in a self-contained example script"),
}


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
        path for path in backend_test_files if "UNCONSTRUCTIBLE" in path.read_text(encoding="utf-8")
    ]


@pytest.fixture
def reflection_allowlist() -> Dict[Tuple[str, str, str, str], Tuple[int, str]]:
    """Core's grandfathered calls plus SQL Server's own reason-bearing sites."""
    return {**reflection_rules.REFLECTION_ALLOWLIST, **SQLSERVER_REFLECTION_ALLOWLIST}


@pytest.fixture
def formatter_allowlist() -> Dict[Tuple[str, str, str, str, str], Tuple[int, str]]:
    """Core's atom escapes plus SQL Server's nine grandfathered escapes."""
    return {**formatter_rules.FORMATTER_ALLOWLIST, **SQLSERVER_FORMATTER_ALLOWLIST}


@pytest.fixture
def raw_sql_allowlist() -> Dict[Tuple[str, str], Tuple[int, str]]:
    """Core's RawSQL sites plus SQL Server's OUTPUT-clause exception."""
    return {**raw_sql_rules.RAWSQL_ALLOWLIST, **SQLSERVER_RAW_SQL_ALLOWLIST}


@pytest.fixture
def exec_allowlist() -> Dict[Tuple[str, str, str, str], Tuple[int, str]]:
    """Core's static-SQL literals plus SQL Server's example-only literal."""
    return {**raw_sql_rules.EXEC_ALLOWLIST, **SQLSERVER_EXEC_ALLOWLIST}
