# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_sqlserver_type_protocol.py
"""Tests for the SQL Server backend data-type protocol compliance.

Covers:
- format/supports 1:1 correspondence
- supports_data_types() includes sqlserver_* + core entries, on a cold import
- suggested_data_types() returns classes, keys disjoint from supported, and
  every suggested class is a type this dialect really renders (D9)
- spelling gates: the default spelling always renders, an unknown one is
  refused and named
- dialect_options forwarding and equality
- Precision validation
"""

import pytest
from rhosocial.activerecord.backend.dialect.exceptions import (
    UnsupportedFeatureError,
)
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression.types import (
    SQLServerBitType,
    SQLServerNCharType,
    SQLServerNVarCharType,
    SQLServerTinyIntType,
    SQLServerUniqueIdentifierType,
    SQLServerVarBinaryType,
    SQLServerXmlType,
)
from rhosocial.activerecord.backend.impl.sqlserver.protocols import (
    SQLServerTypeSupport,
)
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BlobType,
    BooleanType,
    CharType,
    DataType,
    DateTimeType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    JsonType,
    SmallIntType,
    TextType,
    TimeType,
    TimestampType,
    TimestampTzType,
    TinyIntType,
    UUIDType,
    VarCharType,
    XmlType,
)

SQL_SERVER_2022 = (16, 0, 0)
SQL_SERVER_2005 = (9, 0, 0)

#: Words to try when a test needs a spelling that is genuinely *outside* a
#: concept's closed list.  Scanned per concept rather than hardcoded, because a
#: hardcoded probe goes stale: an earlier revision of this file used ``int4``
#: throughout, and ``int4`` stopped being outside the list once core recorded it
#: as a documented synonym of ``INTEGER`` (PostgreSQL's own name for the 4-byte
#: integer).  Every word here is alphanumeric — the probe is also used as a
#: ``pytest.raises(match=...)`` pattern — and the first that the concept under
#: test does not claim is used.
_UNKNOWN_SPELLING_POOL = ("int4", "int64", "uint", "int16", "float4", "decimal4")


def _absent_spelling(concept):
    """A word that is certainly not in ``concept.SPELLINGS``."""
    for candidate in _UNKNOWN_SPELLING_POOL:
        if candidate not in concept.SPELLINGS:
            return candidate
    raise AssertionError(
        f"{concept.__name__}.SPELLINGS now contains every word in "
        f"{_UNKNOWN_SPELLING_POOL}; add another probe to the pool rather than "
        f"hardcoding one here"
    )


class TestFormatSupportsCorrespondence:
    """Every format_data_type_<name> must have a matching supports_data_type_<name>."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_all_format_methods_have_supports_counterpart(self, dialect):
        import re
        format_names = set()
        for attr in dir(type(dialect)):
            m = re.match(r"^format_data_type_([a-z][a-z0-9_]*)$", attr)
            if m:
                format_names.add(m.group(1))

        supports_names = set()
        for attr in dir(type(dialect)):
            m = re.match(r"^supports_data_type_([a-z][a-z0-9_]*)$", attr)
            if m:
                supports_names.add(m.group(1))

        missing = format_names - supports_names
        assert not missing, (
            f"format_data_type_* without supports_data_type_*: {missing}"
        )

    def test_all_supports_methods_have_format_counterpart(self, dialect):
        import re
        format_names = set()
        for attr in dir(type(dialect)):
            m = re.match(r"^format_data_type_([a-z][a-z0-9_]*)$", attr)
            if m:
                format_names.add(m.group(1))

        supports_names = set()
        for attr in dir(type(dialect)):
            m = re.match(r"^supports_data_type_([a-z][a-z0-9_]*)$", attr)
            if m:
                supports_names.add(m.group(1))

        extra = supports_names - format_names
        assert not extra, (
            f"supports_data_type_* without format_data_type_*: {extra}"
        )


class TestSupportsDataTypes:
    """supports_data_types() returns sqlserver_* + core entries."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_returns_dict(self, dialect):
        result = dialect.supports_data_types()
        assert isinstance(result, dict)

    def test_includes_core_types(self, dialect):
        supported = dialect.supports_data_types()
        # ``int`` is deliberately absent: it is a *spelling* of ``integer``,
        # not a second concept, so it has no name to be dispatched by.  The
        # spelling is honoured inside ``format_data_type_integer`` instead —
        # see TestSpellingGates below.
        for name in ["integer", "bigint", "smallint", "tinyint",
                      "varchar", "char", "text", "boolean", "date",
                      "datetime", "time", "timestamp", "timestamptz", "float",
                      "real", "double", "decimal", "json", "xml", "blob",
                      "custom"]:
            assert name in supported, f"Core type {name!r} missing from supports_data_types()"

    def test_includes_sqlserver_types(self, dialect):
        supported = dialect.supports_data_types()
        for name in ["sqlserver_nvarchar", "sqlserver_nchar",
                      "sqlserver_nvarchar_max", "sqlserver_varbinary",
                      "sqlserver_varbinary_max", "sqlserver_xml",
                      "sqlserver_tinyint", "sqlserver_bit",
                      "sqlserver_image"]:
            assert name in supported, f"SQL Server type {name!r} missing from supports_data_types()"

    def test_values_are_type_classes(self, dialect):
        supported = dialect.supports_data_types()
        for name, cls in supported.items():
            assert isinstance(cls, type), (
                f"supports_data_types()[{name!r}] = {cls!r} is not a type class"
            )

    def test_every_key_names_the_class_behind_it(self, dialect):
        """A key with a different class behind it is a dispatch that lies."""
        supported = dialect.supports_data_types()
        for name, cls in supported.items():
            assert issubclass(cls, DataType), f"{name!r} -> {cls!r}"
            assert cls.name == name, f"{cls.__name__}.name={cls.name!r} != {name!r}"

    def test_backend_types_are_advertised_without_a_prior_import(self):
        """``supports_data_types()`` must not depend on load order.

        ``_type_class_for(name)`` resolves a dispatch key by walking the live
        subclass tree of ``DataType``, so a name whose class nobody imported
        resolves to ``None`` and silently drops out of the mapping.  It used to
        drop out: every test that caught this had imported a ``SQLServer*``
        class itself first, which is how the defect survived.  So this runs in
        a subprocess, where the dialect module is the only import.
        """
        import subprocess
        import sys

        script = (
            "from rhosocial.activerecord.backend.impl.sqlserver.dialect "
            "import SQLServerDialect\n"
            f"supported = SQLServerDialect({SQL_SERVER_2022!r}).supports_data_types()\n"
            "print(','.join(sorted(supported)))\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, check=True,
        )
        advertised = set(result.stdout.strip().split(","))
        for name in ("sqlserver_nvarchar", "sqlserver_nchar",
                     "sqlserver_nvarchar_max", "sqlserver_varbinary",
                     "sqlserver_varbinary_max", "sqlserver_xml",
                     "sqlserver_tinyint", "sqlserver_bit",
                     "sqlserver_image", "sqlserver_uniqueidentifier"):
            assert name in advertised, (
                f"{name!r} missing from supports_data_types() on a cold import; "
                f"the backend expression types are not being loaded. Advertised: "
                f"{sorted(advertised)}"
            )


