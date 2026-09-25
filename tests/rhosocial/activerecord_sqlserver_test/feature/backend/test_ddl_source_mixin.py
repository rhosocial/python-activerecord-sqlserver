# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_ddl_source_mixin.py

try:
    from typing import Annotated, ClassVar, Optional
except ImportError:
    from typing_extensions import Annotated, ClassVar, Optional

import pytest

from rhosocial.activerecord.backend.expression import ColumnDefinition
from rhosocial.activerecord.backend.expression.core import Column, Literal
from rhosocial.activerecord.backend.expression.statements import (
    ColumnConstraintType,
    GeneratedColumnExpression,
    GeneratedColumnType,
    IndexDefinition,
    StorageOptionsExpression,
    TableConstraint,
    TableConstraintType,
)
from rhosocial.activerecord.backend.expression.statements.ddl_partition import (
    PartitionClause,
    PartitionStrategy,
)
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression.column import (
    SQLServerColumnOptions,
)
from rhosocial.activerecord.backend.impl.sqlserver.expression.table_options import (
    SQLServerCreateTableOptions,
)
from rhosocial.activerecord.backend.impl.sqlserver.expression.types import (
    SQLServerNCharType,
    SQLServerNVarCharType,
)
from rhosocial.activerecord.base import (
    CharacterSetAttribute,
    CollationAttribute,
    DDLAnnotation,
    DDLAnnotationHandler,
    DDLSourceMixin,
    DDLSource,
    IdentityAttribute,
    UseColumn,
    UseColumnAttributes,
    UseComment,
    UseConstraint,
    UseGeneratedColumn,
    UseIndex,
    UseSqlType,
)
from rhosocial.activerecord.model import ActiveRecord, AsyncActiveRecord


class UseColumnOptions(DDLAnnotation):
    def __init__(self, *options):
        self.options = options


class ColumnOptionsHandler(DDLAnnotationHandler):
    annotation_types = (UseColumnOptions,)

    @classmethod
    def apply(cls, new_class, field_name, annotation, metadata):
        metadata.add_column_options(*annotation.options)


def check_condition(dialect):
    return Column(dialect, "value_col") == "active"


def index_condition(dialect):
    return Column(dialect, "value_col") == "active"


PRIMARY_TYPE = SQLServerNVarCharType(length=64)
FALLBACK_TYPE = SQLServerNCharType(length=8)
TYPE_MARKER = UseSqlType(PRIMARY_TYPE, FALLBACK_TYPE)
DEFAULT_VALUE = Literal(None, "model-default", inline_literals=True)
DEFAULT_CONSTRAINT = UseConstraint(
    ColumnConstraintType.DEFAULT,
    name="df_value",
    default_value=DEFAULT_VALUE,
)
CHECK_CONSTRAINT = UseConstraint(
    ColumnConstraintType.CHECK,
    name="ck_value",
    check_condition=check_condition,
)
INCLUDE_COLUMNS = ["nullable_col"]
INDEX_MARKER = UseIndex(
    "ix_value",
    unique=True,
    type="BTREE",
    partial_condition=index_condition,
    include_columns=INCLUDE_COLUMNS,
    if_not_exists=True,
    tablespace="index_space",
    if_exists=True,
    concurrent=True,
)
SECOND_INDEX_MARKER = UseIndex("ix_value_suffix", type="BTREE")
IDENTITY_ATTRIBUTE = IdentityAttribute(generation="ALWAYS", start=5, increment=2)
COLLATION_ATTRIBUTE = CollationAttribute(name="NOCASE")
CHARACTER_SET_ATTRIBUTE = CharacterSetAttribute(name="utf8mb4")
ATTRIBUTES_MARKER = UseColumnAttributes(IDENTITY_ATTRIBUTE, COLLATION_ATTRIBUTE)
SECOND_ATTRIBUTES_MARKER = UseColumnAttributes(CHARACTER_SET_ATTRIBUTE)
COMMENT_MARKER = UseComment("value comment")
GENERATED_EXPRESSION = GeneratedColumnExpression(
    None,
    Column(None, "value_col"),
    GeneratedColumnType.STORED,
)
GENERATED_MARKER = UseGeneratedColumn(GENERATED_EXPRESSION)
VALUE_OPTIONS = (
    SQLServerColumnOptions(sparse=True, rowguidcol=True),
    SQLServerColumnOptions(sparse=False),
)
VALUE_OPTIONS_MARKER = UseColumnOptions(*VALUE_OPTIONS)
SINGLE_OPTION = SQLServerColumnOptions(rowguidcol=True)
SINGLE_OPTION_MARKER = UseColumnOptions(SINGLE_OPTION)
NULL_CONSTRAINT = UseConstraint(ColumnConstraintType.NULL)
PK_TYPE = Annotated[int, UseColumn("id")]
NULLABLE_TYPE = Annotated[Optional[str], NULL_CONSTRAINT]
VALUE_TYPE = Annotated[
    str,
    UseColumn("value_col"),
    TYPE_MARKER,
    DEFAULT_CONSTRAINT,
    CHECK_CONSTRAINT,
    INDEX_MARKER,
    SECOND_INDEX_MARKER,
    ATTRIBUTES_MARKER,
    SECOND_ATTRIBUTES_MARKER,
    COMMENT_MARKER,
    GENERATED_MARKER,
    VALUE_OPTIONS_MARKER,
]

