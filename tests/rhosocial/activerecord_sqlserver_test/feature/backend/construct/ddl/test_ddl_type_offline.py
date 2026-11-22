# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/ddl/test_ddl_type_offline.py
"""Connectionless unit tests for the SQL Server user-defined TYPE DDL renderer.

Every test drives a real :class:`SQLServerDialect` (which mixes in
``SQLServerTypeDDLMixin``) with no connection and no network. Expression nodes
are real objects from the framework; only the few seams that cannot be reached
with a valid node (a definition that renders bind parameters, a constraint that
renders no SQL) are replaced with ``monkeypatch``/``MagicMock`` stand-ins.
"""

from unittest.mock import MagicMock

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import RawSQLPredicate
from rhosocial.activerecord.backend.expression.objects import Table, Type
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnCheckConstraint,
    ColumnConstraint,
    ColumnDefaultConstraint,
    ColumnDefinition,
    ColumnForeignKeyConstraint,
    ColumnNotNullConstraint,
    ColumnPrimaryKeyConstraint,
    TableCheckConstraint,
    TableConstraint,
    TableForeignKeyConstraint,
    TablePrimaryKeyConstraint,
)
from rhosocial.activerecord.backend.expression.statements.ddl_type import (
    AlterTypeStatement,
    CreateTypeStatement,
    DropTypeStatement,
    TypeAlterAction,
)
from rhosocial.activerecord.backend.impl.dummy.expression import _DummyTypeAlterAction
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.type import (
    SQLServerAliasTypeDefinition,
    SQLServerClrTypeDefinition,
    SQLServerDropTypeExpression,
    SQLServerRenameTypeStatement,
    SQLServerTableTypeDefinition,
)
from rhosocial.activerecord.backend.impl.sqlserver.expression.index import (
    SQLServerIndexDefinition,
)
import rhosocial.activerecord.backend.expression.types as core_types
import rhosocial.activerecord.backend.impl.sqlserver.expression.types as ss_types


V2005 = (9, 0, 0)
V2008 = (10, 0, 0)
V2012 = (11, 0, 0)
V2014 = (12, 0, 0)
V2016 = (13, 0, 0)
V2017 = (14, 0, 0)
V2019 = (15, 0, 0)
V2022 = (16, 0, 0)


def dialect(version=V2022, **kwargs):
    """Build a connectionless dialect (optionally with a deployment target)."""
    return SQLServerDialect(version, **kwargs)


def alias(base_type_cls, version=V2022, nullability=None, **type_kwargs):
    d = dialect(version)
    base = base_type_cls(d, **type_kwargs)
    return d, SQLServerAliasTypeDefinition(d, base, nullability=nullability)


class TestCapabilityBooleans:
    """The supports_* surface is a pure function of version and target."""

    @pytest.mark.parametrize("version", [V2005, V2008, V2016, V2022])
    def test_type_object_capabilities_at_2005_and_later(self, version):
        d = dialect(version)
        assert d.supports_type_objects() is True
        assert d.supports_create_type() is True
        assert d.supports_drop_type() is True
        assert d.supports_rename_type() is True
        assert d.supports_alter_type() is False
        assert d.supports_type_alter_action(_DummyTypeAlterAction) is False
        assert d.supports_create_type_if_not_exists() is False
        assert d.supports_create_type_or_replace() is False
        assert d.supports_alter_type_if_exists() is False
        assert d.supports_multiple_type_alter_actions() is False
        assert d.supports_drop_type_cascade() is False
        assert d.supports_drop_type_restrict() is False

    def test_unadapted_dialect_has_no_version_gated_capabilities(self):
        d = SQLServerDialect(version=None)
        assert d.supports_type_objects() is False
        assert d.supports_create_type() is False
        assert d.supports_drop_type() is False
        assert d.supports_rename_type() is False
        assert d.supports_drop_type_if_exists() is False

    @pytest.mark.parametrize(
        ("version", "expected"),
        [(V2005, False), (V2012, False), (V2016, True), (V2022, True)],
    )
    def test_drop_type_if_exists_is_2016_gate(self, version, expected):
        assert dialect(version).supports_drop_type_if_exists() is expected

    @pytest.mark.parametrize(
        ("version", "expected"), [(V2012, False), (V2014, True), (V2022, True)]
    )
    def test_memory_optimized_table_types_delegate(self, version, expected):
        d = dialect(version)
        assert d.supports_memory_optimized_table_types() is expected
        assert d.supports_memory_optimized_table_types() == bool(
            d.supports_memory_optimized_tables()
        )


