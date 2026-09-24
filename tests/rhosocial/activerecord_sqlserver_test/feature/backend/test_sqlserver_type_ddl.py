# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_sqlserver_type_ddl.py
"""SQL Server schema-level TYPE DDL SQL, capability, and protocol tests."""

import pytest

from rhosocial.activerecord.backend.expression import RawSQLPredicate
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.mixins import UserDefinedTypeMixin
from rhosocial.activerecord.backend.dialect.protocols import UserDefinedTypeSupport
from rhosocial.activerecord.backend.expression.serialization import (
    ExpressionRegistry,
    deserialize,
    deserialize_json,
    deserialize_xml,
    serialize,
    serialize_json,
    serialize_xml,
)
from rhosocial.activerecord.backend.expression.statements import (
    AlterTypeExpression,
    ColumnConstraint,
    ColumnConstraintType,
    ColumnDefinition,
    CreateTypeExpression,
    DropTypeExpression,
    TableConstraint,
    TableConstraintType,
)
from rhosocial.activerecord.backend.expression.types import IntegerType, VarCharType
from rhosocial.activerecord.backend.impl.dummy.expression import _DummyTypeAlterAction
from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.type import (
    SQLServerAliasTypeDefinition,
    SQLServerClrTypeDefinition,
    SQLServerDropTypeExpression,
    SQLServerRenameTypeExpression,
    SQLServerTableTypeDefinition,
)
from rhosocial.activerecord.backend.impl.sqlserver.expression.index import (
    SQLServerIndexDefinition,
)
from rhosocial.activerecord.backend.impl.sqlserver.mixins import SQLServerTypeDDLMixin
from rhosocial.activerecord.backend.impl.sqlserver.protocols import (
    SQLServerUserDefinedTypeSupport,
)

SQL_SERVER_2005 = (9, 0, 0)
SQL_SERVER_2008 = (10, 0, 0)
SQL_SERVER_2012 = (11, 0, 0)
SQL_SERVER_2014 = (12, 0, 0)
SQL_SERVER_2016 = (13, 0, 0)
SQL_SERVER_2017 = (14, 0, 0)
SQL_SERVER_2019 = (15, 0, 0)
SQL_SERVER_2022 = (16, 0, 0)


def test_type_protocol_and_mro():
    dialect = SQLServerDialect(SQL_SERVER_2022)
    assert issubclass(SQLServerUserDefinedTypeSupport, UserDefinedTypeSupport)
    assert isinstance(dialect, SQLServerUserDefinedTypeSupport)
    assert isinstance(dialect, UserDefinedTypeSupport)
    assert isinstance(dialect, SQLServerTypeDDLMixin)
    assert isinstance(dialect, UserDefinedTypeMixin)
    mro = SQLServerDialect.__mro__
    assert mro.index(SQLServerTypeDDLMixin) < mro.index(UserDefinedTypeMixin)
    assert mro.index(SQLServerUserDefinedTypeSupport) < mro.index(UserDefinedTypeSupport)


def test_type_capability_version_boundaries():
    sql2005 = SQLServerDialect(SQL_SERVER_2005)
    sql2008 = SQLServerDialect(SQL_SERVER_2008)
    sql2012 = SQLServerDialect(SQL_SERVER_2012)
    sql2014 = SQLServerDialect(SQL_SERVER_2014)
    sql2016 = SQLServerDialect(SQL_SERVER_2016)

    assert sql2005.supports_type_objects() is True
    assert sql2005.supports_type_definition(SQLServerAliasTypeDefinition) is True
    assert sql2005.supports_type_definition(SQLServerTableTypeDefinition) is False
    assert sql2008.supports_type_definition(SQLServerTableTypeDefinition) is True
    assert sql2012.supports_memory_optimized_table_types() is False
    assert sql2014.supports_memory_optimized_table_types() is True
    memory_definition = SQLServerTableTypeDefinition(
        sql2012,
        columns=[ColumnDefinition(sql2012, "id", IntegerType(sql2012))],
        memory_optimized=True,
    )
    with pytest.raises(UnsupportedFeatureError):
        CreateTypeExpression(sql2012, "too_old", memory_definition).to_sql()
    assert sql2012.supports_drop_type_if_exists() is False
    assert sql2016.supports_drop_type_if_exists() is True
    assert sql2016.supports_create_type_if_not_exists() is False
    assert sql2016.supports_create_type_or_replace() is False
    assert sql2016.supports_alter_type() is False
    assert sql2016.supports_type_alter_action(_DummyTypeAlterAction) is False
    table_definition = SQLServerTableTypeDefinition(
        sql2005,
        columns=[ColumnDefinition(sql2005, "id", IntegerType(sql2005))],
    )
    with pytest.raises(UnsupportedFeatureError):
        CreateTypeExpression(sql2005, "too_old", table_definition).to_sql()


