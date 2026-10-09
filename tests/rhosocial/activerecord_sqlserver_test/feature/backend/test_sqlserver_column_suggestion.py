# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_sqlserver_column_suggestion.py
"""SQL Server's eighteen-entry column-type suggestion table and its narrowing.

Pure dialect tests -- no server, no connection. What is asserted here is the
*declaration*: that the table answers every entry of the protocol's closed list,
that the cells SQL Server deviates on are the ones the live sweep measured, that
the one version gate fires on both sides of 2016, and that each narrowing names
an operation the column class really exposes.

The rendering those cells imply is Phase 2b's work and is deliberately not
asserted here -- with the exceptions that are *not* rendering but capability,
and therefore belong to this phase: ``ilike`` (measured to fail to parse on
every version, with ``ILIKE`` taken for a table alias) and the JSON quantifiers
(measured a syntax error).
"""

import datetime
import decimal
import enum
import uuid

import pytest

from rhosocial.activerecord.backend.dialect.mixins import ColumnSuggestionMixin
from rhosocial.activerecord.backend.expression.column_suggestions import (
    COLUMN_TYPE_ENTRIES,
    UNSUPPORTED,
    ColumnTypeResolutionError,
)
from rhosocial.activerecord.backend.expression.column_types import (
    ArrayColumn,
    BinaryColumn,
    BooleanColumn,
    ColumnBase,
    DateTimeColumn,
    DecimalColumn,
    FloatColumn,
    IntegerColumn,
    JSONColumn,
    NumericColumn,
    StringColumn,
    UUIDColumn,
)
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

#: The three servers the live sweep behind this table ran against, as the
#: backend records them (catalog versions, not the marketing names): 2019 CU32,
#: 2022 CU24 and 2025 CU4.
SQL_SERVER_2019 = (15, 0, 4465)
SQL_SERVER_2022 = (16, 0, 4250)
SQL_SERVER_2025 = (17, 0, 4035)

#: One version on each side of the 2016 boundary the JSON function gate uses
#: (:data:`SQL_SERVER_2016`); 2012 is SQL Server 2012, 2016 is SQL Server 2016.
SQL_SERVER_2012 = (11, 0, 0)
SQL_SERVER_2016 = (13, 0, 0)

_MEASURED_VERSIONS = [SQL_SERVER_2019, SQL_SERVER_2022, SQL_SERVER_2025]
_VERSION_IDS = ["2019", "2022", "2025"]

_ENTRY_IDS = [getattr(entry, "__name__", str(entry)) for entry in COLUMN_TYPE_ENTRIES]


def _answer_name(answer):
    """``UNSUPPORTED`` reads as itself; a class reads as its name."""
    return "UNSUPPORTED" if answer is UNSUPPORTED else answer.__name__


@pytest.fixture(params=_MEASURED_VERSIONS, ids=_VERSION_IDS)
def measured_dialect(request):
    """A dialect at each of the three measured versions."""
    return SQLServerDialect(version=request.param)


@pytest.fixture
def dialect():
    return SQLServerDialect(version=SQL_SERVER_2022)


