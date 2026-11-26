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
from rhosocial.activerecord.backend.dialect.exceptions import (
    ProtocolNotImplementedError,
)
from rhosocial.activerecord.backend.introspection import ItemKind

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


class TestPartitionStateQuestions:
    """The catalogue questions behind the neutral partition answer."""

    def test_table_question_reads_scheme_function_and_key(self):
        sql, params = make_introspector().partition_table_statement(
            table_name="orders", schema="dbo"
        ).to_sql()
        assert "sys.partition_schemes AS ps" in sql
        assert "sys.partition_functions AS pf" in sql
        assert "partition_ordinal = 1" in sql
        assert params == ("dbo", "orders")

    def test_function_question_names_the_direction_and_orders_boundaries(self):
        sql, params = make_introspector().partition_function_statement(
            function_name="pf_orders"
        ).to_sql()
        assert "pf.boundary_value_on_right" in sql
        assert "SQL_VARIANT_PROPERTY" in sql
        assert "ORDER BY pf.name, prv.boundary_id" in sql
        assert params == ("pf_orders",)

    def test_range_question_is_the_only_statistics_read(self):
        sql, params = make_introspector().partition_range_statement(
            table_name="orders", schema="dbo"
        ).to_sql()
        assert "sys.dm_db_partition_stats AS stats" in sql
        assert "stats.partition_number" in sql
        assert "stats.used_page_count" in sql
        assert "low_b.boundary_value AS low_boundary" in sql
        assert params == ("dbo", "orders")