TABLE_INDEXES = [
    IndexDefinition(None, name="ix_table_first", columns=["value_col"], unique=True),
    IndexDefinition(None, name="ix_table_second", columns=["id"]),
]
TABLE_CONSTRAINTS = [
    TableConstraint(
        None,
        TableConstraintType.UNIQUE,
        name="uq_value",
        columns=["value_col"],
    ),
    TableConstraint(
        None,
        TableConstraintType.CHECK,
        name="ck_value_table",
        columns=["value_col"],
        check_condition=check_condition,
    ),
]
TABLE_OPTIONS = SQLServerCreateTableOptions(
    None,
    memory_optimized=True,
    durability="SCHEMA_AND_DATA",
)
STORAGE_OPTIONS = StorageOptionsExpression(None, {"fillfactor": 80})
PARTITION_KEY = Column(None, "id")
TABLE_PARTITION = PartitionClause(
    None,
    PartitionStrategy.RANGE,
    [PARTITION_KEY],
)
INHERITED_TABLES = ["parent_a", "parent_b"]
TABLE_SPACE = "ts_data"
BATCH_METHODS = (
    "columns_name",
    "columns_type",
    "columns_constraints",
    "columns_attributes",
    "columns_indexes",
    "columns_comment",
    "columns_generated",
    "columns_options",
)


class DeclarationMixin:
    __table_indexes__ = TABLE_INDEXES
    __table_constraints__ = TABLE_CONSTRAINTS
    _feature_handlers: ClassVar[list] = [DDLAnnotationHandler, ColumnOptionsHandler]

    @classmethod
    def table_options(cls):
        return TABLE_OPTIONS

    @classmethod
    def table_storage_options(cls):
        return STORAGE_OPTIONS

    @classmethod
    def table_partition(cls):
        return TABLE_PARTITION

    @classmethod
    def table_inherits(cls):
        return INHERITED_TABLES

    @classmethod
    def table_tablespace(cls):
        return TABLE_SPACE


class SyncModel(DeclarationMixin, ActiveRecord):
    __table_name__ = "ddl_source_sync"
    __primary_key__ = "id"

    pk_field: PK_TYPE
    value_field: VALUE_TYPE = DEFAULT_VALUE
    nullable_field: NULLABLE_TYPE = None
    optional_field: Annotated[Optional[str], SINGLE_OPTION_MARKER] = None


class AsyncModel(DeclarationMixin, AsyncActiveRecord):
    __table_name__ = "ddl_source_async"
    __primary_key__ = "id"

    pk_field: PK_TYPE
    value_field: VALUE_TYPE = DEFAULT_VALUE
    nullable_field: NULLABLE_TYPE = None
    optional_field: Annotated[Optional[str], SINGLE_OPTION_MARKER] = None


class CompositeModel(DeclarationMixin, ActiveRecord):
    __table_name__ = "ddl_source_composite"
    __primary_key__ = ("left_col", "right_col")

    left_field: Annotated[int, UseColumn("left_col")]
    right_field: Annotated[int, UseColumn("right_col")]
    value_field: str


