# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/ddl/test_sqlserver_rename_and_default.py
"""SQL Server ``sp_rename`` and named default constraints.

T-SQL has no ``RENAME COLUMN`` / ``RENAME TO`` clause: a rename is the
``sp_rename`` procedure. A column default is a *named* constraint added with
``ALTER TABLE ... ADD CONSTRAINT df DEFAULT ... FOR col``, not the
``ALTER COLUMN ... SET DEFAULT`` clause the SQL standard spells.

Pure-construction tests: no database connection is required.
"""

import pytest

from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import AlterTableStatement
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression import (
    SQLServerAddDefaultConstraintAction,
    SQLServerRenameObjectStatement,
)


@pytest.fixture
def dialect():
    return SQLServerDialect((2019, 0, 0))


class TestRenameObject:
    def test_column_rename(self, dialect):
        sql, params = SQLServerRenameObjectStatement(
            dialect, "dbo.T1.old_col", "new_col", "COLUMN"
        ).to_sql()
        assert sql == "EXEC sp_rename N'dbo.T1.old_col', N'new_col', N'COLUMN'"
        assert params == ()

    def test_table_rename(self, dialect):
        sql, _ = SQLServerRenameObjectStatement(
            dialect, "dbo.T1", "T2", "OBJECT"
        ).to_sql()
        assert sql == "EXEC sp_rename N'dbo.T1', N'T2', N'OBJECT'"

    def test_kind_is_case_insensitive(self, dialect):
        sql, _ = SQLServerRenameObjectStatement(
            dialect, "dbo.T1", "T2", "object"
        ).to_sql()
        assert sql == "EXEC sp_rename N'dbo.T1', N'T2', N'OBJECT'"

    def test_quotes_are_escaped(self, dialect):
        sql, _ = SQLServerRenameObjectStatement(
            dialect, "dbo.T1", "O'Brien", "OBJECT"
        ).to_sql()
        assert "N'O''Brien'" in sql

    def test_unknown_kind_is_refused(self, dialect):
        with pytest.raises(ValueError, match="unknown sp_rename object kind"):
            SQLServerRenameObjectStatement(
                dialect, "dbo.T1", "T2", "TABLE"
            ).to_sql()

    def test_column_rename_requires_a_dotted_address(self, dialect):
        with pytest.raises(ValueError, match="dotted address"):
            SQLServerRenameObjectStatement(
                dialect, "T1.old_col", "new", "COLUMN"
            ).to_sql()

    def test_blank_name_is_refused(self, dialect):
        with pytest.raises(ValueError, match="old_name must be a non-empty string"):
            SQLServerRenameObjectStatement(dialect, "  ", "T2", "OBJECT").to_sql()

    def test_wrong_node_kind_is_refused(self, dialect):
        with pytest.raises(TypeError):
            dialect.format_rename_object_statement(
                SQLServerAddDefaultConstraintAction(dialect, "c", "v")
            )


class TestAddDefaultConstraint:
    def _render(self, dialect, action):
        table = Table(dialect, "T1", schema_name="dbo")
        return AlterTableStatement(dialect, table, action).to_sql()

    def test_named_constraint(self, dialect):
        sql, params = self._render(
            dialect,
            SQLServerAddDefaultConstraintAction(
                dialect, "status", "new", constraint_name="df_status"
            ),
        )
        assert sql == (
            "ALTER TABLE [dbo].[T1] ADD CONSTRAINT [df_status] "
            "DEFAULT N'new' FOR [status]"
        )
        assert params == ()

    def test_unnamed_constraint(self, dialect):
        sql, _ = self._render(
            dialect, SQLServerAddDefaultConstraintAction(dialect, "status", "new")
        )
        assert sql == "ALTER TABLE [dbo].[T1] ADD DEFAULT N'new' FOR [status]"

    def test_value_quotes_are_escaped(self, dialect):
        sql, _ = self._render(
            dialect,
            SQLServerAddDefaultConstraintAction(
                dialect, "note", "O'Brien", constraint_name="df_note"
            ),
        )
        assert "N'O''Brien'" in sql

    def test_empty_value_is_allowed(self, dialect):
        sql, _ = self._render(
            dialect, SQLServerAddDefaultConstraintAction(dialect, "note", "")
        )
        assert "DEFAULT N''" in sql

    def test_non_string_value_is_refused(self, dialect):
        with pytest.raises(TypeError, match="value must be a string"):
            self._render(
                dialect, SQLServerAddDefaultConstraintAction(dialect, "n", 1)
            )

    def test_blank_column_is_refused(self, dialect):
        with pytest.raises(ValueError, match="non-empty column"):
            self._render(
                dialect, SQLServerAddDefaultConstraintAction(dialect, "  ", "v")
            )

    def test_blank_constraint_name_is_refused(self, dialect):
        with pytest.raises(ValueError, match="constraint_name must be a non-empty"):
            self._render(
                dialect,
                SQLServerAddDefaultConstraintAction(
                    dialect, "c", "v", constraint_name=" "
                ),
            )

    def test_probe_is_true(self, dialect):
        assert dialect.supports_default_constraint_add() is True

    def test_wrong_node_kind_is_refused(self, dialect):
        with pytest.raises(TypeError):
            dialect.format_add_default_constraint_action(
                SQLServerRenameObjectStatement(dialect, "dbo.T1", "T2", "OBJECT")
            )
