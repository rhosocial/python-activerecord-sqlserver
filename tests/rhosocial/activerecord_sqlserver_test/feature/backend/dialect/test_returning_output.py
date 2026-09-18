# tests/rhosocial/activerecord_sqlserver_test/feature/backend/dialect/test_returning_output.py
"""SQL Server OUTPUT (RETURNING) capability and formatting tests."""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.core import (
    Column,
    FunctionCall,
    WildcardExpression,
)
from rhosocial.activerecord.backend.expression.statements import ReturningClause
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

pytestmark = [pytest.mark.feature, pytest.mark.backend]


@pytest.fixture
def dialect():
    return SQLServerDialect(version=(16, 0, 0))


class TestSQLServerReturningCapabilities:
    def test_dml_returning_supported(self, dialect):
        assert dialect.supports_returning_insert() is True
        assert dialect.supports_returning_update() is True
        assert dialect.supports_returning_delete() is True

    def test_alias_unsupported(self, dialect):
        assert dialect.supports_returning_alias() is False

    def test_wildcard_unsupported(self, dialect):
        assert dialect.supports_returning_wildcard() is False

    def test_into_supported(self, dialect):
        assert dialect.supports_returning_into() is True


class TestSQLServerOutputFormatting:
    def test_insert_default_prefix(self, dialect):
        clause = ReturningClause(dialect, expressions=[Column(dialect, "id")])
        sql, _ = dialect.format_returning_clause(clause, default_table="INSERTED")
        assert sql == "OUTPUT INSERTED.[id]"

    def test_delete_default_prefix(self, dialect):
        clause = ReturningClause(dialect, expressions=[Column(dialect, "id")])
        sql, _ = dialect.format_returning_clause(clause, default_table="DELETED")
        assert sql == "OUTPUT DELETED.[id]"

    def test_per_expression_prefix(self, dialect):
        clause = ReturningClause(
            dialect,
            expressions=[
                Column(dialect, "name", table="DELETED"),
                Column(dialect, "name", table="INSERTED"),
            ],
        )
        sql, _ = dialect.format_returning_clause(clause, default_table="INSERTED")
        assert "DELETED.[name]" in sql
        assert "INSERTED.[name]" in sql

    def test_output_into(self, dialect):
        clause = ReturningClause(
            dialect, expressions=[Column(dialect, "id")], output_into="@ids"
        )
        sql, _ = dialect.format_returning_clause(clause)
        assert sql == "OUTPUT INSERTED.[id] INTO @ids"

    def test_rejects_non_column_expression(self, dialect):
        clause = ReturningClause(
            dialect, expressions=[FunctionCall(dialect, "UPPER", Column(dialect, "name"))]
        )
        with pytest.raises(UnsupportedFeatureError, match="expressions in OUTPUT"):
            dialect.format_returning_clause(clause)

    def test_rejects_wildcard(self, dialect):
        clause = ReturningClause(dialect, expressions=[WildcardExpression(dialect)])
        with pytest.raises(UnsupportedFeatureError, match="wildcard in OUTPUT"):
            dialect.format_returning_clause(clause)

    def test_rejects_alias(self, dialect):
        clause = ReturningClause(dialect, expressions=[Column(dialect, "id")], alias="r")
        with pytest.raises(UnsupportedFeatureError, match="alias in OUTPUT"):
            dialect.format_returning_clause(clause)
