# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_sqlserver_typed_values.py
"""The typed value nodes on SQL Server: bindings, literals, live answers.

SQL Server spells three of the twelve value kinds its own way: binary (the
unquoted ``0x`` hex constant), UUID (quoted text a ``UNIQUEIDENTIFIER``
column converts) and the boolean (``1``/``0``, because T-SQL's literal
grammar has no ``TRUE``/``FALSE`` keywords -- the boolean branch of the
dialect's ``format_literal`` is what spells it). INTERVAL stays refused by
the core mixin on purpose: T-SQL has no interval literal at all. This file
pins both positions of each:

* the **data position** (``inline_params = False``) must produce a
  placeholder and hand the host value to pyodbc untouched -- bytes,
  ``uuid.UUID`` and ``bool`` are all natively bindable, so any conversion
  there would be work the driver already does;
* the **DDL position** must produce the exact literal text. ``DEFAULT``
  clauses accept no bind parameters, so this is the one place the spelling
  is observable.

The DDL position is exercised through test-local subclasses that declare
``inline_params = True`` -- the same class-level strategy flip
``DdlLiteral`` applies to ``Literal``, because whether a value inlines is
the **class's** decision, never an instance flag. The core has not shipped
DDL variants of the typed value nodes, and a dialect must not invent
nodes, so the strategy flip lives in the test that needs it.

Live confirmation follows the core helper's discipline: a sentinel first
(deliberately invalid SQL must come back REJECTED), then a CREATE TABLE
whose DEFAULT clauses embed the rendered literals, read back through
``INSERT ... DEFAULT VALUES`` and compared as Python values. Those cases
were written against the documented T-SQL grammar; the scenario servers
(11433/11434/11435) were unreachable this session, so they are waiting
for a reachable server and are excluded from local offline runs.
"""

import datetime
import uuid as uuid_module

import pytest

from rhosocial.activerecord.backend.dialect.mixins import TypedValueMixin
from rhosocial.activerecord.backend.expression.execution_testing import (
    ExecutionOutcome,
    classify_execution,
)
from rhosocial.activerecord.backend.expression.values import (
    BinaryValue,
    BooleanValue,
    DateValue,
    IntervalValue,
    StringValue,
    UUIDValue,
)
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.mixins.typed_value import (
    SQLServerTypedValueMixin,
)


# ---------------------------------------------------------------------------
# DDL-position variants: the class-level inline strategy, flipped per class
# ---------------------------------------------------------------------------


class DdlBinaryValue(BinaryValue):
    """A binary value at a DDL syntax position: the class inlines."""

    inline_params: bool = True


class DdlUUIDValue(UUIDValue):
    """A UUID at a DDL syntax position: the class inlines."""

    inline_params: bool = True


class DdlBooleanValue(BooleanValue):
    """A boolean at a DDL syntax position: the class inlines."""

    inline_params: bool = True


class DdlIntervalValue(IntervalValue):
    """An interval at a DDL syntax position: the class inlines -- and T-SQL
    has no literal for it, so the core mixin's refusal is what surfaces."""

    inline_params: bool = True


class DdlStringValue(StringValue):
    """A string at a DDL syntax position: tier-1, inlined by the base."""

    inline_params: bool = True


class DdlDateValue(DateValue):
    """A date at a DDL syntax position: tier-1, inlined by the base."""

    inline_params: bool = True


UUID_TEXT = "01234567-89ab-cdef-0123-456789abcdef"


# ---------------------------------------------------------------------------
# Wiring: the pair must resolve on this backend's mixin
# ---------------------------------------------------------------------------


class TestWiring:
    """The dialect composes SQL Server's mixin ahead of the core's."""

    def test_tier_two_methods_resolve_on_the_sqlserver_mixin(self):
        """MRO must find SQL Server's spellings, not the core refusals.

        The base list puts ``SQLServerTypedValueMixin`` ahead of
        ``TypedValueMixin``; if that order were lost, the DDL position
        would fall back to the core's explicit ``NotImplementedError`` and
        only the bind path would keep working.
        """
        dialect = SQLServerDialect(version=(16, 0, 0))
        for name in ("format_binary_value", "format_uuid_value"):
            resolved = getattr(type(dialect), name)
            assert resolved is getattr(SQLServerTypedValueMixin, name), name

    def test_interval_stays_the_core_refusal(self):
        """No dialect ``format_interval_value``: the absence is structural.

        SQL Server has no interval literal, so the core mixin's explicit
        failure is the answer this backend ships; the test pins the
        resolution so a future override shows up as a change here.
        """
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert (
            type(dialect).format_interval_value
            is TypedValueMixin.format_interval_value
        )

    def test_format_literal_resolves_on_the_sqlserver_intercept(self):
        """The boolean intercept wins over the base's TRUE/FALSE spelling.

        ``SQLServerTypedValueMixin`` precedes ``SQLDialectBase`` in the
        base list; if that position were lost, ``format_literal(True)``
        would render the portable keyword T-SQL cannot parse.
        """
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert (
            type(dialect).format_literal
            is SQLServerTypedValueMixin.format_literal
        )


# ---------------------------------------------------------------------------
# Offline: both positions of every kind this backend spells
# ---------------------------------------------------------------------------