class TestSuggestedDataTypes:
    """suggested_data_types() returns classes, keys disjoint from supported."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_returns_dict(self, dialect):
        result = dialect.suggested_data_types()
        assert isinstance(result, dict)

    def test_values_are_type_classes(self, dialect):
        suggested = dialect.suggested_data_types()
        for name, cls in suggested.items():
            assert isinstance(cls, type) and issubclass(cls, DataType), (
                f"suggested_data_types()[{name!r}] = {cls!r} is not a DataType class"
            )

    def test_keys_disjoint_from_supported(self, dialect):
        supported = set(dialect.supports_data_types().keys())
        suggested = set(dialect.suggested_data_types().keys())
        overlap = supported & suggested
        assert not overlap, (
            f"Keys appear in both supports and suggested: {overlap}"
        )

    def test_every_substitute_is_a_type_this_dialect_renders(self, dialect):
        """A suggestion the backend cannot produce is worse than no suggestion.

        The whole map used to be made of classes this dialect had no formatter
        for: ``IntervalType``, ``ArrayType``, ``JsonBType``, ``TimestampTzType``
        and ``TimeTzType`` were each handed back to a caller as the answer and
        then refused on render.  D9 asks for "what this backend stores instead",
        and that has to be a thing this backend stores.
        """
        supported = dialect.supports_data_types()
        suggested = dialect.suggested_data_types()
        for key, substitute in sorted(suggested.items()):
            assert substitute.name in supported, (
                f"suggested_data_types()[{key!r}] is {substitute.__name__}, "
                f"whose name {substitute.name!r} this dialect does not render"
            )

    def test_suggests_unsupported_core_types(self, dialect):
        suggested = dialect.suggested_data_types()
        # Concepts SQL Server has no T-SQL word for.
        for name in ["uuid", "interval", "array", "enum", "jsonb", "timetz",
                      "binary", "varbinary"]:
            assert name in suggested, (
                f"Expected suggestion for {name!r} in suggested_data_types()"
            )

    def test_does_not_suggest_what_it_renders(self, dialect):
        """``xml`` and ``timestamptz`` have native SQL Server types.

        Substituting text for ``xml`` or a zoneless ``DATETIME2`` for
        ``timestamptz`` would describe a backend that is not this one.
        """
        suggested = dialect.suggested_data_types()
        for name in ("xml", "timestamptz"):
            assert name not in suggested, (
                f"{name!r} is rendered natively on SQL Server "
                f"({'XML' if name == 'xml' else 'DATETIMEOFFSET'}); it must not "
                f"be substituted"
            )
            assert name in dialect.supports_data_types()

    def test_uuid_substitute_is_the_backend_class_not_the_core_one(self, dialect):
        """``uuid`` maps to ``UNIQUEIDENTIFIER``, which this dialect renders.

        It used to map to the core ``UUIDType``, whose ``name`` equals the key —
        and which this dialect cannot render, so the suggestion could not be
        followed.  Pointing at ``SQLServerUniqueIdentifierType`` is the answer
        D9 asks for: a class whose own ``name`` *is* in ``supports_data_types()``.
        """
        assert dialect.suggested_data_types()["uuid"] is SQLServerUniqueIdentifierType

    def test_jsonb_substitute_is_json_because_sql_server_has_one_json(self, dialect):
        """``jsonb`` is PostgreSQL's binary JSON; SQL Server has no such split."""
        assert dialect.suggested_data_types()["jsonb"] is JsonType
        assert dialect.suggested_data_types()["array"] is JsonType


class TestSpellingGates:
    """Which spellings of one concept this dialect renders."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    #: The rendering table this backend commits to.  Locked here so a change to
    #: any one row has to be a deliberate edit to this test rather than an
    #: accident.
    RENDERED = {
        "integer": {"integer": "INT", "int": "INT"},
        "bigint": {"bigint": "BIGINT", "int8": "BIGINT"},
        "smallint": {"smallint": "SMALLINT", "int2": "SMALLINT"},
        "tinyint": {"tinyint": "TINYINT", "int1": "TINYINT"},
        "double": {"double": "FLOAT(53)", "double precision": "FLOAT(53)"},
        "decimal": {"decimal": "DECIMAL", "numeric": "DECIMAL", "dec": "DECIMAL"},
        "boolean": {"boolean": "BIT", "bool": "BIT"},
        "char": {"char": "CHAR(1)", "character": "CHAR(1)"},
        "varchar": {"varchar": "VARCHAR(255)", "character varying": "VARCHAR(255)"},
        "text": {"text": "NVARCHAR(MAX)", "clob": "NVARCHAR(MAX)"},
        "blob": {"blob": "VARBINARY(MAX)", "bytea": "VARBINARY(MAX)"},
    }

    CLASSES = {
        "integer": IntegerType,
        "bigint": BigIntType,
        "smallint": SmallIntType,
        "tinyint": TinyIntType,
        "double": DoubleType,
        "decimal": DecimalType,
        "boolean": BooleanType,
        "char": CharType,
        "varchar": VarCharType,
        "text": TextType,
        "blob": BlobType,
    }

    @pytest.mark.parametrize("concept", sorted(RENDERED))
    def test_spelling_renders_as_declared(self, dialect, concept):
        for spelling, expected in self.RENDERED[concept].items():
            sql, _ = dialect.format_data_type(self.CLASSES[concept](
                dialect, spelling=spelling))
            assert sql == expected, f"{concept}[{spelling!r}] rendered {sql!r}"

    @pytest.mark.parametrize("concept", sorted(RENDERED))
    def test_an_unknown_spelling_is_refused_and_named(self, dialect, concept):
        """The closed list is what makes the spelling safe.

        Without the gate an arbitrary string would reach the SQL.  With it, the
        caller is told which spelling is the problem and what the accepted set
        is — and ``TINYINT; DROP TABLE`` is a ``TypeError``, not a statement.

        The probe is chosen per concept: ``int4`` is a documented synonym of
        ``INTEGER`` and so is inside that concept's list, which is what made a
        hardcoded probe fail for one concept and pass for the rest.
        """
        klass = self.CLASSES[concept]
        unknown = _absent_spelling(klass)
        with pytest.raises(TypeError, match=unknown):
            dialect.format_data_type(klass(dialect, spelling=unknown))

    def test_no_int_key_in_the_dispatch_family(self, dialect):
        """``int`` is a spelling, so it has no ``format_data_type_int``.

        It had one, which meant two dispatch keys for one concept and a
        ``supports_data_types()`` entry that vanished because no class is named
        ``int`` any more.
        """
        assert not hasattr(dialect, "format_data_type_int")
        assert not hasattr(dialect, "supports_data_type_int")

    def test_timestamptz_is_version_gated(self):
        """``DATETIMEOFFSET`` is SQL Server 2008+."""
        assert SQLServerDialect(SQL_SERVER_2005).supports_data_type_timestamptz() is False
        assert SQLServerDialect(SQL_SERVER_2022).supports_data_type_timestamptz() is True


class TestSQLServerTypeSupportProtocol:
    """The stated shape of the backend's own type family."""

    def test_dialect_implements_the_family(self):
        assert isinstance(SQLServerDialect(SQL_SERVER_2022), SQLServerTypeSupport)

    def test_the_family_is_stated_not_implied(self):
        for name in ("supports_data_type_sqlserver_nvarchar",
                     "supports_data_type_sqlserver_nchar",
                     "supports_data_type_sqlserver_nvarchar_max",
                     "supports_data_type_sqlserver_varbinary",
                     "supports_data_type_sqlserver_varbinary_max",
                     "supports_data_type_sqlserver_image",
                     "supports_data_type_sqlserver_tinyint",
                     "supports_data_type_sqlserver_bit",
                     "supports_data_type_sqlserver_xml",
                     "supports_data_type_sqlserver_uniqueidentifier"):
            assert name in vars(SQLServerTypeSupport), (
                f"{name} is dispatched on but not stated in the protocol"
            )


class TestDialectOptionsRemoved:
    """The data-type value objects no longer carry a dialect_options bag."""

    def test_constructor_rejects_dialect_options(self):
        with pytest.raises(TypeError):
            SQLServerNVarCharType(length=100, dialect_options={"foo": "bar"})




    def test_varbinary_identity(self):
        assert SQLServerVarBinaryType.PARAMETERS == ("length",)
        t = SQLServerVarBinaryType(length=512)
        assert t.identity() == (512,)
        assert t != SQLServerVarBinaryType(length=255)

    def test_varbinary_equality(self):
        t1 = SQLServerVarBinaryType(length=512)
        t2 = SQLServerVarBinaryType(length=512)
        t3 = SQLServerVarBinaryType(length=1024)
        assert t1 == t2
        assert t1 != t3

    def test_decimal_identity(self, sqlserver_dialect):
        # Precision, scale and signedness are identity. The spelling is not:
        # DECIMAL(10,2) and NUMERIC(10,2) are the same column to the server,
        # which reports one word for both, so counting it would report a change
        # that was never made. The declared word is still what gets rendered.
        assert DecimalType.PARAMETERS == ("precision", "scale", "unsigned")
        t = DecimalType(precision=10, scale=2)
        assert t.identity() == (10, 2, False)
        assert DecimalType(precision=10, scale=2, spelling="numeric") == t
        assert DecimalType(sqlserver_dialect, 10, 2,
                         spelling="numeric").to_sql()[0] \
            == "DECIMAL(10, 2)"
        # scale really is part of identity, unlike the spelling
        assert DecimalType(precision=10, scale=2) != DecimalType(precision=10)

    def test_decimal_unsigned_is_refused_not_ignored(self, sqlserver_dialect):
        """``unsigned`` joined ``PARAMETERS``; T-SQL cannot express it.

        So the field is identity (a signed and an unsigned DECIMAL(10,2) are
        different columns to the differ) and the formatter refuses it by name
        rather than rendering the signed column and reporting success.
        """
        assert DecimalType(precision=10, scale=2) != DecimalType(
            precision=10, scale=2, unsigned=True)
        assert hash(DecimalType(precision=10, scale=2)) != hash(
            DecimalType(precision=10, scale=2, unsigned=True))
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            sqlserver_dialect.format_data_type(
                DecimalType(sqlserver_dialect, 10, 2, unsigned=True))
        assert "unsigned" in str(excinfo.value)
        assert excinfo.value.suggestion

    def test_float_identity(self):
        assert FloatType.PARAMETERS == ("precision", "unsigned")
        t = FloatType(precision=24)
        assert t.identity() == (24, False)
        assert t != FloatType()

    def test_float_unsigned_is_refused_not_ignored(self, sqlserver_dialect):
        assert FloatType(precision=24) != FloatType(precision=24, unsigned=True)
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            sqlserver_dialect.format_data_type(
                FloatType(sqlserver_dialect, 24, unsigned=True))
        assert "unsigned" in str(excinfo.value)

    def test_double_unsigned_is_refused_not_ignored(self, sqlserver_dialect):
        assert DoubleType() != DoubleType(unsigned=True)
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            sqlserver_dialect.format_data_type(
                DoubleType(sqlserver_dialect, unsigned=True))
        assert "unsigned" in str(excinfo.value)
        # ...and the signed rendering is exactly what it was.
        assert sqlserver_dialect.format_data_type(
            DoubleType(sqlserver_dialect)) == ("FLOAT(53)", ())

    def test_datetime_identity(self):
        assert DateTimeType.PARAMETERS == ("precision",)
        t = DateTimeType(precision=3)
        assert t.identity() == (3,)
        assert t != DateTimeType()


