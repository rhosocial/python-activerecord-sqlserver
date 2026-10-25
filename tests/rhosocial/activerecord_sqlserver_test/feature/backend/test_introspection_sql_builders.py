# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_introspection_sql_builders.py
"""Offline tests for the introspection questions, and the SQL they render.

Covers the injection hardening: every question is parameterized (``?``
placeholders) with its values kept in a separate tuple, instead of
string-interpolated. Also covers the catalog-row to ``full_type`` rebuild in
``parse_columns``: the ``-1`` (MAX) marker that the rebuild used to drop, and
the ``DATETIME_PRECISION`` parameter of ``time``/``datetime2``/
``datetimeoffset``, which it used to ignore.

Every question here is a ``QueryStatement`` over expression nodes, rendered by
the dialect (org guide §16.2). For the families core models that means the
dialect's ``format_*_query_statement`` writes the text -- the introspector only
constructs the statement; for the families only this backend has, the
statement class lives in ``expression/introspection.py`` and its formatter in
``mixins/introspection.py``, and the introspector's ``*_statement`` factory
names one. Either way what the assertions read is the *rendered* statement: the
value the caller passed became a bind parameter and no value leaked into the
text. The identifier spelling is the dialect's, so it is asserted as
``[schema].[TABLE]`` where a position matters and left free where it does not.
"""

from decimal import Decimal

import pytest

from rhosocial.activerecord.backend.expression.introspection import (
    ColumnInfoQueryStatement,
    DatabaseInfoQueryStatement,
    ForeignKeyQueryStatement,
    IndexInfoQueryStatement,
    TableListQueryStatement,
    TriggerListQueryStatement,
    ViewInfoQueryStatement,
    ViewListQueryStatement,
)
from rhosocial.activerecord.backend.expression.types import DataType, TextType
from rhosocial.activerecord.backend.impl.sqlserver.backend import SQLServerBackend
from rhosocial.activerecord.backend.impl.sqlserver.config import SQLServerConnectionConfig
from rhosocial.activerecord.backend.impl.sqlserver.expression.types import (
    SQLServerImageType,
    SQLServerNVarCharType,
    SQLServerVarBinaryMaxType,
    SQLServerXmlType,
)
from rhosocial.activerecord.backend.impl.sqlserver.introspection import (
    SyncSQLServerIntrospector,
    SyncSQLServerStatusIntrospector,
)


def make_introspector() -> SyncSQLServerIntrospector:
    config = SQLServerConnectionConfig(
        host="localhost",
        port=1433,
        database="master",
        username="sa",
        password="",
    )
    backend = SQLServerBackend(connection_config=config)
    backend._version = (16, 0, 0)
    introspector = SyncSQLServerIntrospector(backend, executor=object())
    return introspector


def make_dialect():
    """The dialect the introspector renders its statements with."""
    return make_introspector()._backend.dialect


class TestBuildTableListSql:
    def test_default_schema_parameterized(self):
        sql, params = TableListQueryStatement(make_dialect()).to_sql()
        assert "[TABLE_SCHEMA] = ?" in sql
        assert params == ("dbo",)
        assert "'dbo'" not in sql

    def test_with_table_type_parameterized(self):
        sql, params = TableListQueryStatement(
            make_dialect(), schema="sys", table_type="BASE TABLE"
        ).to_sql()
        assert "[TABLE_TYPE] = ?" in sql
        assert params == ("sys", "BASE TABLE")
        assert "'BASE TABLE'" not in sql

    def test_without_views_no_table_type(self):
        sql, params = TableListQueryStatement(
            make_dialect(), schema="dbo", include_views=False
        ).to_sql()
        # The implicit "tables only" filter is part of the question, not data,
        # so it stays an inline literal exactly as the template wrote it.
        assert "BASE TABLE" in sql
        assert params == ("dbo",)