class TestDeploymentTargetNormalization:
    def test_none_target_disables_clr(self):
        d = SQLServerDialect(V2022, deployment_target=None)
        assert d._is_sqlserver_deployment_target() is False
        assert d.supports_clr_type_definition() is False
        assert d.supports_clr_user_defined_type() is False

    @pytest.mark.parametrize(
        "target",
        [
            "sqlserver",
            "SQL Server",
            "sql_server_linux",
            "Microsoft SQL Server",
            "azure_sql_managed_instance",
            "on-premises",
        ],
    )
    def test_recognized_targets_enable_clr(self, target):
        d = SQLServerDialect(V2022, deployment_target=target)
        assert d._is_sqlserver_deployment_target() is True
        assert d.supports_clr_type_definition() is True
        assert d.supports_clr_user_defined_type() is True

    @pytest.mark.parametrize("target", ["azure_sql_database", "fabric", "postgresql", ""])
    def test_unrecognized_targets_disable_clr(self, target):
        d = SQLServerDialect(V2022, deployment_target=target)
        assert d._is_sqlserver_deployment_target() is False
        assert d.supports_clr_type_definition() is False

    def test_enum_like_target_value_is_unwrapped(self):
        class Target:
            value = "SQL Server Linux"

        d = SQLServerDialect(V2022)
        d.deployment_target = Target()
        assert d._is_sqlserver_deployment_target() is True


class TestSupportedTypeDefinitions:
    @pytest.mark.parametrize(
        ("version", "target", "definition", "expected"),
        [
            (V2005, "sqlserver", SQLServerAliasTypeDefinition, True),
            (V2005, "sqlserver", SQLServerTableTypeDefinition, False),
            (V2008, "sqlserver", SQLServerTableTypeDefinition, True),
            (V2022, "sqlserver", SQLServerClrTypeDefinition, True),
            (V2022, "azure_sql_database", SQLServerClrTypeDefinition, False),
        ],
    )
    def test_definition_support_matrix(self, version, target, definition, expected):
        d = dialect(version, deployment_target=target)
        assert d.supports_type_definition(definition) is expected
        assert (definition in d.supported_type_definitions()) is expected

    def test_non_class_definition_is_not_supported(self):
        d = dialect()
        assert d._definition_is_supported("not-a-class") is False
        assert d.supports_type_definition("not-a-class") is False
        assert d.supports_type_definition(object()) is False


class TestNameAndStringHelpers:
    def test_type_object_name_with_and_without_schema(self):
        d = dialect()
        assert d._type_object_name("my_type") == "[my_type]"
        assert d._type_object_name("my_type", "app") == "[app].[my_type]"
        assert d._type_object_name("type.with.dot", "app") == "[app].[type.with.dot]"

    def test_type_object_name_rejects_empty_type_name(self):
        d = dialect()
        for bad in ("", "   ", None, 42):
            with pytest.raises(ValueError):
                d._type_object_name(bad)

    def test_type_object_name_rejects_bad_schema(self):
        d = dialect()
        with pytest.raises(TypeError):
            d._type_object_name("t", 42)
        with pytest.raises(ValueError):
            d._type_object_name("t", "  ")

    def test_nstring_literal_escapes_quotes(self):
        d = dialect()
        assert d._format_nstring("plain") == "N'plain'"
        assert d._format_nstring("it's") == "N'it''s'"

    def test_nstring_rejects_non_string(self):
        with pytest.raises(TypeError):
            dialect()._format_nstring(42)