class AsyncCompositeModel(DeclarationMixin, AsyncActiveRecord):
    __table_name__ = "ddl_source_async_composite"
    __primary_key__ = ("left_col", "right_col")

    left_field: Annotated[int, UseColumn("left_col")]
    right_field: Annotated[int, UseColumn("right_col")]
    value_field: str


class PlainModel(ActiveRecord):
    __table_name__ = "ddl_source_plain"

    id: int
    optional: Optional[str] = None


class AsyncPlainModel(AsyncActiveRecord):
    __table_name__ = "ddl_source_async_plain"

    id: int
    optional: Optional[str] = None


def _constraint_signature(model, field):
    return [
        (
            constraint.constraint_type,
            constraint.name,
            constraint.default_value,
            constraint.check_condition,
        )
        for constraint in model.column_constraints(field)
    ]


def _index_signature(index):
    return (
        index.name,
        index.columns,
        index.unique,
        index.type,
        index.partial_condition,
        index.include_columns,
        index.if_not_exists,
        index.tablespace,
        index.if_exists,
        index.concurrent,
    )


@pytest.mark.parametrize("model", [SyncModel, AsyncModel], ids=("sync", "async"))
def test_field_declarations_are_collected_in_declaration_order(model):
    assert issubclass(model, DDLSourceMixin)
    assert isinstance(model, DDLSource)
    assert ColumnOptionsHandler in model.get_feature_handlers()
    assert model.ddl_field_names() == (
        "pk_field",
        "value_field",
        "nullable_field",
        "optional_field",
    )
    assert model.columns_name() == {
        "pk_field": "id",
        "value_field": "value_col",
        "nullable_field": "nullable_field",
        "optional_field": "optional_field",
    }
    assert model.column_name("pk_field") == "id"
    assert model.column_name("value_field") == "value_col"
    assert model.column_type("value_field") is TYPE_MARKER
    assert model.column_type("value_field").data_types == (PRIMARY_TYPE, FALLBACK_TYPE)
    assert model.column_type("value_field").data_types[0] is PRIMARY_TYPE
    assert model.column_type("value_field").data_types[1] is FALLBACK_TYPE
    assert isinstance(model.column_type("value_field").data_type, SQLServerNVarCharType)
    assert model.column_type("value_field").data_type.length == 64

    value_constraints = model.column_constraints("value_field")
    assert value_constraints[0] is DEFAULT_CONSTRAINT.constraint
    assert value_constraints[1] is CHECK_CONSTRAINT.constraint
    assert value_constraints[2].constraint_type is ColumnConstraintType.NOT_NULL
    assert value_constraints[0].default_value is DEFAULT_VALUE
    assert value_constraints[1].check_condition is check_condition
    assert model.column_constraints("nullable_field") == [NULL_CONSTRAINT.constraint]
    assert model.column_constraints("optional_field") == []

    attributes = model.column_attributes("value_field")
    assert attributes[0] is IDENTITY_ATTRIBUTE
    assert attributes[1] is COLLATION_ATTRIBUTE
    assert attributes[2] is CHARACTER_SET_ATTRIBUTE

    indexes = model.column_indexes("value_field")
    assert [index.name for index in indexes] == ["ix_value", "ix_value_suffix"]
    assert all(index.columns == ["value_col"] for index in indexes)
    assert indexes[0].unique is True
    assert indexes[0].type == "BTREE"
    assert indexes[0].partial_condition is index_condition
    assert indexes[0].include_columns is INCLUDE_COLUMNS
    assert indexes[0].if_not_exists is True
    assert indexes[0].tablespace == "index_space"
    assert indexes[0].if_exists is True
    assert indexes[0].concurrent is True

    assert model.column_comment("value_field") == "value comment"
    assert model.generated_column("value_field") is GENERATED_EXPRESSION
    options = model.column_options("value_field")
    assert options[0] is VALUE_OPTIONS[0]
    assert options[1] is VALUE_OPTIONS[1]
    assert options[0].sparse is True
    assert options[0].rowguidcol is True
    assert options[1].sparse is False
    assert model.column_options("optional_field") is SINGLE_OPTION
    assert model.field_python_type("value_field") is str
    assert model.field_is_optional("value_field") is False
    assert model.field_is_optional("optional_field") is True