class TestBuildColumnInfoSql:
    def test_parameterized(self):
        sql, params = ColumnInfoQueryStatement(
            make_dialect(), "users", schema="dbo"
        ).to_sql()
        assert "[TABLE_SCHEMA] = ?" in sql
        assert "[TABLE_NAME] = ?" in sql
        assert params == ("dbo", "users")

    def test_selects_datetime_precision(self):
        """The temporal parameter lives only in ``DATETIME_PRECISION``."""
        sql, _ = ColumnInfoQueryStatement(make_dialect(), "users", schema="dbo").to_sql()
        assert "DATETIME_PRECISION" in sql

    def test_identity_flag_rides_the_column(self):
        """``COLUMNPROPERTY(..., 'IsIdentity')`` keeps its alias in the node."""
        sql, _ = ColumnInfoQueryStatement(make_dialect(), "users", schema="dbo").to_sql()
        assert "COLUMNPROPERTY" in sql
        assert "IS_IDENTITY" in sql
        assert "IsIdentity" in sql


class TestBuildPrimaryKeySql:
    def test_parameterized(self):
        introspector = make_introspector()
        sql, params = introspector.primary_key_statement(table_name="users", schema="dbo").to_sql()
        assert "[TABLE_SCHEMA] = ?" in sql
        assert "[TABLE_NAME] = ?" in sql
        assert params == ("dbo", "users")
        assert "'PRIMARY KEY'" in sql, "the constraint kind is part of the question"


class TestBuildIndexInfoSql:
    def test_parameterized(self):
        sql, params = IndexInfoQueryStatement(
            make_dialect(), "users", schema="dbo"
        ).to_sql()
        assert "[s].[name] = ?" in sql
        assert "[t].[name] = ?" in sql
        assert params == ("dbo", "users")


class TestBuildForeignKeySql:
    def test_parameterized(self):
        sql, params = ForeignKeyQueryStatement(
            make_dialect(), "users", schema="dbo"
        ).to_sql()
        assert "[s].[name] = ?" in sql
        assert "[t].[name] = ?" in sql
        assert params == ("dbo", "users")


class TestBuildViewListSql:
    def test_parameterized(self):
        sql, params = ViewListQueryStatement(make_dialect(), schema="dbo").to_sql()
        assert "[TABLE_SCHEMA] = ?" in sql
        assert params == ("dbo",)


class TestBuildViewInfoSql:
    def test_parameterized(self):
        sql, params = ViewInfoQueryStatement(
            make_dialect(), "active_users", schema="dbo"
        ).to_sql()
        assert "[TABLE_SCHEMA] = ?" in sql
        assert "[TABLE_NAME] = ?" in sql
        assert params == ("dbo", "active_users")


class TestBuildTriggerListSql:
    def test_with_table_name_parameterized(self):
        sql, params = TriggerListQueryStatement(
            make_dialect(), schema="dbo", table_name="orders"
        ).to_sql()
        assert "[s].[name] = ? AND [t].[name] = ?" in sql
        assert params == ("dbo", "orders")

    def test_without_table_name(self):
        sql, params = TriggerListQueryStatement(make_dialect(), schema="dbo").to_sql()
        assert "[t].[name] = ?" not in sql
        assert params == ("dbo",)


class TestBuildDatabaseInfoSql:
    def test_returns_sql(self):
        sql, params = DatabaseInfoQueryStatement(make_dialect()).to_sql()
        assert "DB_NAME()" in sql
        assert "SERVERPROPERTY('ProductVersion')" in sql
        assert params == ()


class TestBuildSchemaListSql:
    def test_owner_resolved_by_principal_id_not_name(self):
        introspector = make_introspector()
        sql, params = introspector.schema_list_statement().to_sql()
        assert sql == (
            "SELECT [s].[schema_id], [s].[name] AS [schema_name], "
            "[p].[name] AS [owner] FROM [sys].[schemas] AS [s] "
            "LEFT JOIN [sys].[database_principals] AS [p] "
            "ON [s].[principal_id] = [p].[principal_id] ORDER BY [s].[name]"
        )
        # The keep of a schema whose principal was dropped is why the join to
        # the principal is a LEFT JOIN rather than an inner one.
        assert "LEFT JOIN" in sql
        assert params == ()

    def test_dangling_principal_row_still_a_schema(self):
        """A NULL owner parses to None, the row survives (mirrors the join)."""
        introspector = make_introspector()
        schemas = introspector.parse_schemas(
            [{"schema_id": 5, "schema_name": "orphan", "owner": None}]
        )
        assert schemas[0].owner is None
        assert schemas[0].schema_id == 5


