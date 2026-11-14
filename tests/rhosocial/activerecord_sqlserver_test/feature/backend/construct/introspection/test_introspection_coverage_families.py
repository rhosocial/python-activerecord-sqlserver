# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/introspection/test_introspection_coverage_families.py
"""Offline tests for the partitions, types and constraints families.

SQL Server answers these three families from catalog views this backend did
not previously expose. What is asserted here is the whole local path: the
expression class renders through the dialect, the rendered statement keeps
caller values as bind parameters, and the parser folds the catalog's row
shape into the result type's record shape. No server is needed; the live
family coverage is the integration suite's question.

The identity audit is beside them because it belongs to the same round: the
column listing already asks ``COLUMNPROPERTY(..., 'IsIdentity')``, and the
assertions pin that the value reaches ``IntrospectionColumnInfo`` rather than
being selected and dropped.
"""

import inspect

import pytest

from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import (
    SQLServerConnectionConfig,
)
from rhosocial.activerecord.backend.impl.sqlserver.introspection import (
    AsyncSQLServerIntrospector,
    SQLServerIntrospector,
)


def make_introspector(version=(16, 0, 0)) -> SQLServerIntrospector:
    config = SQLServerConnectionConfig(
        host="localhost",
        port=1433,
        database="master",
        username="sa",
        password="",
    )
    backend = SQLServerBackend(connection_config=config, version=version)
    return SQLServerIntrospector(backend, executor=object())


class TestPartitionStatements:
    """The three catalogue questions behind one partition answer."""

    def test_function_list_reads_the_catalogue_and_parameter_type(self):
        sql, params = (
            make_introspector().partition_function_list_statement().to_sql()
        )
        assert "[sys].[partition_functions] AS [pf]" in sql
        assert "[sys].[partition_parameters] AS [pp]" in sql
        assert "TYPE_NAME([pp].[user_type_id]) AS [data_type]" in sql
        assert "TYPE_NAME([pp].[system_type_id]) AS [base_type]" in sql
        assert "[pf].[boundary_value_on_right]" in sql
        assert params == (), "the question names no caller value"

    def test_boundary_value_is_cast_off_the_sql_variant(self):
        """``value`` is sql_variant and pyodbc refuses to fetch it (HY106)."""
        sql, params = (
            make_introspector().partition_boundary_list_statement().to_sql()
        )
        assert (
            "CAST([prv].[value] AS NVARCHAR(4000)) AS [boundary_value]" in sql
        )
        assert params == ()

    def test_scheme_list_joins_destinations_to_filegroups(self):
        sql, params = (
            make_introspector().partition_scheme_list_statement().to_sql()
        )
        assert "[sys].[partition_schemes] AS [ps]" in sql
        assert "[sys].[destination_data_spaces] AS [dds]" in sql
        assert "[sys].[data_spaces] AS [ds]" in sql
        assert "[ps].[data_space_id] = [dds].[partition_scheme_id]" in sql
        assert params == ()

    def test_aligned_indexes_join_on_the_scheme_data_space(self):
        """An index is aligned when it shares the scheme's ``data_space_id``."""
        sql, params = (
            make_introspector().partition_aligned_index_list_statement().to_sql()
        )
        assert "[sys].[indexes] AS [i]" in sql
        assert "[i].[data_space_id] = [ps].[data_space_id]" in sql
        assert "[ic].[partition_ordinal] > 0" in sql
        assert params == (), "no table named, no caller value carried"

    def test_a_table_name_narrows_the_aligned_indexes(self):
        sql, params = (
            make_introspector()
            .partition_aligned_index_list_statement(
                table_name="orders", schema="sales"
            )
            .to_sql()
        )
        assert "[s].[name] = ?" in sql
        assert "[o].[name] = ?" in sql
        assert params == ("sales", "orders")
        assert "'sales'" not in sql and "'orders'" not in sql

    def test_a_table_name_defaults_the_schema(self):
        sql, params = (
            make_introspector()
            .partition_aligned_index_list_statement(table_name="orders")
            .to_sql()
        )
        assert params == ("dbo", "orders")

    def test_index_storage_is_measured_per_index(self):
        """Row and byte counts are this index's own partitions, not a sum."""
        sql, _ = (
            make_introspector().partition_aligned_index_list_statement().to_sql()
        )
        assert sql.count("[sys].[dm_db_partition_stats] AS [st]") == 2
        assert "[st].[object_id] = [i].[object_id]" in sql
        assert "[st].[index_id] = [i].[index_id]" in sql
        assert "* 8192 AS [size_bytes]" in sql