class TestTableTypeColumnValidation:
    def test_non_column_definition_is_rejected(self):
        with pytest.raises(TypeError, match="ColumnDefinition"):
            dialect()._format_table_type_column(object(), memory_optimized=False)

    def test_comment_is_rejected(self):
        d = dialect()
        column = ColumnDefinition(d, "id", core_types.IntegerType(d))
        column.comment = MagicMock()
        with pytest.raises(UnsupportedFeatureError, match="comment"):
            d._format_table_type_column(column, memory_optimized=False)

    def test_generated_column_is_rejected(self):
        d = dialect()
        column = ColumnDefinition(d, "id", core_types.IntegerType(d))
        column.generated_expression = MagicMock()
        with pytest.raises(UnsupportedFeatureError, match="computed"):
            d._format_table_type_column(column, memory_optimized=False)

    @pytest.mark.parametrize("attribute", ["sparse", "rowguidcol"])
    def test_storage_attributes_are_rejected(self, attribute):
        d = dialect()
        column = ColumnDefinition(d, "id", core_types.IntegerType(d))
        setattr(column, attribute, True)
        with pytest.raises(UnsupportedFeatureError, match="storage attribute"):
            d._format_table_type_column(column, memory_optimized=False)

    def test_unsupported_column_constraint_is_rejected(self):
        d = dialect()
        fk = ColumnForeignKeyConstraint(d, (Table(d, "other"), ["id"]))
        column = ColumnDefinition(
            d,
            "id",
            core_types.IntegerType(d),
            constraints=[ColumnConstraint(d, branch=fk)],
        )
        with pytest.raises(UnsupportedFeatureError, match="TYPE table column constraint"):
            d._format_table_type_column(column, memory_optimized=False)

    def test_memory_optimized_disallowed_constraint_is_rejected(self):
        d = dialect(V2014)
        column = ColumnDefinition(
            d,
            "id",
            core_types.IntegerType(d),
            constraints=[
                ColumnConstraint(
                    d,
                    branch=ColumnCheckConstraint(d, RawSQLPredicate(d, "1 = 1")),
                )
            ],
        )
        with pytest.raises(UnsupportedFeatureError, match="memory-optimized"):
            d._format_table_type_column(column, memory_optimized=True)


class TestTableTypeConstraintValidation:
    def test_non_constraint_is_rejected(self):
        with pytest.raises(TypeError, match="TableConstraint"):
            dialect()._format_table_type_constraint(object(), memory_optimized=False)

    def test_empty_key_columns_are_rejected(self):
        d = dialect()
        constraint = TableConstraint(d, branch=TablePrimaryKeyConstraint(d, []))
        with pytest.raises(ValueError, match="requires columns"):
            d._format_table_type_constraint(constraint, memory_optimized=False)

    @pytest.mark.parametrize(
        ("kwargs", "spelling"),
        [
            ({"deferrable": True}, "DEFERRABLE"),
            ({"not_deferrable": True}, "NOT DEFERRABLE"),
            ({"initially_deferred": True}, "INITIALLY DEFERRED"),
            ({"initially_immediate": True}, "INITIALLY IMMEDIATE"),
            ({"enforced": True}, "ENFORCED"),
            ({"not_enforced": True}, "NOT ENFORCED"),
        ],
    )
    def test_constraint_options_are_rejected(self, kwargs, spelling):
        d = dialect()
        constraint = TableConstraint(d, branch=TablePrimaryKeyConstraint(d, ["id"]), **kwargs)
        with pytest.raises(UnsupportedFeatureError, match=spelling.replace(" ", ".")):
            d._format_table_type_constraint(constraint, memory_optimized=False)

    def test_validation_option_is_rejected(self):
        d = dialect()
        branch = TableCheckConstraint(d, RawSQLPredicate(d, "1 = 1"))
        constraint = TableConstraint(d, branch=branch, validation=MagicMock())
        with pytest.raises(UnsupportedFeatureError, match="validation"):
            d._format_table_type_constraint(constraint, memory_optimized=False)

    def test_empty_rendered_sql_is_rejected(self, monkeypatch):
        d = dialect()
        constraint = TableConstraint(d, branch=TablePrimaryKeyConstraint(d, ["id"]))
        monkeypatch.setattr(d, "render_table_constraint", lambda *a, **k: ("", ()))
        with pytest.raises(ValueError, match="did not render SQL"):
            d._format_table_type_constraint(constraint, memory_optimized=False)

    def test_memory_optimized_check_requires_2016(self):
        d = dialect(V2014)
        constraint = TableConstraint(
            d, branch=TableCheckConstraint(d, RawSQLPredicate(d, "1 = 1"))
        )
        with pytest.raises(UnsupportedFeatureError, match="2016"):
            d._format_table_type_constraint(constraint, memory_optimized=True)

    def test_memory_optimized_foreign_key_is_rejected(self):
        d = dialect()
        constraint = TableConstraint(
            d,
            branch=TableForeignKeyConstraint(
                d, ["id"], (Type(d, "other"), ["id"])
            ),
        )
        with pytest.raises(UnsupportedFeatureError, match="memory-optimized"):
            d._format_table_type_constraint(constraint, memory_optimized=True)