class TestBuildExtendedPropertyListSql:
    def test_every_filter_is_a_bind_parameter(self):
        introspector = make_introspector()
        sql, params = introspector.extended_property_list_statement(
            major_id=123, minor_id=1, class_name="OBJECT_OR_COLUMN", schema="dbo"
        ).to_sql()
        assert params == (123, "OBJECT_OR_COLUMN", 1, "dbo")
        assert "'dbo'" not in sql and "'OBJECT_OR_COLUMN'" not in sql
        assert "[ep].[major_id] = ?" in sql
        assert "[ep].[class_desc] = ?" in sql
        assert "[ep].[minor_id] = ?" in sql
        assert "[s].[name] = ?" in sql

    def test_value_cast_off_the_sql_variant(self):
        """``value`` is sql_variant, which the driver cannot fetch (HY106)."""
        introspector = make_introspector()
        sql, params = introspector.extended_property_list_statement(
            major_id=123, minor_id=None, class_name="OBJECT_OR_COLUMN", schema=None
        ).to_sql()
        assert "CAST([ep].[value] AS NVARCHAR(4000)) AS [property_value]" in sql
        # No minor_id, no schema: two predicates only.
        assert params == (123, "OBJECT_OR_COLUMN")

    def test_unknown_class_refused_before_the_query(self):
        introspector = make_introspector()
        for bad in ("", "MS_Description", "object_or_column"):
            # The refusal is the formatter's -- it happens when the statement
            # is rendered, before anything reaches the server.
            with pytest.raises(ValueError):
                introspector.extended_property_list_statement(
                    major_id=123, minor_id=None, class_name=bad, schema=None
                ).to_sql()

    def test_schema_only_narrows_object_scoped_classes(self):
        introspector = make_introspector()
        # INDEX is object-scoped (a major_id in sys.objects space)...
        introspector.extended_property_list_statement(
            major_id=1, minor_id=None, class_name="INDEX", schema="dbo"
        ).to_sql()
        # ...but DATABASE/SCHEMA properties have no object to narrow by.
        with pytest.raises(ValueError):
            introspector.extended_property_list_statement(
                major_id=1, minor_id=None, class_name="DATABASE", schema="dbo"
            ).to_sql()
        with pytest.raises(ValueError):
            introspector.extended_property_list_statement(
                major_id=1, minor_id=None, class_name="SCHEMA", schema="dbo"
            ).to_sql()

    def test_public_manager_refuses_at_the_same_point(self):
        """``list_extended_properties`` is where the refusal is observed."""
        introspector = make_introspector()
        with pytest.raises(ValueError, match="unknown extended-property class"):
            introspector.list_extended_properties(123, class_name="MS_Description")
        with pytest.raises(ValueError, match="object-scoped extended properties"):
            introspector.list_extended_properties(1, class_name="DATABASE", schema="dbo")


class TestBuildRoutineListSql:
    def test_procedures_ask_for_p_and_pc(self):
        introspector = make_introspector()
        sql, params = introspector.procedure_list_statement(schema=None).to_sql()
        assert "[o].[type] IN ('P', 'PC')" in sql
        assert params == ("dbo",)

    def test_functions_ask_for_the_five_codes(self):
        introspector = make_introspector()
        sql, params = introspector.function_list_statement(schema=None).to_sql()
        assert "[o].[type] IN ('FN', 'IF', 'TF', 'FS', 'FT')" in sql
        assert params == ("dbo",)

    def test_explicit_schema_is_a_parameter(self):
        introspector = make_introspector()
        sql, params = introspector.procedure_list_statement(schema="sales").to_sql()
        assert "[s].[name] = ?" in sql
        assert "'sales'" not in sql
        assert params == ("sales",)

    def test_procedures_and_functions_differ_only_in_codes(self):
        introspector = make_introspector()
        procs, _ = introspector.procedure_list_statement(schema="dbo").to_sql()
        fns, _ = introspector.function_list_statement(schema="dbo").to_sql()
        assert procs.replace("IN ('P', 'PC')", "") == fns.replace(
            "IN ('FN', 'IF', 'TF', 'FS', 'FT')", ""
        )