def test_clr_definition_is_platform_gated():
    sqlserver = SQLServerDialect(SQL_SERVER_2022)
    managed_instance = SQLServerDialect(
        SQL_SERVER_2022,
        deployment_target="azure_sql_managed_instance",
    )
    azure = SQLServerDialect(SQL_SERVER_2022, deployment_target="azure_sql_database")
    fabric = SQLServerDialect(SQL_SERVER_2022, deployment_target="fabric")
    definition = SQLServerClrTypeDefinition(sqlserver, "sample_assembly", "Sample.Type")

    assert sqlserver.supports_clr_type_definition() is True
    assert sqlserver.supports_type_definition(SQLServerClrTypeDefinition) is True
    assert managed_instance.supports_clr_type_definition() is True
    assert managed_instance.supports_type_definition(SQLServerClrTypeDefinition) is True
    assert azure.supports_clr_type_definition() is False
    assert azure.supports_type_definition(SQLServerClrTypeDefinition) is False
    assert fabric.supports_clr_type_definition() is False
    assert fabric.supports_type_definition(SQLServerClrTypeDefinition) is False
    with pytest.raises(UnsupportedFeatureError):
        CreateTypeExpression(azure, "clr_type", definition).to_sql()


def test_backend_passes_deployment_target_from_connection_config():
    config = SQLServerConnectionConfig(
        host="localhost",
        database="master",
        username="sa",
        password="",
        deployment_target="azure_sql_database",
    )
    backend = SQLServerBackend(connection_config=config)

    assert backend.dialect.deployment_target == "azure_sql_database"
    assert backend.dialect.supports_clr_type_definition() is False


def test_async_backend_passes_deployment_target_from_connection_config():
    pytest.importorskip("aioodbc")
    from rhosocial.activerecord.backend.impl.sqlserver.async_backend import (
        AsyncSQLServerBackend,
    )

    config = SQLServerConnectionConfig(
        host="localhost",
        database="master",
        username="sa",
        password="",
        deployment_target="fabric",
    )
    backend = AsyncSQLServerBackend(connection_config=config)

    assert backend.dialect.deployment_target == "fabric"
    assert backend.dialect.supports_clr_type_definition() is False


def test_alias_type_schema_and_identifier_escaping():
    dialect = SQLServerDialect(SQL_SERVER_2022)
    definition = SQLServerAliasTypeDefinition(
        dialect,
        VarCharType(dialect, length=50),
        nullability="NOT NULL",
    )
    expression = CreateTypeExpression(
        dialect,
        "name]x",
        definition,
        schema_name="app]schema",
    )

    assert expression.to_sql() == (
        "CREATE TYPE [app]]schema].[name]]x] FROM VARCHAR(50) NOT NULL",
        (),
    )


def test_type_name_dot_is_a_single_identifier():
    dialect = SQLServerDialect(SQL_SERVER_2022)
    definition = SQLServerAliasTypeDefinition(dialect, IntegerType(dialect))
    expression = CreateTypeExpression(
        dialect,
        "type.with.dot",
        definition,
        schema_name="app",
    )

    assert expression.to_sql() == (
        "CREATE TYPE [app].[type.with.dot] FROM INT",
        (),
    )