class TestParsePartitions:
    """The four row shapes fold into one record per partition function."""

    @staticmethod
    def _functions():
        return [
            {
                "partition_function": "pf_orders",
                "function_id": 11,
                "type_desc": "RANGE",
                "fanout": 3,
                "boundary_value_on_right": 1,
                "data_type": "datetime2",
                "base_type": "datetime2",
                "parameter_id": 1,
            }
        ]

    @staticmethod
    def _boundaries():
        return [
            {"function_id": 11, "boundary_id": 2, "parameter_id": 1,
             "boundary_value": "2026-02-01"},
            {"function_id": 11, "boundary_id": 1, "parameter_id": 1,
             "boundary_value": "2026-01-01"},
        ]

    @staticmethod
    def _schemes():
        return [
            {"scheme_name": "ps_orders", "scheme_id": 21, "function_id": 11,
             "destination_id": 2, "filegroup_name": "fg_2"},
            {"scheme_name": "ps_orders", "scheme_id": 21, "function_id": 11,
             "destination_id": 1, "filegroup_name": "fg_1"},
        ]

    @staticmethod
    def _indexes():
        return [
            {
                "scheme_name": "ps_orders",
                "function_id": 11,
                "schema_name": "dbo",
                "table_name": "orders",
                "index_name": "PK_orders",
                "index_id": 1,
                "index_type": "CLUSTERED",
                "is_unique": 1,
                "is_primary_key": 1,
                "partition_column": "created_at",
                "partition_ordinal": 1,
                "row_count": 120,
                "size_bytes": 8192,
            }
        ]

    def _parse(self, table_name=None):
        return make_introspector().parse_partitions(
            self._functions(), self._boundaries(), self._schemes(),
            self._indexes(), table_name,
        )

    def test_function_level_fields_are_read(self):
        partition = self._parse()[0]
        assert partition.name == "pf_orders"
        assert partition.function_id == 11
        assert partition.fanout == 3
        assert partition.range_direction == "RIGHT"
        assert partition.data_type == "datetime2"

    def test_boundary_value_bits_read_left_when_the_flag_is_clear(self):
        rows = self._functions()
        rows[0]["boundary_value_on_right"] = 0
        partition = make_introspector().parse_partitions(
            rows, self._boundaries(), self._schemes(), self._indexes()
        )[0]
        assert partition.range_direction == "LEFT"

    def test_boundaries_are_ordered_and_folded(self):
        assert self._parse()[0].boundary_values == (
            "2026-01-01", "2026-02-01"
        )

    def test_scheme_keeps_its_filegroups(self):
        scheme = self._parse()[0].schemes[0]
        assert (scheme.name, scheme.data_space_id) == ("ps_orders", 21)
        assert scheme.filegroups == ("fg_1", "fg_2")

    def test_aligned_index_keeps_its_partitioning_column_and_storage(self):
        index = self._parse()[0].indexes[0]
        assert (index.schema, index.table, index.name) == ("dbo", "orders", "PK_orders")
        assert index.columns == ("created_at",)
        assert (index.row_count, index.size_bytes) == (120, 8192)

    def test_a_table_filter_keeps_only_the_functions_it_uses(self):
        functions = self._functions() + [
            {"partition_function": "pf_unused", "function_id": 12,
             "fanout": 2, "boundary_value_on_right": 1}
        ]
        partitions = make_introspector().parse_partitions(
            functions, self._boundaries(), self._schemes(), self._indexes(),
            table_name="orders",
        )
        assert [partition.name for partition in partitions] == ["pf_orders"]

    def test_a_function_no_index_uses_is_kept_without_a_table_filter(self):
        functions = self._functions() + [
            {"partition_function": "pf_unused", "function_id": 12,
             "fanout": 2, "boundary_value_on_right": 1}
        ]
        partitions = make_introspector().parse_partitions(
            functions, self._boundaries(), self._schemes(), self._indexes()
        )
        assert {partition.name for partition in partitions} == {
            "pf_orders", "pf_unused"
        }

    def test_a_schema_filter_keeps_only_the_functions_used_there(self):
        sales_indexes = self._indexes()
        sales_indexes[0]["schema_name"] = "sales"
        partitions = make_introspector().parse_partitions(
            self._functions(), self._boundaries(), self._schemes(),
            sales_indexes, schema="sales",
        )
        assert [partition.name for partition in partitions] == ["pf_orders"]
        assert make_introspector().parse_partitions(
            self._functions(), self._boundaries(), self._schemes(),
            [], schema="dbo",
        ) == []