class TestBuildSequenceListSql:
    def test_sql_variant_columns_are_cast_to_text(self):
        introspector = make_introspector()
        sql, params = introspector.sequence_list_statement(schema=None).to_sql()
        for column in (
            "start_value",
            "increment",
            "minimum_value",
            "maximum_value",
            "current_value",
        ):
            assert f"CAST([q].[{column}] AS NVARCHAR(64)) AS [{column}]" in sql
        assert "CAST([q].[cache_size] AS BIGINT) AS [cache_size]" in sql
        assert "TYPE_NAME([q].[user_type_id]) AS [data_type]" in sql
        assert params == ("dbo",)

    def test_explicit_schema_is_a_parameter(self):
        introspector = make_introspector()
        sql, params = introspector.sequence_list_statement(schema="sales").to_sql()
        assert "[s].[name] = ?" in sql
        assert "'sales'" not in sql
        assert params == ("sales",)


class TestParseBackendSpecificTypes:
    """The parsers read the aliases the builders above project."""

    @staticmethod
    def _routine(**overrides):
        row = {
            "routine_name": "usp_x",
            "schema_name": "dbo",
            "type_code": " P ",
            "type_desc": "SQL_STORED_PROCEDURE",
            "created_at": None,
            "modified_at": None,
            "is_ms_shipped": 0,
            **overrides,
        }
        return make_introspector().parse_routines([row])[0]

    def test_routine_type_code_stripped_and_flagged(self):
        routine = self._routine()
        assert routine.type_code == "P"
        assert routine.name == "usp_x"
        assert routine.schema == "dbo"
        # ``is_ms_shipped`` arrives as the driver's int.
        assert routine.is_ms_shipped is False
        assert self._routine(is_ms_shipped=1).is_ms_shipped is True

    def test_sequence_values_read_back_as_exact_numbers(self):
        introspector = make_introspector()
        row = {
            "sequence_name": "seq",
            "schema_name": "dbo",
            "data_type": "bigint",
            "start_value": "5",
            "increment": "2",
            "minimum_value": "1",
            "maximum_value": "9223372036854775807",
            "current_value": None,
            "is_cycling": 0,
            "is_cached": 1,
            "cache_size": 50,
        }
        seq = introspector.parse_sequences([row])[0]
        assert seq.start_value == Decimal("5")
        assert seq.increment == Decimal("2")
        assert seq.maximum_value == Decimal("9223372036854775807")
        # An unstarted sequence has no current_value, and it stays None.
        assert seq.current_value is None
        assert seq.is_cached is True and seq.is_cycling is False
        assert seq.cache_size == 50

    def test_unparseable_sequence_value_degrades_to_none(self):
        introspector = make_introspector()
        rows = [
            {"sequence_name": "seq", "start_value": "not-a-number"},
            {"sequence_name": "seq", "cache_size": None},
        ]
        parsed = introspector.parse_sequences(rows)
        assert parsed[0].start_value is None
        assert parsed[0].cache_size is None

    def test_null_extended_property_value_stays_none(self):
        introspector = make_introspector()
        row = {
            "class_id": 1,
            "class_name": "OBJECT_OR_COLUMN",
            "major_id": 77,
            "minor_id": 0,
            "property_name": "MS_Description",
            "property_value": None,
        }
        prop = introspector.parse_extended_properties([row])[0]
        # A property set to NULL is a value, not a missing row.
        assert prop.value is None
        assert prop.name == "MS_Description"
        assert (prop.class_id, prop.major_id, prop.minor_id) == (1, 77, 0)


