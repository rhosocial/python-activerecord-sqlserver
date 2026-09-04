# tests/rhosocial/activerecord_sqlserver_test/feature/backend/ddl/test_typed_model_ddl.py
"""Cross-backend UseSqlType demonstration — SQL Server rendering.

The shared ``TypedUser`` model (core generic types) renders SQL Server-native
SQL without any per-dialect string mappings. Dialect instantiation needs no
DB server; only ``to_sql()`` is exercised here.
"""

from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.examples.ddl_types import TypedUser


def _render() -> str:
    sql, _ = TypedUser.generate_create_table(dialect=SQLServerDialect()).to_sql()
    return sql


def test_sqlserver_typed_user_ddl_columns():
    sql = _render()
    assert "CREATE TABLE [typed_users]" in sql
    assert "[id] INT PRIMARY KEY IDENTITY(1,1)" in sql
    assert "[username] VARCHAR(100) NOT NULL" in sql
    assert "[email] VARCHAR(255) NOT NULL" in sql
    assert "[is_active] BIT NOT NULL" in sql
    assert "[balance] DECIMAL(10, 2)" in sql
    assert "[birthday] DATE" in sql
    assert "[created_at] DATETIME2 NOT NULL" in sql
    assert "[bio] NVARCHAR(MAX)" in sql
    assert "[metadata] NVARCHAR(MAX)" in sql
    assert "[big_counter] BIGINT" in sql
    assert "[avatar] VARBINARY(MAX)" in sql
    assert "[wake_up_time] TIME" in sql


def test_sqlserver_typed_user_no_per_dialect_string_keys():
    for _field_name, marker in TypedUser.__table_field_sql_types__.items():
        assert not hasattr(marker, "dialect_types")
        assert marker.data_type is not None