def test_clr_type_sql():
    dialect = SQLServerDialect(SQL_SERVER_2022)
    definition = SQLServerClrTypeDefinition(
        dialect,
        "sample_assembly",
        "Sample.Namespace.UserType",
    )
    expression = CreateTypeExpression(dialect, "clr_type", definition, schema_name="app")

    assert expression.to_sql() == (
        "CREATE TYPE [app].[clr_type] EXTERNAL NAME "
        "[sample_assembly].[Sample.Namespace.UserType]",
        (),
    )


def test_table_type_columns_constraints_indexes_and_memory():
    dialect = SQLServerDialect(SQL_SERVER_2014)
    columns = [
        ColumnDefinition(
            dialect,
            "id",
            IntegerType(dialect),
            constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)],
        ),
        ColumnDefinition(dialect, "name", VarCharType(dialect, length=100)),
    ]
    constraints = [
        TableConstraint(
            dialect,
            TableConstraintType.PRIMARY_KEY,
            columns=["id"],
        )
    ]
    indexes = [SQLServerIndexDefinition(dialect, "ix_name", ["name"], type="NONCLUSTERED")]
    definition = SQLServerTableTypeDefinition(
        dialect,
        columns=columns,
        constraints=constraints,
        indexes=indexes,
        memory_optimized=True,
    )
    expression = CreateTypeExpression(dialect, "inventory_type", definition)
    sql, params = expression.to_sql()

    assert sql.startswith("CREATE TYPE [inventory_type] AS TABLE (")
    assert "[id] INT NOT NULL" in sql
    assert "PRIMARY KEY NONCLUSTERED ([id])" in sql
    assert "INDEX [ix_name] NONCLUSTERED ([name])" in sql
    assert sql.endswith("WITH (MEMORY_OPTIMIZED = ON)")
    assert params == ()


def test_memory_table_type_requires_an_index():
    dialect = SQLServerDialect(SQL_SERVER_2014)
    definition = SQLServerTableTypeDefinition(
        dialect,
        columns=[ColumnDefinition(dialect, "id", IntegerType(dialect))],
        memory_optimized=True,
    )

    with pytest.raises(ValueError, match="at least one index"):
        CreateTypeExpression(dialect, "missing_index_type", definition).to_sql()


def test_non_memory_table_type_keeps_regular_constraints():
    dialect = SQLServerDialect(SQL_SERVER_2014)
    definition = SQLServerTableTypeDefinition(
        dialect,
        columns=[
            ColumnDefinition(dialect, "id", IntegerType(dialect)),
            ColumnDefinition(dialect, "name", VarCharType(dialect, length=20)),
        ],
        constraints=[
            TableConstraint(
                dialect,
                TableConstraintType.PRIMARY_KEY,
                columns=["id"],
            ),
            TableConstraint(
                dialect,
                TableConstraintType.UNIQUE,
                columns=["name"],
            ),
        ],
    )

    sql, params = CreateTypeExpression(dialect, "regular_type", definition).to_sql()
    assert "PRIMARY KEY ([id])" in sql
    assert "UNIQUE ([name])" in sql
    assert "MEMORY_OPTIMIZED" not in sql
    assert params == ()


def test_memory_table_type_column_key_constraints_use_nonclustered():
    dialect = SQLServerDialect(SQL_SERVER_2014)
    definition = SQLServerTableTypeDefinition(
        dialect,
        columns=[
            ColumnDefinition(
                dialect,
                "id",
                IntegerType(dialect),
                constraints=[
                    ColumnConstraint(dialect, ColumnConstraintType.PRIMARY_KEY),
                ],
            ),
            ColumnDefinition(
                dialect,
                "code",
                VarCharType(dialect, length=20),
                constraints=[ColumnConstraint(dialect, ColumnConstraintType.UNIQUE)],
            ),
        ],
        memory_optimized=True,
    )

    sql, params = CreateTypeExpression(dialect, "column_keys_type", definition).to_sql()
    assert "PRIMARY KEY NONCLUSTERED" in sql
    assert "UNIQUE NONCLUSTERED" in sql
    assert params == ()