def make_status_introspector(version=(16, 0, 0)) -> SyncSQLServerStatusIntrospector:
    config = SQLServerConnectionConfig(
        host="localhost",
        port=1433,
        database="master",
        username="sa",
        password="",
    )
    backend = SQLServerBackend(connection_config=config, version=version)
    return SyncSQLServerStatusIntrospector(backend)


class TestStatusQueries:
    """The status queries are nodes too, and the caps they used are version-gated.

    Each row shape here is the contract the parsers above read: the aliases in
    the projection are what ``row["counter_name"]`` and friends look up, so a
    rename here would silently empty a status report rather than fail.
    """

    def test_version_query_asks_the_engine(self):
        sql, params = make_status_introspector()._version_sql()
        assert sql == "SELECT CAST(SERVERPROPERTY('ProductVersion') AS NVARCHAR(128))"
        assert params == ()

    def test_configuration_projection_and_aliases(self):
        sql, params = make_status_introspector()._configuration_sql()
        assert "[value_in_use]" in sql and "AS [value_in_use]" in sql
        assert "FROM [sys].[configurations]" in sql
        assert "ORDER BY [name]" in sql
        assert params == ()

    def test_performance_cap_is_pagination_not_top(self):
        sql, _ = make_status_introspector()._performance_metrics_sql(50)
        assert "OFFSET 0 ROWS FETCH NEXT 50 ROWS ONLY" in sql
        assert "TOP 50" not in sql
        assert "ORDER BY [cntr_value] DESC" in sql
        # The cap precedes the ORDER BY it depends on, so the ordering the
        # old TOP 50 relied on for "busiest first" is still what is asked for.

    def test_performance_cap_dropped_before_2012(self):
        """``OFFSET/FETCH`` arrived in 2012; older servers read every counter."""
        introspector = make_status_introspector(version=(10, 0, 0))
        assert introspector._performance_metrics_limit() is None
        sql, _ = introspector._performance_metrics_sql(None)
        assert "OFFSET" not in sql
        assert "ORDER BY [cntr_value] DESC" in sql

    def test_performance_cap_kept_from_2012(self):
        assert make_status_introspector(version=(11, 0, 0))._performance_metrics_limit() == 50

    def test_connection_info_halves_are_subqueries(self):
        sql, params = make_status_introspector()._connection_info_sql()
        assert "(SELECT COUNT(*) FROM [sys].[dm_exec_connections]) AS [active]" in sql
        assert "AS [max_conn]" in sql
        assert params == (), "the setting name is part of the question"

    def test_storage_sums_the_page_units(self):
        sql, params = make_status_introspector()._storage_info_sql()
        assert sql == (
            "SELECT SUM([size] * 8 * 1024) AS [total_bytes] "
            "FROM [sys].[master_files] WHERE [database_id] > 0"
        )
        assert params == ()

    def test_database_list_groups_and_orders_by_name(self):
        sql, params = make_status_introspector()._database_list_sql()
        assert "LEFT JOIN [sys].[master_files] AS [mf]" in sql
        assert "GROUP BY [d].[name]" in sql
        assert "ORDER BY [d].[name]" in sql
        assert params == ()

    def test_user_list_filters_login_types(self):
        sql, params = make_status_introspector()._user_list_sql()
        assert "[type] IN ('S', 'U', 'G')" in sql
        assert params == ()

    def test_session_info_keeps_the_niladic_login_name_unquoted(self):
        """``SYSTEM_USER`` is the value function, not a column to look up."""
        sql, params = make_status_introspector()._session_info_sql()
        assert sql.startswith("SELECT SYSTEM_USER AS [session_user]")
        assert "CONNECTIONPROPERTY('net_transport')" in sql
        assert params == ()