class TestTypeStatements:
    """``sys.types`` with its table-type and description joins."""

    def test_schema_is_a_bind_parameter(self):
        sql, params = make_introspector().type_list_statement(schema="sales").to_sql()
        assert "[s].[name] = ?" in sql
        assert params == ("sales",)
        assert "'sales'" not in sql

    def test_schema_defaults_to_dbo(self):
        sql, params = make_introspector().type_list_statement().to_sql()
        assert params == ("dbo",)

    def test_only_user_defined_types_are_asked_for(self):
        sql, _ = make_introspector().type_list_statement().to_sql()
        assert "[t].[is_user_defined] = 1" in sql

    def test_table_types_add_the_object_whose_columns_are_counted(self):
        sql, _ = make_introspector().type_list_statement().to_sql()
        assert "[sys].[table_types] AS [tt]" in sql
        assert "[tt].[type_table_object_id]" in sql
        assert "COUNT(*) FROM [sys].[columns] AS [c]" in sql

    def test_description_comes_from_the_type_class(self):
        sql, _ = make_introspector().type_list_statement().to_sql()
        assert "[ep].[class_desc] = 'TYPE'" in sql
        assert "[ep].[major_id] = [t].[user_type_id]" in sql
        assert "AS [type_comment]" in sql


class TestParseTypes:
    def _parse_one(self, **overrides):
        row = {
            "type_name": "order_note",
            "schema_name": "dbo",
            "base_type": "nvarchar",
            "max_length": 40,
            "precision": 0,
            "scale": 0,
            "collation": "Latin1_General_CI_AS",
            "is_nullable": 1,
            "is_user_defined": 1,
            "is_table_type": 0,
            "is_assembly_type": 0,
            "default_object_id": 0,
            "rule_object_id": 7,
            "column_count": 0,
            "type_comment": "a note",
        }
        row.update(overrides)
        return make_introspector().parse_types([row])[0]

    def test_an_alias_type_keeps_its_base_and_length(self):
        type_ = self._parse_one()
        assert type_.kind == "ALIAS_TYPE"
        assert type_.base_type == "nvarchar"
        assert type_.max_length == 40
        assert type_.rule_object_id == 7
        assert type_.comment == "a note"
        assert type_.column_count is None

    def test_a_table_type_is_named_and_counted(self):
        type_ = self._parse_one(
            type_name="order_line", is_table_type=1, column_count=3
        )
        assert type_.kind == "TABLE_TYPE"
        assert type_.is_table_type is True
        assert type_.column_count == 3

    def test_a_clr_type_is_named_as_one(self):
        type_ = self._parse_one(
            type_name="geo_point", is_assembly_type=1, base_type="geometry"
        )
        assert type_.kind == "CLR_TYPE"
        assert type_.is_assembly_type is True


class TestConstraintStatements:
    """One ``sys.objects`` question with each family's view joined."""

    def test_the_five_constraint_codes_are_the_question(self):
        sql, _ = make_introspector().constraint_list_statement().to_sql()
        assert "[o].[type] IN ('PK', 'UQ', 'F', 'C', 'D')" in sql

    def test_schema_is_a_bind_parameter_and_table_is_optional(self):
        sql, params = (
            make_introspector().constraint_list_statement(
                table_name="orders", schema="sales"
            ).to_sql()
        )
        assert "[s].[name] = ?" in sql
        assert "[t].[name] = ?" in sql
        assert params == ("sales", "orders")

    def test_no_table_name_asks_for_the_schema(self):
        sql, params = make_introspector().constraint_list_statement().to_sql()
        assert "[t].[name] = ?" not in sql
        assert params == ("dbo",)

    def test_each_family_is_joined_on_its_object_id(self):
        sql, _ = make_introspector().constraint_list_statement().to_sql()
        for view in (
            "check_constraints",
            "default_constraints",
            "foreign_keys",
            "key_constraints",
        ):
            assert f"[sys].[{view}] AS " in sql
        assert "[cc].[object_id] = [o].[object_id]" in sql
        assert "[dc].[object_id] = [o].[object_id]" in sql
        assert "[fk].[object_id] = [o].[object_id]" in sql
        assert "[kc].[object_id] = [o].[object_id]" in sql

    def test_foreign_key_columns_and_reference_are_joined(self):
        sql, _ = make_introspector().constraint_list_statement().to_sql()
        assert "[sys].[foreign_key_columns] AS [fkc]" in sql
        assert "[sys].[tables] AS [rt]" in sql
        assert "[sys].[schemas] AS [rs]" in sql
        assert "[fkc].[referenced_column_id]" in sql

    def test_primary_key_columns_come_from_the_unique_index(self):
        sql, _ = make_introspector().constraint_list_statement().to_sql()
        assert "[ic].[object_id] = [kc].[parent_object_id]" in sql
        assert "[ic].[index_id] = [kc].[unique_index_id]" in sql
        assert "[ic].[key_ordinal] > 0" in sql

    def test_system_constraints_are_not_in_the_listing(self):
        sql, _ = make_introspector().constraint_list_statement().to_sql()
        assert "[o].[is_ms_shipped] = 0" in sql


