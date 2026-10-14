# tests/providers/fixtures/mixins.py
"""DDL expressions for the ``feature/mixins`` table group (SQL Server).

Reference: ``tests/rhosocial/activerecord_sqlserver_test/feature/mixins/schema/``.
"""

from typing import Callable, Dict

from rhosocial.activerecord.backend.expression import (
    CreateTableStatement,
)
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    ColumnConstraint,
    ColumnDefaultConstraint,
    ColumnNotNullConstraint,
    ColumnNullableConstraint,
    ColumnPrimaryKeyConstraint,
)
from rhosocial.activerecord.backend.expression.types import (
    BooleanType,
    DateTimeType,
    DecimalType,
    IntegerType,
    TextType,
    VarCharType,
)

from . import _common


def to_sql(expr: CreateTableStatement):
    return _common.to_sqlserver_ddl_sql(expr)


def create_combined_articles_table(dialect, table_name: str = "combined_articles") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", IntegerType(dialect),
                constraints=[
                    ColumnConstraint(
                        dialect,
                        branch=ColumnPrimaryKeyConstraint(dialect, is_auto_increment=True),
                    )
                ]),
            ColumnDefinition(dialect, "title", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "content", TextType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "status", VarCharType(dialect, length=50),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, "draft"))]),
            ColumnDefinition(dialect, "created_at", DateTimeType(dialect, precision=6)),
            ColumnDefinition(dialect, "updated_at", DateTimeType(dialect, precision=6)),
            ColumnDefinition(dialect, "version", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 1))]),
            ColumnDefinition(dialect, "deleted_at", DateTimeType(dialect, precision=6),
                constraints=[ColumnConstraint(dialect, branch=ColumnNullableConstraint(dialect))]),
        ],
    )


def create_tasks_table(dialect, table_name: str = "tasks") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", IntegerType(dialect),
                constraints=[
                    ColumnConstraint(
                        dialect,
                        branch=ColumnPrimaryKeyConstraint(dialect, is_auto_increment=True),
                    )
                ]),
            ColumnDefinition(dialect, "title", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "is_completed", BooleanType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 0))]),
            ColumnDefinition(dialect, "deleted_at", TextType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNullableConstraint(dialect))]),
        ],
    )


def create_timestamped_posts_table(dialect, table_name: str = "timestamped_posts") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", IntegerType(dialect),
                constraints=[
                    ColumnConstraint(
                        dialect,
                        branch=ColumnPrimaryKeyConstraint(dialect, is_auto_increment=True),
                    )
                ]),
            ColumnDefinition(dialect, "title", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "content", TextType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "created_at", DateTimeType(dialect, precision=6)),
            ColumnDefinition(dialect, "updated_at", DateTimeType(dialect, precision=6)),
        ],
    )


def create_versioned_products_table(dialect, table_name: str = "versioned_products") -> CreateTableStatement:
    return CreateTableStatement(
        dialect=dialect,
        table=Table(dialect, table_name),
        if_not_exists=False,
        columns=[
            ColumnDefinition(dialect, "id", IntegerType(dialect),
                constraints=[
                    ColumnConstraint(
                        dialect,
                        branch=ColumnPrimaryKeyConstraint(dialect, is_auto_increment=True),
                    )
                ]),
            ColumnDefinition(dialect, "name", VarCharType(dialect, length=255),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))]),
            ColumnDefinition(dialect, "price", DecimalType(dialect, precision=10, scale=2),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 0.0))]),
            ColumnDefinition(dialect, "version", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 1))]),
        ],
    )


TABLE_EXPRESSIONS: Dict[str, Callable] = {
    "combined_articles": create_combined_articles_table,
    "tasks": create_tasks_table,
    "timestamped_posts": create_timestamped_posts_table,
    "versioned_products": create_versioned_products_table,
}
