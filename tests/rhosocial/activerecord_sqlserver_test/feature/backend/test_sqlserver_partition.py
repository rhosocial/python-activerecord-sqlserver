import inspect
from typing import Set, Tuple

import pytest
from rhosocial.activerecord.backend.dialect import SQLDialectBase
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect import protocols as dialect_protocols
from rhosocial.activerecord.backend.expression import (
    Column,
    CreateTableExpression,
    ColumnDefinition,
)
from rhosocial.activerecord.backend.expression.statements import (
    PartitionClause,
    PartitionStrategy,
    ColumnConstraint,
    ColumnConstraintType,
)
from rhosocial.activerecord.backend.expression.types import DateType, IntegerType, VarCharType
from rhosocial.activerecord.backend.dialect.mixins import (
    IdentifierMixin,
    DDLColumnMixin,
    ExpressionMixin,
    DDLTypeMixin,
    TableMixin,
)
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.protocols import SQLServerPartitionSupport
from rhosocial.activerecord.backend.impl.sqlserver.expression.partition import (
    SQLServerPartitionFunctionExpression,
    SQLServerPartitionSchemeExpression,
    SQLServerPartitionByRangeClause,
    SQLServerPartitionRangeDirection,
)


SQL_SERVER_2022 = (16, 0, 0)
SQL_SERVER_2005 = (9, 0, 0)