class TestParseConstraints:
    @staticmethod
    def _parse(rows):
        return make_introspector().parse_constraints(rows)

    def test_primary_key_columns_are_ordered_by_key_ordinal(self):
        rows = [
            {"constraint_name": "pk_orders", "schema_name": "dbo",
             "table_name": "orders", "constraint_type": "PK",
             "constraint_type_desc": "PRIMARY_KEY_CONSTRAINT",
             "key_ordinal": 2, "key_column": "tenant_id"},
            {"constraint_name": "pk_orders", "schema_name": "dbo",
             "table_name": "orders", "constraint_type": "PK",
             "constraint_type_desc": "PRIMARY_KEY_CONSTRAINT",
             "key_ordinal": 1, "key_column": "id"},
        ]
        constraint = self._parse(rows)[0]
        assert constraint.constraint_type == "PK"
        assert constraint.columns == ("id", "tenant_id")

    def test_foreign_key_columns_and_reference_are_folded(self):
        rows = [
            {"constraint_name": "fk_order_customer", "schema_name": "dbo",
             "table_name": "orders", "constraint_type": "F",
             "constraint_type_desc": "FOREIGN_KEY_CONSTRAINT",
             "fk_ordinal": 1, "fk_column": "customer_id",
             "fk_referenced_column": "id", "referenced_schema": "dbo",
             "referenced_table": "customers", "on_delete": "CASCADE",
             "on_update": "NO_ACTION", "fk_disabled": 0, "fk_not_trusted": 1},
        ]
        constraint = self._parse(rows)[0]
        assert constraint.columns == ("customer_id",)
        assert constraint.referenced_columns == ("id",)
        assert (constraint.referenced_schema, constraint.referenced_table) == (
            "dbo", "customers",
        )
        assert (constraint.delete_action, constraint.update_action) == (
            "CASCADE", "NO_ACTION",
        )
        assert constraint.is_disabled is False
        assert constraint.is_not_trusted is True

    def test_check_constraint_carries_its_expression_and_flags(self):
        rows = [
            {"constraint_name": "ck_orders_total", "schema_name": "dbo",
             "table_name": "orders", "constraint_type": "C",
             "constraint_type_desc": "CHECK_CONSTRAINT",
             "check_column": "total", "check_column_id": 3,
             "check_definition": "([total] > (0))", "check_disabled": 1,
             "check_not_trusted": 1},
        ]
        constraint = self._parse(rows)[0]
        assert constraint.constraint_type == "C"
        assert constraint.columns == ("total",)
        assert constraint.definition == "([total] > (0))"
        assert constraint.is_disabled is True
        assert constraint.is_not_trusted is True

    def test_default_constraint_carries_its_expression(self):
        rows = [
            {"constraint_name": "df_orders_status", "schema_name": "dbo",
             "table_name": "orders", "constraint_type": "D",
             "constraint_type_desc": "DEFAULT_CONSTRAINT",
             "default_column": "status", "default_column_id": 4,
             "default_definition": "('pending')"},
        ]
        constraint = self._parse(rows)[0]
        assert constraint.constraint_type == "D"
        assert constraint.columns == ("status",)
        assert constraint.definition == "('pending')"
        assert constraint.is_disabled is None

    def test_a_primary_key_does_not_acquire_the_foreign_key_columns(self):
        rows = [
            {"constraint_name": "pk_orders", "schema_name": "dbo",
             "table_name": "orders", "constraint_type": "PK",
             "key_ordinal": 1, "key_column": "id",
             "fk_ordinal": None, "fk_column": None},
        ]
        constraint = self._parse(rows)[0]
        assert constraint.columns == ("id",)
        assert constraint.referenced_columns == ()

    def test_constraints_are_ordered_by_schema_table_and_name(self):
        rows = [
            {"constraint_name": "z", "schema_name": "dbo",
             "table_name": "orders", "constraint_type": "C"},
            {"constraint_name": "a", "schema_name": "dbo",
             "table_name": "orders", "constraint_type": "D"},
        ]
        assert [c.name for c in self._parse(rows)] == ["a", "z"]