class TestTableTypeIndexValidation:
    def make_index(self, **kwargs):
        d = dialect()
        return d, SQLServerIndexDefinition(d, "ix", ["id"], **kwargs)

    @pytest.mark.parametrize("index", [object(), "index", None])
    def test_non_index_definition_is_rejected(self, index):
        with pytest.raises(TypeError, match="IndexDefinition"):
            dialect()._format_table_type_index(index, memory_optimized=False)

    @pytest.mark.parametrize("name", ["", "   ", None])
    def test_empty_index_name_is_rejected(self, name):
        d = dialect()
        index = SQLServerIndexDefinition(d, name, ["id"])
        with pytest.raises(ValueError, match="non-empty string"):
            d._format_table_type_index(index, memory_optimized=False)

    def test_no_columns_is_rejected(self):
        d = dialect()
        index = SQLServerIndexDefinition(d, "ix", [])
        with pytest.raises(ValueError, match="at least one column"):
            d._format_table_type_index(index, memory_optimized=False)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"partial_condition": MagicMock()},
            {"if_not_exists": True},
            {"if_exists": True},
            {"tablespace": "ts"},
        ],
    )
    def test_unsupported_index_options_are_rejected(self, kwargs):
        d = dialect()
        index = SQLServerIndexDefinition(d, "ix", ["id"])
        for key, value in kwargs.items():
            setattr(index, key, value)
        with pytest.raises(UnsupportedFeatureError, match="TYPE table index option"):
            d._format_table_type_index(index, memory_optimized=False)

    @pytest.mark.parametrize("bad", [True, "1024", 1.5])
    def test_bucket_count_must_be_an_integer(self, bad):
        d, index = self.make_index(hash_index=True, bucket_count=1024)
        index.bucket_count = bad
        with pytest.raises(TypeError, match="bucket_count must be an integer"):
            d._format_table_type_index(index, memory_optimized=True)

    @pytest.mark.parametrize("bad", [0, -1, 1_073_741_825])
    def test_bucket_count_range_is_enforced(self, bad):
        d = dialect(V2014)
        index = SQLServerIndexDefinition(
            d, "ix", ["id"], hash_index=True, bucket_count=bad
        )
        with pytest.raises(ValueError, match="bucket_count must be between"):
            d._format_table_type_index(index, memory_optimized=True)

    def test_bucket_count_requires_hash_index(self):
        d = dialect()
        index = SQLServerIndexDefinition(d, "ix", ["id"], bucket_count=1024)
        with pytest.raises(UnsupportedFeatureError, match="bucket_count is valid only"):
            d._format_table_type_index(index, memory_optimized=False)

    def test_hash_index_requires_memory_optimized(self):
        d = dialect()
        index = SQLServerIndexDefinition(
            d, "ix", ["id"], hash_index=True, bucket_count=1024
        )
        with pytest.raises(UnsupportedFeatureError, match="memory-optimized"):
            d._format_table_type_index(index, memory_optimized=False)

    def test_hash_index_requires_bucket_count(self):
        d = dialect(V2014)
        index = SQLServerIndexDefinition(d, "ix", ["id"], hash_index=True)
        with pytest.raises(ValueError, match="bucket_count is required"):
            d._format_table_type_index(index, memory_optimized=True)

    def test_bad_index_type_is_rejected(self):
        d, index = self.make_index(type="heap")
        with pytest.raises(UnsupportedFeatureError, match="index type HEAP"):
            d._format_table_type_index(index, memory_optimized=False)

    def test_non_string_index_type_is_rejected(self):
        d, index = self.make_index(type=123)
        with pytest.raises(TypeError, match="index type must be a string"):
            d._format_table_type_index(index, memory_optimized=False)

    def test_clustered_index_rejected_on_memory_optimized(self):
        d, index = self.make_index(type="clustered")
        with pytest.raises(UnsupportedFeatureError, match="cannot be clustered"):
            d._format_table_type_index(index, memory_optimized=True)

    def test_expression_index_column_is_rendered(self):
        d = dialect()
        index = SQLServerIndexDefinition(d, "ix", [Type(d, "col")])
        sql, params = d._format_table_type_index(index, memory_optimized=False)
        assert "INDEX [ix] ([col])" in sql
        assert params == ()

    def test_bad_index_column_type_is_rejected(self):
        d = dialect()
        index = SQLServerIndexDefinition(d, "ix", [42])
        with pytest.raises(TypeError, match="strings or expressions"):
            d._format_table_type_index(index, memory_optimized=False)

    def test_unique_index_and_include_columns_render(self):
        d = dialect(V2019)
        index = SQLServerIndexDefinition(
            d, "ix", ["id"], unique=True, include_columns=["payload"]
        )
        sql, _ = d._format_table_type_index(index, memory_optimized=True)
        assert sql.startswith("UNIQUE INDEX [ix] NONCLUSTERED")
        assert "INCLUDE ([payload])" in sql

    def test_non_string_include_column_is_rejected(self):
        d = dialect(V2019)
        index = SQLServerIndexDefinition(d, "ix", ["id"], include_columns=["ok"])
        index.include_columns = ["ok", 42]
        with pytest.raises(TypeError, match="INCLUDE columns must be strings"):
            d._format_table_type_index(index, memory_optimized=True)

    def test_hack_index_include_is_rejected(self):
        d = dialect(V2019)
        index = SQLServerIndexDefinition(
            d,
            "ix",
            ["id"],
            hash_index=True,
            bucket_count=1024,
            include_columns=["payload"],
        )
        with pytest.raises(UnsupportedFeatureError, match="HASH indexes cannot use INCLUDE"):
            d._format_table_type_index(index, memory_optimized=True)

    def test_hash_index_emits_bucket_count(self):
        d = dialect(V2014)
        index = SQLServerIndexDefinition(
            d, "ix", ["id"], hash_index=True, bucket_count=2048
        )
        sql, _ = d._format_table_type_index(index, memory_optimized=True)
        assert "NONCLUSTERED HASH ([id]) WITH (BUCKET_COUNT = 2048)" in sql

    def test_include_requires_2019(self):
        d = dialect(V2017)
        index = SQLServerIndexDefinition(d, "ix", ["id"], include_columns=["payload"])
        with pytest.raises(UnsupportedFeatureError, match="2019"):
            d._format_table_type_index(index, memory_optimized=True)


