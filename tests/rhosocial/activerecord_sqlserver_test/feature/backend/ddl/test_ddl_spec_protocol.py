# tests/rhosocial/activerecord_sqlserver_test/feature/backend/ddl/test_ddl_spec_protocol.py
"""SQL Server DDL feature-spec claiming tests (``build_spec``).

Covers the SQL Server-specific Spec (RANGE partitioning with scheme) and the
generic Specs on the SQL Server dialect:

- ``SQLServerRangePartition`` translates to ``SQLServerPartitionByRangeClause``
  with the scheme carried through ``dialect_options``.
- Generic Specs still translate via the core ``DDLSpecBuildingMixin``.
- Foreign Specs (``PartitionSpec`` marker, unknown objects) return ``None``.
"""

import pytest

from rhosocial.activerecord.base import (
    CheckSpec,
    PartitionSpec,
    PrimaryKeySpec,
    UniqueSpec,
)
from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.ddl_spec import SQLServerRangePartition


@pytest.fixture
def dialect():
    d = SQLServerDialect()
    d.version = (15, 0, 0)
    return d


class TestProtocolConformance:
    def test_build_spec_returns_none_for_unknown(self, dialect):
        assert dialect.build_spec(object()) is None

    def test_build_spec_returns_none_for_base_partition_marker(self, dialect):
        assert dialect.build_spec(PartitionSpec()) is None


class TestGenericSpecTranslation:
    def test_unique_spec(self, dialect):
        result = dialect.build_spec(UniqueSpec(["a", "b"], name="uq_ab"))
        assert result.columns == ["a", "b"]

    def test_check_spec_lazy(self, dialect):
        result = dialect.build_spec(
            CheckSpec(lambda d: Column(d, "age") >= 18, name="ck_age")
        )
        assert result.check_condition is not None

    def test_primary_key_single(self, dialect):
        result = dialect.build_spec(PrimaryKeySpec(["id"]))
        from rhosocial.activerecord.backend.expression.statements import (
            ColumnConstraint,
            ColumnConstraintType,
        )
        assert isinstance(result, ColumnConstraint)
        assert result.constraint_type == ColumnConstraintType.PRIMARY_KEY


class TestSQLServerPartitionSpecs:
    def test_range_partition_right(self, dialect):
        spec = SQLServerRangePartition(
            "created_at",
            "ps_orders",
            boundaries=["2026-01-01", "2027-01-01"],
        )
        expr = dialect.build_spec(spec)
        assert type(expr).__name__ == "SQLServerPartitionByRangeClause"
        sql, _ = expr.to_sql()
        assert "ON [ps_orders]" in sql
        assert "[created_at]" in sql

    def test_range_partition_left(self, dialect):
        spec = SQLServerRangePartition("created_at", "ps_orders", right=False)
        expr = dialect.build_spec(spec)
        from rhosocial.activerecord.backend.impl.sqlserver.expression.partition import (
            SQLServerPartitionRangeDirection,
        )
        assert expr.range_direction == SQLServerPartitionRangeDirection.LEFT

    def test_range_partition_requires_scheme(self):
        with pytest.raises(ValueError):
            SQLServerRangePartition("created_at", "")

    def test_range_partition_requires_column(self):
        with pytest.raises(ValueError):
            SQLServerRangePartition("", "ps_orders")


class TestBuildSpecFeedsCreateTable:
    def test_partition_spec_feeds_create_table(self, dialect):
        from rhosocial.activerecord.backend.expression.statements import (
            ColumnDefinition,
            CreateTableExpression,
        )
        from rhosocial.activerecord.backend.expression.types import IntegerType

        part = dialect.build_spec(
            SQLServerRangePartition("created_at", "ps_orders")
        )
        pk = dialect.build_spec(PrimaryKeySpec(["id"]))
        cols = [
            ColumnDefinition("id", IntegerType(), constraints=[pk]),
            ColumnDefinition("created_at", IntegerType()),
        ]
        expr = CreateTableExpression(
            dialect=dialect,
            table="orders",
            columns=cols,
            partition=part,
        )
        sql, _ = expr.to_sql()
        assert "ON [ps_orders]" in sql


class TestModelIntegration:
    def test_model_partition_spec(self, dialect):
        from rhosocial.activerecord.model import ActiveRecord

        class Orders(ActiveRecord):
            __table_name__ = "orders"
            __table_partition__ = [
                SQLServerRangePartition("created_at", "ps_orders"),
            ]
            created_at: str

        expr = Orders.generate_create_table(dialect)
        assert expr.partition is not None
        sql, _ = expr.to_sql()
        assert "ON [ps_orders]" in sql

    def test_model_unclaimed_partition_is_ignored(self):
        from rhosocial.activerecord.backend.impl.sqlite.dialect import SQLiteDialect
        from rhosocial.activerecord.model import ActiveRecord

        class Orders(ActiveRecord):
            __table_name__ = "orders"
            __table_partition__ = [
                SQLServerRangePartition("created_at", "ps_orders"),
            ]
            created_at: str

        # The same model on SQLite: SQL Server partition spec unclaimed → plain table.
        expr = Orders.generate_create_table(SQLiteDialect())
        assert expr.partition is None