class TestTableCompleteness:
    """A hole in the table is a silent gap, and the protocol forbids one."""

    def test_the_dialect_carries_the_mixin(self, dialect):
        assert isinstance(dialect, ColumnSuggestionMixin)

    def test_every_entry_is_answered(self, dialect):
        """All eighteen, by name -- an omission fails here, not at lookup."""
        missing = [e for e in COLUMN_TYPE_ENTRIES if e not in dialect.suggested_column_types()]
        assert missing == []

    def test_the_table_has_exactly_the_protocol_entries(self, dialect):
        """No backend-only extension is claimed, so the key space is closed here."""
        assert set(dialect.suggested_column_types()) == set(COLUMN_TYPE_ENTRIES)

    def test_no_entry_is_answered_none(self, dialect):
        """``None`` would be indistinguishable from "not filled in yet"."""
        table = dialect.suggested_column_types()
        assert [e for e in COLUMN_TYPE_ENTRIES if table[e] is None] == []

    def test_no_entry_is_unsupported(self, measured_dialect):
        """SQL Server answers every entry, so the sentinel never appears here.

        Unlike MySQL below 5.7 or Firebird at any version, there is no entry the
        χ routes cannot carry: a document goes in ``NVARCHAR(MAX)``, and the
        three measured servers give the same answers item for item.
        """
        table = measured_dialect.suggested_column_types()
        assert [e for e in COLUMN_TYPE_ENTRIES if table[e] is UNSUPPORTED] == []

    @pytest.mark.parametrize("entry", COLUMN_TYPE_ENTRIES, ids=_ENTRY_IDS)
    def test_every_answer_is_a_column_class(self, dialect, entry):
        answer = dialect.suggested_column_types()[entry]
        assert isinstance(answer, type)
        assert issubclass(answer, ColumnBase)

    @pytest.mark.parametrize("entry", COLUMN_TYPE_ENTRIES, ids=_ENTRY_IDS)
    def test_every_entry_resolves_to_its_own_answer(self, dialect, entry):
        assert dialect.column_class_for(entry) is dialect.suggested_column_types()[entry]

    def test_the_table_is_a_copy(self, dialect):
        """Mutating one answer must not corrupt the class attribute."""
        first = dialect.suggested_column_types()
        first[str] = FloatColumn
        assert dialect.suggested_column_types()[str] is StringColumn


class TestBaselineCells:
    """The ten-backend baseline, restated cell by cell."""

    @pytest.mark.parametrize(
        "entry, expected",
        [
            (bool, BooleanColumn),
            (int, IntegerColumn),
            (float, FloatColumn),
            (decimal.Decimal, DecimalColumn),
            (str, StringColumn),
            (bytes, BinaryColumn),
            (bytearray, BinaryColumn),
            (datetime.date, DateTimeColumn),
            (datetime.time, DateTimeColumn),
            (datetime.datetime, DateTimeColumn),
            (datetime.timedelta, NumericColumn),
            (uuid.UUID, UUIDColumn),
            (enum.Enum, StringColumn),
        ],
        ids=[
            "bool",
            "int",
            "float",
            "Decimal",
            "str",
            "bytes",
            "bytearray",
            "date",
            "time",
            "datetime",
            "timedelta",
            "UUID",
            "Enum",
        ],
    )
    def test_baseline_entry(self, dialect, entry, expected):
        assert dialect.suggested_column_types()[entry] is expected

    def test_the_tz_form_lands_on_the_same_entry(self, dialect):
        """A tz-aware ``datetime`` is annotated as ``datetime``; nothing is refused.

        The protocol has no separate tz entry, and this backend has no reason to
        want one: ``AT TIME ZONE 'UTC'`` was measured working in both directions
        on 2019, 2022 and 2025, and ``DATETIMEOFFSET`` is a real storage type.
        The tz concern that does exist -- the old ODBC driver refusing to bind a
        ``date`` / ``time`` parameter -- is value-layer, not a column class.
        """
        from datetime import timezone

        from rhosocial.activerecord.backend.expression.column_suggestions import (
            column_type_entry_for,
        )

        aware = datetime.datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
        keys = dialect.suggested_column_types()
        assert column_type_entry_for(type(aware), keys) is datetime.datetime
        assert dialect.column_class_for(datetime.datetime) is DateTimeColumn

    def test_uuid_is_native_and_still_the_baseline(self, measured_dialect):
        """``UNIQUEIDENTIFIER`` is native, and the column answer is unchanged.

        Its unusual **order** (measured ``[2, 1, 3]`` where the text order is
        ``[1, 2, 3]``, restored by ``CONVERT(varchar(36), u)``) is a rendering
        fact for Phase 2b, so it must not leak into the table as a refusal.
        """
        assert measured_dialect.suggested_column_types()[uuid.UUID] is UUIDColumn
        assert measured_dialect.supports_column_operation("UUIDColumn", "eq") is True