def test_memory_table_type_rejects_unsupported_constraints():
    dialect = SQLServerDialect(SQL_SERVER_2014)
    check = RawSQLPredicate(dialect, "1 = 1")
    definitions = [
        SQLServerTableTypeDefinition(
            dialect,
            columns=[
                ColumnDefinition(
                    dialect,
                    "id",
                    IntegerType(dialect),
                    constraints=[
                        ColumnConstraint(
                            dialect,
                            ColumnConstraintType.CHECK,
                            check_condition=check,
                        )
                    ],
                )
            ],
            indexes=[SQLServerIndexDefinition(dialect, "ix_id", ["id"])],
            memory_optimized=True,
        ),
        SQLServerTableTypeDefinition(
            dialect,
            columns=[ColumnDefinition(dialect, "id", IntegerType(dialect))],
            constraints=[
                TableConstraint(
                    dialect,
                    TableConstraintType.CHECK,
                    check_condition=check,
                )
            ],
            indexes=[SQLServerIndexDefinition(dialect, "ix_id", ["id"])],
            memory_optimized=True,
        ),
        SQLServerTableTypeDefinition(
            dialect,
            columns=[ColumnDefinition(dialect, "id", IntegerType(dialect))],
            constraints=[
                TableConstraint(
                    dialect,
                    TableConstraintType.FOREIGN_KEY,
                    columns=["id"],
                    foreign_key_table="other",
                    foreign_key_columns=["id"],
                )
            ],
            indexes=[SQLServerIndexDefinition(dialect, "ix_id", ["id"])],
            memory_optimized=True,
        ),
    ]

    for definition in definitions:
        with pytest.raises(UnsupportedFeatureError):
            CreateTypeExpression(dialect, "invalid_memory_type", definition).to_sql()


def test_memory_table_type_default_is_supported_from_2014():
    dialect = SQLServerDialect(SQL_SERVER_2014)
    definition = SQLServerTableTypeDefinition(
        dialect,
        columns=[
            ColumnDefinition(
                dialect,
                "id",
                IntegerType(dialect),
                constraints=[
                    ColumnConstraint(
                        dialect,
                        ColumnConstraintType.DEFAULT,
                        default_value=0,
                    )
                ],
            )
        ],
        indexes=[SQLServerIndexDefinition(dialect, "ix_id", ["id"])],
        memory_optimized=True,
    )

    sql, params = CreateTypeExpression(dialect, "default_type", definition).to_sql()
    assert "DEFAULT 0" in sql
    assert params == ()


def test_memory_table_type_check_and_unique_version_gates():
    sql2014 = SQLServerDialect(SQL_SERVER_2014)
    check_2014 = SQLServerTableTypeDefinition(
        sql2014,
        columns=[
            ColumnDefinition(
                sql2014,
                "id",
                IntegerType(sql2014),
                constraints=[
                    ColumnConstraint(
                        sql2014,
                        ColumnConstraintType.CHECK,
                        check_condition=RawSQLPredicate(sql2014, "1 = 1"),
                    )
                ],
            )
        ],
        indexes=[SQLServerIndexDefinition(sql2014, "ix_id", ["id"])],
        memory_optimized=True,
    )
    with pytest.raises(UnsupportedFeatureError, match="2016\\+"):
        CreateTypeExpression(sql2014, "check_2014", check_2014).to_sql()

    unique_2014 = SQLServerTableTypeDefinition(
        sql2014,
        columns=[
            ColumnDefinition(
                sql2014,
                "code",
                IntegerType(sql2014),
                constraints=[
                    ColumnConstraint(sql2014, ColumnConstraintType.UNIQUE),
                ],
            )
        ],
        indexes=[SQLServerIndexDefinition(sql2014, "ix_code", ["code"])],
        memory_optimized=True,
    )
    with pytest.raises(UnsupportedFeatureError, match="2016\\+"):
        CreateTypeExpression(sql2014, "unique_2014", unique_2014).to_sql()

    sql2016 = SQLServerDialect(SQL_SERVER_2016)
    allowed = SQLServerTableTypeDefinition(
        sql2016,
        columns=[
            ColumnDefinition(
                sql2016,
                "id",
                IntegerType(sql2016),
                constraints=[
                    ColumnConstraint(
                        sql2016,
                        ColumnConstraintType.CHECK,
                        check_condition=RawSQLPredicate(sql2016, "1 = 1"),
                    )
                ],
            ),
            ColumnDefinition(
                sql2016,
                "code",
                IntegerType(sql2016),
                constraints=[
                    ColumnConstraint(sql2016, ColumnConstraintType.UNIQUE),
                ],
            ),
        ],
        indexes=[SQLServerIndexDefinition(sql2016, "ix_id", ["id"])],
        memory_optimized=True,
    )
    sql, params = CreateTypeExpression(sql2016, "keys_2016", allowed).to_sql()
    assert "CHECK (1 = 1)" in sql
    assert "UNIQUE NONCLUSTERED" in sql
    assert params == ()


