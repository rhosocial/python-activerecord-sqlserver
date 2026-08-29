# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_auto_increment_ddl.py
"""Regression tests for DDL compilation of auto-increment, standard types,
boolean defaults, and timestamps.

Covers bugs found in rbac cross-backend testing:
- is_auto_increment=True on PRIMARY_KEY must produce IDENTITY(1,1).
- format_create_table_statement must return a string for all types.
- BooleanType with DEFAULT True must be accepted.
- TimestampType must map to DATETIME2.
"""

import pytest

from rhosocial.activerecord.backend.expression import (
    CreateTableExpression, ColumnDefinition, ColumnConstraint, ColumnConstraintType,
)
from rhosocial.activerecord.backend.expression.types import (
    BooleanType, IntegerType, TextType, TimestampType, VarCharType,
)
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


@pytest.fixture
def dialect():
    return SQLServerDialect()


def _pk():
    return [ColumnConstraint(ColumnConstraintType.PRIMARY_KEY, is_auto_increment=True)]


def _build_table(dialect):
    return CreateTableExpression(
        dialect=dialect, table="test_tbl",
        columns=[
            ColumnDefinition("id", IntegerType(), constraints=_pk()),
            ColumnDefinition("name", TextType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)]),
            ColumnDefinition("flag", BooleanType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                             ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=True)]),
            ColumnDefinition("code", VarCharType(16)),
            ColumnDefinition("created_at", TimestampType()),
        ],
    )


class TestAutoIncrementDDL:

    def test_auto_increment_in_ddl(self, dialect):
        sql, _ = dialect.format_create_table_statement(_build_table(dialect))
        assert "IDENTITY(1,1)" in sql.upper(), f"auto-increment missing: {sql}"

    def test_all_standard_types_compile(self, dialect):
        sql, params = dialect.format_create_table_statement(_build_table(dialect))
        assert isinstance(sql, str)
        assert isinstance(params, tuple)

    def test_boolean_default_true(self, dialect):
        expr = CreateTableExpression(
            dialect=dialect, table="bool_test",
            columns=[
                ColumnDefinition("id", IntegerType(), constraints=_pk()),
                ColumnDefinition("flag", BooleanType(),
                    constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL),
                                 ColumnConstraint(ColumnConstraintType.DEFAULT, default_value=True)]),
            ],
        )
        sql, _ = dialect.format_create_table_statement(expr)
        assert "BIT" in sql.upper()

    def test_timestamp_type(self, dialect):
        expr = CreateTableExpression(
            dialect=dialect, table="ts_test",
            columns=[
                ColumnDefinition("id", IntegerType(), constraints=_pk()),
                ColumnDefinition("created_at", TimestampType()),
            ],
        )
        sql, _ = dialect.format_create_table_statement(expr)
        assert "DATETIME2" in sql.upper()
