# tests/rhosocial/activerecord_sqlserver_test/feature/query/test_collation_expression.py
"""
Tests for expression-level COLLATE support on SQL Server.
"""

import pytest

from rhosocial.activerecord.backend.expression import Column, Literal
from rhosocial.activerecord.backend.impl.sqlserver import SQLServerCollation, SQLServerDialect


@pytest.fixture
def dialect():
    return SQLServerDialect(version=(15, 0, 0))


@pytest.fixture
def collation_table(sqlserver_backend):
    sqlserver_backend.execute("IF OBJECT_ID('test_collation_expression', 'U') IS NOT NULL DROP TABLE test_collation_expression")
    sqlserver_backend.execute("""
        CREATE TABLE test_collation_expression (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name NVARCHAR(100) COLLATE Latin1_General_CI_AS NOT NULL
        )
    """)
    sqlserver_backend.execute("""
        INSERT INTO test_collation_expression (name)
        VALUES (N'Alice'), (N'alice'), (N'Bob')
    """)
    yield "test_collation_expression"
    sqlserver_backend.execute("IF OBJECT_ID('test_collation_expression', 'U') IS NOT NULL DROP TABLE test_collation_expression")


class TestSQLServerCollationExpression:
    def test_column_collate_generates_sql(self, dialect):
        expr = Column(dialect, "name", table="users").collate(
            SQLServerCollation.LATIN1_GENERAL_CS_AS
        )

        sql, params = expr.to_sql()

        assert sql == "[users].[name] COLLATE Latin1_General_CS_AS"
        assert params == ()

    def test_literal_collate_preserves_parameter_binding(self, dialect):
        expr = Literal(dialect, "Alice").collate(SQLServerCollation.LATIN1_GENERAL_CI_AS)

        sql, params = expr.to_sql()

        assert sql == "? COLLATE Latin1_General_CI_AS"
        assert params == ("Alice",)

    def test_database_default_keyword_generates_sql(self, dialect):
        expr = Column(dialect, "name").collate("DATABASE_DEFAULT", keyword=True)

        sql, params = expr.to_sql()

        assert sql == "[name] COLLATE DATABASE_DEFAULT"
        assert params == ()

    def test_rejects_schema_qualified_collation(self, dialect):
        expr = Column(dialect, "name").collate(
            SQLServerCollation.LATIN1_GENERAL_CI_AS.value, schema="dbo"
        )

        with pytest.raises(Exception, match="schema-qualified COLLATE"):
            expr.to_sql()

    def test_rejects_unsupported_keyword(self, dialect):
        expr = Column(dialect, "name").collate("CATALOG_DEFAULT", keyword=True)

        with pytest.raises(ValueError, match="Unsupported SQL Server collation keyword"):
            expr.to_sql()

    def test_rejects_unsupported_collation(self, dialect):
        expr = Column(dialect, "name").collate("unknown_ci")

        with pytest.raises(ValueError, match="Unsupported SQL Server collation"):
            expr.to_sql()

    @pytest.mark.skip(reason="SQL Server feature/query tests do not expose a raw backend fixture")
    def test_collate_executes_case_sensitive_match(self, sqlserver_backend, collation_table):
        expr = Column(sqlserver_backend.dialect, "name", table=collation_table).collate(
            SQLServerCollation.LATIN1_GENERAL_CS_AS
        )
        sql, params = expr.to_sql()

        rows = sqlserver_backend.fetch_all(
            f"SELECT name FROM [{collation_table}] WHERE {sql} = ? ORDER BY id",
            (*params, "Alice"),
        )

        assert [row["name"] for row in rows] == ["Alice"]

    @pytest.mark.skip(reason="SQL Server feature/query tests do not expose a raw backend fixture")
    def test_collate_executes_case_insensitive_match(self, sqlserver_backend, collation_table):
        expr = Column(sqlserver_backend.dialect, "name", table=collation_table).collate(
            SQLServerCollation.LATIN1_GENERAL_CI_AS
        )
        sql, params = expr.to_sql()

        rows = sqlserver_backend.fetch_all(
            f"SELECT name FROM [{collation_table}] WHERE {sql} = ? ORDER BY id",
            (*params, "Alice"),
        )

        assert [row["name"] for row in rows] == ["Alice", "alice"]