class TestPrecisionValidation:
    """Precision parameters are validated per SQL Server rules."""

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_decimal_precision_too_high(self, dialect):
        with pytest.raises(ValueError, match="precision must be 1-38"):
            dialect.format_data_type(DecimalType(precision=39, scale=0))

    def test_decimal_scale_exceeds_precision(self, dialect):
        with pytest.raises(ValueError, match="scale.*must not exceed precision"):
            dialect.format_data_type(DecimalType(precision=5, scale=10))

    def test_decimal_valid(self, dialect):
        sql, _ = dialect.format_data_type(DecimalType(precision=38, scale=38))
        assert sql == "DECIMAL(38, 38)"

    def test_float_precision_too_high(self, dialect):
        with pytest.raises(ValueError, match="precision must be 1-53"):
            dialect.format_data_type(FloatType(precision=54))

    def test_float_precision_zero(self, dialect):
        with pytest.raises(ValueError, match="precision must be 1-53"):
            dialect.format_data_type(FloatType(precision=0))

    def test_float_valid(self, dialect):
        sql, _ = dialect.format_data_type(FloatType(precision=53))
        assert sql == "FLOAT(53)"

    def test_datetime_precision_too_high(self, dialect):
        with pytest.raises(ValueError, match="precision.*must be 0-7"):
            dialect.format_data_type(DateTimeType(precision=8))

    def test_datetime_precision_negative(self, dialect):
        with pytest.raises(ValueError, match="precision.*must be 0-7"):
            dialect.format_data_type(DateTimeType(precision=-1))

    def test_datetime_valid(self, dialect):
        sql, _ = dialect.format_data_type(DateTimeType(precision=7))
        assert sql == "DATETIME2(7)"

    def test_time_precision_too_high(self, dialect):
        with pytest.raises(ValueError, match="precision.*must be 0-7"):
            dialect.format_data_type(TimeType(precision=8))

    def test_time_valid(self, dialect):
        sql, _ = dialect.format_data_type(TimeType(precision=3))
        assert sql == "TIME(3)"

    def test_timestamp_precision_validation(self, dialect):
        with pytest.raises(ValueError, match="precision.*must be 0-7"):
            dialect.format_data_type(TimestampType(precision=8))

    def test_timestamptz_precision_validation(self, dialect):
        """``DATETIMEOFFSET`` bounds fractional seconds at 7 like DATETIME2."""
        assert dialect.format_data_type(TimestampTzType(dialect, precision=7))[0] == (
            "DATETIMEOFFSET(7)"
        )
        with pytest.raises(ValueError, match="precision.*must be 0-7"):
            dialect.format_data_type(TimestampTzType(dialect, precision=8))


class TestConceptAnchoring:
    """A backend type that says "I am this concept" must be that concept.

    These are the three assertions the previous hierarchy got wrong, so they are
    written as guards rather than as comments: the mistake was invisible to the
    renderer (dispatch runs on ``name``) and invisible to equality (it ran on
    ``type(self)``), so nothing else would have caught a reversion.
    """

    def test_xml_is_the_xml_concept_and_not_a_varchar(self):
        assert issubclass(SQLServerXmlType, XmlType)
        assert not issubclass(SQLServerXmlType, VarCharType)
        assert not issubclass(SQLServerXmlType, TextType)

    def test_tinyint_is_the_eight_bit_concept_and_not_a_32_bit_integer(self):
        assert issubclass(SQLServerTinyIntType, TinyIntType)
        assert not issubclass(SQLServerTinyIntType, IntegerType)

    def test_tinyint_records_that_it_is_unsigned(self):
        """Signedness is a field (D5), so it is asserted through the field.

        ``unsigned`` is fixed to ``True`` because no T-SQL spelling of this type
        is signed, and it is declared in identity so a comparison against a
        signed ``TinyIntType`` — or against ``INTEGER`` — actually differs.
        """
        assert SQLServerTinyIntType.PARAMETERS == ("unsigned",)
        tinyint = SQLServerTinyIntType()
        assert tinyint.unsigned is True
        assert tinyint.identity() == (True,)
        assert tinyint != TinyIntType()
        assert tinyint != TinyIntType(unsigned=True)
        assert tinyint != IntegerType()

    def test_tinyint_keeps_both_spellings(self):
        """``TINYINT`` and ``INT1`` both render, and neither is a different type.

        The spelling is **not** in ``PARAMETERS``, so the two instances are
        deliberately *not* equal — the declaration differs even though the
        rendered SQL does not.  What matters here is that both spellings are
        accepted rather than one being refused.
        """
        dialect = SQLServerDialect(SQL_SERVER_2022)
        assert dialect.format_data_type(SQLServerTinyIntType())[0] == "TINYINT"
        assert dialect.format_data_type(
            SQLServerTinyIntType(dialect, spelling="int1"))[0] == "TINYINT"
        with pytest.raises(TypeError, match="int2"):
            dialect.format_data_type(
                SQLServerTinyIntType(dialect, spelling="int2"))

    def test_bit_is_the_boolean_and_not_a_bit_string(self):
        """SQL Server's ``BIT`` is 0/1/NULL (D6).

        The same *spelling* in MySQL and PostgreSQL is a bit string of ``n``
        bits, which is why those backends keep their own root-level class.  The
        consequence worth locking is that this class is a ``BooleanType`` and
        takes no bit count.
        """
        assert issubclass(SQLServerBitType, BooleanType)
        with pytest.raises(TypeError):
            SQLServerBitType(n=8)

    def test_uniqueidentifier_is_the_uuid_concept(self):
        assert issubclass(SQLServerUniqueIdentifierType, UUIDType)

    def test_rendered_sql_is_unchanged_by_the_reparenting(self):
        """The three re-parented classes render exactly what they always did.

        Dispatch runs on ``name``, so a re-parenting cannot change the SQL —
        which is precisely why this assertion is here and not merely assumed.
        """
        dialect = SQLServerDialect(SQL_SERVER_2022)
        assert dialect.format_data_type(SQLServerXmlType(dialect)) == ("XML", ())
        assert dialect.format_data_type(SQLServerTinyIntType(dialect)) == ("TINYINT", ())
        assert dialect.format_data_type(SQLServerBitType(dialect)) == ("BIT", ())
        assert dialect.format_data_type(SQLServerUniqueIdentifierType(dialect)) == (
            "UNIQUEIDENTIFIER", ()
        )
        assert dialect.format_data_type(XmlType(dialect)) == ("XML", ())

    def test_dialect_is_the_first_positional_parameter(self):
        """A signature that puts ``length`` first fails *silently*.

        ``SQLServerNVarCharType(dialect, 100)`` follows the documented
        convention; a dialect passed to ``(100, dialect)`` would be stored as
        the length and the error would only surface at render time.
        """
        dialect = SQLServerDialect(SQL_SERVER_2022)
        t = SQLServerNVarCharType(dialect, 100)
        assert t.dialect is dialect
        assert t.length == 100
        assert t.to_sql() == ("NVARCHAR(100)", ())
        assert SQLServerVarBinaryType(dialect, 64).to_sql() == ("VARBINARY(64)", ())