class TestAsyncParity:
    """The asynchronous manager answers the same three questions."""

    @pytest.mark.parametrize(
        ("sync_method", "async_method"),
        [
            ("list_partitions", "list_partitions"),
            ("list_types", "list_types"),
            ("get_type_info", "get_type_info"),
            ("list_constraints", "list_constraints"),
        ],
    )
    def test_the_async_class_has_the_same_method_with_the_same_parameters(
        self, sync_method, async_method
    ):
        sync_parameters = inspect.signature(
            getattr(SQLServerIntrospector, sync_method)
        ).parameters
        async_parameters = inspect.signature(
            getattr(AsyncSQLServerIntrospector, async_method)
        ).parameters
        assert list(sync_parameters) == list(async_parameters)
        assert inspect.iscoroutinefunction(
            getattr(AsyncSQLServerIntrospector, async_method)
        )

    def test_the_async_parsers_are_the_same_functions(self):
        for name in ("parse_partitions", "parse_types", "parse_constraints"):
            sync_parser = getattr(SQLServerIntrospector, name)
            async_parser = getattr(AsyncSQLServerIntrospector, name)
            assert sync_parser is async_parser


class _AsyncExecutor:
    """Answer each catalogue question with the rows the test declared."""

    def __init__(self) -> None:
        self.calls = []

    async def execute(self, sql, params):
        self.calls.append((sql, params))
        return _rows_for(sql)


class _SyncExecutor:
    """The synchronous shape of :class:`_AsyncExecutor`."""

    def __init__(self) -> None:
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))
        return _rows_for(sql)


def _rows_for(sql):
    if "partition_functions" in sql:
        return [_function_row()]
    if "partition_range_values" in sql:
        return [_boundary_row()]
    if "key_constraints" in sql:
        return [_constraint_row()]
    if "index_columns" in sql:
        return [_index_row()]
    if "partition_schemes" in sql:
        return [_scheme_row()]
    if "table_types" in sql:
        return [_type_row()]
    return []


def _function_row():
    return {
        "partition_function": "pf_orders", "function_id": 11, "fanout": 2,
        "boundary_value_on_right": 1, "data_type": "datetime2",
        "base_type": "datetime2",
    }


def _boundary_row():
    return {
        "function_id": 11, "boundary_id": 1, "parameter_id": 1,
        "boundary_value": "2026-01-01",
    }


def _scheme_row():
    return {
        "scheme_name": "ps_orders", "scheme_id": 21, "function_id": 11,
        "destination_id": 1, "filegroup_name": "fg_1",
    }


def _index_row():
    return {
        "scheme_name": "ps_orders", "function_id": 11, "schema_name": "dbo",
        "table_name": "orders", "index_name": "PK_orders", "index_id": 1,
        "index_type": "CLUSTERED", "is_unique": 1, "is_primary_key": 1,
        "partition_column": "created_at", "partition_ordinal": 1,
        "row_count": 2, "size_bytes": 8192,
    }


def _type_row():
    return {
        "type_name": "order_note", "schema_name": "dbo", "base_type": "nvarchar",
        "max_length": 40, "is_nullable": 1, "is_user_defined": 1,
        "is_table_type": 0, "is_assembly_type": 0,
    }


def _constraint_row():
    return {
        "constraint_name": "ck_orders_total", "schema_name": "dbo",
        "table_name": "orders", "constraint_type": "C",
        "constraint_type_desc": "CHECK_CONSTRAINT", "check_column": "total",
        "check_definition": "([total] > (0))", "check_disabled": 0,
        "check_not_trusted": 0,
    }


