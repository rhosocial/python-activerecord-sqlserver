# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_introspection_sql_builders.py
"""Offline tests for the introspector's pure-Python paths.

Covers the SQL injection hardening changes: every ``_build_*_sql`` method
now returns parameterized SQL (``?`` placeholders) with separate params,
instead of string-interpolated values.  Also covers the catalog-row to
``full_type`` rebuild in ``_parse_columns``: the ``-1`` (MAX) marker that the
rebuild used to drop, and the ``DATETIME_PRECISION`` parameter of
``time``/``datetime2``/``datetimeoffset``, which it used to ignore.
"""
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
)


def make_introspector() -> SyncSQLServerIntrospector:
    config = SQLServerConnectionConfig(
        host="localhost", port=1433, database="master", username="sa", password="",
    )
    backend = SQLServerBackend(connection_config=config)
    backend._version = (16, 0, 0)
    introspector = SyncSQLServerIntrospector(backend, executor=object())
    return introspector


class TestBuildTableListSql:
    def test_default_schema_parameterized(self):
        introspector = make_introspector()
        sql, params = introspector._build_table_list_sql(None, False)
        assert "TABLE_SCHEMA = ?" in sql
        assert params == ("dbo",)

    def test_with_table_type_parameterized(self):
        introspector = make_introspector()
        sql, params = introspector._build_table_list_sql("sys", False, table_type="BASE TABLE")
        assert "TABLE_TYPE = ?" in sql
        assert params == ("sys", "BASE TABLE")

    def test_without_views_no_table_type(self):
        introspector = make_introspector()
        sql, params = introspector._build_table_list_sql("dbo", False, include_views=False)
        assert "BASE TABLE" in sql
        assert params == ("dbo",)


class TestBuildColumnInfoSql:
    def test_parameterized(self):
        introspector = make_introspector()
        sql, params = introspector._build_column_info_sql("users", "dbo")
        assert "c.TABLE_SCHEMA = ?" in sql
        assert params == ("dbo", "users")

    def test_selects_datetime_precision(self):
        """The temporal parameter lives only in ``DATETIME_PRECISION``."""
        introspector = make_introspector()
        sql, _ = introspector._build_column_info_sql("users", "dbo")
        assert "c.DATETIME_PRECISION" in sql


class TestBuildPrimaryKeySql:
    def test_parameterized(self):
        introspector = make_introspector()
        sql, params = introspector._build_primary_key_sql("users", "dbo")
        assert "tc.TABLE_SCHEMA = ?" in sql
        assert params == ("dbo", "users")


class TestBuildIndexInfoSql:
    def test_parameterized(self):
        introspector = make_introspector()
        sql, params = introspector._build_index_info_sql("users", "dbo")
        assert "s.name = ?" in sql
        assert params == ("dbo", "users")


class TestBuildForeignKeySql:
    def test_parameterized(self):
        introspector = make_introspector()
        sql, params = introspector._build_foreign_key_sql("users", "dbo")
        assert "s.name = ?" in sql
        assert params == ("dbo", "users")


class TestBuildViewListSql:
    def test_parameterized(self):
        introspector = make_introspector()
        sql, params = introspector._build_view_list_sql("dbo", False)
        assert "TABLE_SCHEMA = ?" in sql
        assert params == ("dbo",)


class TestBuildViewInfoSql:
    def test_parameterized(self):
        introspector = make_introspector()
        sql, params = introspector._build_view_info_sql("active_users", "dbo")
        assert "TABLE_SCHEMA = ?" in sql
        assert params == ("dbo", "active_users")


class TestBuildTriggerListSql:
    def test_with_table_name_parameterized(self):
        introspector = make_introspector()
        sql, params = introspector._build_trigger_list_sql("orders", "dbo")
        assert "AND t.name = ?" in sql
        assert params == ("dbo", "orders")

    def test_without_table_name(self):
        introspector = make_introspector()
        sql, params = introspector._build_trigger_list_sql(None, "dbo")
        assert "AND t.name = ?" not in sql
        assert params == ("dbo",)


class TestBuildDatabaseInfoSql:
    def test_returns_sql(self):
        introspector = make_introspector()
        sql, params = introspector._build_database_info_sql()
        assert "DB_NAME()" in sql
        assert params == ()


class TestParseColumnsFullTypeRebuild:
    """Offline tests for the ``full_type`` rebuild in ``_parse_columns``.

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
        return introspector._parse_columns([row], "t", "dbo")[0]

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
    """Offline tests for the ``DATETIME_PRECISION`` rebuild in ``_parse_columns``.

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
        return introspector._parse_columns([row], "t", "dbo")[0]

    def test_explicit_precision_rebuilds_and_matches_declared(self):
        dialect = make_introspector()._backend.dialect
        for word in self.PRECISIONED:
            col = self._parse_one(word, 3)
            assert col.data_type_full == f"{word}(3)"
            assert col.parsed_data_type == DataType.parse_data_type_str(
                dialect, f"{word}(3)")

    def test_zero_precision_is_rebuilt(self):
        dialect = make_introspector()._backend.dialect
        for word in self.PRECISIONED:
            col = self._parse_one(word, 0)
            assert col.data_type_full == f"{word}(0)"
            assert col.parsed_data_type == DataType.parse_data_type_str(
                dialect, f"{word}(0)")

    def test_server_default_precision_stays_bare(self):
        dialect = make_introspector()._backend.dialect
        for word in self.PRECISIONED:
            col = self._parse_one(word, 7)
            assert col.data_type_full == word
            assert col.parsed_data_type == DataType.parse_data_type_str(
                dialect, word)

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
        assert sdt.parsed_data_type == DataType.parse_data_type_str(
            dialect, "smalldatetime")