class TestParsePartitionState:
    """The catalogue rows fold into core's neutral ``PartitionState``."""

    @staticmethod
    def _table():
        return [
            {
                "scheme_name": "ps_orders",
                "function_name": "pf_orders",
                "partition_column": "created_at",
                "partition_count": 3,
            }
        ]

    @staticmethod
    def _functions():
        return [
            {
                "boundary_value_on_right": 1,
                "partition_count": 3,
                "boundary_id": 1,
                "boundary_value": "2026-01-01",
            },
            {
                "boundary_value_on_right": 1,
                "partition_count": 3,
                "boundary_id": 2,
                "boundary_value": "2026-02-01",
            },
        ]

    @staticmethod
    def _ranges():
        return [
            {
                "partition_number": 1,
                "row_count": 120,
                "used_page_count": 3,
                "low_boundary": None,
                "high_boundary": "2026-01-01",
            },
            {
                "partition_number": 2,
                "row_count": 80,
                "used_page_count": 2,
                "low_boundary": "2026-01-01",
                "high_boundary": "2026-02-01",
            },
            {
                "partition_number": 3,
                "row_count": 40,
                "used_page_count": 1,
                "low_boundary": "2026-02-01",
                "high_boundary": None,
            },
        ]

    def _parse(self, *, include_stats=False, range_rows=None):
        return make_introspector().parse_partition_state(
            self._table(),
            self._functions(),
            self._ranges() if range_rows is None else range_rows,
            include_stats=include_stats,
        )

    def test_an_unpartitioned_table_has_no_scheme(self):
        state = make_introspector().parse_partition_state(
            [], [], [], include_stats=False
        )
        assert state is None

    def test_scheme_key_and_direction_are_the_neutral_answer(self):
        state = self._parse()
        assert state.scheme.value == "range"
        assert state.key_expression == "created_at"
        assert state.key_columns == ("created_at",)
        assert state.raw["scheme_name"] == "ps_orders"
        assert state.raw["range_direction"] == "RIGHT"
        assert state.raw["function_name"] == "pf_orders"

    def test_the_direction_is_read_from_the_function_flag(self):
        functions = self._functions()
        for row in functions:
            row["boundary_value_on_right"] = 0
        state = make_introspector().parse_partition_state(
            self._table(), functions, [], include_stats=False
        )
        assert state.raw["range_direction"] == "LEFT"

    def test_bounds_come_from_the_boundary_rows_without_statistics(self):
        state = self._parse()
        assert [bound.name for bound in state.bounds] == ["p1", "p2", "p3"]
        assert [bound.upper for bound in state.bounds] == [
            "2026-01-01", "2026-02-01", None,
        ]
        assert state.bounds[-1].is_maxvalue is True
        assert all(bound.row_count is None for bound in state.bounds)
        assert all(bound.size_bytes is None for bound in state.bounds)

    def test_statistics_fill_row_count_and_size_only_when_asked(self):
        state = self._parse(include_stats=True)
        assert [bound.name for bound in state.bounds] == ["p1", "p2", "p3"]
        assert [bound.row_count for bound in state.bounds] == [120, 80, 40]
        assert [bound.size_bytes for bound in state.bounds] == [24576, 16384, 8192]

    def test_a_statistics_request_that_came_back_empty_still_answers_bounds(self):
        state = self._parse(include_stats=True, range_rows=[])
        assert [bound.name for bound in state.bounds] == ["p1", "p2", "p3"]
        assert all(bound.row_count is None for bound in state.bounds)

    def test_the_function_answers_one_partition_when_it_has_no_boundary(self):
        table = self._table()
        table[0]["partition_count"] = 1
        state = make_introspector().parse_partition_state(
            table, [], [], include_stats=False
        )
        assert len(state.bounds) == 1
        assert state.bounds[0].upper is None
        assert state.bounds[0].is_maxvalue is True


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
    """The asynchronous manager answers the same questions."""

    @pytest.mark.parametrize(
        ("sync_method", "async_method"),
        [
            ("get_partition_state", "get_partition_state"),
            ("list_types", "list_types"),
            ("get_type_info", "get_type_info"),
            ("list_constraints", "list_constraints"),
            ("list_index_states", "list_index_states"),
            ("list_constraint_states", "list_constraint_states"),
            ("list_derived_objects", "list_derived_objects"),
            ("item_exists", "item_exists"),
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
        for name in (
            "parse_partition_state",
            "parse_sequence_states",
            "parse_types",
            "parse_constraints",
        ):
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


class _NoQueries:
    """Fail if a kind without a catalogue query reaches the executor."""

    def execute(self, sql, params):
        raise AssertionError(
            "a kind without a catalogue query must not reach the executor"
        )


class _AsyncNoQueries:
    """The asynchronous shape of :class:`_NoQueries`."""

    async def execute(self, sql, params):
        raise AssertionError(
            "a kind without a catalogue query must not reach the executor"
        )


def _rows_for(sql):
    if "dm_db_partition_stats" in sql and "boundary_text" in sql:
        return _partition_range_rows()
    if "sys.partition_functions AS pf" in sql:
        return _partition_function_rows()
    if "sys.destination_data_spaces AS dds" in sql:
        return [_scheme_row()]
    if "sys.partition_schemes AS ps" in sql:
        return [_partition_table_row()]
    if "history_table_id" in sql:
        return [_history_row()]
    if "[sys].[database_principals] AS [p]" in sql:
        return [{"schema_id": 1, "schema_name": "dbo", "owner": "dbo"}]
    if "key_constraints" in sql:
        return [_constraint_row(), _default_row()]
    if "[sys].[objects] AS [o]" in sql:
        return [_table_row()]
    if "[sys].[indexes] AS [i]" in sql:
        return [_core_index_row()]
    if "table_types" in sql:
        return [_type_row()]
    return []


def _partition_table_row():
    return {
        "table_name": "orders", "schema_name": "dbo", "scheme_name": "ps_orders",
        "function_name": "pf_orders", "partition_column": "created_at",
        "partition_count": 3,
    }


def _partition_function_rows():
    return [
        {
            "function_name": "pf_orders", "boundary_value_on_right": 1,
            "partition_count": 3, "boundary_id": 1,
            "boundary_value": "2026-01-01",
        },
        {
            "function_name": "pf_orders", "boundary_value_on_right": 1,
            "partition_count": 3, "boundary_id": 2,
            "boundary_value": "2026-02-01",
        },
    ]


def _partition_range_rows():
    return [
        {
            "partition_number": 1, "row_count": 120, "used_page_count": 3,
            "low_boundary": None, "high_boundary": "2026-01-01",
        },
        {
            "partition_number": 2, "row_count": 80, "used_page_count": 2,
            "low_boundary": "2026-01-01", "high_boundary": "2026-02-01",
        },
        {
            "partition_number": 3, "row_count": 40, "used_page_count": 1,
            "low_boundary": "2026-02-01", "high_boundary": None,
        },
    ]


def _scheme_row():
    return {
        "scheme_name": "ps_orders", "scheme_id": 21, "function_id": 11,
        "destination_id": 1, "filegroup_name": "fg_1",
    }


def _history_row():
    return {
        "history_table": "orders_history", "history_schema": "dbo",
        "temporal_type": 2,
    }


def _table_row():
    return {
        "TABLE_NAME": "orders", "TABLE_TYPE": "U", "table_comment": "orders",
        "size_bytes": 40960, "data_size_bytes": 32768,
        "index_size_bytes": 8192,
    }


def _type_row():
    return {
        "type_name": "order_note", "schema_name": "dbo", "base_type": "nvarchar",
        "max_length": 40, "is_nullable": 1, "is_user_defined": 1,
        "is_table_type": 0, "is_assembly_type": 0,
    }


def _core_index_row():
    return {
        "index_name": "ix_orders_status", "is_unique": 0,
        "is_primary_key": 0, "index_type": "NONCLUSTERED",
        "column_name": "status", "column_position": 1,
        "is_descending_key": 0, "is_disabled": 1,
        "is_hypothetical": 0, "has_filter": 1,
        "filter_definition": "([status] = 'paid')",
    }


def _constraint_row():
    return {
        "constraint_name": "ck_orders_total", "schema_name": "dbo",
        "table_name": "orders", "constraint_type": "C",
        "constraint_type_desc": "CHECK_CONSTRAINT", "check_column": "total",
        "check_definition": "([total] > (0))", "check_disabled": 0,
        "check_not_trusted": 0,
    }


def _default_row():
    return {
        "constraint_name": "df_orders_status", "schema_name": "dbo",
        "table_name": "orders", "constraint_type": "D",
        "constraint_type_desc": "DEFAULT_CONSTRAINT", "default_column": "status",
        "default_definition": "('pending')", "default_system_named": 0,
    }


class TestAsyncExecution:
    """The await path reaches the same parsers and result types."""

    def _introspector(self):
        return AsyncSQLServerIntrospector(
            make_introspector()._backend, executor=_AsyncExecutor()
        )

    @pytest.mark.asyncio
    async def test_get_partition_state_does_not_read_statistics_by_default(self):
        introspector = self._introspector()
        state = await introspector.get_partition_state("orders")
        assert state.scheme.value == "range"
        assert [bound.name for bound in state.bounds] == ["p1", "p2", "p3"]
        assert all(bound.row_count is None for bound in state.bounds)
        assert len(introspector._executor.calls) == 2
        assert all(
            "dm_db_partition_stats" not in sql
            for sql, _params in introspector._executor.calls
        )

    @pytest.mark.asyncio
    async def test_get_partition_state_reads_statistics_only_when_asked(self):
        introspector = self._introspector()
        state = await introspector.get_partition_state("orders", include_stats=True)
        assert [bound.row_count for bound in state.bounds] == [120, 80, 40]
        assert len(introspector._executor.calls) == 3
        assert "dm_db_partition_stats" in introspector._executor.calls[-1][0]

    @pytest.mark.asyncio
    async def test_an_unpartitioned_table_answers_no_scheme(self):
        class _Unpartitioned(_AsyncExecutor):
            async def execute(self, sql, params):
                if "sys.partition_schemes AS ps" in sql:
                    self.calls.append((sql, params))
                    return []
                return await super().execute(sql, params)

        introspector = AsyncSQLServerIntrospector(
            make_introspector()._backend, executor=_Unpartitioned()
        )
        assert await introspector.get_partition_state("orders") is None
        assert len(introspector._executor.calls) == 1

    @pytest.mark.asyncio
    async def test_list_index_states_maps_the_disabled_flag(self):
        introspector = self._introspector()
        states = await introspector.list_index_states("orders")
        assert states[0].name == "ix_orders_status"
        assert states[0].usable is False
        assert states[0].method == "NONCLUSTERED"
        assert states[0].predicate == "([status] = 'paid')"

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

    @pytest.mark.asyncio
    async def test_absent_kinds_answer_false_without_a_query(self):
        introspector = AsyncSQLServerIntrospector(
            make_introspector()._backend, executor=_AsyncNoQueries()
        )
        for kind in AsyncSQLServerIntrospector.ITEM_KINDS_ABSENT:
            assert await introspector.item_exists(kind, "anything") is False

    @pytest.mark.asyncio
    async def test_unqueried_kinds_refuse_instead_of_answering_false(self):
        introspector = AsyncSQLServerIntrospector(
            make_introspector()._backend, executor=_AsyncNoQueries()
        )
        for kind in AsyncSQLServerIntrospector.ITEM_KINDS_UNQUERIED:
            with pytest.raises(ProtocolNotImplementedError):
                await introspector.item_exists(kind, "anything")


class TestSyncExecution:
    """The synchronous manager reaches the same parsers and result types."""

    def _introspector(self):
        return SQLServerIntrospector(
            make_introspector()._backend, executor=_SyncExecutor()
        )

    def test_get_partition_state_does_not_read_statistics_by_default(self):
        introspector = self._introspector()
        state = introspector.get_partition_state("orders")
        assert state.scheme.value == "range"
        assert [bound.name for bound in state.bounds] == ["p1", "p2", "p3"]
        assert all(bound.row_count is None for bound in state.bounds)
        assert len(introspector._executor.calls) == 2
        assert all(
            "dm_db_partition_stats" not in sql
            for sql, _params in introspector._executor.calls
        )

    def test_get_partition_state_reads_statistics_only_when_asked(self):
        introspector = self._introspector()
        state = introspector.get_partition_state("orders", include_stats=True)
        assert [bound.row_count for bound in state.bounds] == [120, 80, 40]
        assert [bound.size_bytes for bound in state.bounds] == [
            24576, 16384, 8192,
        ]
        assert len(introspector._executor.calls) == 3
        assert "dm_db_partition_stats" in introspector._executor.calls[-1][0]

    def test_an_unpartitioned_table_answers_no_scheme(self):
        class _Unpartitioned(_SyncExecutor):
            def execute(self, sql, params):
                if "sys.partition_schemes AS ps" in sql:
                    self.calls.append((sql, params))
                    return []
                return super().execute(sql, params)

        introspector = SQLServerIntrospector(
            make_introspector()._backend, executor=_Unpartitioned()
        )
        assert introspector.get_partition_state("orders") is None
        assert len(introspector._executor.calls) == 1

    def test_list_index_states_maps_the_disabled_flag(self):
        introspector = self._introspector()
        states = introspector.list_index_states("orders")
        assert states[0].name == "ix_orders_status"
        assert states[0].usable is False
        assert states[0].method == "NONCLUSTERED"
        assert states[0].predicate == "([status] = 'paid')"

    def test_list_constraint_states_report_the_kind_and_trust(self):
        introspector = self._introspector()
        states = introspector.list_constraint_states("orders")
        check = next(state for state in states if state.name == "ck_orders_total")
        assert check.kind == "check"
        assert check.validated is True
        assert check.enforced is True

    def test_list_derived_objects_reads_the_named_default_and_history(self):
        introspector = self._introspector()
        objects = introspector.list_derived_objects("orders")
        assert [item.kind for item in objects] == [
            "history_table", "named_default",
        ]
        default = next(item for item in objects if item.kind == "named_default")
        assert (default.name, default.owned_by) == ("df_orders_status", "status")
        history = next(item for item in objects if item.kind == "history_table")
        assert history.name == "orders_history"

    def test_item_exists_answers_the_shared_objects_it_can(self):
        introspector = self._introspector()
        assert introspector.item_exists(
            ItemKind.PARTITION_FUNCTION, "pf_orders"
        ) is True
        assert introspector.item_exists(
            ItemKind.PARTITION_SCHEME, "ps_orders"
        ) is True
        assert introspector.item_exists(ItemKind.SCHEMA, "dbo") is True

    def test_absent_kinds_answer_false_without_a_query(self):
        introspector = SQLServerIntrospector(
            make_introspector()._backend, executor=_NoQueries()
        )
        for kind in SQLServerIntrospector.ITEM_KINDS_ABSENT:
            assert introspector.item_exists(kind, "anything") is False

    def test_unqueried_kinds_refuse_instead_of_answering_false(self):
        introspector = SQLServerIntrospector(
            make_introspector()._backend, executor=_NoQueries()
        )
        for kind in SQLServerIntrospector.ITEM_KINDS_UNQUERIED:
            with pytest.raises(ProtocolNotImplementedError):
                introspector.item_exists(kind, "anything")

    def test_list_schemas_is_the_neutral_names_only(self):
        introspector = self._introspector()
        assert introspector.list_schemas() == ["dbo"]
        infos = introspector.list_schema_infos()
        assert [(schema.name, schema.owner) for schema in infos] == [
            ("dbo", "dbo"),
        ]

    def test_get_table_state_carries_the_kind_and_partitioning(self):
        introspector = self._introspector()
        state = introspector.get_table_state("orders")
        assert state.kind == "regular"
        assert state.comment == "orders"
        assert state.partitioning is not None
        assert state.partitioning.scheme.value == "range"

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


class TestItemKindDeclarations:
    """Every ``ItemKind`` is declared before ``item_exists`` answers.

    The three sets are the declaration the method dispatches on: absent kinds
    answer ``False``, queried kinds answer from the catalogue, and the
    remainder refuses. The guard walks the enum, so a kind added to core
    cannot arrive here without being classified.
    """

    @pytest.mark.parametrize("kind", list(ItemKind))
    def test_every_kind_belongs_to_exactly_one_set(self, kind):
        declared = (
            kind in SQLServerIntrospector.ITEM_KINDS_ABSENT,
            kind in SQLServerIntrospector.ITEM_KINDS_UNQUERIED,
            kind in SQLServerIntrospector.ITEM_KINDS_QUERIED,
        )
        assert sum(declared) == 1, kind

    def test_the_declared_sets_cover_the_whole_enum(self):
        declared = (
            SQLServerIntrospector.ITEM_KINDS_ABSENT
            | SQLServerIntrospector.ITEM_KINDS_UNQUERIED
            | SQLServerIntrospector.ITEM_KINDS_QUERIED
        )
        assert declared == frozenset(ItemKind)


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