class TestDataPositionBindsTheHostValue:
    """A data position emits a placeholder and hands pyodbc the host value."""

    def test_binary_binds_bytes(self):
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert BinaryValue(dialect, b"\x01\x02").to_sql() == ("?", (b"\x01\x02",))

    def test_uuid_binds_the_uuid_object(self):
        dialect = SQLServerDialect(version=(16, 0, 0))
        value = uuid_module.UUID(UUID_TEXT)
        assert UUIDValue(dialect, value).to_sql() == ("?", (value,))

    def test_boolean_binds_the_bool(self):
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert BooleanValue(dialect, True).to_sql() == ("?", (True,))

    def test_tier_one_kinds_keep_the_core_binding(self):
        """The date is tier-1: the core mixin binds it unchanged."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert DateValue(dialect, datetime.date(2026, 10, 17)).to_sql() == (
            "?",
            (datetime.date(2026, 10, 17),),
        )


class TestDdlPositionLiterals:
    """A DDL position inlines the exact literal text, no parameters."""

    def test_binary_is_an_unquoted_hex_constant(self):
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert DdlBinaryValue(dialect, b"\x01\x02").to_sql() == ("0x0102", ())

    def test_binary_accepts_a_bytearray(self):
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert DdlBinaryValue(dialect, bytearray(b"\xff\x00")).to_sql() == (
            "0xFF00",
            (),
        )

    def test_uuid_is_the_quoted_canonical_text(self):
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert DdlUUIDValue(dialect, uuid_module.UUID(UUID_TEXT)).to_sql() == (
            f"'{UUID_TEXT}'",
            (),
        )

    def test_boolean_is_numeric(self):
        """T-SQL has no TRUE/FALSE keywords; BIT takes 1/0 (see the mixin)."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert DdlBooleanValue(dialect, True).to_sql() == ("1", ())
        assert DdlBooleanValue(dialect, False).to_sql() == ("0", ())

    def test_raw_bool_literals_are_numeric_too(self):
        """A bare host bool at any DDL position takes the same spelling.

        ``format_literal`` is the single spelling point: the typed node's
        inline branch delegates to it, and so does every DDL clause that
        carries a raw scalar -- one spelling, no drift.
        """
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert dialect.format_literal(True) == "1"
        assert dialect.format_literal(False) == "0"

    def test_tier_one_string_still_inlines_through_the_base(self):
        """Tier-1 kinds inline via ``format_literal``; the escape is the base's."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert DdlStringValue(dialect, "it's").to_sql() == ("'it''s'", ())

    def test_tier_one_date_still_inlines_through_the_base(self):
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert DdlDateValue(dialect, datetime.date(2026, 10, 17)).to_sql() == (
            "'2026-10-17'",
            (),
        )

    def test_interval_refuses_explicitly(self):
        """No interval literal exists in T-SQL; the refusal names the kind."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        with pytest.raises(NotImplementedError, match="INTERVAL literals"):
            DdlIntervalValue(dialect, datetime.timedelta(days=1)).to_sql()


# ---------------------------------------------------------------------------
# Live: the rendered literals are accepted and read back by the server
# ---------------------------------------------------------------------------


class TestLiveLiteralRoundTrip:
    """Execution confirmation on every configured scenario server.

    The defaults are rendered by the dialect's own formatters (through the
    DDL-position classes above), then executed, then read back as Python
    values. Written against the documented T-SQL grammar -- the constant
    forms ``0x<hex>`` and the string-to-UNIQUEIDENTIFIER/BIT conversions --
    and waiting on a reachable server: the scenario ports were refused
    (~31 s per dial) while this wave was developed, so CI's live scenarios
    are what exercises this class.
    """

    BINARY = b"\x01\x02"
    UUID = uuid_module.UUID(UUID_TEXT)

    def test_sentinel_rejected_and_control_accepted(self, sqlserver_backend):
        """The classifier must see both answers before any verdict is trusted."""
        assert (
            classify_execution(sqlserver_backend, "THIS IS NOT SQL")
            is ExecutionOutcome.REJECTED
        )
        assert (
            classify_execution(sqlserver_backend, "SELECT 1")
            is ExecutionOutcome.ACCEPTED
        )

    def test_column_defaults_round_trip(self, sqlserver_backend):
        """The binary, UUID and boolean literals as DEFAULTs survive a read-back."""
        dialect = sqlserver_backend.dialect
        b_default, _ = DdlBinaryValue(dialect, self.BINARY).to_sql()
        u_default, _ = DdlUUIDValue(dialect, self.UUID).to_sql()
        f_default, _ = DdlBooleanValue(dialect, True).to_sql()

        table = "test_typed_value_defaults"
        sqlserver_backend.execute(f"""
            CREATE TABLE {table} (
                b VARBINARY(8) DEFAULT {b_default},
                u UNIQUEIDENTIFIER DEFAULT {u_default},
                f BIT DEFAULT {f_default}
            )
        """)
        try:
            sqlserver_backend.execute(f"INSERT INTO {table} DEFAULT VALUES")
            row = sqlserver_backend.fetch_one(
                f"SELECT b AS b, u AS u, f AS f FROM {table}"
            )
            assert row is not None
            assert bytes(row["b"]) == self.BINARY
            assert row["u"] == self.UUID
            assert bool(row["f"]) is True
        finally:
            sqlserver_backend.execute(f"DROP TABLE IF EXISTS {table}")
