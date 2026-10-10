# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_sqlserver_column_type.py
"""SQL Server's eighteen-entry column-type table.

Pure dialect tests -- no server, no connection. What is asserted here is the
*declaration*: that the dialect composes core's
:class:`~rhosocial.activerecord.backend.dialect.mixins.column_type.ColumnTypeMixin`
and answers every one of the framework's common Python types, that the cells
SQL Server deviates on are the ones the live sweep measured, and that no entry
is left to a ``None`` that nobody decided on.

The rendering those cells imply is Phase 2b's work and is deliberately not
asserted here. Two of the old assertions that *were* asserted here --
``ilike`` and the JSON quantifier family -- measured capabilities rather than
renderings; they lived on ``supports_column_operation()``, which the core
rebuild deleted along with the rest of the capability mechanism. Their evidence
is carried in the mixin's docstring until the protocol grows an accessor for
it, and the module records the same thing so the loss is visible rather than
silent.
"""

import datetime
import decimal
import enum
import uuid

import pytest

from rhosocial.activerecord.backend.dialect.mixins import ColumnTypeMixin
from rhosocial.activerecord.backend.expression.column_types import (
    ArrayColumn,
    BinaryColumn,
    BooleanColumn,
    ColumnBase,
    IntegerColumn,
    JSONColumn,
    NumericColumn,
    StringColumn,
    TimestampColumn,
    UUIDColumn,
)
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.mixins import (
    SQLServerColumnTypeMixin,
)
from rhosocial.activerecord.testsuite.feature.query.typed_column.column_helpers import (
    COMMON_TYPES,
    resolve_column_class,
)

#: The three servers the live sweep behind this table ran against, as the
#: backend records them (catalog versions, not the marketing names): 2019 CU32,
#: 2022 CU24 and 2025 CU4.
SQL_SERVER_2019 = (15, 0, 4465)
SQL_SERVER_2022 = (16, 0, 4250)
SQL_SERVER_2025 = (17, 0, 4035)

_MEASURED_VERSIONS = [SQL_SERVER_2019, SQL_SERVER_2022, SQL_SERVER_2025]
_VERSION_IDS = ["2019", "2022", "2025"]

_ENTRY_IDS = [getattr(entry, "__name__", str(entry)) for entry in COMMON_TYPES]


def _answer_name(answer):
    """A class reads as its name; ``None`` reads as the deliberate ``None``."""
    return "None" if answer is None else answer.__name__


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
        assert isinstance(dialect, ColumnTypeMixin)

    def test_the_dialect_carries_the_sql_server_mixin(self, dialect):
        """The backend's own half, not just core's plumbing.

        Core supplies no table of its own -- its ``suggested_column_types()``
        raises -- so the answer a model layer reads can only come from the
        backend's own mixin being in the MRO.
        """
        assert isinstance(dialect, SQLServerColumnTypeMixin)

    def test_the_mixin_overrides_core(self):
        """The backend's answer, not core's NotImplementedError, is reached."""
        assert (
            SQLServerColumnTypeMixin.suggested_column_types
            is not ColumnTypeMixin.suggested_column_types
        )

    def test_every_entry_is_answered(self, dialect):
        """All eighteen, by name -- an omission fails here, not at lookup."""
        missing = [e for e in COMMON_TYPES if e not in dialect.suggested_column_types()]
        assert missing == []

    def test_the_table_has_exactly_the_protocol_entries(self, dialect):
        """No backend-only extension is claimed, so the key space is closed here."""
        assert set(dialect.suggested_column_types()) == set(COMMON_TYPES)

    def test_no_entry_is_answered_none(self, dialect):
        """``None`` is the last resort, and SQL Server never needs it.

        Every value family this server carries rides on a working pairing: a
        document goes in ``NVARCHAR(MAX)`` and the JSON functions read it, a
        sequence has no native array so it takes the JSON route, a span has no
        interval type so it is a count. Refusing any of them would read the
        *storage* as a statement about the *operations*.
        """
        table = dialect.suggested_column_types()
        assert [e for e in COMMON_TYPES if table[e] is None] == []

    @pytest.mark.parametrize("entry", COMMON_TYPES, ids=_ENTRY_IDS)
    def test_every_answer_is_a_column_class(self, dialect, entry):
        answer = dialect.suggested_column_types()[entry]
        assert isinstance(answer, type)
        assert issubclass(answer, ColumnBase)

    @pytest.mark.parametrize("entry", COMMON_TYPES, ids=_ENTRY_IDS)
    def test_every_entry_resolves_through_the_selection(self, dialect, entry):
        """Through the field accessor's own resolution, not by reading the dict.

        ``FieldAccessor._select_column_class`` is the production path a model
        layer takes, so the table is only really answered if it surfaces there.
        """
        assert resolve_column_class(dialect, entry) is dialect.suggested_column_types()[entry]

    def test_the_table_is_a_copy(self, dialect):
        """Mutating one answer must not corrupt the class attribute."""
        first = dialect.suggested_column_types()
        first[str] = NumericColumn
        assert dialect.suggested_column_types()[str] is StringColumn

    def test_the_extra_table_is_empty(self, dialect):
        """SQL Server offers nothing beyond the framework's common types."""
        assert dialect.suggested_extra_column_types() == {}