class TestBitTakesNoWidth:
    """``parse_type("bit(1)")`` used to escape as a bare ``KeyError``.

    Appendix F.4-8: the BIT branch spelled its three spellings out in an
    exact-match dictionary keyed by the whole uppercased word, so a
    parenthesised form fell past the lookup and raised ``KeyError: 'BIT(1)'``
    from inside a parser whose documented answer for anything it cannot map is
    a type (or ``CustomType``), never a crash.  The measurement that settles
    the replacement: all three live instances (SQL Server 2019 15.0.4465.1,
    2022 16.0.4250.1, 2025 17.0.4035.5) reject ``CREATE TABLE t (b bit(1))``
    with error 2716, "Cannot specify a column width on data type bit." — so the
    width is not a spelling to be silently dropped; it is an invalid
    declaration, and the parser says so with the ``ValueError`` this module
    uses for values the server itself rejects.
    """

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    @pytest.mark.parametrize("raw", ["BIT", "bit", "BOOL", "bool",
                                     "BOOLEAN", "boolean"])
    def test_bare_spellings_still_parse_to_the_bit_class(self, dialect, raw):
        assert isinstance(dialect.parse_type(raw), SQLServerBitType)

    @pytest.mark.parametrize("raw", ["BIT(1)", "bit(1)", "BIT(0)", "BOOL(1)",
                                     "bit (1)"])
    def test_a_width_is_refused_with_the_server_answer(self, dialect, raw):
        with pytest.raises(ValueError,
                           match="Cannot specify a column width on data type bit") as excinfo:
            dialect.parse_type(raw)
        assert "2716" in str(excinfo.value)
        # A server-rejected value, not an inexpressible declaration: the two
        # exception families stay apart, as everywhere else in this file.
        assert not isinstance(excinfo.value, UnsupportedFeatureError)


# --- unsigned is a field, so it must be honoured or refused ---

#: Every integer formatter on this backend, with the signed SQL it has always
#: rendered and the word its refusal names.
#:
#: The evidence is T-SQL's own documentation, and it splits the four widths in
#: two, which is why the message does too:
#:
#:   * ``bigint`` -2^63 to 2^63-1, ``int`` -2^31 to 2^31-1, ``smallint`` -2^15
#:     to 2^15-1, and the exact-numeric category is closed
#:     (tinyint/smallint/int/bigint/bit/decimal/numeric/money/smallmoney), so
#:     those three have no unsigned form —
#:     https://learn.microsoft.com/en-us/sql/t-sql/data-types/data-types-transact-sql
#:     https://learn.microsoft.com/en-us/sql/t-sql/data-types/int-bigint-smallint-and-tinyint-transact-sql
#:   * ``<column_definition>`` has no type modifier after ``<data_type>`` — no
#:     ``UNSIGNED`` token, so there is not even a spelling that would parse —
#:     https://learn.microsoft.com/en-us/sql/t-sql/statements/create-table-transact-sql
#:   * ``tinyint`` is documented "0 to 255" (``2^0-1 to 2^8-1``), i.e. it *is*
#:     the unsigned 8-bit integer, which is why that width is refused by name
#:     rather than by the "no unsigned integer type" argument.
INTEGER_WIDTHS = [
    (TinyIntType, "TINYINT"),
    (SmallIntType, "SMALLINT"),
    (IntegerType, "INT"),
    (BigIntType, "BIGINT"),
]

INTEGER_WIDTH_IDS = [klass.name for klass, _word in INTEGER_WIDTHS]


class TestIntegerSignednessIsRefused:
    """``unsigned`` is in the integer concepts' ``PARAMETERS``, so it is part of
    their identity — and the four core formatters used to never read it:
    ``IntegerType(unsigned=True)`` rendered a plain ``INT``, so the constructor
    accepted a signedness and the render threw it away.

    That is the paradigm violation this file's round exists to close: the
    declared column is not the column the caller gets, the SQL is byte-identical
    to the signed declaration, and nothing reports it.  Either the field changes
    the rendering or the render stops with a message that says why.
    """

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    @pytest.mark.parametrize("klass,signed_sql", INTEGER_WIDTHS,
                             ids=INTEGER_WIDTH_IDS)
    def test_the_signed_rendering_is_unchanged(self, dialect, klass, signed_sql):
        """The refusal is not paid for by moving the signed rendering.

        These four words are what this dialect has always emitted, default flag
        and explicit ``unsigned=False`` alike.
        """
        assert dialect.format_data_type(klass(dialect)) == (signed_sql, ())
        assert dialect.format_data_type(
            klass(dialect, unsigned=False)) == (signed_sql, ())

    @pytest.mark.parametrize("klass,signed_sql", INTEGER_WIDTHS,
                             ids=INTEGER_WIDTH_IDS)
    def test_unsigned_is_refused_not_rendered_signed(self, dialect, klass,
                                                     signed_sql):
        """The defect itself: flipping the field stops the render."""
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect.format_data_type(klass(dialect, unsigned=True))
        message = str(excinfo.value)
        assert signed_sql in message, (
            f"{message!r} does not name the width {signed_sql!r}")
        assert "unsigned" in message

    @pytest.mark.parametrize("klass,signed_sql", INTEGER_WIDTHS,
                             ids=INTEGER_WIDTH_IDS)
    def test_the_refusal_says_what_to_do_instead(self, dialect, klass,
                                                 signed_sql):
        """A refusal with no route forward is the same as silence, only louder.

        Every one of the four points at something the caller can actually
        declare: a ``CHECK`` constraint where the backend has no unsigned type
        at all, and :class:`SQLServerTinyIntType` on the one width whose
        unsigned column T-SQL really does have.
        """
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect.format_data_type(klass(dialect, unsigned=True))
        message = str(excinfo.value)
        suggestion = excinfo.value.suggestion
        assert suggestion, "the refusal must carry a way forward"
        if signed_sql == "TINYINT":
            assert "SQLServerTinyIntType" in message
            assert "SQLServerTinyIntType" in suggestion
        else:
            assert "no unsigned integer type" in message
            assert "CHECK" in suggestion

    @pytest.mark.parametrize("klass,signed_sql", INTEGER_WIDTHS,
                             ids=INTEGER_WIDTH_IDS)
    def test_the_named_way_forward_actually_renders(self, dialect, klass,
                                                    signed_sql):
        """Advice that does not run is worse than a bare refusal.

        ``SQLServerTinyIntType`` is the class that declares the unsigned 8-bit
        column, so the suggestion must name something this dialect renders and
        must render it.
        """
        if signed_sql != "TINYINT":
            pytest.skip("only the 8-bit width has a class to point at")
        assert dialect.format_data_type(SQLServerTinyIntType(dialect)) == (
            "TINYINT", ()
        )
        assert SQLServerTinyIntType(dialect).unsigned is True

    @pytest.mark.parametrize("klass,signed_sql", INTEGER_WIDTHS,
                             ids=INTEGER_WIDTH_IDS)
    def test_a_bad_spelling_is_still_the_spelling_error(self, dialect, klass,
                                                        signed_sql):
        """Order is part of the contract: the spelling gate runs first.

        The probe is chosen per concept, because a hardcoded one goes stale —
        ``int4`` is a documented synonym of ``INTEGER`` and so is inside that
        concept's list.  If the signedness check ran first the caller would be
        told about ``unsigned``'s meaning on a request whose actual fault is a
        malformed word, and the closed list would stop being the only thing
        standing between an arbitrary string and the DDL.
        """
        unknown = _absent_spelling(klass)
        with pytest.raises(TypeError, match=unknown):
            dialect.format_data_type(
                klass(dialect, spelling=unknown, unsigned=True))

    @pytest.mark.parametrize("klass,signed_sql", INTEGER_WIDTHS,
                             ids=INTEGER_WIDTH_IDS)
    def test_no_spelling_reaches_an_unsigned_column(self, dialect, klass,
                                                    signed_sql):
        """Both spellings of each concept are refused for an unsigned request.

        Some backends accept only one of a concept's spellings; this one
        accepts them all and normalises to the T-SQL word.  Either way, no
        spelling may be a way round the refusal, or the closed list would be a
        decoration.
        """
        for spelling in klass.SPELLINGS:
            assert dialect.format_data_type(
                klass(dialect, spelling=spelling)) == (signed_sql, ())
            with pytest.raises(UnsupportedFeatureError):
                dialect.format_data_type(
                    klass(dialect, spelling=spelling, unsigned=True))

    @pytest.mark.parametrize("klass,signed_sql", INTEGER_WIDTHS,
                             ids=INTEGER_WIDTH_IDS)
    def test_signedness_still_participates_in_identity(self, dialect, klass,
                                                      signed_sql):
        """Why refusing is the right answer: the two are different types.

        ``unsigned`` is in ``PARAMETERS``, so it reaches ``identity()`` and the
        differ can see that a caller changed its mind.  Refusing at render time
        stops the DDL from lying about that; it must not flatten the model to
        make the refusal easier.
        """
        assert klass.PARAMETERS == ("unsigned",), klass.__name__
        signed = klass(dialect)
        unsigned = klass(dialect, unsigned=True)
        assert signed.identity() == (False,)
        assert unsigned.identity() == (True,)
        assert signed != unsigned
        assert hash(signed) != hash(unsigned)
        # ...and a signed declaration still equals itself and hashes equal.
        assert klass(dialect) == signed
        assert hash(klass(dialect)) == hash(signed)
        assert hash(signed) == hash(klass(dialect))

    @pytest.mark.parametrize("name", [klass.name for klass, _w in INTEGER_WIDTHS])
    def test_no_integer_formatter_drops_the_flag_silently(self, dialect, name):
        """The rule in one assertion, over every width this dialect renders:
        flipping the field either changes the SQL or raises.  Byte-identical SQL
        for both signs is the violation, whatever the reason for it.
        """
        klass = dialect.supports_data_types()[name]
        signed = dialect.format_data_type(klass(dialect))[0]
        try:
            unsigned = dialect.format_data_type(
                klass(dialect, unsigned=True))[0]
        except UnsupportedFeatureError:
            return  # refused — the other permitted answer
        assert unsigned != signed, (
            f"{name}: unsigned=True renders {unsigned!r}, the same as "
            f"unsigned=False — the flag is silently dropped")

    def test_the_backend_class_pins_the_flag_so_it_cannot_be_flipped(self, dialect):
        """``SQLServerTinyIntType`` owns the unsigned 8-bit column.

        It pins ``unsigned=True`` in its own ``__init__``, so its formatter
        cannot be reached with ``unsigned=False`` and has nothing to refuse —
        which is why the gate sits on the generic concept instead.
        """
        assert SQLServerTinyIntType.PARAMETERS == ("unsigned",)
        with pytest.raises(TypeError):
            SQLServerTinyIntType(dialect, unsigned=False)
        assert dialect.format_data_type(SQLServerTinyIntType(dialect)) == (
            "TINYINT", ()
        )

    def test_sql_server_has_exactly_one_unsigned_integer(self):
        """Guards the conclusion the messages rest on, not the code.

        Every server-side claim in ``_refuse_unsigned_integer`` is
        documentation-based — there is no SQL Server in this environment to
        measure — so the evidence is written out here, and this fails if a
        future reference documents an unsigned variant of one of the three
        signed widths.
        """
        documented_ranges = {
            "BIGINT": "-9,223,372,036,854,775,808 to 9,223,372,036,854,775,807",
            "INT": "-2,147,483,648 to 2,147,483,647",
            "SMALLINT": "-32,768 to 32,767",
            "TINYINT": "0 to 255",
        }
        for _klass, word in INTEGER_WIDTHS:
            assert word in documented_ranges, word
        # A range that reaches below zero is a signed one, and only TINYINT's
        # does not — which is exactly why the four refusals do not share one
        # reason and why two of them are two different messages.
        unsigned_words = {
            word for word, span in documented_ranges.items()
            if not span.split(" to ")[0].startswith("-")
        }
        assert unsigned_words == {"TINYINT"}

    def test_the_range_table_the_messages_quote_is_registered(self):
        """The formatters are copied onto the dialect class, so a table that
        stayed on the mixin would be an ``AttributeError`` at render time —
        which the refusal test would surface as a missing range, not as the
        reason.  Assert the copy directly instead.
        """
        ranges = SQLServerDialect._SQLSERVER_INTEGER_RANGES
        assert set(ranges) == {"INT", "SMALLINT", "BIGINT"}, ranges
        assert "TINYINT" not in ranges, (
            "TINYINT is refused by _refuse_unsigned_tinyint, which quotes no "
            "signed range because there is none"
        )


