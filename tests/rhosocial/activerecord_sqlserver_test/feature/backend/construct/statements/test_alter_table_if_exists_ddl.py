# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/statements/test_alter_table_if_exists_ddl.py
"""Tests for SQL Server ALTER TABLE IF [NOT] EXISTS handling.

SQL Server supports ``DROP COLUMN IF EXISTS`` and ``DROP CONSTRAINT
IF EXISTS`` since 2016 but **not** ``ADD COLUMN IF NOT EXISTS``. The
``ADD`` form omits the ``COLUMN`` literal (SQL Server syntax).
"""

import ast
from pathlib import Path

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.statements import ColumnDefinition
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddColumnAction,
    DropColumnAction,
    DropTableConstraintAction,
)
from rhosocial.activerecord.backend.expression.types import TextType
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


def _project_root() -> Path:
    """The repository root, found by walking up to ``pyproject.toml``."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise AssertionError("could not locate the project root (no pyproject.toml)")


def _scan_dialect_support_bases(source_root: Path) -> tuple[int, list[str]]:
    """AST-walk *source_root* for ``Dialect`` classes with ``Support`` bases.

    A ``runtime_checkable`` protocol is satisfied structurally, so inheriting
    one adds nothing but ellipsis stubs -- and makes ``isinstance`` lie when
    the class does not actually implement the contract. The dialect must
    therefore compose mixins, never protocol classes.

    Returns ``(files_scanned, violations)`` so a caller can also assert that
    the walk was not empty.
    """
    files = sorted(source_root.rglob("*.py"))
    violations = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or not node.name.endswith("Dialect"):
                continue
            for base in node.bases:
                base_name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
                if base_name.endswith("Support"):
                    violations.append(f"{path}:{node.lineno}: {node.name} inherits {base_name}")
    return len(files), violations


@pytest.fixture
def dialect():
    return SQLServerDialect(version=(15, 0, 0))


class TestDialectBasesAreNotProtocols:
    """No ``Dialect`` class may inherit a ``*Support`` protocol.

    Inheriting a ``runtime_checkable`` protocol is not how conformance is
    obtained -- structural satisfaction is -- so the base only contributes
    ellipsis stubs and a nominal ``isinstance`` answer that can disagree with
    the implementation. Composition belongs to mixins; protocol classes are
    contracts, not superclasses.
    """

    def test_supports_switches_scan_all_dialect_classes(self):
        """The real source tree has no ``Dialect`` class with a protocol base."""
        source_root = _project_root() / "src"
        files_scanned, violations = _scan_dialect_support_bases(source_root)
        assert files_scanned > 0, "the AST walk found no source files"
        assert not violations, "Dialect classes inherit protocol stubs:\n" + "\n".join(violations)

    def test_supports_switches_guard_rejects_fabricated_violation(self, tmp_path):
        """The guard itself catches a ``Dialect`` class with a protocol base."""
        (tmp_path / "fabricated_dialect.py").write_text(
            "class FabricatedDialect(SomeSupport):\n    pass\n",
            encoding="utf-8",
        )
        files_scanned, violations = _scan_dialect_support_bases(tmp_path)
        assert files_scanned == 1
        assert violations, "the guard did not flag a fabricated Support base"
        assert "FabricatedDialect" in violations[0]
        assert "SomeSupport" in violations[0]

    def test_supports_switches_guard_accepts_a_clean_control(self, tmp_path):
        """A ``Dialect`` class composed from a mixin is accepted."""
        (tmp_path / "clean_dialect.py").write_text(
            "class CleanDialect(CleanMixin):\n    pass\n",
            encoding="utf-8",
        )
        files_scanned, violations = _scan_dialect_support_bases(tmp_path)
        assert files_scanned == 1
        assert violations == []


class TestAlterTableModifierCapabilities:
    def test_supports_switches(self, dialect):
        assert dialect.supports_add_column_if_not_exists() is False
        assert dialect.supports_drop_column_if_exists() is True
        assert dialect.supports_drop_constraint_if_exists() is True

    def test_if_exists_switches_gate_on_2016(self):
        """Both IF EXISTS clauses arrived in 2016, so 2012 answers no."""
        old = SQLServerDialect(version=(11, 0, 0))
        assert old.supports_drop_column_if_exists() is False
        assert old.supports_drop_constraint_if_exists() is False


class TestAddColumn:
    def test_add_column_omits_column_literal(self, dialect):
        action = AddColumnAction(dialect, ColumnDefinition(dialect, "content", TextType(dialect)))
        sql, params = action.to_sql()
        assert sql.startswith("ADD [content]")
        assert "ADD COLUMN" not in sql
        assert params == ()

    def test_add_column_if_not_exists_raises(self, dialect):
        action = AddColumnAction(
            dialect,
            ColumnDefinition(dialect, "content", TextType(dialect)),
            if_not_exists=True,
        )
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()


class TestDropColumnIfExists:
    def test_if_exists_renders_qualifier(self, dialect):
        action = DropColumnAction(dialect, column_name="x", if_exists=True)
        sql, params = action.to_sql()
        assert "DROP COLUMN IF EXISTS [x]" == sql
        assert params == ()

    def test_if_exists_refused_before_2016(self):
        """The clause does not exist below 2016, so it is refused by name."""
        action = DropColumnAction(
            SQLServerDialect(version=(11, 0, 0)), column_name="x", if_exists=True
        )
        with pytest.raises(UnsupportedFeatureError, match="DROP COLUMN IF EXISTS"):
            action.to_sql()

    def test_none_renders_plain_form(self, dialect):
        action = DropColumnAction(dialect, column_name="x")
        sql, params = action.to_sql()
        assert "DROP COLUMN [x]" == sql
        assert "IF EXISTS" not in sql
        assert params == ()


class TestDropConstraintIfExists:
    def test_if_exists_renders_qualifier(self, dialect):
        action = DropTableConstraintAction(
            dialect, constraint_name="fk", if_exists=True
        )
        sql, params = action.to_sql()
        assert "DROP CONSTRAINT IF EXISTS [fk]" == sql
        assert params == ()

    def test_if_exists_refused_before_2016(self):
        """The clause does not exist below 2016, so it is refused by name."""
        action = DropTableConstraintAction(
            SQLServerDialect(version=(11, 0, 0)), constraint_name="fk", if_exists=True
        )
        with pytest.raises(UnsupportedFeatureError, match="DROP CONSTRAINT IF EXISTS"):
            action.to_sql()

    def test_none_renders_plain_form(self, dialect):
        action = DropTableConstraintAction(dialect, constraint_name="fk")
        sql, params = action.to_sql()
        assert "DROP CONSTRAINT [fk]" == sql
        assert "IF EXISTS" not in sql
        assert params == ()