def test_collected_backend_data_type_renders_with_dialect():
    dialect = SQLServerDialect((16, 0, 0))
    data_type = SyncModel.column_type("value_field").data_types[0]
    assert isinstance(data_type, SQLServerNVarCharType)
    data_type.dialect = dialect
    try:
        rendered = ColumnDefinition(dialect, "value_col", data_type).to_sql()
    finally:
        data_type.dialect = None
    assert rendered == ("[value_col] NVARCHAR(64)", ())


@pytest.mark.parametrize("model", [SyncModel, AsyncModel], ids=("sync", "async"))
def test_table_declarations_are_returned_unchanged(model):
    assert model.__table_indexes__ is TABLE_INDEXES
    assert model.__table_constraints__ is TABLE_CONSTRAINTS
    indexes = model.table_indexes()
    assert indexes is not TABLE_INDEXES
    assert indexes[0] is TABLE_INDEXES[0]
    assert indexes[1] is TABLE_INDEXES[1]
    constraints = model.table_constraints()
    assert constraints is not TABLE_CONSTRAINTS
    assert constraints[0] is TABLE_CONSTRAINTS[0]
    assert constraints[1] is TABLE_CONSTRAINTS[1]
    assert model.table_options() is TABLE_OPTIONS
    assert model.table_options().memory_optimized is True
    assert model.table_options().durability == "SCHEMA_AND_DATA"
    assert model.table_storage_options() is STORAGE_OPTIONS
    assert model.table_partition() is TABLE_PARTITION
    assert model.table_partition().method == PartitionStrategy.RANGE.value
    assert model.table_partition().keys[0] is PARTITION_KEY
    assert model.table_inherits() is INHERITED_TABLES
    assert model.table_inherits() == ["parent_a", "parent_b"]
    assert model.table_tablespace() == TABLE_SPACE
    assert model.create_table_statement_classes() is None


@pytest.mark.parametrize("model", [SyncModel, AsyncModel], ids=("sync", "async"))
def test_single_primary_key_is_composed_on_the_physical_column(model):
    assert model.primary_key_columns() == ("id",)
    assert model.primary_key_field() == "pk_field"
    assert model.column_name("pk_field") == "id"
    constraints = model.column_constraints("pk_field")
    assert [item.constraint_type for item in constraints] == [
        ColumnConstraintType.PRIMARY_KEY,
        ColumnConstraintType.NOT_NULL,
    ]
    assert all(
        item.constraint_type is not TableConstraintType.PRIMARY_KEY
        for item in model.table_constraints()
    )


@pytest.mark.parametrize(
    "model", [CompositeModel, AsyncCompositeModel], ids=("sync", "async")
)
def test_composite_primary_key_is_composed_as_a_table_constraint(model):
    assert model.primary_key_columns() == ("left_col", "right_col")
    assert model.primary_key_field() == ("left_field", "right_field")
    assert model.column_name("left_field") == "left_col"
    assert model.column_name("right_field") == "right_col"
    assert [item.constraint_type for item in model.column_constraints("left_field")] == [
        ColumnConstraintType.NOT_NULL
    ]
    assert [item.constraint_type for item in model.column_constraints("right_field")] == [
        ColumnConstraintType.NOT_NULL
    ]
    constraints = model.table_constraints()
    assert constraints[0] is TABLE_CONSTRAINTS[0]
    assert constraints[1] is TABLE_CONSTRAINTS[1]
    assert constraints[2].constraint_type is TableConstraintType.PRIMARY_KEY
    assert constraints[2].columns == ["left_col", "right_col"]


@pytest.mark.parametrize("model", [PlainModel, AsyncPlainModel], ids=("sync", "async"))
def test_default_declarations_and_batch_interfaces(model):
    assert model.ddl_field_names() == ("id", "optional")
    assert model.columns_name() == {"id": "id", "optional": "optional"}
    assert model.column_type("id") is None
    assert model.column_comment("id") is None
    assert model.generated_column("id") is None
    assert model.column_options("id") is None
    assert model.column_attributes("id") == []
    assert model.column_indexes("id") == []
    assert [item.constraint_type for item in model.column_constraints("id")] == [
        ColumnConstraintType.PRIMARY_KEY,
        ColumnConstraintType.NOT_NULL,
    ]
    assert model.column_constraints("optional") == []
    assert model.columns_type() == {"id": None, "optional": None}
    assert model.columns_constraints()["optional"] == []
    assert model.columns_attributes() == {"id": [], "optional": []}
    assert model.columns_indexes() == {"id": [], "optional": []}
    assert model.columns_comment() == {"id": None, "optional": None}
    assert model.columns_generated() == {"id": None, "optional": None}
    assert model.columns_options() == {"id": None, "optional": None}
    assert model.table_options() is None
    assert model.table_storage_options() is None
    assert model.table_partition() is None
    assert model.table_inherits() is None
    assert model.table_tablespace() is None
    assert model.table_indexes() == []
    assert model.table_constraints() == []
    assert model.create_table_statement_classes() is None