# ---------------------------------------------------------------------------
# DECIMAL scale: honoured when anchored to a precision, refused when not
# ---------------------------------------------------------------------------

#: The T-SQL grammar this backend's ``decimal`` formatters implement, as the
#: reference writes it.  Quoted here rather than only in the formatter because
#: every server-side claim on this file is documentation-based — there is no SQL
#: Server in this environment (``pyodbc`` has no data source) to measure — and a
#: test that only asserted behaviour would keep passing if the vendor changed
#: the grammar.
#: https://learn.microsoft.com/en-us/sql/t-sql/data-types/decimal-and-numeric-transact-sql
SQL_SERVER_DECIMAL_GRAMMAR = "decimal [ ( p [ , s ] ) ] and numeric [ ( p [ , s ] ) ]"

SQL_SERVER_SCALE_RULE = (
    "Scale must be a value from 0 through p, and can only be specified if "
    "precision is specified."
)

#: Every concept this dialect renders whose ``PARAMETERS`` carry a precision or a
#: scale field, with the T-SQL it renders when the field is left alone.  Five of
#: these six honour the field outright; ``DecimalType`` is the odd one out
#: because ``scale`` alone is not a declaration T-SQL admits.
FRACTIONAL_FIELDS = [
    (FloatType, ("precision",), "FLOAT"),
    (DateTimeType, ("precision",), "DATETIME2"),
    (TimeType, ("precision",), "TIME"),
    (TimestampType, ("precision",), "DATETIME2"),
    (TimestampTzType, ("precision",), "DATETIMEOFFSET"),
    (DecimalType, ("precision", "scale"), "DECIMAL"),
]

FRACTIONAL_FIELD_IDS = [
    f"{klass.name}.{'+'.join(fields)}"
    for klass, fields, _sql in FRACTIONAL_FIELDS
]

#: A value to flip each field to, chosen so the probe distinguishes "honoured"
#: from "refused" and not "refused because the number was out of range": every
#: one of these is inside the documented bound for its field on every formatter
#: below (``FLOAT`` 1-53, ``DATETIME2``/``TIME``/``DATETIMEOFFSET`` 0-7,
#: ``DECIMAL`` precision 1-38 with 0 <= s <= p).
FRACTIONAL_PROBE_VALUES = {"precision": 3, "scale": 2}


def _rendered_concepts_with_a_fractional_field(dialect):
    """Every concept this dialect renders whose ``PARAMETERS`` name ``precision``
    or ``scale``, found by walking the supported-types mapping.

    Walked rather than listed so the table above cannot quietly fall behind: a
    new concept with a fractional field turns up here and fails the equality
    check against it.
    """
    found = {}
    for klass in dialect.supports_data_types().values():
        fields = tuple(
            field for field in klass.PARAMETERS
            if field in FRACTIONAL_PROBE_VALUES
        )
        if fields:
            found[klass] = fields
    return found


class TestFractionalFieldsAreHonouredOrRefused:
    """``precision`` and ``scale`` are in ``PARAMETERS``, so they are part of
    these types' identity.

    Five of the six formatters here already read their field and render it.
    ``DecimalType`` did not read ``scale`` unless a precision came with it, so a
    scale on its own rendered bare ``DECIMAL`` — a different column to
    ``identity()`` and to the differ, with byte-identical DDL.  That is the
    paradigm violation, and the fix is a refusal rather than a rewrite, because
    T-SQL has no declaration for a bare scale.
    """

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_the_table_is_every_rendered_concept_with_a_fractional_field(self,
                                                                        dialect):
        """The list above is the complete set, not a sample."""
        assert _rendered_concepts_with_a_fractional_field(dialect) == {
            klass: fields for klass, fields, _sql in FRACTIONAL_FIELDS
        }, (
            "a concept this dialect renders has gained, lost or renamed a "
            "precision/scale identity field; the table and its refusals must "
            "follow it"
        )

    @pytest.mark.parametrize("klass,fields,sql", FRACTIONAL_FIELDS,
                             ids=FRACTIONAL_FIELD_IDS)
    def test_the_fieldless_rendering_is_unchanged(self, dialect, klass, fields,
                                                  sql):
        """The refusal is not paid for by moving the bare rendering.

        These are the SQL fragments each of these concepts has always produced
        here, for the default field *and* for every accepted spelling.
        """
        for spelling in (klass.SPELLINGS or (None,)):
            kwargs = {} if spelling is None else {"spelling": spelling}
            assert dialect.format_data_type(klass(dialect, **kwargs)) == (sql, ())

    @pytest.mark.parametrize("klass,fields,sql", FRACTIONAL_FIELDS,
                             ids=FRACTIONAL_FIELD_IDS)
    def test_no_fractional_field_is_silently_dropped(self, dialect, klass, fields,
                                                    sql):
        """The rule, in one assertion, over every fractional field this dialect
        renders: flipping it either changes the SQL or raises.

        Byte-identical SQL for both values is the violation, whatever the reason
        for it — which is why this asserts the *rule* rather than a list of the
        particular fields that were fixed.
        """
        for field in fields:
            value = FRACTIONAL_PROBE_VALUES[field]
            try:
                flipped = dialect.format_data_type(
                    klass(dialect, **{field: value}))[0]
            except UnsupportedFeatureError:
                continue  # refused — the other permitted answer
            assert flipped != sql, (
                f"{klass.__name__}.{field}={value!r} renders {flipped!r}, the "
                f"same as no {field} at all — the field is silently dropped"
            )

    @pytest.mark.parametrize("klass,fields,sql", FRACTIONAL_FIELDS,
                             ids=FRACTIONAL_FIELD_IDS)
    def test_the_field_still_participates_in_identity(self, dialect, klass, fields,
                                                     sql):
        """Why refusing is the right answer: the two really are different types.

        The fields are in ``PARAMETERS``, so they reach ``identity()`` and the
        differ.  Refusing at render time stops the DDL from lying about that; it
        must not flatten the model to make the refusal easier.
        """
        for field in fields:
            assert field in klass.PARAMETERS, f"{klass.__name__}.{field}"
            plain = klass(dialect)
            declared = klass(dialect, **{field: FRACTIONAL_PROBE_VALUES[field]})
            assert plain != declared, f"{klass.__name__}.{field}"
            assert hash(plain) != hash(declared), f"{klass.__name__}.{field}"
            assert plain == klass(dialect)


