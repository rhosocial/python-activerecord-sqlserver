# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/ddl/test_rename_capabilities.py
"""SQL Server reports table and column rename as unsupported.

Core defaults ``supports_rename_table`` / ``supports_rename_column`` to ``True``
and its action formatters emit ``RENAME TO`` / ``RENAME COLUMN``. Neither clause
is T-SQL: SQL Server renames objects through the ``sp_rename`` stored procedure,
which is a procedure call and cannot be rendered as the single ``ALTER TABLE``
action fragment a :class:`RenameTableAction` or :class:`RenameColumnAction`
contributes. ``SQLServerTableMixin`` therefore answers ``False`` to both probes,
so core's formatters fail fast with ``UnsupportedFeatureError`` rather than
handing invalid SQL to the driver.
"""

import inspect

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.mixins.alter_table_mixin import AlterTableMixin
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    RenameColumnAction,
    RenameTableAction,
)
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

SQL_SERVER_2019 = (15, 0, 0)
BACKEND_PACKAGE = "rhosocial.activerecord.backend.impl.sqlserver."

PROBES = ("supports_rename_table", "supports_rename_column")


def _dialect():
    return SQLServerDialect(SQL_SERVER_2019)


def _declaring_class(switch_name):
    """The first class in the dialect's MRO that declares ``switch_name``."""
    for cls in SQLServerDialect.__mro__:
        if switch_name in cls.__dict__:
            return cls
    raise AssertionError(f"no class in the MRO declares {switch_name}()")


class TestRenameProbes:
    @pytest.mark.parametrize("probe", PROBES)
    def test_probe_is_false(self, probe):
        """Honest answer: the standard rename clauses do not exist in T-SQL."""
        assert getattr(_dialect(), probe)() is False

    @pytest.mark.parametrize("probe", PROBES)
    def test_declared_by_this_backend(self, probe):
        """A changed core default must not silently move SQL Server's answer."""
        declaring = _declaring_class(probe)
        assert declaring.__module__.startswith(BACKEND_PACKAGE), (
            f"{probe} is inherited from {declaring.__module__}; declare it in "
            f"this backend's mixins so the answer is explicit."
        )

    @pytest.mark.parametrize("probe", PROBES)
    def test_declaring_class_precedes_core_alter_table_mixin(self, probe):
        """The backend declaration must win in the MRO, not just be present."""
        mro = SQLServerDialect.__mro__
        assert mro.index(_declaring_class(probe)) < mro.index(AlterTableMixin), (
            f"{probe} is declared after core's AlterTableMixin in the MRO; "
            f"core's True default would answer instead."
        )

    @pytest.mark.parametrize("probe", PROBES)
    def test_probe_takes_no_argument(self, probe):
        """A probe answers one question and carries no object kind."""
        parameters = list(inspect.signature(getattr(_dialect(), probe)).parameters)
        assert parameters == []

    @pytest.mark.parametrize("probe", PROBES)
    def test_docstring_records_the_reality(self, probe):
        """The reason for ``False`` is documented in English, in the docstring."""
        docstring = inspect.getdoc(getattr(SQLServerDialect, probe)) or ""
        assert "sp_rename" in docstring, (
            f"{probe}'s docstring no longer names the procedure SQL Server "
            f"actually uses to rename objects."
        )

    @pytest.mark.parametrize("version", [(15, 0, 0), (16, 0, 0), (17, 0, 0)])
    def test_version_does_not_move_the_values(self, version):
        """The two answers are statement-level facts, not version gates."""
        dialect = SQLServerDialect(version)
        for probe in PROBES:
            assert getattr(dialect, probe)() is False


class TestRenameActionRendering:
    """Core's formatters refuse once the probes answer ``False``."""

    def test_rename_table_action_refused(self):
        d = _dialect()
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            RenameTableAction(d, "old_name", "new_name").to_sql()
        assert excinfo.value.feature_name == "ALTER TABLE RENAME TO"

    def test_rename_column_action_refused(self):
        d = _dialect()
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            RenameColumnAction(d, "old_name", "new_name").to_sql()
        assert excinfo.value.feature_name == "ALTER TABLE RENAME COLUMN"

    def test_no_invalid_rename_clause_is_emitted(self):
        """Neither action can render the SQL-standard rename clauses."""
        d = _dialect()
        for action in (
            RenameTableAction(d, "old_name", "new_name"),
            RenameColumnAction(d, "old_name", "new_name"),
        ):
            with pytest.raises(UnsupportedFeatureError):
                sql, _params = action.to_sql()
                pytest.fail(f"{type(action).__name__} rendered invalid SQL: {sql!r}")