def _memory_type_with_indexes(dialect, count):
    columns = [
        ColumnDefinition(dialect, f"column_{index}", IntegerType(dialect))
        for index in range(count)
    ]
    indexes = [
        SQLServerIndexDefinition(
            dialect,
            f"ix_{index}",
            [f"column_{index}"],
            type="NONCLUSTERED",
        )
        for index in range(count)
    ]
    return SQLServerTableTypeDefinition(
        dialect,
        columns=columns,
        indexes=indexes,
        memory_optimized=True,
    )


@pytest.mark.parametrize("version", [SQL_SERVER_2014, SQL_SERVER_2016])
def test_memory_table_type_index_limit_before_2017(version):
    dialect = SQLServerDialect(version)
    definition = _memory_type_with_indexes(dialect, 9)

    with pytest.raises(UnsupportedFeatureError, match="8 indexes"):
        CreateTypeExpression(dialect, "too_many_indexes", definition).to_sql()


def test_memory_table_type_index_limit_removed_in_2017():
    dialect = SQLServerDialect(SQL_SERVER_2017)
    definition = _memory_type_with_indexes(dialect, 9)

    sql, params = CreateTypeExpression(dialect, "many_indexes", definition).to_sql()
    assert sql.count("INDEX ") == 9
    assert params == ()


@pytest.mark.parametrize("version", [SQL_SERVER_2014, SQL_SERVER_2016, SQL_SERVER_2017])
def test_memory_table_type_include_requires_2019(version):
    dialect = SQLServerDialect(version)
    definition = SQLServerTableTypeDefinition(
        dialect,
        columns=[
            ColumnDefinition(dialect, "id", IntegerType(dialect)),
            ColumnDefinition(dialect, "payload", IntegerType(dialect)),
        ],
        indexes=[
            SQLServerIndexDefinition(
                dialect,
                "ix_id",
                ["id"],
                include_columns=["payload"],
            )
        ],
        memory_optimized=True,
    )

    with pytest.raises(UnsupportedFeatureError, match="2019\\+"):
        CreateTypeExpression(dialect, "include_type", definition).to_sql()


def test_memory_table_type_include_is_supported_from_2019():
    dialect = SQLServerDialect(SQL_SERVER_2019)
    definition = SQLServerTableTypeDefinition(
        dialect,
        columns=[
            ColumnDefinition(dialect, "id", IntegerType(dialect)),
            ColumnDefinition(dialect, "payload", IntegerType(dialect)),
        ],
        indexes=[
            SQLServerIndexDefinition(
                dialect,
                "ix_id",
                ["id"],
                include_columns=["payload"],
            )
        ],
        memory_optimized=True,
    )

    sql, params = CreateTypeExpression(dialect, "include_type", definition).to_sql()
    assert "INCLUDE ([payload])" in sql
    assert params == ()


def test_table_type_hash_index_sql():
    dialect = SQLServerDialect(SQL_SERVER_2014)
    definition = SQLServerTableTypeDefinition(
        dialect,
        columns=[ColumnDefinition(dialect, "id", IntegerType(dialect))],
        indexes=[
            SQLServerIndexDefinition(
                dialect,
                "ix_id",
                ["id"],
                hash_index=True,
                bucket_count=1024,
            )
        ],
        memory_optimized=True,
    )
    sql, params = CreateTypeExpression(dialect, "hash_type", definition).to_sql()
    assert "NONCLUSTERED HASH ([id]) WITH (BUCKET_COUNT = 1024)" in sql
    assert params == ()


