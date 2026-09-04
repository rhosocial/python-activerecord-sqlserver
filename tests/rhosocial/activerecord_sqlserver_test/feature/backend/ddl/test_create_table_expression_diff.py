# tests/rhosocial/activerecord_sqlserver_test/feature/backend/ddl/test_create_table_expression_diff.py
"""CreateTableExpression.diff() coverage for the SQL Server dialect.

Verified dialect behaviour underpinning the capability hooks:

- ``ALTER COLUMN`` on SQL Server is a whole-column redefinition
  (``ALTER COLUMN col INT NOT NULL``); there is no standalone
  ``SET DEFAULT`` / ``DROP NOT NULL`` subclause, and defaults are managed
  through ``ADD CONSTRAINT DF_...`` / ``DROP CONSTRAINT``. Verified via
  ``SQLServerAlterColumnModifierMixin.format_alter_column_action`` which
  only dispatches ``SET DATA TYPE`` / masking variants and raises
  ``UnsupportedFeatureError`` otherwise
  → ``_supports_alter_column_properties()`` overridden to False.
- SQL Server has no ``ALTER TABLE ADD/DROP INDEX``; indexes are managed
  with ``CREATE INDEX`` / ``DROP INDEX`` statements
  → ``_supports_alter_table_index_actions()`` overridden to False.
- Type changes keep the generic rebuild path: T-SQL could redefine a
  column in place, but the core diff vocabulary has no full-column
  redefinition action, so ``_supports_alter_column_type()`` stays False
  and diffs produce a RebuildPlan.
"""

import pytest

from rhosocial.activerecord.backend.dialect.protocols import CreateTableExpressionDiffSupport
from rhosocial.activerecord.backend.expression import DiffPlan, RebuildPlan
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddColumn,
    AlterTableExpression,
    DropColumn,
    RenameTable,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnConstraint,
    ColumnConstraintType,
    ColumnDefinition,
    CreateTableExpression,
    IndexDefinition,
    TableConstraint,
    TableConstraintType,
)
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    IntegerType,
    TextType,
    VarCharType,
)
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


def _col(name, dtype, *constraints):
    return ColumnDefinition(name=name, data_type=dtype, constraints=list(constraints))


def _pk():
    return ColumnConstraint(constraint_type=ColumnConstraintType.PRIMARY_KEY)


def _not_null():
    return ColumnConstraint(constraint_type=ColumnConstraintType.NOT_NULL)


def _default(value):
    return ColumnConstraint(
        constraint_type=ColumnConstraintType.DEFAULT, default_value=value
    )


def _expr(dialect, columns, indexes=None, constraints=None, **kwargs):
    return CreateTableExpression(
        dialect=dialect,
        table=kwargs.pop("table", "items"),
        columns=columns,
        indexes=indexes,
        table_constraints=constraints,
        **kwargs,
    )


@pytest.fixture(scope="module")
def dialect():
    return SQLServerDialect(version=(16, 0, 0))


class TestProtocolConformance:

    def test_sqlserver_dialect_satisfies_protocol(self, dialect):
        assert isinstance(dialect, CreateTableExpressionDiffSupport)

    def test_capability_hooks(self, dialect):
        """The hooks match SQL Server reality: no property subclauses, no
        ALTER TABLE index actions, and type changes keep the rebuild path."""
        assert dialect._supports_alter_column_properties() is False
        assert dialect._supports_alter_table_index_actions() is False
        assert dialect._supports_alter_column_type() is False


class TestValidation:

    def test_cross_dialect_raises(self, dialect):
        from rhosocial.activerecord.backend.impl.sqlite.dialect import SQLiteDialect

        old = _expr(dialect, [_col("id", IntegerType(), _pk())])
        new = _expr(SQLiteDialect(), [_col("id", IntegerType(), _pk())])
        with pytest.raises(ValueError, match="different dialects"):
            old.diff(new)

    def test_cross_table_raises(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk())])
        new = _expr(dialect, [_col("id", IntegerType(), _pk())], table="other")
        with pytest.raises(ValueError, match="different tables"):
            old.diff(new)


class TestNoChange:

    def test_identical_definitions_empty_plan(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("name", VarCharType(length=100))])
        new = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("name", VarCharType(length=100))])
        plan = old.diff(new)
        assert not plan.has_changes
        assert plan.rebuild is None
        assert plan.alters == []


class TestColumnChanges:

    def test_added_column_yields_add_action(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk())])
        new = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("bio", VarCharType(length=4000))])
        plan = old.diff(new)
        assert plan.rebuild is None and plan.has_changes
        (alter,) = plan.alters
        assert len(alter.actions) == 1
        action = alter.actions[0]
        assert isinstance(action, AddColumn)
        assert action.column.name == "bio"

    def test_removed_column_yields_drop_action(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("bio", VarCharType(length=4000))])
        new = _expr(dialect, [_col("id", IntegerType(), _pk())])
        plan = old.diff(new)
        (alter,) = plan.alters
        action = alter.actions[0]
        assert isinstance(action, DropColumn)
        assert action.column_name == "bio"

    def test_add_action_renders_sql_server_add(self, dialect):
        """AddColumn renders the T-SQL ``ADD <column>`` form (no COLUMN keyword)."""
        old = _expr(dialect, [_col("id", IntegerType(), _pk())])
        new = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("bio", VarCharType(length=100))])
        plan = old.diff(new)
        sql, _params = plan.alters[0].to_sql()
        assert sql.upper().startswith("ALTER TABLE [ITEMS] ADD")
        assert "ADD COLUMN" not in sql.upper()
        assert "[BIO]" in sql.upper()

    def test_drop_action_renders_sql_server_drop(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("bio", VarCharType(length=100))])
        new = _expr(dialect, [_col("id", IntegerType(), _pk())])
        plan = old.diff(new)
        sql, _params = plan.alters[0].to_sql()
        assert sql.upper().endswith("DROP COLUMN [BIO]")


