# tests/providers/fixtures/query.py
"""DDL expressions for the ``feature/query`` table group (SQL Server).

Each factory builds a :class:`CreateTableExpression` whose generated T-SQL
DDL is semantically equivalent to the reference ``.sql`` schema files under
``tests/rhosocial/activerecord_sqlserver_test/feature/query/schema/``.
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
    ReferentialAction,
)
from rhosocial.activerecord.backend.expression.types import (
    BooleanType,
    DateTimeType,
    DecimalType,
    DoubleType,
    IntegerType,
    JsonType,
    TextType,
    VarCharType,
)

from . import _common

_CASCADE = ReferentialAction.CASCADE


def to_sql(expr: CreateTableExpression):
    return _common.to_sqlserver_ddl_sql(expr)


def create_users_table(dialect, table_name: str = "users") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition("username", VarCharType(length=191),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.UNIQUE)]),
            ColumnDefinition("email", VarCharType(length=191),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.UNIQUE)]),
            ColumnDefinition("age", IntegerType()),
            ColumnDefinition("balance", DoubleType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0.0)]),
            ColumnDefinition("is_active", BooleanType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=1)]),
            ColumnDefinition("created_at", DateTimeType(precision=6)),
            ColumnDefinition("updated_at", DateTimeType(precision=6)),
        ],
    )


def create_posts_table(dialect, table_name: str = "posts") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition("user_id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("title", VarCharType(length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("content", TextType()),
            ColumnDefinition("status", VarCharType(length=50),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value="published")]),
            ColumnDefinition("created_at", DateTimeType(precision=6)),
            ColumnDefinition("updated_at", DateTimeType(precision=6)),
        ],
        indexes=[
            IndexDefinition(name="idx_user_id", columns=["user_id"]),
            IndexDefinition(name="idx_status", columns=["status"]),
        ],
        table_constraints=[
            ForeignKeyConstraint(columns=["user_id"], foreign_key_table="users", foreign_key_columns=["id"],
                on_delete=_CASCADE),
        ],
    )


def create_comments_table(dialect, table_name: str = "comments") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition("user_id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("post_id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("content", TextType()),
            ColumnDefinition("is_hidden", BooleanType(),
                constraints=[ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0)]),
            ColumnDefinition("created_at", DateTimeType(precision=6)),
            ColumnDefinition("updated_at", DateTimeType(precision=6)),
        ],
        indexes=[
            IndexDefinition(name="idx_user_id", columns=["user_id"]),
            IndexDefinition(name="idx_post_id", columns=["post_id"]),
        ],
        table_constraints=[
            ForeignKeyConstraint(columns=["user_id"], foreign_key_table="users", foreign_key_columns=["id"],
                on_delete=_CASCADE),
            ForeignKeyConstraint(columns=["post_id"], foreign_key_table="posts", foreign_key_columns=["id"],
                on_delete=ReferentialAction.NO_ACTION),
        ],
    )


def create_orders_table(dialect, table_name: str = "orders") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition("user_id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("order_number", VarCharType(length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("total_amount", DecimalType(precision=10, scale=2),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0.0)]),
            ColumnDefinition("status", VarCharType(length=50),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value="pending")]),
            ColumnDefinition("created_at", DateTimeType(precision=6)),
            ColumnDefinition("updated_at", DateTimeType(precision=6)),
        ],
        indexes=[IndexDefinition(name="idx_user_id", columns=["user_id"])],
        table_constraints=[
            ForeignKeyConstraint(columns=["user_id"], foreign_key_table="users", foreign_key_columns=["id"]),
        ],
    )


def create_order_items_table(dialect, table_name: str = "order_items") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition("order_id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("product_name", VarCharType(length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("quantity", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=1)]),
            ColumnDefinition("unit_price", DecimalType(precision=10, scale=2),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("subtotal", DecimalType(precision=10, scale=2),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0.0)]),
            ColumnDefinition("created_at", DateTimeType(precision=6)),
            ColumnDefinition("updated_at", DateTimeType(precision=6)),
        ],
        indexes=[IndexDefinition(name="idx_order_id", columns=["order_id"])],
        table_constraints=[
            ForeignKeyConstraint(columns=["order_id"], foreign_key_table="orders", foreign_key_columns=["id"],
                on_delete=_CASCADE),
        ],
    )


def create_profiles_table(dialect, table_name: str = "profiles") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition("user_id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("bio", TextType()),
            ColumnDefinition("avatar_url", VarCharType(length=512)),
            ColumnDefinition("created_at", DateTimeType(precision=6)),
            ColumnDefinition("updated_at", DateTimeType(precision=6)),
        ],
        table_constraints=[
            ForeignKeyConstraint(columns=["user_id"], foreign_key_table="users", foreign_key_columns=["id"]),
        ],
    )


def create_json_users_table(dialect, table_name: str = "json_users") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition("username", VarCharType(length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("email", VarCharType(length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("age", IntegerType()),
            ColumnDefinition("created_at", DateTimeType(precision=6)),
            ColumnDefinition("updated_at", DateTimeType(precision=6)),
            ColumnDefinition("settings", JsonType()),
            ColumnDefinition("tags", JsonType()),
            ColumnDefinition("profile", JsonType()),
            ColumnDefinition("roles", JsonType()),
            ColumnDefinition("scores", JsonType()),
            ColumnDefinition("subscription", JsonType()),
            ColumnDefinition("preferences", JsonType()),
        ],
    )


def create_nodes_table(dialect, table_name: str = "nodes") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition("name", VarCharType(length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("parent_id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NULL)]),
            ColumnDefinition("value", DecimalType(precision=10, scale=2),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0.0)]),
            ColumnDefinition("created_at", DateTimeType(precision=6)),
            ColumnDefinition("updated_at", DateTimeType(precision=6)),
        ],
        indexes=[IndexDefinition(name="idx_parent_id", columns=["parent_id"])],
        table_constraints=[
            ForeignKeyConstraint(columns=["parent_id"], foreign_key_table="nodes", foreign_key_columns=["id"],
                on_delete=ReferentialAction.NO_ACTION),
        ],
    )


def create_searchable_items_table(dialect, table_name: str = "searchable_items") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition("name", VarCharType(length=255)),
            ColumnDefinition("tags", TextType()),
            ColumnDefinition("created_at", DateTimeType(precision=6)),
            ColumnDefinition("updated_at", DateTimeType(precision=6)),
        ],
    )


def create_extended_orders_table(dialect, table_name: str = "extended_orders") -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition("user_id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("order_number", VarCharType(length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("total_amount", DecimalType(precision=10, scale=2),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=0.0)]),
            ColumnDefinition("status", VarCharType(length=50),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value="pending")]),
            ColumnDefinition("priority", VarCharType(length=50),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value="medium")]),
            ColumnDefinition("region", VarCharType(length=50),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value="default")]),
            ColumnDefinition("category", VarCharType(length=255)),
            ColumnDefinition("product", VarCharType(length=255)),
            ColumnDefinition("department", VarCharType(length=255)),
            ColumnDefinition("year", VarCharType(length=10)),
            ColumnDefinition("quarter", VarCharType(length=10)),
            ColumnDefinition("created_at", DateTimeType(precision=6)),
            ColumnDefinition("updated_at", DateTimeType(precision=6)),
        ],
        indexes=[
            IndexDefinition(name="idx_user_id", columns=["user_id"]),
            IndexDefinition(name="idx_status", columns=["status"]),
            IndexDefinition(name="idx_priority", columns=["priority"]),
            IndexDefinition(name="idx_region", columns=["region"]),
        ],
        table_constraints=[
            ForeignKeyConstraint(columns=["user_id"], foreign_key_table="users", foreign_key_columns=["id"],
                on_delete=_CASCADE),
        ],
    )


def create_extended_order_items_table(
    dialect, table_name: str = "extended_order_items"
) -> CreateTableExpression:
    return CreateTableExpression(
        dialect=dialect,
        table=table_name,
        if_not_exists=False,
        columns=[
            ColumnDefinition("id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]),
            ColumnDefinition("order_id", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("product_name", VarCharType(length=255),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("quantity", IntegerType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=1)]),
            ColumnDefinition("price", DecimalType(precision=10, scale=2),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("category", VarCharType(length=255)),
            ColumnDefinition("region", VarCharType(length=50)),
            ColumnDefinition("created_at", DateTimeType(precision=6)),
            ColumnDefinition("updated_at", DateTimeType(precision=6)),
        ],
        indexes=[IndexDefinition(name="idx_order_id", columns=["order_id"])],
        table_constraints=[
            ForeignKeyConstraint(columns=["order_id"], foreign_key_table="extended_orders",
                foreign_key_columns=["id"], on_delete=_CASCADE),
        ],
    )


TABLE_EXPRESSIONS: Dict[str, Callable] = {
    "users": create_users_table,
    "posts": create_posts_table,
    "comments": create_comments_table,
    "orders": create_orders_table,
    "order_items": create_order_items_table,
    "profiles": create_profiles_table,
    "json_users": create_json_users_table,
    "nodes": create_nodes_table,
    "searchable_items": create_searchable_items_table,
    "extended_orders": create_extended_orders_table,
    "extended_order_items": create_extended_order_items_table,
}