@pytest.mark.parametrize("model", [SyncModel, AsyncModel], ids=("sync", "async"))
def test_batch_interfaces_preserve_requested_field_order(model):
    for method_name in BATCH_METHODS:
        method = getattr(model, method_name)
        assert tuple(method()) == model.ddl_field_names()

    fields = ["value_field", "pk_field", "optional_field"]
    names = model.columns_name(fields)
    types = model.columns_type(fields)
    constraints = model.columns_constraints(fields)
    attributes = model.columns_attributes(fields)
    indexes = model.columns_indexes(fields)
    comments = model.columns_comment(fields)
    generated = model.columns_generated(fields)
    options = model.columns_options(fields)

    assert list(names) == fields
    assert list(types) == fields
    assert list(constraints) == fields
    assert list(attributes) == fields
    assert list(indexes) == fields
    assert list(comments) == fields
    assert list(generated) == fields
    assert list(options) == fields
    assert names == {
        "value_field": "value_col",
        "pk_field": "id",
        "optional_field": "optional_field",
    }
    assert types["value_field"] is TYPE_MARKER
    assert constraints["value_field"][0] is DEFAULT_CONSTRAINT.constraint
    assert attributes["value_field"][0] is IDENTITY_ATTRIBUTE
    assert indexes["value_field"][0].columns == ["value_col"]
    assert comments["value_field"] == "value comment"
    assert generated["value_field"] is GENERATED_EXPRESSION
    assert options["value_field"][0] is VALUE_OPTIONS[0]
    assert options["optional_field"] is SINGLE_OPTION


def test_sync_and_async_ddl_sources_collect_the_same_declarations():
    assert SyncModel.columns_name() == AsyncModel.columns_name()
    assert SyncModel.columns_type() == AsyncModel.columns_type()
    assert SyncModel.columns_attributes() == AsyncModel.columns_attributes()
    assert SyncModel.columns_comment() == AsyncModel.columns_comment()
    assert SyncModel.columns_generated() == AsyncModel.columns_generated()
    assert SyncModel.columns_options() == AsyncModel.columns_options()
    for field in ("pk_field", "value_field", "nullable_field", "optional_field"):
        assert _constraint_signature(SyncModel, field) == _constraint_signature(
            AsyncModel, field
        )
        sync_indexes = SyncModel.column_indexes(field)
        async_indexes = AsyncModel.column_indexes(field)
        assert len(sync_indexes) == len(async_indexes)
        for sync_index, async_index in zip(sync_indexes, async_indexes):
            assert _index_signature(sync_index) == _index_signature(async_index)
    assert SyncModel.table_indexes()[0] is AsyncModel.table_indexes()[0]
    assert SyncModel.table_indexes()[1] is AsyncModel.table_indexes()[1]
    assert SyncModel.table_constraints()[0] is AsyncModel.table_constraints()[0]
    assert SyncModel.table_constraints()[1] is AsyncModel.table_constraints()[1]
    assert SyncModel.table_options() is AsyncModel.table_options()
    assert SyncModel.table_storage_options() is AsyncModel.table_storage_options()
    assert SyncModel.table_partition() is AsyncModel.table_partition()
    assert SyncModel.table_inherits() is AsyncModel.table_inherits()
    assert SyncModel.table_tablespace() == AsyncModel.table_tablespace()
    assert _constraint_signature(CompositeModel, "left_field") == _constraint_signature(
        AsyncCompositeModel, "left_field"
    )
    assert _constraint_signature(CompositeModel, "right_field") == _constraint_signature(
        AsyncCompositeModel, "right_field"
    )
    assert [
        (item.constraint_type, item.columns) for item in CompositeModel.table_constraints()
    ] == [
        (item.constraint_type, item.columns)
        for item in AsyncCompositeModel.table_constraints()
    ]