class TestAsyncExecution:
    """The await path reaches the same parsers and result types."""

    def _introspector(self):
        return AsyncSQLServerIntrospector(
            make_introspector()._backend, executor=_AsyncExecutor()
        )

    @pytest.mark.asyncio
    async def test_list_partitions_executes_all_four_questions(self):
        introspector = self._introspector()
        partitions = await introspector.list_partitions("orders")
        assert [partition.name for partition in partitions] == ["pf_orders"]
        assert len(introspector._executor.calls) == 4
        last_params = introspector._executor.calls[-1][1]
        assert last_params == ("dbo", "orders")

    @pytest.mark.asyncio
    async def test_list_types_and_get_type_info_answer(self):
        introspector = self._introspector()
        types = await introspector.list_types()
        assert types[0].name == "order_note"
        assert await introspector.get_type_info("order_note") == types[0]
        assert await introspector.get_type_info("missing") is None

    @pytest.mark.asyncio
    async def test_list_constraints_answers(self):
        introspector = self._introspector()
        constraints = await introspector.list_constraints("orders")
        assert constraints[0].constraint_type == "C"


class TestSyncExecution:
    """The synchronous manager reaches the same parsers and result types."""

    def _introspector(self):
        return SQLServerIntrospector(
            make_introspector()._backend, executor=_SyncExecutor()
        )

    def test_list_partitions_executes_all_four_questions(self):
        introspector = self._introspector()
        partitions = introspector.list_partitions("orders")
        assert [partition.name for partition in partitions] == ["pf_orders"]
        assert len(introspector._executor.calls) == 4
        assert introspector._executor.calls[-1][1] == ("dbo", "orders")

    def test_list_types_and_get_type_info_answer(self):
        introspector = self._introspector()
        types = introspector.list_types()
        assert types[0].name == "order_note"
        assert introspector.get_type_info("order_note") == types[0]
        assert introspector.get_type_info("missing") is None

    def test_list_constraints_answers(self):
        introspector = self._introspector()
        constraints = introspector.list_constraints("orders")
        assert constraints[0].constraint_type == "C"


class TestIdentityAudit:
    """IDENTITY columns must report ``is_auto_increment``."""

    @staticmethod
    def _parse_one(**catalog):
        row = {
            "COLUMN_NAME": "id",
            "DATA_TYPE": "int",
            "ORDINAL_POSITION": 1,
            "IS_NULLABLE": "NO",
            **catalog,
        }
        return make_introspector().parse_columns([row], "t", "dbo")[0]

    def test_identity_flag_becomes_auto_increment(self):
        column = self._parse_one(IS_IDENTITY=1)
        assert column.is_auto_increment is True

    def test_a_non_identity_column_is_not_auto_increment(self):
        assert self._parse_one(IS_IDENTITY=0).is_auto_increment is False
        assert self._parse_one().is_auto_increment is False

    def test_a_text_flag_does_not_read_zero_as_truthy(self):
        """``bool("0")`` is ``True``; the flag is parsed, not coerced."""
        assert self._parse_one(IS_IDENTITY="0").is_auto_increment is False
        assert self._parse_one(IS_IDENTITY="1").is_auto_increment is True

    def test_the_column_question_projects_the_identity_property(self):
        """The flag is selected by ``COLUMNPROPERTY``, not inferred later."""
        from rhosocial.activerecord.backend.expression.introspection import (
            ColumnInfoQueryStatement,
        )

        sql, _ = ColumnInfoQueryStatement(
            make_introspector()._backend.dialect, "users", schema="dbo"
        ).to_sql()
        assert "COLUMNPROPERTY" in sql
        assert "IsIdentity" in sql
        assert "IS_IDENTITY" in sql


class TestCapabilitySwitches:
    def test_the_three_local_switches_answer_true(self):
        dialect = make_introspector(version=(16, 0, 0))._backend.dialect
        assert dialect.supports_partition_info() is True
        assert dialect.supports_partition_metadata_introspection() is True
        assert dialect.supports_type_introspection() is True
        assert dialect.supports_constraint_introspection() is True

    def test_partition_metadata_follows_the_partitioning_floor(self):
        dialect = make_introspector(version=(9, 0, 0))._backend.dialect
        assert dialect.supports_partition_info() is False
        assert dialect.supports_partition_metadata_introspection() is False

    def test_type_introspection_follows_the_table_type_floor(self):
        """``sys.table_types`` and ``is_table_type`` arrived with 2008."""
        dialect = make_introspector(version=(9, 0, 0))._backend.dialect
        assert dialect.supports_type_introspection() is False
        newer = make_introspector(version=(10, 0, 0))._backend.dialect
        assert newer.supports_type_introspection() is True