class TestDecimalScaleNeedsAPrecision:
    """``DecimalType.scale`` — T-SQL's grammar is ``decimal[(p[,s])]``.

    The scale is honoured on every request that carries a precision; a scale with
    nothing to attach it to is refused, because the reference says a scale "can
    only be specified if precision is specified" and there is no type-modifier
    position after the type name where one could go instead.
    https://learn.microsoft.com/en-us/sql/t-sql/data-types/decimal-and-numeric-transact-sql
    """

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    def test_the_renderings_that_carry_a_precision_are_unchanged(self, dialect):
        """Before and after are identical for every request with a precision."""
        assert dialect.format_data_type(DecimalType(dialect)) == ("DECIMAL", ())
        assert dialect.format_data_type(
            DecimalType(dialect, precision=10)) == ("DECIMAL(10)", ())
        assert dialect.format_data_type(
            DecimalType(dialect, precision=10, scale=0)) == ("DECIMAL(10, 0)", ())
        assert dialect.format_data_type(
            DecimalType(dialect, precision=10, scale=2)) == ("DECIMAL(10, 2)", ())
        assert dialect.format_data_type(
            DecimalType(dialect, precision=38, scale=38)) == ("DECIMAL(38, 38)", ())
        for spelling in DecimalType.SPELLINGS:
            assert dialect.format_data_type(
                DecimalType(dialect, precision=10, scale=2, spelling=spelling)
            ) == ("DECIMAL(10, 2)", ())

    def test_an_anchored_scale_is_honoured_not_merely_accepted(self, dialect):
        """The other permitted answer, pinned so it cannot be quietly swapped out.

        T-SQL's own reference is explicit that each pair is a distinct type:
        "SQL Server considers each combination of precision and scale as a
        different data type.  For example, decimal(5,5) and decimal(5,0) are
        considered different data types."  So this dialect renders them
        differently, and must keep doing so.
        """
        zero = dialect.format_data_type(
            DecimalType(dialect, precision=5, scale=0))[0]
        five = dialect.format_data_type(
            DecimalType(dialect, precision=5, scale=5))[0]
        assert five == "DECIMAL(5, 5)"
        assert zero != five
        assert DecimalType(dialect, precision=5, scale=0) != DecimalType(
            dialect, precision=5, scale=5)

    @pytest.mark.parametrize("scale", [0, 1, 2, 18, 38])
    def test_an_unanchored_scale_is_refused_not_ignored(self, dialect, scale):
        """The defect itself: flipping ``scale`` with no precision stops the
        render, where it used to render bare ``DECIMAL``."""
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect.format_data_type(DecimalType(dialect, scale=scale))
        message = str(excinfo.value)
        assert "scale" in message
        assert f"scale={scale}" in message
        assert "precision" in message, (
            f"{message!r} does not name the field that is missing"
        )

    def test_the_refusal_is_not_a_range_error(self, dialect):
        """``scale=38`` with no precision is a *shape* problem, not a range one.

        The existing range checks still answer for values T-SQL does bound: a
        scale that exceeds its precision, and a precision outside 1-38.  A bare
        scale is neither — it is a request with no spelling at all — so it is
        reported as the missing field it is rather than as an out-of-range
        number, which would send the caller looking in the wrong place.
        """
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_data_type(DecimalType(dialect, scale=38))
        with pytest.raises(ValueError, match="must not exceed precision"):
            dialect.format_data_type(DecimalType(dialect, precision=5, scale=10))
        with pytest.raises(ValueError, match="precision must be 1-38"):
            dialect.format_data_type(DecimalType(dialect, precision=39, scale=0))

    def test_the_refusal_says_what_to_do_instead(self, dialect):
        """The route is a declaration, and it renders."""
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect.format_data_type(DecimalType(dialect, scale=2))
        suggestion = excinfo.value.suggestion
        assert suggestion
        assert "precision" in suggestion
        assert dialect.format_data_type(
            DecimalType(dialect, precision=10, scale=2)) == ("DECIMAL(10, 2)", ())

    def test_the_bare_decimal_is_not_the_default_column_it_looks_like(self, dialect):
        """Why writing ``DECIMAL`` instead would be wrong, not merely lossy.

        T-SQL documents a default precision of 18 and a default scale of 0, so
        bare ``DECIMAL`` is ``DECIMAL(18, 0)`` — 18 digits, none of them
        fractional.  A caller who asked for ``scale=2`` and nothing else asked
        for a fractional column, and would have been handed one with none.  The
        refusal says what bare ``DECIMAL`` actually is so the caller can see the
        difference rather than infer it.
        """
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect.format_data_type(DecimalType(dialect, scale=2))
        assert "DECIMAL(18, 0)" in excinfo.value.suggestion
        assert "scale 0" in excinfo.value.suggestion

    def test_a_bad_spelling_is_still_the_spelling_error(self, dialect):
        """Order is part of the contract: the spelling gate runs first.

        Were the scale check to run first, a request whose actual fault is a
        malformed word would be told about scales instead — and the closed list
        would stop being the only thing standing between an arbitrary string and
        the DDL.
        """
        with pytest.raises(TypeError, match="int4"):
            dialect.format_data_type(
                DecimalType(dialect, spelling="int4", scale=2))

    def test_no_spelling_is_a_way_round_the_refusal(self, dialect):
        for spelling in DecimalType.SPELLINGS:
            with pytest.raises(UnsupportedFeatureError):
                dialect.format_data_type(
                    DecimalType(dialect, spelling=spelling, scale=2))

    def test_the_parser_never_produces_an_unanchored_scale(self, dialect):
        """The refusal cannot be reached from this dialect's own round trip.

        ``parse_type`` reads ``(p, s)`` with a regex whose first group is the
        precision, so a parsed ``scale`` always has a precision beside it — the
        refusal is unreachable from introspection, which is what makes refusing
        it safe.
        """
        for raw, expected in (
            ("DECIMAL(10,2)", "DECIMAL(10, 2)"),
            ("NUMERIC(10, 2)", "DECIMAL(10, 2)"),
            ("dec(10,2)", "DECIMAL(10, 2)"),
            ("DECIMAL(10)", "DECIMAL(10)"),
            ("DECIMAL", "DECIMAL"),
            ("NUMERIC", "DECIMAL"),
            ("MONEY", "DECIMAL"),
            ("SMALLMONEY", "DECIMAL"),
        ):
            assert dialect.format_data_type(dialect.parse_type(raw))[0] == expected, raw

    def test_the_documented_grammar_still_puts_the_scale_second(self):
        """Guards the conclusion the refusal rests on, not the code.

        The reference's own syntax line and its ``s`` entry are written out here
        so that a future version of the page which gave ``DECIMAL`` a bare scale
        fails here — at which point the refusal above is wrong rather than merely
        conservative.
        """
        assert SQL_SERVER_DECIMAL_GRAMMAR == (
            "decimal [ ( p [ , s ] ) ] and numeric [ ( p [ , s ] ) ]"
        )
        assert "can only be specified if precision is specified" in (
            SQL_SERVER_SCALE_RULE
        )


# ---------------------------------------------------------------------------
# Numbers outside the range the vendor documents — ValueError, not a refusal
# ---------------------------------------------------------------------------


#: The bound itself, from the rest of the same ``s`` (scale) entry above — the
#: part ``_check_decimal_scale_sign`` enforces, and the part the earlier
#: ``scale <= precision`` comparison could not see because it has no lower edge.
#: https://learn.microsoft.com/en-us/sql/t-sql/data-types/decimal-and-numeric-transact-sql
SQL_SERVER_SCALE_BOUND = "The default scale is 0, and so 0 <= s <= p."