def test_create_and_drop_type_fail_fast_options():
    dialect = SQLServerDialect(SQL_SERVER_2022)
    definition = SQLServerAliasTypeDefinition(dialect, IntegerType(dialect))

    with pytest.raises(UnsupportedFeatureError):
        CreateTypeExpression(dialect, "status", definition, if_not_exists=True).to_sql()
    with pytest.raises(UnsupportedFeatureError):
        CreateTypeExpression(dialect, "status", definition, or_replace=True).to_sql()
    with pytest.raises(ValueError):
        SQLServerDropTypeExpression(dialect, "status", cascade=True, restrict=True)
    with pytest.raises(UnsupportedFeatureError):
        SQLServerDropTypeExpression(dialect, "status", cascade=True).to_sql()
    with pytest.raises(UnsupportedFeatureError):
        SQLServerDropTypeExpression(dialect, "status", restrict=True).to_sql()

    pre_2016 = SQLServerDialect(SQL_SERVER_2012)
    with pytest.raises(UnsupportedFeatureError):
        DropTypeExpression(pre_2016, "status", schema_name="app", if_exists=True).to_sql()
    assert DropTypeExpression(
        dialect,
        "status",
        schema_name="app",
        if_exists=True,
    ).to_sql() == ("DROP TYPE IF EXISTS [app].[status]", ())


def test_alter_type_is_explicitly_unsupported():
    dialect = SQLServerDialect(SQL_SERVER_2022)
    action = _DummyTypeAlterAction(dialect, "renamed")
    expression = AlterTypeExpression(dialect, "status", [action])

    with pytest.raises(UnsupportedFeatureError, match="ALTER TYPE"):
        expression.to_sql()


def test_rename_type_uses_sp_rename():
    dialect = SQLServerDialect(SQL_SERVER_2022)
    expression = SQLServerRenameTypeExpression(
        dialect,
        "old]name",
        "new]name",
        schema_name="app]schema",
    )

    assert expression.to_sql() == (
        "EXECUTE sp_rename N'[app]]schema].[old]]name]', "
        "N'new]name', N'USERDATATYPE'",
        (),
    )


def test_type_expressions_are_explicitly_registered():
    dialect = SQLServerDialect(SQL_SERVER_2022)
    expressions = (
        SQLServerAliasTypeDefinition(dialect, IntegerType(dialect)),
        SQLServerClrTypeDefinition(dialect, "assembly", "Class"),
        SQLServerTableTypeDefinition(
            dialect,
            columns=[ColumnDefinition(dialect, "id", IntegerType(dialect))],
        ),
        SQLServerDropTypeExpression(dialect, "type_name"),
        SQLServerRenameTypeExpression(dialect, "old_name", "new_name"),
    )
    for expression in expressions:
        fqn = f"{type(expression).__module__}.{type(expression).__name__}"
        assert ExpressionRegistry.lookup(fqn) is type(expression)
        for encoder, decoder in (
            (serialize, deserialize),
            (serialize_json, deserialize_json),
            (serialize_xml, deserialize_xml),
        ):
            restored = decoder(encoder(expression), dialect)
            assert type(restored) is type(expression)
            assert encoder(restored) == encoder(expression)


def test_table_type_rejects_foreign_key_constraint():
    dialect = SQLServerDialect(SQL_SERVER_2022)
    definition = SQLServerTableTypeDefinition(
        dialect,
        columns=[ColumnDefinition(dialect, "id", IntegerType(dialect))],
        constraints=[
            TableConstraint(
                dialect,
                TableConstraintType.FOREIGN_KEY,
                columns=["id"],
                foreign_key_table="other",
                foreign_key_columns=["id"],
            )
        ],
    )
    with pytest.raises(UnsupportedFeatureError):
        CreateTypeExpression(dialect, "invalid_type", definition).to_sql()
