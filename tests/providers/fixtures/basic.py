# tests/providers/fixtures/basic.py
"""DDL expressions for the ``feature/basic`` table group (SQL Server).

Each factory builds a :class:`CreateTableExpression` whose generated T-SQL
DDL is semantically equivalent to the reference ``.sql`` schema files under
``tests/rhosocial/activerecord_sqlserver_test/feature/basic/schema/``.
"""

from typing import Callable, Dict

from rhosocial.activerecord.backend.expression import (
    CreateTableExpression,
)
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    ColumnConstraint,
    ColumnConstraintType,
    ForeignKeyConstraint,
    IndexDefinition,
    TableConstraint,
    TableConstraintType,
    ReferentialAction,
)
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BooleanType,
    CharType,
    DateType,
    DateTimeType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    JsonType,
    SmallIntType,
    TextType,
    TimeType,
    BlobType,
    VarCharType,
)

from . import _common

_CASCADE = ReferentialAction.CASCADE


def to_sql(expr: CreateTableExpression):
    """Route a CreateTableExpression through the canonical SQL Server DDL pass-through."""
    return _common.to_sqlserver_ddl_sql(expr)


def create_users_table(dialect, table_name: str = "users") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition(dialect, "username", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.UNIQUE)]),
            ColumnDefinition(dialect, "email", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.UNIQUE)]),
            ColumnDefinition(dialect, "age", IntegerType(dialect)),
            ColumnDefinition(dialect, "balance", FloatType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0.0)]),
            ColumnDefinition(dialect, "is_active", BooleanType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=1)]),
            ColumnDefinition(dialect, "created_at", TextType(dialect)),
            ColumnDefinition(dialect, "updated_at", TextType(dialect)),
        ],
    )


def create_type_cases_table(dialect, table_name: str = "type_cases") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", CharType(dialect, length=36),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "username", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "email", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "tiny_int", SmallIntType(dialect)),
            ColumnDefinition(dialect, "small_int", SmallIntType(dialect)),
            ColumnDefinition(dialect, "big_int", BigIntType(dialect)),
            ColumnDefinition(dialect, "float_val", FloatType(dialect)),
            ColumnDefinition(dialect, "double_val", DoubleType(dialect)),
            ColumnDefinition(dialect, "decimal_val", DecimalType(dialect, precision=10, scale=6)),
            ColumnDefinition(dialect, "char_val", CharType(dialect, length=10)),
            ColumnDefinition(dialect, "varchar_val", VarCharType(dialect, length=50)),
            ColumnDefinition(dialect, "text_val", TextType(dialect)),
            ColumnDefinition(dialect, "date_val", DateType(dialect)),
            ColumnDefinition(dialect, "time_val", TimeType(dialect)),
            ColumnDefinition(dialect, "timestamp_val", DateTimeType(dialect)),
            ColumnDefinition(dialect, "blob_val", BlobType(dialect)),
            ColumnDefinition(dialect, "json_val", JsonType(dialect)),
            ColumnDefinition(dialect, "array_val", JsonType(dialect)),
            ColumnDefinition(dialect, "is_active", BooleanType(dialect)),
        ],
    )


def create_type_tests_table(dialect, table_name: str = "type_tests") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", CharType(dialect, length=36),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)]),
            ColumnDefinition(dialect, "string_field", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value="test string")]),
            ColumnDefinition(dialect, "int_field", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=42)]),
            ColumnDefinition(dialect, "float_field", FloatType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=3.14)]),
            ColumnDefinition(dialect, "decimal_field", DoubleType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=10.99)]),
            ColumnDefinition(dialect, "bool_field", BooleanType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=1)]),
            ColumnDefinition(dialect, "datetime_field", TextType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "json_field", JsonType(dialect)),
            ColumnDefinition(dialect, "nullable_field", VarCharType(dialect, length=255)),
        ],
    )


def create_validated_field_users_table(dialect, table_name: str = "validated_field_users") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition(dialect, "username", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "email", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "age", IntegerType(dialect)),
            ColumnDefinition(dialect, "balance", DecimalType(dialect, precision=10, scale=2)),
            ColumnDefinition(dialect, "credit_score", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "status", VarCharType(dialect, length=50),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value="active")]),
            ColumnDefinition(dialect, "is_active", BooleanType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=1)]),
        ],
    )


def create_validated_users_table(dialect, table_name: str = "validated_users") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition(dialect, "username", VarCharType(dialect, length=50),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "email", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "age", IntegerType(dialect)),
        ],
    )


def create_pydantic_validated_models_table(
    dialect, table_name: str = "pydantic_validated_models"
) -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition(dialect, "code", VarCharType(dialect, length=32)),
            ColumnDefinition(dialect, "quantity", IntegerType(dialect)),
            ColumnDefinition(dialect, "step_count", IntegerType(dialect)),
            ColumnDefinition(dialect, "price", DecimalType(dialect, precision=10, scale=2)),
            ColumnDefinition(dialect, "start_at", DateTimeType(dialect)),
            ColumnDefinition(dialect, "end_at", DateTimeType(dialect)),
            ColumnDefinition(dialect, "status", VarCharType(dialect, length=32)),
            ColumnDefinition(dialect, "normalized_name", VarCharType(dialect, length=50)),
            ColumnDefinition(dialect, "created_token", VarCharType(dialect, length=255)),
        ],
    )