class TestNegativeDecimalScaleIsRefused:
    """``DecimalType(precision=10, scale=-1)`` used to render ``DECIMAL(10, -1)``.

    The existing ``scale <= precision`` comparison could not see it, because
    ``-1`` is not greater than ``10`` — so the check passed, the statement was
    written, and the server rejected it.  Nothing was dropped: the declared value
    reached the DDL exactly as declared, which is why the fix belongs here, at the
    point where the mistake is made, and not in a clamp.

    The bound is the vendor's, quoted in the same entry that forbids a bare scale:
    "Scale must be a value from 0 through *p* ... and so 0 <= s <= p".
    https://learn.microsoft.com/en-us/sql/t-sql/data-types/decimal-and-numeric-transact-sql
    """

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    @pytest.mark.parametrize("precision,scale", [
        (10, -1), (1, -1), (38, -1), (5, -38), (10, -2), (1, -100),
    ])
    def test_a_negative_scale_is_refused(self, dialect, precision, scale):
        with pytest.raises(ValueError) as excinfo:
            dialect.format_data_type(
                DecimalType(dialect, precision=precision, scale=scale))
        message = str(excinfo.value)
        assert "must not be negative" in message, message
        assert f"got {scale}" in message, (
            f"the message must name the offending value; got {message!r}"
        )
        assert "0 <= s <= p" in message, (
            f"the message must quote the documented bound; got {message!r}"
        )

    def test_a_bare_negative_scale_is_refused_too(self, dialect):
        """No precision is needed to know a negative scale is wrong.

        The lower bound holds for every precision — the smallest documented
        precision is 1 — so ``scale=-1`` cannot be rescued by adding one.  That
        is why it is a range error rather than the un-anchorable-scale refusal:
        telling the caller to "declare the precision as well" would be advice
        that does not work.
        """
        with pytest.raises(ValueError, match="must not be negative"):
            dialect.format_data_type(DecimalType(dialect, scale=-1))

    def test_it_is_not_clamped_to_zero(self, dialect):
        """Clamping would be the same defect as the silent drop it replaces.

        ``DECIMAL(10, 0)`` is a column other than the one declared, and the
        caller would never be told.
        """
        with pytest.raises(ValueError):
            dialect.format_data_type(
                DecimalType(dialect, precision=10, scale=-1))
        assert dialect.format_data_type(
            DecimalType(dialect, precision=10, scale=0)) == ("DECIMAL(10, 0)", ())

    def test_it_is_a_value_error_and_not_a_refusal(self, dialect):
        """The cross-backend convention, checked rather than assumed.

        ``UnsupportedFeatureError`` does **not** subclass ``ValueError``, so the
        two are not interchangeable to a caller writing an ``except`` clause, and
        only the second carries a route forward.  ``DECIMAL(p, s)`` with ``s < 0``
        is a declaration this grammar expresses perfectly well — the number is
        what is wrong — so it must not answer with the inexpressible-declaration
        error.
        """
        with pytest.raises(ValueError) as excinfo:
            dialect.format_data_type(DecimalType(dialect, precision=10, scale=-1))
        assert not isinstance(excinfo.value, UnsupportedFeatureError)

    def test_the_scale_bounds_still_hold_on_either_side(self, dialect):
        """The neighbouring boundaries, so the new check cannot have moved them."""
        assert dialect.format_data_type(
            DecimalType(dialect, precision=10, scale=0)) == ("DECIMAL(10, 0)", ())
        assert dialect.format_data_type(
            DecimalType(dialect, precision=10, scale=10)) == ("DECIMAL(10, 10)", ())
        with pytest.raises(ValueError, match="must not exceed precision"):
            dialect.format_data_type(
                DecimalType(dialect, precision=10, scale=11))
        # T-SQL's documented precision ceiling, unchanged.
        assert dialect.format_data_type(
            DecimalType(dialect, precision=38, scale=38)) == ("DECIMAL(38, 38)", ())
        with pytest.raises(ValueError, match="precision must be 1-38"):
            dialect.format_data_type(
                DecimalType(dialect, precision=39, scale=0))
        with pytest.raises(ValueError, match="precision must be 1-38"):
            dialect.format_data_type(
                DecimalType(dialect, precision=0, scale=0))

    def test_the_precision_bound_is_still_enforced_on_the_scaled_path(self,
                                                                      dialect):
        """``1..38`` is checked on the path that carries a scale as well.

        Both bounds live on the same path in ``format_data_type_decimal``, so a
        check added for one can quietly disable the other; this pins both.
        """
        for precision in (0, 39, 100):
            for scale in (None, 0, 5):
                with pytest.raises(ValueError, match="precision must be 1-38"):
                    dialect.format_data_type(DecimalType(
                        dialect, precision=precision, scale=scale))

    def test_a_bad_spelling_is_still_the_spelling_error(self, dialect):
        """Order is part of the contract, and it is unchanged.

        The spelling gate runs before the range check, so a request whose real
        fault is a malformed word is told about the word rather than about the
        scale.
        """
        unknown = _absent_spelling(DecimalType)
        with pytest.raises(TypeError, match=unknown):
            dialect.format_data_type(
                DecimalType(dialect, spelling=unknown, precision=10, scale=-1))

    def test_no_spelling_is_a_way_round_the_check(self, dialect):
        for spelling in DecimalType.SPELLINGS:
            with pytest.raises(ValueError, match="must not be negative"):
                dialect.format_data_type(
                    DecimalType(dialect, spelling=spelling, precision=10,
                                scale=-1))

    def test_the_valid_renderings_are_byte_identical(self, dialect):
        """Before and after are the same SQL for every documented value."""
        for precision, scale, expected in (
            (None, None, "DECIMAL"),
            (10, None, "DECIMAL(10)"),
            (10, 0, "DECIMAL(10, 0)"),
            (10, 2, "DECIMAL(10, 2)"),
            (1, 1, "DECIMAL(1, 1)"),
            (38, 38, "DECIMAL(38, 38)"),
        ):
            data_type = (DecimalType(dialect) if precision is None
                         else DecimalType(dialect, precision=precision,
                                         scale=scale))
            assert dialect.format_data_type(data_type) == (expected, ()), data_type

    def test_the_documented_bound_is_still_what_is_checked(self):
        """Guards the conclusion, not the code — there is no SQL Server here.

        Every server-side claim in ``_check_decimal_scale_sign`` is
        documentation-based, so the sentence is written out rather than asserted
        against a server.
        https://learn.microsoft.com/en-us/sql/t-sql/data-types/decimal-and-numeric-transact-sql
        """
        assert "0 <= s <= p" in SQL_SERVER_SCALE_BOUND
        assert "0 through p" in SQL_SERVER_SCALE_RULE
        assert "can only be specified if precision is specified" in (
            SQL_SERVER_SCALE_RULE
        )


