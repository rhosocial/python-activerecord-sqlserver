# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_sqlserver_column_definition.py
"""Tests for the SQL Server-specific column definition expressions."""

import pytest

from rhosocial.activerecord.backend.expression import ColumnDefinition
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.impl.sqlserver.expression import (
    SQLServerColumnDefinition,
    SQLServerColumnOptions,
)


@pytest.fixture
def dialect():
    from rhosocial.activerecord.backend.impl.sqlserver import SQLServerDialect

    return SQLServerDialect((2022, 0, 0))


def test_derives_generic_column_definition():
    assert ColumnDefinition in SQLServerColumnDefinition.__mro__


def test_sparse(dialect):
    sql, _ = SQLServerColumnDefinition(dialect, "x", IntegerType(dialect), sparse=True).to_sql()
    assert sql == "[x] INT SPARSE"


def test_rowguidcol(dialect):
    sql, _ = SQLServerColumnDefinition(
        dialect, "x", IntegerType(dialect), rowguidcol=True
    ).to_sql()
    assert sql == "[x] INT ROWGUIDCOL"


def test_generic_column_still_renders_on_sqlserver(dialect):
    generic = ColumnDefinition(dialect, "x", IntegerType(dialect))
    sql, _ = generic.to_sql()
    assert sql == "[x] INT"


def test_options_select_sqlserver_column_class():
    assert SQLServerColumnOptions(sparse=True).column_definition_class() is (
        SQLServerColumnDefinition
    )


def test_options_apply_to(dialect):
    options = SQLServerColumnOptions(sparse=True, rowguidcol=True)
    col = SQLServerColumnDefinition(dialect, "c", IntegerType(dialect))
    options.apply_to(col)
    assert col.sparse is True
    assert col.rowguidcol is True


def test_options_apply_to_rejects_generic_column(dialect):
    options = SQLServerColumnOptions(sparse=True)
    generic = ColumnDefinition(dialect, "c", IntegerType(dialect))
    with pytest.raises(TypeError, match="SQLServerColumnDefinition"):
        options.apply_to(generic)