class TestSQLServerDeviations:
    """The three groups of cells that differ from core's neutral baseline."""

    def test_float_and_decimal_are_not_one_generic_number(self, dialect):
        """``FLOAT`` and ``DECIMAL(p,s)`` are two families with two roundings.

        Measured: ``ROUND(2.675, 2)`` is ``2.68`` on a ``decimal`` column and
        ``2.67`` on a ``float`` one.
        """
        table = dialect.suggested_column_types()
        assert table[float] is FloatColumn
        assert table[decimal.Decimal] is DecimalColumn

    def test_dict_is_json_column(self, dialect):
        """The χ route: ``NVARCHAR(MAX)`` plus the 2016 function family."""
        assert dialect.suggested_column_types()[dict] is JSONColumn

    @pytest.mark.parametrize(
        "entry", [list, tuple, set, frozenset], ids=["list", "tuple", "set", "frozenset"]
    )
    def test_containers_take_the_json_route(self, dialect, entry):
        """SQL Server has no array type on any version, so the JSON path answers.

        ``ArrayColumn``'s whole surface is ``array_length`` / ``unnest`` over a
        *native* array -- a column this server cannot declare at all.
        """
        assert dialect.suggested_column_types()[entry] is JSONColumn

    def test_no_entry_answers_array_column(self, dialect):
        """Core's neutral table says ``ArrayColumn`` for the containers; SQL Server may not."""
        table = dialect.suggested_column_types()
        assert [e for e, cls in table.items() if cls is ArrayColumn] == []

    def test_timedelta_is_numeric(self, dialect):
        """There is no interval *type*; a span exists only as ``DATEDIFF``."""
        assert dialect.suggested_column_types()[datetime.timedelta] is NumericColumn


class TestColumnClassResolution:
    """What a model layer gets when it asks the dialect for a class."""

    def test_dict_resolves_to_json_column_on_2019(self):
        assert SQLServerDialect(version=SQL_SERVER_2019).column_class_for(dict) is JSONColumn

    def test_list_resolves_to_json_column_on_2025(self):
        assert SQLServerDialect(version=SQL_SERVER_2025).column_class_for(list) is JSONColumn

    def test_timedelta_resolves_to_numeric_column(self, dialect):
        assert dialect.column_class_for(datetime.timedelta) is NumericColumn

    def test_the_refusal_is_a_type_error(self):
        """``ColumnTypeResolutionError`` subclasses ``TypeError`` by design."""
        assert issubclass(ColumnTypeResolutionError, TypeError)

    def test_an_explicit_declaration_wins(self):
        """``UseColumnType`` is the escape hatch, and it is backend-independent."""
        from rhosocial.activerecord.base.fields import UseColumnType

        server = SQLServerDialect(version=SQL_SERVER_2019)
        assert server.column_class_for(dict, UseColumnType(BinaryColumn)) is BinaryColumn

    @pytest.mark.parametrize(
        "annotation",
        [list, tuple, set, frozenset],
        ids=["list", "tuple", "set", "frozenset"],
    )
    def test_container_subclasses_normalise(self, dialect, annotation):
        """A user subclass walks to its protocol entry, per the normalisation rules."""

        class MyList(list):
            pass

        expected = JSONColumn
        assert dialect.column_class_for(annotation) is expected
        assert dialect.column_class_for(MyList) is expected

    def test_an_enum_subclass_normalises(self, dialect):
        class Weekday(enum.Enum):
            MONDAY = 1

        assert dialect.column_class_for(Weekday) is StringColumn

    def test_a_str_subclass_normalises(self, dialect):
        class MyStr(str):
            pass

        assert dialect.column_class_for(MyStr) is StringColumn

    def test_an_unknown_annotation_is_not_guessed(self, dialect):
        """No universal column: an annotation outside the list fails by name."""
        with pytest.raises(ColumnTypeResolutionError):
            dialect.column_class_for(complex)