class TestFormatCreateType:
    def test_create_alias_type_renders_all_representative_sql_server_types(self):
        cases = [
            (core_types.IntegerType, {}, "INT"),
            (core_types.BigIntType, {}, "BIGINT"),
            (core_types.DecimalType, {"precision": 10, "scale": 2}, "DECIMAL(10, 2)"),
            (ss_types.SQLServerNVarCharType, {"length": 64}, "NVARCHAR(64)"),
            (core_types.VarCharType, {"length": 32}, "VARCHAR(32)"),
            (ss_types.SQLServerUniqueIdentifierType, {}, "UNIQUEIDENTIFIER"),
            (core_types.TimestampType, {}, "DATETIME2"),
            (core_types.TimestampTzType, {}, "DATETIMEOFFSET"),
            (ss_types.SQLServerVarBinaryType, {"length": 100}, "VARBINARY(100)"),
            (ss_types.SQLServerXmlType, {}, "XML"),
        ]
        for type_cls, kwargs, fragment in cases:
            d = dialect()
            base = type_cls(d, **kwargs)
            definition = SQLServerAliasTypeDefinition(d, base)
            stmt = CreateTypeStatement(d, Type(d, "t"), definition)
            sql, params = d.format_create_type_statement(stmt)
            assert sql == f"CREATE TYPE [t] FROM {fragment}"
            assert params == ()

    def test_create_type_rejects_wrong_statement_type(self):
        with pytest.raises(TypeError, match="CreateTypeStatement"):
            dialect().format_create_type_statement(object())

    def test_create_type_rejects_mutually_exclusive_options(self):
        d, definition = alias(core_types.IntegerType)
        stmt = CreateTypeStatement(d, Type(d, "t"), definition)
        stmt.if_not_exists = True
        stmt.or_replace = True
        with pytest.raises(ValueError, match="mutually exclusive"):
            d.format_create_type_statement(stmt)

    def test_create_type_rejects_old_version_and_unsupported_options(self):
        d = SQLServerDialect(version=None)
        definition = SQLServerAliasTypeDefinition(d, core_types.IntegerType(d))
        stmt = CreateTypeStatement(d, Type(d, "t"), definition)
        with pytest.raises(UnsupportedFeatureError):
            d.format_create_type_statement(stmt)

        modern = dialect()
        definition = SQLServerAliasTypeDefinition(modern, core_types.IntegerType(modern))
        with pytest.raises(UnsupportedFeatureError, match="IF NOT EXISTS"):
            modern.format_create_type_statement(
                CreateTypeStatement(modern, Type(modern, "t"), definition, if_not_exists=True)
            )
        with pytest.raises(UnsupportedFeatureError, match="OR REPLACE"):
            modern.format_create_type_statement(
                CreateTypeStatement(modern, Type(modern, "t"), definition, or_replace=True)
            )

    def test_create_type_rejects_wrong_type_object(self):
        d, definition = alias(core_types.IntegerType)
        stmt = CreateTypeStatement(d, MagicMock(), definition)
        with pytest.raises(TypeError, match="must be a Type"):
            d.format_create_type_statement(stmt)

    def test_create_type_rejects_wrong_definition(self):
        d = dialect()
        stmt = CreateTypeStatement(d, Type(d, "t"), MagicMock())
        with pytest.raises(TypeError, match="TypeDefinition"):
            d.format_create_type_statement(stmt)

    def test_create_type_rejects_definition_with_bind_params(self, monkeypatch):
        d, definition = alias(core_types.IntegerType)
        monkeypatch.setattr(definition, "to_sql", lambda: ("FROM INT", (1,)))
        stmt = CreateTypeStatement(d, Type(d, "t"), definition)
        with pytest.raises(ValueError, match="without bind parameters"):
            d.format_create_type_statement(stmt)