def create_bulk_users_table(dialect, table_name: str = "bulk_users") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition(dialect, "name", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "age", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0)]),
            ColumnDefinition(dialect, "email", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.DEFAULT, default_value="")]),
        ],
    )


def create_posts_table(dialect, table_name: str = "posts") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition(dialect, "author", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "title", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "content", TextType(dialect)),
            ColumnDefinition(dialect, "published_at", DateTimeType(dialect, precision=6)),
            ColumnDefinition(dialect, "published", BooleanType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0)]),
            ColumnDefinition(dialect, "created_at", DateTimeType(dialect, precision=6)),
            ColumnDefinition(dialect, "updated_at", DateTimeType(dialect, precision=6)),
        ],
        indexes=[IndexDefinition(name="idx_author", columns=["author"])],
        table_constraints=[
            ForeignKeyConstraint(columns=["author"], foreign_key_table="users", foreign_key_columns=["id"],
                on_delete=_CASCADE),
        ],
    )


def create_comments_table(dialect, table_name: str = "comments") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition(dialect, "post_ref", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "author", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "text", TextType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "created_at", DateTimeType(dialect, precision=6),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "updated_at", DateTimeType(dialect, precision=6)),
            ColumnDefinition(dialect, "approved", BooleanType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0)]),
        ],
        indexes=[
            IndexDefinition(name="idx_post_ref", columns=["post_ref"]),
            IndexDefinition(name="idx_author", columns=["author"]),
        ],
        table_constraints=[
            ForeignKeyConstraint(columns=["post_ref"], foreign_key_table="posts", foreign_key_columns=["id"],
                on_delete=_CASCADE),
            ForeignKeyConstraint(columns=["author"], foreign_key_table="users", foreign_key_columns=["id"],
                on_delete=ReferentialAction.NO_ACTION),
        ],
    )


def create_column_mapping_items_table(
    dialect, table_name: str = "column_mapping_items"
) -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition(dialect, "name", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "item_total", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "remarks", IntegerType(dialect)),
        ],
    )


def create_mixed_annotation_items_table(
    dialect, table_name: str = "mixed_annotation_items"
) -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition(dialect, "name", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "tags", TextType(dialect)),
            ColumnDefinition(dialect, "meta", TextType(dialect)),
            ColumnDefinition(dialect, "description", TextType(dialect)),
            ColumnDefinition(dialect, "status", TextType(dialect)),
        ],
    )


def create_type_adapter_tests_table(
    dialect, table_name: str = "type_adapter_tests"
) -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=True,
        columns=[
            ColumnDefinition(dialect, "id", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition(dialect, "name", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "optional_name", VarCharType(dialect, length=255)),
            ColumnDefinition(dialect, "optional_age", IntegerType(dialect)),
            ColumnDefinition(dialect, "last_login", TextType(dialect)),
            ColumnDefinition(dialect, "is_premium", BooleanType(dialect)),
            ColumnDefinition(dialect, "unsupported_union", VarCharType(dialect, length=255)),
            ColumnDefinition(dialect, "custom_bool", VarCharType(dialect, length=3)),
            ColumnDefinition(dialect, "optional_custom_bool", VarCharType(dialect, length=3)),
        ],
    )


def create_composite_pk_order_items_table(
    dialect, table_name: str = "order_items"
) -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "order_id", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "product_id", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "quantity", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=1)]),
            ColumnDefinition(dialect, "unit_price", DecimalType(dialect, precision=10, scale=2),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
        ],
        table_constraints=[
            TableConstraint(constraint_type=TableConstraintType.PRIMARY_KEY,
                columns=["order_id", "product_id"]),
        ],
    )


def create_store_inventory_table(dialect, table_name: str = "store_inventory") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "store_id", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "product_id", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "batch_id", VarCharType(dialect, length=64),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "stock", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0)]),
        ],
        table_constraints=[
            TableConstraint(constraint_type=TableConstraintType.PRIMARY_KEY,
                columns=["store_id", "product_id", "batch_id"]),
        ],
    )


def create_orders_table(dialect, table_name: str = "orders") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition(dialect, "total", DecimalType(dialect, precision=10, scale=2),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "created_at", TextType(dialect)),
            ColumnDefinition(dialect, "updated_at", TextType(dialect)),
        ],
    )


def create_product_table(dialect, table_name: str = "product") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=True,
        columns=[
            ColumnDefinition(dialect, "id", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition(dialect, "name", TextType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "price", FloatType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition(dialect, "quantity", IntegerType(dialect),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
        ],
    )


TABLE_EXPRESSIONS: Dict[str, Callable] = {
    "users": create_users_table,
    "type_cases": create_type_cases_table,
    "type_tests": create_type_tests_table,
    "validated_field_users": create_validated_field_users_table,
    "validated_users": create_validated_users_table,
    "pydantic_validated_models": create_pydantic_validated_models_table,
    "bulk_users": create_bulk_users_table,
    "posts": create_posts_table,
    "comments": create_comments_table,
    "column_mapping_items": create_column_mapping_items_table,
    "mixed_annotation_items": create_mixed_annotation_items_table,
    "type_adapter_tests": create_type_adapter_tests_table,
    "order_items": create_composite_pk_order_items_table,
    "store_inventory": create_store_inventory_table,
    "orders": create_orders_table,
    "product": create_product_table,
}