class TestBaselineCells:
    """The baseline every backend answers, restated cell by cell."""

    @pytest.mark.parametrize(
        "entry, expected",
        [
            (bool, BooleanColumn),
            (int, IntegerColumn),
            (float, NumericColumn),
            (decimal.Decimal, NumericColumn),
            (str, StringColumn),
            (bytes, BinaryColumn),
            (bytearray, BinaryColumn),
            (datetime.date, TimestampColumn),
            (datetime.time, TimestampColumn),
            (datetime.datetime, TimestampColumn),
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

        aware = datetime.datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
        keys = dialect.suggested_column_types()
        assert resolve_column_class(dialect, type(aware)) is keys[datetime.datetime]

    def test_uuid_is_native_and_still_the_baseline(self, measured_dialect):
        """``UNIQUEIDENTIFIER`` is native, and the column answer is unchanged.

        Its unusual **order** (measured ``[2, 1, 3]`` where the text order is
        ``[1, 2, 3]``, restored by ``CONVERT(varchar(36), u)``) is a rendering
        fact for Phase 2b, so it must not leak into the table as a refusal.
        """
        assert measured_dialect.suggested_column_types()[uuid.UUID] is UUIDColumn


class TestSQLServerDeviations:
    """The groups of cells that differ from the portable baseline."""

    def test_the_numeric_family_is_one_class(self, dialect):
        """``float`` and ``Decimal`` share the one numeric class.

        Measured: ``ROUND(2.675, 2)`` is ``2.68`` on a ``decimal`` column and
        ``2.67`` on a ``float`` one -- a real difference in SQL Server, because
        ``FLOAT`` and ``DECIMAL(p,s)`` are two families. Core's column layer
        cannot express it any longer: :class:`NumericColumn` is one class for
        every numeric width and precision, the operations being the same
        either way. The measured fact survives in the DDL layer's ``DataType``
        declaration rather than being dropped here.
        """
        table = dialect.suggested_column_types()
        assert table[float] is NumericColumn
        assert table[decimal.Decimal] is NumericColumn

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
        """The portable baseline says ``ArrayColumn`` for the containers; SQL Server may not."""
        table = dialect.suggested_column_types()
        assert [e for e, cls in table.items() if cls is ArrayColumn] == []

    def test_timedelta_is_numeric(self, dialect):
        """There is no interval *type*; a span exists only as ``DATEDIFF``."""
        assert dialect.suggested_column_types()[datetime.timedelta] is NumericColumn


class TestColumnClassResolution:
    """What a model layer gets when it asks the dialect for a class."""

    def test_dict_resolves_to_json_column_on_2019(self):
        assert resolve_column_class(SQLServerDialect(version=SQL_SERVER_2019), dict) is JSONColumn

    def test_list_resolves_to_json_column_on_2025(self):
        assert resolve_column_class(SQLServerDialect(version=SQL_SERVER_2025), list) is JSONColumn

    def test_timedelta_resolves_to_numeric_column(self, dialect):
        assert resolve_column_class(dialect, datetime.timedelta) is NumericColumn

    def test_the_refusal_is_a_type_error(self):
        """``ColumnTypeResolutionError`` subclasses ``TypeError`` by design."""
        from rhosocial.activerecord.base import ColumnTypeResolutionError

        assert issubclass(ColumnTypeResolutionError, TypeError)

    def test_an_explicit_declaration_wins(self):
        """``UseColumnType`` is the escape hatch, and it is backend-independent."""
        from rhosocial.activerecord.base.fields import UseColumnType

        server = SQLServerDialect(version=SQL_SERVER_2019)
        resolved = resolve_column_class(server, dict, UseColumnType(BinaryColumn))
        assert resolved is BinaryColumn

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
        assert resolve_column_class(dialect, annotation) is expected
        assert resolve_column_class(dialect, MyList) is expected

    def test_an_enum_subclass_normalises(self, dialect):
        class Weekday(enum.Enum):
            MONDAY = 1

        assert resolve_column_class(dialect, Weekday) is StringColumn

    def test_a_str_subclass_normalises(self, dialect):
        class MyStr(str):
            pass

        assert resolve_column_class(dialect, MyStr) is StringColumn

    def test_an_unknown_annotation_is_not_guessed(self, dialect):
        """No universal column: an annotation outside the list fails by name."""
        from rhosocial.activerecord.base import ColumnTypeResolutionError

        with pytest.raises(ColumnTypeResolutionError):
            resolve_column_class(dialect, complex)


class TestEveryAnswerBuildsAWorkingColumn:
    """A table answer is only real if the column it names can be constructed."""

    @pytest.mark.parametrize("entry", COMMON_TYPES, ids=_ENTRY_IDS)
    def test_every_entry_builds_a_column_that_renders(self, dialect, entry):
        """The selection answering and the object refusing to build would leave
        the failure at query time with a message about a column rather than
        about the annotation, which is the outcome the narrow column classes
        were introduced to remove."""
        column = resolve_column_class(dialect, entry)(dialect, "c")
        assert isinstance(column, ColumnBase)
        assert column.to_sql() == ("[c]", ())


class TestTheUnadaptedDialectAnswers:
    """A dialect built without a version answers rather than raising."""

    def test_the_table_needs_no_version(self):
        assert SQLServerDialect().suggested_column_types()[dict] is JSONColumn


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


def test_the_summary_table_reads_the_way_the_spec_writes_it():
    """One test that states the whole answer, so a diff is legible at a glance."""
    table = SQLServerDialect(version=SQL_SERVER_2022).suggested_column_types()
    summary = {entry.__name__: _answer_name(table[entry]) for entry in COMMON_TYPES}
    assert summary == {
        "bool": "BooleanColumn",
        "int": "IntegerColumn",
        "float": "NumericColumn",
        "Decimal": "NumericColumn",
        "str": "StringColumn",
        "bytes": "BinaryColumn",
        "bytearray": "BinaryColumn",
        "date": "TimestampColumn",
        "time": "TimestampColumn",
        "datetime": "TimestampColumn",
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