class TestFormatAlterAndDropType:
    def test_alter_type_statement_is_always_unsupported(self):
        d = dialect()
        action = _DummyTypeAlterAction(d, "renamed")
        with pytest.raises(TypeError, match="AlterTypeStatement"):
            d.format_alter_type_statement(object())
        with pytest.raises(UnsupportedFeatureError, match="ALTER TYPE"):
            d.format_alter_type_statement(
                AlterTypeStatement(d, Type(d, "t"), [action])
            )

    def test_format_type_alter_action(self):
        d = dialect()
        action = _DummyTypeAlterAction(d, "renamed")
        assert isinstance(action, TypeAlterAction)
        with pytest.raises(TypeError, match="TypeAlterAction"):
            d.format_type_alter_action(object())
        with pytest.raises(UnsupportedFeatureError, match="ALTER TYPE action"):
            d.format_type_alter_action(action)

    def test_drop_type_renders_if_exists_on_modern_versions(self):
        d = dialect(V2016)
        sql, params = d.format_drop_type_statement(
            DropTypeStatement(d, Type(d, "status", schema_name="app"), if_exists=True)
        )
        assert sql == "DROP TYPE IF EXISTS [app].[status]"
        assert params == ()

    def test_drop_type_rejects_wrong_statement_and_type(self):
        d = dialect()
        with pytest.raises(TypeError, match="DropTypeStatement"):
            d.format_drop_type_statement(object())
        stmt = DropTypeStatement(d, MagicMock())
        with pytest.raises(TypeError, match="must be a Type"):
            d.format_drop_type_statement(stmt)

    def test_drop_type_if_exists_requires_2016(self):
        d = dialect(V2012)
        stmt = DropTypeStatement(d, Type(d, "status"), if_exists=True)
        with pytest.raises(UnsupportedFeatureError, match="2016"):
            d.format_drop_type_statement(stmt)

    def test_drop_type_cascade_and_restrict_are_rejected(self):
        d = dialect()
        target = Type(d, "status")
        with pytest.raises(ValueError, match="mutually exclusive"):
            SQLServerDropTypeExpression(d, target, cascade=True, restrict=True)
        with pytest.raises(UnsupportedFeatureError, match="CASCADE"):
            d.format_drop_type_statement(
                SQLServerDropTypeExpression(d, target, cascade=True)
            )
        with pytest.raises(UnsupportedFeatureError, match="RESTRICT"):
            d.format_drop_type_statement(
                SQLServerDropTypeExpression(d, target, restrict=True)
            )


