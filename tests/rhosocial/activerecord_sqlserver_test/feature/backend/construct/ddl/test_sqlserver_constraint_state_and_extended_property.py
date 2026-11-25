# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/ddl/test_constraint_state_extended_property.py
"""SQL Server constraint-state and extended-property write statements.

Both families are backend-proprietary: T-SQL spells the constraint state with
``CHECK`` / ``NOCHECK CONSTRAINT`` (two keyword positions, verified against
Microsoft Learn's ALTER TABLE page) and writes extended properties through the
three ``sys.sp_*extendedproperty`` procedures. Neither has a core counterpart.

Pure-construction tests: no database connection is required.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression import (
    SQLServerCheckConstraintStatement,
    SQLServerExtendedPropertyWriteStatement,
    SQLServerNocheckConstraintStatement,
)


@pytest.fixture
def dialect():
    return SQLServerDialect((2019, 0, 0))


class TestConstraintStateProbes:
    def test_both_probes_answer_true_on_2019(self, dialect):
        assert dialect.supports_constraint_check_nocheck() is True
        assert dialect.supports_extended_properties_write() is True

    def test_protocols_are_advertised(self, dialect):
        from rhosocial.activerecord.backend.impl.sqlserver.protocols import (
            SQLServerConstraintStateSupport,
            SQLServerExtendedPropertyWriteSupport,
        )

        assert isinstance(dialect, SQLServerConstraintStateSupport)
        assert isinstance(dialect, SQLServerExtendedPropertyWriteSupport)


class TestCheckConstraintRendering:
    def test_all_with_check(self, dialect):
        sql, params = SQLServerCheckConstraintStatement(
            dialect, "dbo.t", all_constraints=True, with_check=True
        ).to_sql()
        assert sql == "ALTER TABLE [dbo].[t] WITH CHECK CHECK CONSTRAINT ALL"
        assert params == ()

    def test_named_constraints(self, dialect):
        sql, _ = SQLServerCheckConstraintStatement(
            dialect, "t", constraint_names=["ck_a", "ck_b"]
        ).to_sql()
        assert sql == "ALTER TABLE [t] CHECK CONSTRAINT [ck_a], [ck_b]"

    def test_with_nocheck_prefix(self, dialect):
        sql, _ = SQLServerCheckConstraintStatement(
            dialect, "t", constraint_names=["ck_a"], with_nocheck=True
        ).to_sql()
        assert sql == "ALTER TABLE [t] WITH NOCHECK CHECK CONSTRAINT [ck_a]"

    def test_both_prefixes_are_refused(self, dialect):
        with pytest.raises(ValueError, match="mutually exclusive"):
            SQLServerCheckConstraintStatement(
                dialect, "t", constraint_names=["ck_a"],
                with_check=True, with_nocheck=True,
            ).to_sql()

    def test_all_plus_names_are_refused(self, dialect):
        with pytest.raises(ValueError, match="mutually exclusive"):
            SQLServerCheckConstraintStatement(
                dialect, "t", all_constraints=True, constraint_names=["ck_a"]
            ).to_sql()

    def test_no_address_is_refused(self, dialect):
        with pytest.raises(ValueError, match="ALL or at least one constraint"):
            SQLServerCheckConstraintStatement(dialect, "t").to_sql()

    def test_wrong_node_kind_is_refused(self, dialect):
        with pytest.raises(TypeError):
            dialect.format_check_constraint_statement(
                SQLServerNocheckConstraintStatement(dialect, "t", all_constraints=True)
            )


class TestNocheckConstraintRendering:
    def test_all(self, dialect):
        sql, params = SQLServerNocheckConstraintStatement(
            dialect, "dbo.t", all_constraints=True
        ).to_sql()
        assert sql == "ALTER TABLE [dbo].[t] NOCHECK CONSTRAINT ALL"
        assert params == ()

    def test_named(self, dialect):
        sql, _ = SQLServerNocheckConstraintStatement(
            dialect, "t", constraint_names=["fk_a"]
        ).to_sql()
        assert sql == "ALTER TABLE [t] NOCHECK CONSTRAINT [fk_a]"

    def test_mirror_refusals(self, dialect):
        with pytest.raises(ValueError, match="mutually exclusive"):
            SQLServerNocheckConstraintStatement(
                dialect, "t", constraint_names=["a"], with_check=True, with_nocheck=True
            ).to_sql()
        with pytest.raises(ValueError, match="ALL or at least one constraint"):
            SQLServerNocheckConstraintStatement(dialect, "t").to_sql()


class TestExtendedPropertyRendering:
    def test_add_with_value(self, dialect):
        sql, params = SQLServerExtendedPropertyWriteStatement(
            dialect, "ADD", "MS_Description", value="O'Brien",
            level0type="SCHEMA", level0name="dbo",
            level1type="TABLE", level1name="T1",
        ).to_sql()
        assert sql == (
            "EXEC sys.sp_addextendedproperty @name = N'MS_Description', "
            "@value = N'O''Brien', @level0type = N'SCHEMA', @level0name = N'dbo', "
            "@level1type = N'TABLE', @level1name = N'T1'"
        )
        assert params == ()

    def test_update_with_null_value(self, dialect):
        sql, _ = SQLServerExtendedPropertyWriteStatement(
            dialect, "UPDATE", "MS_Description",
            level0type="SCHEMA", level0name="dbo",
            level1type="TABLE", level1name="T1",
        ).to_sql()
        assert "@value = NULL" in sql
        assert sql.startswith("EXEC sys.sp_updateextendedproperty ")

    def test_drop_has_no_value_argument(self, dialect):
        sql, _ = SQLServerExtendedPropertyWriteStatement(
            dialect, "DROP", "MS_Description",
            level0type="SCHEMA", level0name="dbo",
            level1type="TABLE", level1name="T1",
        ).to_sql()
        assert sql.startswith("EXEC sys.sp_dropextendedproperty ")
        assert "@value" not in sql

    def test_drop_with_value_is_refused(self, dialect):
        with pytest.raises(ValueError, match="no @value argument"):
            SQLServerExtendedPropertyWriteStatement(
                dialect, "DROP", "MS_Description", value="x",
                level0type="SCHEMA", level0name="dbo",
            ).to_sql()

    def test_database_level_property_has_no_levels(self, dialect):
        sql, _ = SQLServerExtendedPropertyWriteStatement(
            dialect, "ADD", "AppName", value="demo"
        ).to_sql()
        assert sql == "EXEC sys.sp_addextendedproperty @name = N'AppName', @value = N'demo'"

    def test_column_level(self, dialect):
        sql, _ = SQLServerExtendedPropertyWriteStatement(
            dialect, "ADD", "MS_Description", value="col",
            level0type="SCHEMA", level0name="dbo",
            level1type="TABLE", level1name="T1",
            level2type="COLUMN", level2name="id",
        ).to_sql()
        assert "@level2type = N'COLUMN'" in sql
        assert "@level2name = N'id'" in sql

    def test_type_without_name_is_refused(self, dialect):
        with pytest.raises(ValueError, match="must be supplied together"):
            SQLServerExtendedPropertyWriteStatement(
                dialect, "ADD", "MS_Description", value="x",
                level0type="SCHEMA",
            ).to_sql()

    def test_child_level_requires_parent(self, dialect):
        with pytest.raises(ValueError, match="@level1 requires @level0"):
            SQLServerExtendedPropertyWriteStatement(
                dialect, "ADD", "MS_Description", value="x",
                level1type="TABLE", level1name="T1",
            ).to_sql()

    def test_unknown_operation_is_refused(self, dialect):
        with pytest.raises(ValueError, match="unknown extended-property operation"):
            SQLServerExtendedPropertyWriteStatement(
                dialect, "MERGE", "MS_Description", value="x"
            ).to_sql()

    def test_blank_name_is_refused(self, dialect):
        with pytest.raises(ValueError, match="@name must be a non-empty string"):
            SQLServerExtendedPropertyWriteStatement(
                dialect, "ADD", "   ", value="x"
            ).to_sql()

    def test_empty_value_is_allowed(self, dialect):
        sql, _ = SQLServerExtendedPropertyWriteStatement(
            dialect, "ADD", "MS_Description", value=""
        ).to_sql()
        assert "@value = N''" in sql

    def test_wrong_node_kind_is_refused(self, dialect):
        with pytest.raises(TypeError):
            dialect.format_extended_property_write_statement(
                SQLServerNocheckConstraintStatement(dialect, "t", all_constraints=True)
            )


class TestCapabilityGates:
    def test_check_state_refuses_when_probe_withdrawn(self, dialect, monkeypatch):
        monkeypatch.setattr(
            dialect, "supports_constraint_check_nocheck", lambda: False
        )
        with pytest.raises(UnsupportedFeatureError):
            SQLServerCheckConstraintStatement(
                dialect, "t", all_constraints=True
            ).to_sql()

    def test_extended_property_refuses_below_the_floor(self, monkeypatch):
        # (8, 0, 0) is SQL Server 2000; the procedures arrive with 2005 (9, 0, 0).
        old = SQLServerDialect((8, 0, 0))
        with pytest.raises(UnsupportedFeatureError):
            SQLServerExtendedPropertyWriteStatement(
                old, "ADD", "MS_Description", value="x"
            ).to_sql()