class TestOperationNarrowing:
    """Each narrowing names an operation the column class really exposes."""

    def test_ilike_is_refused_on_every_version(self):
        """Measured on 2019, 2022 and 2025: ``ILIKE`` is parsed for a table alias."""
        for version in _MEASURED_VERSIONS:
            assert (
                SQLServerDialect(version=version).supports_column_operation(
                    "StringColumn", "ilike"
                )
                is False
            )

    def test_like_is_not_refused(self, dialect):
        """The narrowing is one operation, not the whole string surface.

        SQL Server's default collation is already case-insensitive -- storing
        ``'Zebra'`` and querying ``'zebra'`` matched one row on all three
        measured versions -- which is why this is a narrowing rather than a
        capability loss.
        """
        assert dialect.supports_column_operation("StringColumn", "like") is True

    def test_the_narrowing_is_at_the_column_class_grain(self, dialect):
        """An integer still adds; refusing ``ilike`` must not refuse ``eq``."""
        assert dialect.supports_column_operation("IntegerColumn", "eq") is True
        assert dialect.supports_column_operation("NumericColumn", "add") is True

    def test_ilike_is_an_attribute_of_the_string_column(self, dialect):
        """Operation names are attribute names, so the table is cross-checkable."""
        assert hasattr(StringColumn, "ilike")
        assert hasattr(StringColumn, "like")

    @pytest.mark.parametrize("op", ["@>", "@?", "any_of"], ids=["contains", "has_key", "any_of"])
    def test_json_quantifier_operations_are_refused(self, dialect, op):
        """``@>`` / ``@?`` are PostgreSQL's; ``v = ANY(x)`` is a syntax error here.

        The emulation that does work --
        ``IN (SELECT CAST([value] AS INT) FROM OPENJSON)`` -- is Phase 2b's to
        write deliberately, not something this answer may quietly substitute.
        """
        assert dialect.supports_column_operation("JSONColumn", op) is False

    @pytest.mark.parametrize(
        "op",
        ["json_path", "json_value", "array_length", "has_key", "json_valid", "unnest"],
    )
    def test_the_json_path_family_is_available_on_every_measured_version(self, op):
        """The whole battery passes on 2019, 2022 and 2025 alike."""
        for version in _MEASURED_VERSIONS:
            assert (
                SQLServerDialect(version=version).supports_column_operation("JSONColumn", op)
                is True
            )

    @pytest.mark.parametrize(
        "op",
        ["json_path", "json_value", "array_length", "has_key", "json_valid", "unnest"],
    )
    def test_the_json_function_family_gates_on_2016(self, op):
        """Below 2016 there is no ``JSON_VALUE``, no ``OPENJSON``, no ``ISJSON``."""
        assert (
            SQLServerDialect(version=SQL_SERVER_2012).supports_column_operation("JSONColumn", op)
            is False
        )

    @pytest.mark.parametrize(
        "version",
        [SQL_SERVER_2012, SQL_SERVER_2016, SQL_SERVER_2022, SQL_SERVER_2025],
        ids=["2012", "2016", "2022", "2025"],
    )
    def test_the_gate_agrees_with_the_json_mixin(self, version):
        """One boundary, two readers: the mixin and the table cannot drift.

        ``supports_json_type`` is the expression layer's own statement that the
        JSON functions arrived with 2016; the table's gate is read from the same
        constant, so the two cannot disagree about a version.
        """
        server = SQLServerDialect(version=version)
        assert (
            server.supports_column_operation("JSONColumn", "json_path")
            is server.supports_json_type()
        )

    def test_json_path_is_an_attribute_of_the_json_column(self, dialect):
        """Cross-check: the operation named in the narrowing is a real attribute."""
        assert hasattr(JSONColumn, "json_path")
        assert hasattr(JSONColumn, "json_value")

    def test_json_equality_is_deliberately_not_narrowed(self, dialect):
        """The column is text, so whole-column equality is available on every version.

        What is *not* portable is the shape: SQL Server does not normalise the
        way MySQL 5.7/8.0's ``JSON`` column does, so a text comparison is
        correct here -- and the semantically explicit recipe (count +
        ``JSON_VALUE`` concat) is a Phase 2b rendering obligation.
        """
        assert dialect.supports_column_operation("JSONColumn", "json_equal") is True
        assert dialect.supports_column_operation("JSONColumn", "eq") is True

    def test_uuid_ordering_is_not_narrowed_either(self, dialect):
        """It runs; it just is not the canonical text order without a ``CONVERT``.

        Measured ``ORDER BY u`` returning ``[2, 1, 3]`` where the text order is
        ``[1, 2, 3]``, restored by ``CONVERT(varchar(36), u)``. Refusing the
        operation would refuse a query that works.
        """
        assert dialect.supports_column_operation("UUIDColumn", "eq") is True
        assert dialect.supports_column_operation("StringColumn", "length") is True

    def test_unrelated_operations_are_left_at_the_default(self, dialect):
        assert dialect.supports_column_operation("BooleanColumn", "is_true") is True
        assert dialect.supports_column_operation("DateTimeColumn", "add") is True
        assert dialect.supports_column_operation("BinaryColumn", "eq") is True