class TestFormatTypeDefinition:
    def test_alias_nullability_spellings(self):
        d = dialect()
        base = core_types.IntegerType(d)
        assert d.format_type_definition(SQLServerAliasTypeDefinition(d, base)) == (
            "FROM INT",
            (),
        )
        assert d.format_type_definition(
            SQLServerAliasTypeDefinition(d, base, nullability=True)
        ) == ("FROM INT NOT NULL", ())
        assert d.format_type_definition(
            SQLServerAliasTypeDefinition(d, base, nullability=False)
        ) == ("FROM INT NULL", ())

    def test_alias_with_bind_params_is_rejected(self, monkeypatch):
        d = dialect()
        definition = SQLServerAliasTypeDefinition(d, core_types.IntegerType(d))
        monkeypatch.setattr(definition.base_type, "to_sql", lambda: ("INT", (5,)))
        with pytest.raises(ValueError, match="without bind parameters"):
            d.format_type_definition(definition)

    def test_clr_definition_with_and_without_class(self):
        d = dialect()
        without_class = SQLServerClrTypeDefinition(d, "My.Assembly")
        with_class = SQLServerClrTypeDefinition(d, "My.Assembly", "My.Class")
        assert d.format_type_definition(without_class) == ("EXTERNAL NAME [My.Assembly]", ())
        assert d.format_type_definition(with_class) == (
            "EXTERNAL NAME [My.Assembly].[My.Class]",
            (),
        )

    def test_table_definition_delegates_to_table_renderer(self):
        d = dialect()
        definition = SQLServerTableTypeDefinition(
            d, columns=[ColumnDefinition(d, "id", core_types.IntegerType(d))]
        )
        sql, params = d.format_type_definition(definition)
        assert sql == "AS TABLE ([id] INT)"
        assert params == ()

    def test_wrong_definition_type_is_rejected(self):
        with pytest.raises(TypeError, match="TypeDefinition"):
            dialect().format_type_definition(object())

    def test_unsupported_definition_is_rejected(self):
        d = dialect()
        unsupported = SQLServerClrTypeDefinition(d, "assembly", "Class")
        azure = dialect(deployment_target="azure_sql_database")
        with pytest.raises(UnsupportedFeatureError, match="TYPE definition"):
            azure.format_type_definition(unsupported)


class TestFormatRenameType:
    def test_rename_uses_sp_rename(self):
        d = dialect()
        stmt = SQLServerRenameTypeStatement(d, "old", "new", schema_name="app")
        sql, params = d.format_rename_type_statement(stmt)
        assert sql == "EXECUTE sp_rename N'[app].[old]', N'new', N'USERDATATYPE'"
        assert params == ()

    def test_rename_rejects_wrong_statement(self):
        with pytest.raises(TypeError, match="SQLServerRenameTypeStatement"):
            dialect().format_rename_type_statement(object())

    def test_rename_requires_2005(self):
        d = SQLServerDialect(version=None)
        stmt = SQLServerRenameTypeStatement(d, "old", "new")
        with pytest.raises(UnsupportedFeatureError, match="2005"):
            d.format_rename_type_statement(stmt)


class TestTableTypeDefinitionGuards:
    def test_memory_optimized_requires_2014(self):
        d = dialect(V2012)
        definition = SQLServerTableTypeDefinition(
            d,
            columns=[ColumnDefinition(d, "id", core_types.IntegerType(d))],
            indexes=[SQLServerIndexDefinition(d, "ix", ["id"])],
            memory_optimized=True,
        )
        with pytest.raises(UnsupportedFeatureError, match="2014"):
            d.format_type_definition(definition)

    def test_memory_optimized_without_key_or_index_is_rejected(self):
        d = dialect(V2014)
        definition = SQLServerTableTypeDefinition(
            d,
            columns=[ColumnDefinition(d, "id", core_types.IntegerType(d))],
            memory_optimized=True,
        )
        with pytest.raises(ValueError, match="at least one index"):
            d.format_type_definition(definition)

    def test_too_many_indexes_before_2017(self):
        d = dialect(V2016)
        columns = [
            ColumnDefinition(d, f"c{i}", core_types.IntegerType(d)) for i in range(9)
        ]
        indexes = [SQLServerIndexDefinition(d, f"ix{i}", [f"c{i}"]) for i in range(9)]
        definition = SQLServerTableTypeDefinition(
            d, columns=columns, indexes=indexes, memory_optimized=True
        )
        with pytest.raises(UnsupportedFeatureError, match="8 indexes"):
            d.format_type_definition(definition)

    @pytest.mark.parametrize(
        ("branch_cls", "args"),
        [
            (ColumnNotNullConstraint, ()),
            (ColumnPrimaryKeyConstraint, ()),
            (ColumnDefaultConstraint, (0,)),
        ],
    )
    def test_supported_column_constraints_render(self, branch_cls, args):
        d = dialect()
        branch = branch_cls(d, *args)
        column = ColumnDefinition(
            d, "id", core_types.IntegerType(d), constraints=[ColumnConstraint(d, branch=branch)]
        )
        sql, _ = d._format_table_type_column(column, memory_optimized=False)
        assert sql.startswith("[id] INT")


