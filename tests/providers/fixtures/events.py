# tests/providers/fixtures/events.py
"""DDL expressions for the ``feature/events`` table group (SQL Server).

Reference: ``tests/rhosocial/activerecord_sqlserver_test/feature/events/schema/``.
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
    DateTimeType,
    IntegerType,
    TextType,
    VarCharType,
)

from . import _common


def to_sql(expr: CreateTableStatement):
    return _common.to_sqlserver_ddl_sql(expr)


def create_event_tests_table(dialect, table_name: str = "event_tests") -> CreateTableStatement:
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
            ColumnDefinition(dialect, "status", VarCharType(dialect, length=50),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, "draft"))]),
            ColumnDefinition(dialect, "revision", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 1))]),
            ColumnDefinition(dialect, "content", TextType(dialect)),
            ColumnDefinition(dialect, "created_at", DateTimeType(dialect, precision=6)),
            ColumnDefinition(dialect, "updated_at", DateTimeType(dialect, precision=6)),
        ],
    )


def create_event_tracking_models_table(
    dialect, table_name: str = "event_tracking_models"
) -> CreateTableStatement:
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
            ColumnDefinition(dialect, "view_count", IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect)),
                             ColumnConstraint(dialect, branch=ColumnDefaultConstraint(dialect, 0))]),
            ColumnDefinition(dialect, "last_viewed_at", DateTimeType(dialect, precision=6),
                constraints=[ColumnConstraint(dialect, branch=ColumnNullableConstraint(dialect))]),
        ],
    )


TABLE_EXPRESSIONS: Dict[str, Callable] = {
    "event_tests": create_event_tests_table,
    "event_tracking_models": create_event_tracking_models_table,
}
