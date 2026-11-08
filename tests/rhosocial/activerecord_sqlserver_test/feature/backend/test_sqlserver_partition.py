from datetime import date
from typing import Set

import pytest
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect import protocols as dialect_protocols
from rhosocial.activerecord.backend.expression import (
    Column,
    CreateTableStatement,
    ColumnDefinition,
)
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import (
    PartitionClause,
    PartitionStrategy,
    ColumnConstraint,
    ColumnPrimaryKeyConstraint,
)
from rhosocial.activerecord.backend.expression.types import DateType, IntegerType, VarCharType
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.protocols import SQLServerPartitionSupport
from rhosocial.activerecord.backend.impl.sqlserver.expression.partition import (
    SQLServerPartitionFunctionExpression,
    SQLServerPartitionSchemeExpression,
    SQLServerPartitionByRangeClause,
    SQLServerPartitionRangeDirection,
    SQLServerPartitionFunctionSplitExpression,
    SQLServerPartitionFunctionMergeExpression,
    SQLServerPartitionSchemeNextUsedExpression,
    SQLServerSwitchPartitionExpression,
    SQLServerDropPartitionFunctionExpression,
    SQLServerDropPartitionSchemeExpression,
    SQLServerPartitionFunctionQueryStatement,
    SQLServerPartitionSchemeQueryStatement,
    SQLServerPartitionTableQueryStatement,
    SQLServerPartitionRangeQueryStatement,
    SQLServerPartitionBoundaryQueryStatement,
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
        partition = SQLServerPartitionByRangeClause(d, [col], "ps_sales")
        sql, params = d.format_partition_clause(partition)
        assert "ON [ps_sales] ([create_date])" in sql
        assert params == ()

    def test_format_partition_clause_multiple_keys(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        col1 = Column(d, "year")
        col2 = Column(d, "month")
        partition = SQLServerPartitionByRangeClause(d, [col1, col2], "ps_date")
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
        pk = ColumnConstraint(d, branch=ColumnPrimaryKeyConstraint(d))
        col_def = ColumnDefinition(d, "id", IntegerType(d), constraints=[pk])
        col_def2 = ColumnDefinition(d, "name", VarCharType(d, length=100))
        col_def3 = ColumnDefinition(d, "create_date", DateType(d))

        col = Column(d, "create_date")
        partition = SqlServerPartitionClause(
            d, [col],
            partition_scheme="ps_sales",
        )

        stmt = CreateTableStatement(
            d, Table(d, "orders"),
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
        pk = ColumnConstraint(d, branch=ColumnPrimaryKeyConstraint(d))
        col_def = ColumnDefinition(d, "id", IntegerType(d), constraints=[pk])
        stmt = CreateTableStatement(
            d, Table(d, "users"),
            columns=[col_def],
        )
        sql, params = stmt.to_sql()
        assert "CREATE TABLE" in sql
        assert "[users]" in sql
        assert "ON" not in sql

    def test_create_table_with_partition_on_old_version(self):
        """Should fail on SQL Server 2005 which doesn't support partitioning."""
        d = SQLServerDialect(SQL_SERVER_2005)
        pk = ColumnConstraint(d, branch=ColumnPrimaryKeyConstraint(d))
        col_def = ColumnDefinition(d, "id", IntegerType(d), constraints=[pk])
        col = Column(d, "id")
        partition = SQLServerPartitionByRangeClause(d, [col], "ps_test")
        stmt = CreateTableStatement(
            d, Table(d, "test"),
            columns=[col_def],
            partition=partition,
        )
        with pytest.raises(UnsupportedFeatureError):
            stmt.to_sql()


class TestSQLServerPartitionMaintenanceExpressions:
    """SPLIT/MERGE/SWITCH/NEXT USED and the two drops."""

    def test_split_range(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        expr = SQLServerPartitionFunctionSplitExpression(
            d, "pf_sales", date(2026, 2, 1)
        )
        sql, params = expr.to_sql()
        assert sql == (
            "ALTER PARTITION FUNCTION [pf_sales] () "
            "SPLIT RANGE ('2026-02-01')"
        )
        assert params == ()

    def test_merge_range_accepts_a_dotted_function_name(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        expr = SQLServerPartitionFunctionMergeExpression(
            d, "dbo.pf_sales", date(2026, 2, 1)
        )
        sql, _ = expr.to_sql()
        assert sql == (
            "ALTER PARTITION FUNCTION [dbo].[pf_sales] () "
            "MERGE RANGE ('2026-02-01')"
        )

    def test_next_used(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        expr = SQLServerPartitionSchemeNextUsedExpression(
            d, "ps_sales", "PRIMARY"
        )
        sql, _ = expr.to_sql()
        assert sql == "ALTER PARTITION SCHEME [ps_sales] NEXT USED [PRIMARY]"

    def test_switch_one_partition(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        expr = SQLServerSwitchPartitionExpression(
            d, "logs", "logs_archive", source_partition=2
        )
        sql, params = expr.to_sql()
        assert sql == (
            "ALTER TABLE [logs] SWITCH PARTITION 2 TO [logs_archive]"
        )
        assert params == ()

    def test_switch_with_schemas_on_both_tables(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        expr = SQLServerSwitchPartitionExpression(
            d,
            "logs",
            "logs_archive",
            source_partition=1,
            schema="dbo",
            target_schema="dbo",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            "ALTER TABLE [dbo].[logs] SWITCH PARTITION 1 "
            "TO [dbo].[logs_archive]"
        )

    def test_switch_whole_table(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        expr = SQLServerSwitchPartitionExpression(d, "logs", "logs_archive")
        sql, _ = expr.to_sql()
        assert sql == "ALTER TABLE [logs] SWITCH TO [logs_archive]"

    def test_switch_refuses_dots_and_a_separate_schema(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        with pytest.raises(ValueError, match="must not carry dots"):
            SQLServerSwitchPartitionExpression(
                d, "dbo.logs", "archive", schema="dbo"
            )

    def test_switch_refuses_a_non_positive_partition(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        with pytest.raises(ValueError, match="positive integer"):
            SQLServerSwitchPartitionExpression(
                d, "logs", "archive", source_partition=0
            )

    def test_drops(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        assert SQLServerDropPartitionFunctionExpression(
            d, "pf_sales"
        ).to_sql() == ("DROP PARTITION FUNCTION [pf_sales]", ())
        assert SQLServerDropPartitionSchemeExpression(
            d, "ps_sales"
        ).to_sql() == ("DROP PARTITION SCHEME [ps_sales]", ())

    def test_split_and_merge_are_refused_on_old_versions(self):
        d = SQLServerDialect(SQL_SERVER_2005)
        with pytest.raises(UnsupportedFeatureError):
            SQLServerPartitionFunctionSplitExpression(
                d, "pf", date(2026, 1, 1)
            ).to_sql()
        with pytest.raises(UnsupportedFeatureError):
            SQLServerPartitionFunctionMergeExpression(
                d, "pf", date(2026, 1, 1)
            ).to_sql()


class TestSQLServerPartitionCatalogueQuestions:
    """The questions maintenance asks of ``sys.partition_*``."""

    def test_function_list_projects_boundaries_and_type(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        sql, params = SQLServerPartitionFunctionQueryStatement(d).to_sql()
        assert params == ()
        assert "FROM sys.partition_functions AS pf" in sql
        assert "sys.partition_range_values AS prv" in sql
        assert "boundary_value_on_right" in sql
        assert "SQL_VARIANT_PROPERTY" in sql
        assert "ORDER BY pf.name, prv.boundary_id" in sql

    def test_function_list_takes_one_optional_name(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        sql, params = SQLServerPartitionFunctionQueryStatement(
            d, function_name="pf_sales"
        ).to_sql()
        assert "WHERE pf.name = ?" in sql
        assert params == ("pf_sales",)

    def test_scheme_list_projects_destinations(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        sql, params = SQLServerPartitionSchemeQueryStatement(d).to_sql()
        assert "sys.partition_schemes AS ps" in sql
        assert "sys.destination_data_spaces AS dds" in sql
        assert params == ()

    def test_scheme_list_filters_by_function_and_name(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        sql, params = SQLServerPartitionSchemeQueryStatement(
            d, scheme_name="ps_sales", function_name="pf_sales"
        ).to_sql()
        assert "WHERE ps.name = ? AND pf.name = ?" in sql
        assert params == ("ps_sales", "pf_sales")

    def test_table_list_resolves_the_partition_column(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        sql, params = SQLServerPartitionTableQueryStatement(
            d, table_name="logs", schema="dbo"
        ).to_sql()
        assert "sys.index_columns AS ic" in sql
        assert "partition_ordinal = 1" in sql
        assert "WHERE s.name = ? AND t.name = ?" in sql
        assert params == ("dbo", "logs")

    def test_range_list_carries_bounds_rows_and_pages(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        sql, params = SQLServerPartitionRangeQueryStatement(
            d, table_name="logs", schema="dbo"
        ).to_sql()
        assert "WITH boundary_text AS" in sql
        assert "sys.dm_db_partition_stats AS stats" in sql
        assert "stats.partition_number" in sql
        assert "stats.used_page_count" in sql
        assert "WHERE s.name = ? AND t.name = ?" in sql
        assert params == ("dbo", "logs")

    def test_boundary_question_casts_to_the_function_type(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        sql, params = SQLServerPartitionBoundaryQueryStatement(
            d,
            function_name="pf_sales",
            data_type="DATE",
            boundary_value=date(2026, 1, 1),
        ).to_sql()
        assert "prv.value = CAST(? AS DATE)" in sql
        assert params == ("pf_sales", date(2026, 1, 1))

    def test_boundary_question_refuses_an_unsafe_type(self):
        d = SQLServerDialect(SQL_SERVER_2022)
        with pytest.raises(ValueError, match="invalid partition-function data type"):
            SQLServerPartitionBoundaryQueryStatement(
                d,
                function_name="pf",
                data_type="DATE; DROP TABLE x",
                boundary_value=date(2026, 1, 1),
            )


# Helper wrappers for tests
class SqlServerPartitionClause(SQLServerPartitionByRangeClause):
    """Test helper that constructs the KVS dict for scheme name."""

    def __init__(self, dialect, keys, *, partition_scheme):
        super().__init__(dialect, keys, partition_scheme)


def _get_protocol_methods(protocol: type) -> Set[str]:
    """Extract public methods declared by a protocol."""
    return {
        name
        for name, value in protocol.__dict__.items()
        if not name.startswith("_") and callable(value)
    }
