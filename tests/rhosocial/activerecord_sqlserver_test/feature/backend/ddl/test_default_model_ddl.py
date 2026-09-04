# tests/rhosocial/activerecord_sqlserver_test/feature/backend/ddl/test_default_model_ddl.py
"""Default-type model rendering — SQL Server.

``DefaultUser`` declares plain Python types with no ``UseSqlType``; SQL Server
derives the column types via its own suggestion mapping.
"""

from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.examples.ddl_default_types import DefaultUser


def _render() -> str:
    sql, _ = DefaultUser.generate_create_table(dialect=SQLServerDialect()).to_sql()
    return sql


def test_default_user_has_no_explicit_sql_types():
    assert DefaultUser.__table_field_sql_types__ == {}


def test_sqlserver_default_user_ddl_columns():
    sql = _render()
    assert "CREATE TABLE [default_users]" in sql
    assert "[id] INT PRIMARY KEY IDENTITY(1,1)" in sql
    assert "[username] VARCHAR(255) NOT NULL" in sql
    assert "[email] VARCHAR(255) NOT NULL" in sql
    assert "[is_active] BIT NOT NULL" in sql
    assert "[balance] FLOAT(53) NOT NULL" in sql
    assert "[created_at] DATETIME2 NOT NULL" in sql
    assert "[metadata] NVARCHAR(MAX) NOT NULL" in sql
    assert "[avatar] VARBINARY(MAX) NOT NULL" in sql
    assert "[birthday] DATE" in sql