class TestUnadaptedDialectAnswers:
    """A dialect built without a version answers rather than raising."""

    def test_the_table_needs_no_version(self):
        assert SQLServerDialect().suggested_column_types()[dict] is JSONColumn

    def test_ilike_is_refused_without_a_version(self):
        """The narrowing has no version in it, so it does not need one."""
        assert SQLServerDialect().supports_column_operation("StringColumn", "ilike") is False

    def test_the_json_family_is_refused_without_a_version(self):
        """Read as "before 2016" -- the side that cannot promise a query will run."""
        assert SQLServerDialect().supports_column_operation("JSONColumn", "json_path") is False

    def test_everything_else_still_answers_true(self):
        assert SQLServerDialect().supports_column_operation("StringColumn", "like") is True


class TestTheUnicodeDialectInheritsTheSameAnswers:
    """The default dialect is the Unicode one, so it must answer identically."""

    def test_the_backend_dialect_is_a_sql_server_dialect(self):
        from rhosocial.activerecord.backend.impl.sqlserver.backend.backend import (
            SQLServerUnicodeDialect,
        )

        assert issubclass(SQLServerUnicodeDialect, SQLServerDialect)

    def test_the_answers_are_identical(self):
        from rhosocial.activerecord.backend.impl.sqlserver.backend.backend import (
            SQLServerUnicodeDialect,
        )

        plain = SQLServerDialect(version=SQL_SERVER_2022).suggested_column_types()
        unicode_ = SQLServerUnicodeDialect(version=SQL_SERVER_2022).suggested_column_types()
        assert plain == unicode_
        assert (
            SQLServerUnicodeDialect(version=SQL_SERVER_2022).supports_column_operation(
                "StringColumn", "ilike"
            )
            is False
        )


def test_the_summary_table_reads_the_way_the_spec_writes_it():
    """One test that states the whole answer, so a diff is legible at a glance."""
    table = SQLServerDialect(version=SQL_SERVER_2022).suggested_column_types()
    summary = {entry.__name__: _answer_name(table[entry]) for entry in COLUMN_TYPE_ENTRIES}
    assert summary == {
        "bool": "BooleanColumn",
        "int": "IntegerColumn",
        "float": "FloatColumn",
        "Decimal": "DecimalColumn",
        "str": "StringColumn",
        "bytes": "BinaryColumn",
        "bytearray": "BinaryColumn",
        "date": "DateTimeColumn",
        "time": "DateTimeColumn",
        "datetime": "DateTimeColumn",
        "timedelta": "NumericColumn",
        "UUID": "UUIDColumn",
        "dict": "JSONColumn",
        "list": "JSONColumn",
        "tuple": "JSONColumn",
        "set": "JSONColumn",
        "frozenset": "JSONColumn",
        "Enum": "StringColumn",
    }


def test_the_three_measured_servers_agree_item_for_item():
    """No version gate on the table: 2019, 2022 and 2025 give one answer."""
    answers = []
    for version in _MEASURED_VERSIONS:
        table = SQLServerDialect(version=version).suggested_column_types()
        answers.append({e.__name__: _answer_name(cls) for e, cls in table.items()})
    assert answers[0] == answers[1] == answers[2]