class TestTypeChangeRebuild:
    """Type changes keep the generic rebuild path on SQL Server."""

    def test_type_change_rebuilds(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("code", IntegerType())])
        new = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("code", BigIntType())])
        plan = old.diff(new)
        assert plan.alters == []
        rp = plan.rebuild
        assert isinstance(rp, RebuildPlan)
        assert "type change" in rp.reason

    def test_rebuild_plan_shape(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("code", IntegerType())])
        new = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("code", VarCharType(length=50))])
        rp = old.diff(new).rebuild
        assert rp.create.table_name == "items__rebuild__"
        assert rp.drop_old.table.name == "items"
        assert rp.rename.table == "items__rebuild__"
        rename_action = rp.rename.actions[0]
        assert isinstance(rename_action, RenameTable)
        assert rename_action.new_name == "items"
        assert rp.copy_columns == ["id", "code"]
        stmts = rp.ordered_statements()
        assert stmts[0] is rp.create and stmts[1] is rp.drop_old and stmts[2] is rp.rename

    def test_rebuild_plan_renders_executable_sql(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("code", IntegerType())])
        new = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("code", VarCharType(length=50))])
        rp = old.diff(new).rebuild
        create_sql, _ = rp.create.to_sql()
        drop_sql, _ = rp.drop_old.to_sql()
        rename_sql, _ = rp.rename.to_sql()
        assert "CREATE TABLE" in create_sql.upper()
        assert "DROP TABLE" in drop_sql.upper()
        # SQL Server renames via sp_rename, which the rename action surfaces
        assert "RENAME" in rename_sql.upper() or "SP_RENAME" in rename_sql.upper()


class TestColumnPropertyChanges:
    """Property changes have no standalone subclause on SQL Server → rebuild."""

    def test_set_default(self, dialect):
        """No standalone SET DEFAULT on SQL Server → rebuild."""
        old = _expr(dialect, [_col("status", VarCharType(length=20))])
        new = _expr(dialect, [_col("status", VarCharType(length=20), _default("ok"))])
        plan = old.diff(new)
        assert plan.alters == []
        assert plan.rebuild is not None
        assert "not supported in-place" in plan.rebuild.reason

    def test_drop_default(self, dialect):
        old = _expr(dialect, [_col("status", VarCharType(length=20), _default("ok"))])
        new = _expr(dialect, [_col("status", VarCharType(length=20))])
        assert old.diff(new).rebuild is not None

    def test_set_not_null(self, dialect):
        old = _expr(dialect, [_col("name", VarCharType(length=100))])
        new = _expr(dialect, [_col("name", VarCharType(length=100), _not_null())])
        plan = old.diff(new)
        assert plan.alters == []
        assert plan.rebuild is not None

    def test_drop_not_null(self, dialect):
        old = _expr(dialect, [_col("name", VarCharType(length=100), _not_null())])
        new = _expr(dialect, [_col("name", VarCharType(length=100))])
        assert old.diff(new).rebuild is not None


class TestIndexChanges:
    """No ALTER TABLE ADD/DROP INDEX on SQL Server → index changes rebuild."""

    def test_added_index(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk())])
        new = _expr(dialect, [_col("id", IntegerType(), _pk())],
                    indexes=[IndexDefinition(name="idx_code", columns=["id"])])
        plan = old.diff(new)
        assert plan.alters == []
        assert plan.rebuild is not None
        assert "index change" in plan.rebuild.reason

    def test_removed_index(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk())],
                    indexes=[IndexDefinition(name="idx_id", columns=["id"])])
        new = _expr(dialect, [_col("id", IntegerType(), _pk())])
        assert old.diff(new).rebuild is not None


class TestTableConstraintChanges:

    def test_pk_change_rebuilds(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType()), _col("code", VarCharType(length=50))],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.PRIMARY_KEY, columns=["id"])])
        new = _expr(dialect, [_col("id", IntegerType()), _col("code", VarCharType(length=50))],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.PRIMARY_KEY, columns=["code"])])
        plan = old.diff(new)
        assert plan.rebuild is not None
        assert "primary key" in plan.rebuild.reason

    def test_named_unique_constraint_add(self, dialect):
        """Named non-PK table constraints stay on the alter path."""
        old = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("email", VarCharType(length=255))])
        new = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("email", VarCharType(length=255))],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.UNIQUE,
                        name="uq_email", columns=["email"])])
        plan = old.diff(new)
        assert plan.rebuild is None
        (alter,) = plan.alters
        assert type(alter.actions[0]).__name__ == "AddTableConstraint"


class TestDiffPlanInvariants:

    def test_alters_and_rebuild_mutually_exclusive(self, dialect):
        old = _expr(dialect, [_col("id", IntegerType(), _pk())])
        new = _expr(dialect, [_col("id", IntegerType(), _pk()), _col("x", TextType())])
        plan = old.diff(new)
        assert plan.rebuild is None and plan.alters
        old2 = _expr(dialect, [_col("code", IntegerType())])
        new2 = _expr(dialect, [_col("code", VarCharType(length=50))])
        plan2 = old2.diff(new2)
        assert plan2.rebuild is not None and plan2.alters == []

    def test_plan_rejects_both_fields(self, dialect):
        old = _expr(dialect, [_col("code", IntegerType())])
        new = _expr(dialect, [_col("code", VarCharType(length=50))])
        rp = old.diff(new).rebuild
        assert rp is not None
        alter = AlterTableExpression(dialect, table="t", actions=[])
        with pytest.raises(ValueError, match="mutually exclusive"):
            DiffPlan(alters=[alter], rebuild=rp)