class TestRemainingBranches:
    """Small targeted checks for the last reachable renderer branches."""

    def test_unmatched_definition_class_is_not_supported(self):
        assert dialect()._definition_is_supported(object) is False

    def test_memory_optimized_column_foreign_key_is_rejected(self):
        d = dialect()
        column = ColumnDefinition(
            d,
            "id",
            core_types.IntegerType(d),
            constraints=[
                ColumnConstraint(
                    d, branch=ColumnForeignKeyConstraint(d, (Table(d, "other"), ["id"]))
                )
            ],
        )
        with pytest.raises(UnsupportedFeatureError, match="memory-optimized"):
            d._format_table_type_column(column, memory_optimized=True)

    def test_table_foreign_key_constraint_is_rejected(self):
        d = dialect()
        constraint = TableConstraint(
            d,
            branch=TableForeignKeyConstraint(d, ["id"], (Table(d, "other"), ["id"])),
        )
        with pytest.raises(UnsupportedFeatureError, match="TYPE table constraint"):
            d._format_table_type_constraint(constraint, memory_optimized=False)

    def test_successful_table_constraint_render(self):
        d = dialect()
        constraint = TableConstraint(d, branch=TablePrimaryKeyConstraint(d, ["id"]))
        sql, params = d._format_table_type_constraint(constraint, memory_optimized=False)
        assert "PRIMARY KEY ([id])" in sql
        assert params == ()

    def test_hash_index_requires_2014(self):
        d = dialect(V2012)
        index = SQLServerIndexDefinition(d, "ix", ["id"], hash_index=True, bucket_count=1024)
        with pytest.raises(UnsupportedFeatureError, match="2014"):
            d._format_table_type_index(index, memory_optimized=True)

    def test_explicit_index_type_spelling(self):
        d = dialect()
        index = SQLServerIndexDefinition(d, "ix", ["id"], type="nonclustered")
        sql, _ = d._format_table_type_index(index, memory_optimized=False)
        assert sql == "INDEX [ix] NONCLUSTERED ([id])"

    def test_table_definition_renders_constraints_and_indexes(self):
        d = dialect()
        definition = SQLServerTableTypeDefinition(
            d,
            columns=[ColumnDefinition(d, "id", core_types.IntegerType(d))],
            constraints=[TableConstraint(d, branch=TablePrimaryKeyConstraint(d, ["id"]))],
            indexes=[SQLServerIndexDefinition(d, "ix", ["id"])],
        )
        sql, params = d.format_type_definition(definition)
        assert "PRIMARY KEY ([id])" in sql
        assert "INDEX [ix] ([id])" in sql
        assert params == ()

    def test_memory_optimized_definition_appends_option(self):
        d = dialect(V2014)
        definition = SQLServerTableTypeDefinition(
            d,
            columns=[ColumnDefinition(d, "id", core_types.IntegerType(d))],
            indexes=[SQLServerIndexDefinition(d, "ix", ["id"])],
            memory_optimized=True,
        )
        sql, params = d.format_type_definition(definition)
        assert sql.endswith("WITH (MEMORY_OPTIMIZED = ON)")
        assert params == ()

    def test_create_type_rejects_unsupported_definition(self):
        d = dialect()
        clr = SQLServerClrTypeDefinition(d, "assembly", "Class")
        azure = dialect(deployment_target="azure_sql_database")
        stmt = CreateTypeStatement(azure, Type(azure, "t"), clr)
        with pytest.raises(UnsupportedFeatureError, match="TYPE definition"):
            azure.format_create_type_statement(stmt)

    def test_drop_type_rejects_unadapted_dialect(self):
        d = SQLServerDialect(version=None)
        stmt = DropTypeStatement(d, Type(d, "status"))
        with pytest.raises(UnsupportedFeatureError, match="DROP TYPE"):
            d.format_drop_type_statement(stmt)

    def test_manually_flagged_cascade_and_restrict_are_rejected(self):
        d = dialect()
        expr = SQLServerDropTypeExpression(d, Type(d, "status"))
        expr.cascade = True
        expr.restrict = True
        with pytest.raises(ValueError, match="mutually exclusive"):
            d.format_drop_type_statement(expr)