class TestParseColumnsFullTypeRebuild:
    """Offline tests for the ``full_type`` rebuild in ``parse_columns``.

    ``INFORMATION_SCHEMA.COLUMNS.CHARACTER_MAXIMUM_LENGTH`` reports ``-1``
    for the MAX-capable declarations.  The rebuild used to skip any
    non-positive length, so ``NVARCHAR(MAX)`` came back as the bare word and
    re-read as the declared default width (``NVARCHAR(255)``): a phantom
    diff against a declared ``NVARCHAR(MAX)``, and a missed change against
    a real ``NVARCHAR(255)``.
    """

    @staticmethod
    def _parse_one(data_type: str, **catalog):
        row = {
            "COLUMN_NAME": "col",
            "DATA_TYPE": data_type,
            "ORDINAL_POSITION": 1,
            "IS_NULLABLE": "YES",
            **catalog,
        }
        introspector = make_introspector()
        return introspector.parse_columns([row], "t", "dbo")[0]

    def test_nvarchar_max_marker_rebuilds_to_max(self):
        dialect = make_introspector()._backend.dialect
        col = self._parse_one("nvarchar", CHARACTER_MAXIMUM_LENGTH=-1)
        assert col.data_type_full == "nvarchar(MAX)"
        assert isinstance(col.parsed_data_type, TextType)
        # Declared ``NVARCHAR(MAX)`` (TextType) and the introspected column
        # now agree, so the phantom diff is gone...
        assert col.parsed_data_type == TextType(dialect)
        assert col.parsed_data_type == DataType.parse_data_type_str(dialect, "NVARCHAR(MAX)")
        # ...and a MAX column no longer compares equal to a sized one.
        assert col.parsed_data_type != SQLServerNVarCharType(dialect, length=255)
        assert col.parsed_data_type != DataType.parse_data_type_str(dialect, "NVARCHAR(255)")

    def test_varchar_max_marker_rebuilds_to_max(self):
        dialect = make_introspector()._backend.dialect
        col = self._parse_one("varchar", CHARACTER_MAXIMUM_LENGTH=-1)
        assert col.data_type_full == "varchar(MAX)"
        assert isinstance(col.parsed_data_type, TextType)
        assert col.parsed_data_type == TextType(dialect)
        assert col.parsed_data_type != DataType.parse_data_type_str(dialect, "VARCHAR(255)")

    def test_varbinary_max_marker_rebuilds_to_max_type(self):
        col = self._parse_one("varbinary", CHARACTER_MAXIMUM_LENGTH=-1)
        assert col.data_type_full == "varbinary(MAX)"
        assert isinstance(col.parsed_data_type, SQLServerVarBinaryMaxType)

    def test_introspected_max_differs_from_introspected_255(self):
        """The missed-change half: MAX and 255 must not compare equal."""
        sized = self._parse_one("nvarchar", CHARACTER_MAXIMUM_LENGTH=255)
        maxed = self._parse_one("nvarchar", CHARACTER_MAXIMUM_LENGTH=-1)
        assert sized.data_type_full == "nvarchar(255)"
        assert sized.parsed_data_type != maxed.parsed_data_type

    def test_sized_column_rebuild_unchanged(self):
        col = self._parse_one("nvarchar", CHARACTER_MAXIMUM_LENGTH=30)
        assert col.data_type_full == "nvarchar(30)"
        assert isinstance(col.parsed_data_type, SQLServerNVarCharType)
        assert col.parsed_data_type.length == 30

    def test_legacy_lob_and_xml_marker_handling_unchanged(self):
        # text/ntext/image report their own maximum rather than -1...
        text = self._parse_one("text", CHARACTER_MAXIMUM_LENGTH=2147483647)
        assert text.data_type_full == "text(2147483647)"
        assert isinstance(text.parsed_data_type, TextType)
        ntext = self._parse_one("ntext", CHARACTER_MAXIMUM_LENGTH=1073741823)
        assert ntext.data_type_full == "ntext(1073741823)"
        assert isinstance(ntext.parsed_data_type, TextType)
        image = self._parse_one("image", CHARACTER_MAXIMUM_LENGTH=2147483647)
        assert image.data_type_full == "image(2147483647)"
        assert isinstance(image.parsed_data_type, SQLServerImageType)
        # ...and xml takes no length argument, so a -1 marker stays bare.
        xml = self._parse_one("xml", CHARACTER_MAXIMUM_LENGTH=-1)
        assert xml.data_type_full == "xml"
        assert isinstance(xml.parsed_data_type, SQLServerXmlType)