class TestLengthsAreRangeChecked:
    """``VARCHAR(n)``, ``CHAR(n)``, ``NVARCHAR(n)``, ``NCHAR(n)``,
    ``VARBINARY(n)`` — a length outside the documented inline range.

    ``VARCHAR(9000)`` and ``NVARCHAR(4001)`` rendered, and the server answers
    those with the classic "The size of the data type varchar(n) exceeds the
    maximum allowed for any data type (8000)".  Nothing was dropped — the length
    reached the DDL exactly as declared — so the refusal belongs at the point of
    the mistake, not in a truncation.
    https://learn.microsoft.com/en-us/sql/t-sql/data-types/char-and-varchar-transact-sql
    https://learn.microsoft.com/en-us/sql/t-sql/data-types/nchar-and-nvarchar-transact-sql
    https://learn.microsoft.com/en-us/sql/t-sql/data-types/binary-and-varbinary-transact-sql
    """

    @pytest.fixture
    def dialect(self):
        return SQLServerDialect(SQL_SERVER_2022)

    #: ``(class, factory)`` for every formatter that carries a length.
    LENGTH_CARRIERS = [
        (CharType, lambda d, n: CharType(d, length=n)),
        (VarCharType, lambda d, n: VarCharType(d, length=n)),
        (SQLServerNCharType, lambda d, n: SQLServerNCharType(d, length=n)),
        (SQLServerNVarCharType, lambda d, n: SQLServerNVarCharType(d, length=n)),
        (SQLServerVarBinaryType, lambda d, n: SQLServerVarBinaryType(d, length=n)),
    ]

    CARRIER_IDS = [klass.name for klass, _ in LENGTH_CARRIERS]

    @pytest.mark.parametrize("klass,build", LENGTH_CARRIERS, ids=CARRIER_IDS)
    @pytest.mark.parametrize("length", [-1, -8000])
    def test_a_negative_length_is_refused(self, dialect, klass, build, length):
        """Both documented readings of these pages exclude a negative ``n``.

        ``char-and-varchar`` says "1 through 8,000" in its Arguments and
        "(0 to 8,000)" in its Remarks, so ``n = 0`` is one the documentation
        disagrees about and is rendered verbatim.  A negative is excluded by both,
        and by ``binary-and-varbinary``'s single stated range too.
        """
        with pytest.raises(ValueError) as excinfo:
            dialect.format_data_type(build(dialect, length))
        message = str(excinfo.value)
        assert f"got {length}" in message, (
            f"the message must name the offending value; got {message!r}"
        )
        assert "length must be" in message

    @pytest.mark.parametrize(
        "klass,build,smallest,largest",
        [
            (CharType, lambda d, n: CharType(d, length=n), 0, 8000),
            (VarCharType, lambda d, n: VarCharType(d, length=n), 0, 8000),
            (SQLServerNCharType, lambda d, n: SQLServerNCharType(d, length=n),
             0, 4000),
            (SQLServerNVarCharType, lambda d, n: SQLServerNVarCharType(d, length=n),
             0, 4000),
            (SQLServerVarBinaryType,
             lambda d, n: SQLServerVarBinaryType(d, length=n), 1, 8000),
        ],
        ids=CARRIER_IDS,
    )
    def test_a_length_above_the_documented_ceiling_is_refused(
            self, dialect, klass, build, smallest, largest):
        with pytest.raises(ValueError) as excinfo:
            dialect.format_data_type(build(dialect, largest + 1))
        message = str(excinfo.value)
        assert f"must be {smallest}-{largest}" in message, message
        assert f"got {largest + 1}" in message

    @pytest.mark.parametrize(
        "klass,build,smallest,largest,word",
        [
            (CharType, lambda d, n: CharType(d, length=n), 0, 8000, "CHAR"),
            (VarCharType, lambda d, n: VarCharType(d, length=n), 0, 8000,
             "VARCHAR"),
            (SQLServerNCharType, lambda d, n: SQLServerNCharType(d, length=n),
             0, 4000, "NCHAR"),
            (SQLServerNVarCharType, lambda d, n: SQLServerNVarCharType(d, length=n),
             0, 4000, "NVARCHAR"),
            (SQLServerVarBinaryType,
             lambda d, n: SQLServerVarBinaryType(d, length=n), 1, 8000,
             "VARBINARY"),
        ],
        ids=CARRIER_IDS,
    )
    def test_a_length_on_the_ceiling_still_renders(
            self, dialect, klass, build, smallest, largest, word):
        """The boundary value itself, on the side that must keep working."""
        assert dialect.format_data_type(build(dialect, largest)) == (
            f"{word}({largest})", ()
        )
        if smallest:
            assert dialect.format_data_type(build(dialect, smallest)) == (
                f"{word}({smallest})", ()
            )

    def test_the_national_types_have_the_smaller_ceiling(self, dialect):
        """Why ``NVARCHAR`` is 4000 and ``VARCHAR`` is 8000.

        ``n`` counts byte-pairs in the national types and bytes in the others, so
        the same number of characters costs twice as much storage — which is the
        vendor's own reason for the halved ceiling, and the reason the bound is
        looked up per word rather than shared.
        """
        assert dialect.format_data_type(
            VarCharType(dialect, length=8000)) == ("VARCHAR(8000)", ())
        with pytest.raises(ValueError, match="must be 0-4000"):
            dialect.format_data_type(SQLServerNVarCharType(dialect, length=8000))
        assert dialect.format_data_type(
            SQLServerNVarCharType(dialect, length=4000)) == ("NVARCHAR(4000)", ())

    def test_varbinary_zero_is_refused_and_the_other_zero_is_not(self, dialect):
        """The one asymmetry in the enforced table, stated as a test.

        ``binary-and-varbinary`` documents a single range — "n can be a value from
        1 through 8,000" — so 0 is outside it and is refused.  The two character
        pages state two different lower bounds ("1 through 8,000" and
        "(0 to 8,000)"), so 0 is a value the documentation does not exclude, and
        refusing it would be picking a side.  ``VARCHAR(0)`` is rendered verbatim:
        what the caller wrote is what reaches the DDL.
        """
        with pytest.raises(ValueError, match="must be 1-8000"):
            dialect.format_data_type(SQLServerVarBinaryType(dialect, length=0))
        assert dialect.format_data_type(
            VarCharType(dialect, length=0)) == ("VARCHAR(0)", ())
        assert dialect.format_data_type(CharType(dialect, length=0)) == ("CHAR(0)", ())

    def test_no_length_still_renders_the_dialect_default(self, dialect):
        """The absent parameter is untouched: only a *declared* length is bound."""
        assert dialect.format_data_type(VarCharType(dialect)) == ("VARCHAR(255)", ())
        assert dialect.format_data_type(CharType(dialect)) == ("CHAR(1)", ())
        assert dialect.format_data_type(SQLServerNVarCharType(dialect)) == (
            "NVARCHAR(255)", ()
        )
        assert dialect.format_data_type(SQLServerNCharType(dialect)) == (
            "NCHAR(1)", ()
        )
        assert dialect.format_data_type(SQLServerVarBinaryType(dialect)) == (
            "VARBINARY(255)", ()
        )

    @pytest.mark.parametrize("klass,build", LENGTH_CARRIERS, ids=CARRIER_IDS)
    @pytest.mark.parametrize("length", [1, 2, 255, 1000])
    def test_an_ordinary_length_is_byte_identical(self, dialect, klass, build,
                                                  length):
        """Before and after are the same SQL for every length in range."""
        assert dialect.format_data_type(build(dialect, length))[0].endswith(
            f"({length})"
        )

    @pytest.mark.parametrize("klass,build", LENGTH_CARRIERS, ids=CARRIER_IDS)
    def test_it_is_a_value_error_and_not_a_refusal(self, dialect, klass, build):
        """The cross-backend convention, checked rather than assumed.

        ``VARCHAR(n)`` is a declaration this grammar expresses perfectly well;
        the number is out of range.  ``UnsupportedFeatureError`` does not
        subclass ``ValueError`` and carries a ``suggestion`` meant for the case
        where there is no spelling at all, so neither belongs here.
        """
        with pytest.raises(ValueError) as excinfo:
            dialect.format_data_type(build(dialect, 8001))
        assert not isinstance(excinfo.value, UnsupportedFeatureError)
        assert not hasattr(excinfo.value, "suggestion")

    def test_the_documented_ceilings_are_still_what_is_enforced(self):
        """Guards the conclusion, not the code — there is no SQL Server here.

        Every server-side claim in ``_check_length`` is documentation-based, so
        the bounds are written out here rather than asserted against a server.
        """
        assert SQLServerDialect._SQLSERVER_LENGTH_LIMITS == {
            "CHAR": (0, 8000),
            "VARCHAR": (0, 8000),
            "NCHAR": (0, 4000),
            "NVARCHAR": (0, 4000),
            "VARBINARY": (1, 8000),
        }


# ---------------------------------------------------------------------------
# parse_type: the shared round-trip sweep over the whole declared surface


class TestParseRoundTripSweep:
    """Every rendered type parses back coherently, in one assertion each way.

    The formatter contracts above are thorough on the write side -- refusals,
    ranges, identity -- but the read side had exactly one test
    (``test_the_parser_never_produces_an_unanchored_scale``). The testsuite's
    ``parse_roundtrip_failures`` now sweeps the whole round-trip registry:
    **string stability** -- parsing a rendering and re-rendering the answer
    produces the identical string -- and **class honesty** -- the answer is
    the declared instance, or the documented widening answer recorded below
    with its reason.

    The widening answers are storage facts: ``BLOB`` is ``VARBINARY(MAX)`` and
    ``BIT`` is this backend's boolean; ``DATETIME2`` is the storage of the
    timestamp concept here and also of the ``DATETIME`` concept, so the
    storage's own concept answers; ``NVARCHAR(MAX)`` is unbounded text, which
    is what a JSON or NVARCHAR(MAX) declaration is stored as; ``FLOAT(53)``
    is the one float type, and the parse answers with the concept whose
    rendering that is; ``XML`` and ``TINYINT`` are the backend's own classes
    for those storages. A bare ``SQLServerVarBinaryType`` declaration carries
    the dialect's default length, and the parse hands back the same class
    with the parameters the rendered string named.
    """

    WIDENING_ANSWERS = {
        "BlobType": "SQLServerVarBinaryMaxType",
        "BooleanType": "SQLServerBitType",
        "TimestampType": "DateTimeType",
        "TinyIntType": "SQLServerTinyIntType",
        "JsonType": "TextType",
        "DoubleType": "FloatType",
        "XmlType": "SQLServerXmlType",
        "SQLServerNVarCharMaxType": "TextType",
        "SQLServerVarBinaryType": "SQLServerVarBinaryType",
    }

    @pytest.fixture(scope="class")
    def registry(self):
        """The round-trip module's registry, loaded from beside this file.

        Executing it also registers its special constructors, which the
        sweep's ``make_instance`` consults -- the same registrations the
        full suite performs at collection time, repeated here so the
        sweep also holds when this file runs alone.
        """
        import importlib.util
        from pathlib import Path

        path = Path(__file__).with_name("test_expression_roundtrip_all.py")
        spec = importlib.util.spec_from_file_location("sqlserver_rt_registry", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        registry = getattr(module, "ALL_CLASSES", None) or module.REGISTERED
        assert registry, "the round-trip module exposes no registry"
        return registry

    def test_every_rendered_type_parses_back_coherently(self, registry):
        from rhosocial.activerecord.testsuite.utils.parse_contract import (
            parse_roundtrip_failures,
        )

        dialect = SQLServerDialect(SQL_SERVER_2022)
        failures = parse_roundtrip_failures(
            dialect,
            registry,
            widening=self.WIDENING_ANSWERS,
        )
        assert failures == [], "\n".join(failures)