class TestSQLServerPartitionProtocolConformance:
    """Tests SQLServerPartitionMixin satisfies PartitionSupport and SQLServerPartitionSupport."""

    def test_partition_mixin_satisfies_partition_support_protocol(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        assert isinstance(d, dialect_protocols.PartitionSupport)
        assert isinstance(d, SQLServerPartitionSupport)

    def test_sqlserver_partition_protocol_methods_are_implemented(self):
        """Every SQLServerPartitionSupport method should exist on the dialect."""
        protocol_methods = _get_protocol_methods(dialect_protocols.PartitionSupport)
        protocol_methods |= _get_protocol_methods(SQLServerPartitionSupport)
        dialect_methods = {name for name in dir(SQLServerDialect) if not name.startswith("_")}
        missing = protocol_methods - dialect_methods
        assert missing == set(), f"Missing methods: {missing}"


class TestSQLServerPartitionCapabilities:
    """Tests partition capability flags for various SQL Server versions."""

    def test_partition_supported_on_modern_versions(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        assert d.supports_table_partitioning() is True
        assert d.supports_partitioned_table_creation() is True
        assert d.supports_range_table_partitioning() is True
        assert d.supports_range_right_partitioning() is True
        assert d.supports_range_left_partitioning() is True
        assert d.supports_partition_function() is True
        assert d.supports_partition_scheme() is True

    def test_list_and_hash_not_supported(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        assert d.supports_list_table_partitioning() is False
        assert d.supports_hash_table_partitioning() is False
        assert d.supports_subpartitioning() is False

    def test_partition_not_supported_on_very_old_versions(self):
        d = SQLServerDialect(SQL_SERVER_2005)
        assert d.supports_table_partitioning() is False
        assert d.supports_partition_function() is False

    def test_maintenance_operations_not_implemented_in_phase1(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        assert d.supports_add_partition() is False
        assert d.supports_drop_partition() is False
        assert d.supports_truncate_partition() is False

    def test_switch_split_merge_capabilities(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        assert d.supports_switch_partition() is True
        assert d.supports_split_partition() is True
        assert d.supports_merge_partition() is True


class TestSQLServerPartitionClause:
    """Tests format_partition_clause for core PartitionClause."""

    def test_format_partition_clause_with_scheme(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        col = Column(d, "create_date")
        partition = PartitionClause(
            d, PartitionStrategy.RANGE, [col],
            dialect_options={"partition_scheme": "ps_sales"},
        )
        sql, params = d.format_partition_clause(partition)
        assert "ON [ps_sales] ([create_date])" in sql
        assert params == ()

    def test_format_partition_clause_multiple_keys(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        col1 = Column(d, "year")
        col2 = Column(d, "month")
        partition = PartitionClause(
            d, PartitionStrategy.RANGE, [col1, col2],
            dialect_options={"partition_scheme": "ps_date"},
        )
        sql, params = d.format_partition_clause(partition)
        assert "ON [ps_date] ([year], [month])" in sql

    def test_format_partition_clause_without_scheme(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        col = Column(d, "id")
        partition = PartitionClause(d, PartitionStrategy.RANGE, [col])
        sql, params = d.format_partition_clause(partition)
        # Falls back to placeholder
        assert "partition_scheme_name" in sql

    def test_format_partition_clause_unsupported_method(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        col = Column(d, "id")
        partition = PartitionClause(d, PartitionStrategy.HASH, [col])
        with pytest.raises(UnsupportedFeatureError):
            d.format_partition_clause(partition)

    def test_format_partition_clause_on_old_version(self):
        d = SQLServerDialect(SQL_SERVER_2005)
        col = Column(d, "id")
        partition = PartitionClause(d, PartitionStrategy.RANGE, [col])
        with pytest.raises(UnsupportedFeatureError):
            d.format_partition_clause(partition)


class TestSQLServerPartitionFunction:
    """Tests CREATE PARTITION FUNCTION formatting."""

    def test_basic_partition_function(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        pf = SQLServerPartitionFunctionExpression(
            d, "pf_sales", "DATE",
            ["2020-01-01", "2021-01-01", "2022-01-01"],
        )
        sql, params = pf.to_sql()
        assert sql == (
            "CREATE PARTITION FUNCTION [pf_sales] (DATE) "
            "AS RANGE RIGHT FOR VALUES ('2020-01-01', '2021-01-01', '2022-01-01')"
        )
        assert params == ()

    def test_partition_function_range_left(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        pf = SQLServerPartitionFunctionExpression(
            d, "pf_test", "INT",
            [0, 100, 1000],
            range_direction=SQLServerPartitionRangeDirection.LEFT,
        )
        sql, _ = pf.to_sql()
        assert "RANGE LEFT FOR VALUES (0, 100, 1000)" in sql
        assert "[pf_test]" in sql

    def test_partition_function_with_nulls_and_strings(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        pf = SQLServerPartitionFunctionExpression(
            d, "pf_region", "NVARCHAR(50)",
            ["North", "South", None, "East"],
        )
        sql, _ = pf.to_sql()
        assert "'North'" in sql
        assert "'South'" in sql
        assert "NULL" in sql

    def test_partition_function_schema_qualified(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        pf = SQLServerPartitionFunctionExpression(
            d, "dbo.pf_sales", "DATE", ["2020-01-01"],
        )
        sql, _ = pf.to_sql()
        assert "[dbo].[pf_sales]" in sql


class TestSQLServerPartitionScheme:
    """Tests CREATE PARTITION SCHEME formatting."""

    def test_basic_partition_scheme(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        ps = SQLServerPartitionSchemeExpression(
            d, "ps_sales", "pf_sales",
            ["PRIMARY", "fg2020", "fg2021", "fg2022"],
        )
        sql, params = ps.to_sql()
        expected = (
            "CREATE PARTITION SCHEME [ps_sales] "
            "AS PARTITION [pf_sales] "
            "TO ([PRIMARY], [fg2020], [fg2021], [fg2022])"
        )
        assert sql == expected
        assert params == ()

    def test_partition_scheme_all_to_filegroup(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        ps = SQLServerPartitionSchemeExpression(
            d, "ps_all", "pf_all",
            [],
            all_filegroup="PRIMARY",
        )
        sql, _ = ps.to_sql()
        expected = (
            "CREATE PARTITION SCHEME [ps_all] "
            "AS PARTITION [pf_all] "
            "ALL TO ([PRIMARY])"
        )
        assert sql == expected


class TestSQLServerCreateTableWithPartition:
    """Tests CREATE TABLE with partition clause."""

    def test_create_table_with_partition(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        pk = ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)
        col_def = ColumnDefinition("id", IntegerType(), constraints=[pk])
        col_def2 = ColumnDefinition("name", VarCharType(100))
        col_def3 = ColumnDefinition("create_date", DateType())

        col = Column(d, "create_date")
        partition = SqlServerPartitionClause(
            d, [col],
            partition_scheme="ps_sales",
        )

        stmt = CreateTableExpression(
            d, "orders",
            columns=[col_def, col_def2, col_def3],
            partition=partition,
        )
        sql, params = stmt.to_sql()
        assert "CREATE TABLE" in sql
        assert "[orders]" in sql
        assert "ON [ps_sales] ([create_date])" in sql

    def test_create_table_without_partition(self):
        """Unchanged behavior when no partition is specified."""
        d = SQLServerDialect(SQL_SERVER_2022)
        pk = ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)
        col_def = ColumnDefinition("id", IntegerType(), constraints=[pk])
        stmt = CreateTableExpression(
            d, "users",
            columns=[col_def],
        )
        sql, params = stmt.to_sql()
        assert "CREATE TABLE" in sql
        assert "[users]" in sql
        assert "ON" not in sql

    def test_create_table_with_partition_on_old_version(self):
        """Should fail on SQL Server 2005 which doesn't support partitioning."""
        d = SQLServerDialect(SQL_SERVER_2005)
        pk = ColumnConstraint(ColumnConstraintType.PRIMARY_KEY)
        col_def = ColumnDefinition("id", IntegerType(), constraints=[pk])
        col = Column(d, "id")
        partition = PartitionClause(
            d, PartitionStrategy.RANGE, [col],
            dialect_options={"partition_scheme": "ps_test"},
        )
        stmt = CreateTableExpression(
            d, "test",
            columns=[col_def],
            partition=partition,
        )
        with pytest.raises(UnsupportedFeatureError):
            stmt.to_sql()


# Helper wrappers for tests
class SqlServerPartitionClause(PartitionClause):
    """Test helper that constructs the KVS dict for scheme name."""

    def __init__(self, dialect, keys, *, partition_scheme):
        super().__init__(
            dialect,
            PartitionStrategy.RANGE,
            keys,
            dialect_options={"partition_scheme": partition_scheme},
        )


def _get_protocol_methods(protocol: type) -> Set[str]:
    """Extract public methods declared by a protocol."""
    return {
        name
        for name, value in protocol.__dict__.items()
        if not name.startswith("_") and callable(value)
    }