class TestParseColumnsDatetimePrecision:
    """Offline tests for the ``DATETIME_PRECISION`` rebuild in ``parse_columns``.

    Appendix F.4-1..3: the three temporal types that carry a
    fractional-seconds precision report it only in ``DATETIME_PRECISION``
    (their ``NUMERIC_PRECISION`` is NULL), and the rebuild used not to read
    it at all: ``time(3)`` came back bare and re-read as the default
    precision, while ``time(0)`` and ``time(7)`` folded into the very same
    bare type.  The catalog answers, measured live and identical on SQL
    Server 2019 (15.0.4465.1), 2022 (16.0.4250.1) and 2025 (17.0.4035.5):

        bare time/datetime2/datetimeoffset -> 7
        (0)                                -> 0
        (3)                                -> 3
        (7)                                -> 7

    So the rebuild emits ``(n)`` only when ``n`` differs from the server
    default ``7``, and rebuilds the bare word at the default — which is also
    what the server reports for an explicit ``(7)``, a declaration it cannot
    tell apart from the bare word.
    """

    PRECISIONED = ("time", "datetime2", "datetimeoffset")

    @staticmethod
    def _parse_one(data_type: str, dt_precision):
        row = {
            "COLUMN_NAME": "col",
            "DATA_TYPE": data_type,
            "ORDINAL_POSITION": 1,
            "IS_NULLABLE": "YES",
            "DATETIME_PRECISION": dt_precision,
        }
        introspector = make_introspector()
        return introspector.parse_columns([row], "t", "dbo")[0]

    def test_explicit_precision_rebuilds_and_matches_declared(self):
        dialect = make_introspector()._backend.dialect
        for word in self.PRECISIONED:
            col = self._parse_one(word, 3)
            assert col.data_type_full == f"{word}(3)"
            assert col.parsed_data_type == DataType.parse_data_type_str(dialect, f"{word}(3)")

    def test_zero_precision_is_rebuilt(self):
        dialect = make_introspector()._backend.dialect
        for word in self.PRECISIONED:
            col = self._parse_one(word, 0)
            assert col.data_type_full == f"{word}(0)"
            assert col.parsed_data_type == DataType.parse_data_type_str(dialect, f"{word}(0)")

    def test_server_default_precision_stays_bare(self):
        dialect = make_introspector()._backend.dialect
        for word in self.PRECISIONED:
            col = self._parse_one(word, 7)
            assert col.data_type_full == word
            assert col.parsed_data_type == DataType.parse_data_type_str(dialect, word)

    def test_missing_catalog_precision_stays_bare(self):
        # Defensive: a row without the field rebuilds exactly as before.
        for word in self.PRECISIONED:
            col = self._parse_one(word, None)
            assert col.data_type_full == word

    def test_missed_change_between_zero_and_default_is_closed(self):
        zero = self._parse_one("time", 0)
        three = self._parse_one("time", 3)
        default = self._parse_one("time", 7)
        assert zero.parsed_data_type != default.parsed_data_type
        assert three.parsed_data_type != default.parsed_data_type

    def test_legacy_datetime_aliases_keep_their_bare_path(self):
        """``datetime`` (dtprec 3) and ``smalldatetime`` (dtprec 0) are fixed
        legacy aliases folded into the ``DATETIME2`` concept; the rebuild
        leaves them bare rather than inventing a parameter their grammar does
        not have."""
        dialect = make_introspector()._backend.dialect
        dt = self._parse_one("datetime", 3)
        assert dt.data_type_full == "datetime"
        assert dt.parsed_data_type == DataType.parse_data_type_str(dialect, "datetime")
        sdt = self._parse_one("smalldatetime", 0)
        assert sdt.data_type_full == "smalldatetime"
        assert sdt.parsed_data_type == DataType.parse_data_type_str(dialect, "smalldatetime")
