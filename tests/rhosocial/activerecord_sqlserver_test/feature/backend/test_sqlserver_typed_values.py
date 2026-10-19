# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_sqlserver_typed_values.py
"""The value literals on SQL Server: bindings, spellings, live answers.

One ``Literal`` class carries every value now, and the only question it owns
is how the value reaches SQL: bound (``inline=False``, the data-position
default -- a placeholder plus the host value handed to pyodbc untouched,
because bytes, ``uuid.UUID``, ``bool`` and ``timedelta`` are all natively
bindable) or written as text (``inline=True``, for the DDL syntax positions
that accept no bind parameters). The *spelling* of that text is the dialect's
``format_literal``, and SQL Server differs from the portable forms on three
types and no more:

* a boolean inlines as ``1``/``0`` -- T-SQL's literal grammar has no
  ``TRUE``/``FALSE`` keywords, and ``BIT``'s constants are numeric;
* bytes inline as the unquoted ``0x`` hex constant;
* a UUID inlines as the quoted canonical text a ``UNIQUEIDENTIFIER``
  converts.

INTERVAL stays refused on purpose: T-SQL has no interval literal, so a
``timedelta`` at an inline position reaches the base implementation's ladder
and fails explicitly naming its type -- the structural absence is the
dialect's answer, not an oversight.

Live confirmation follows the core helper's discipline: a sentinel first
(deliberately invalid SQL must come back REJECTED), then a CREATE TABLE
whose DEFAULT clauses embed the rendered literals, read back through
``INSERT ... DEFAULT VALUES`` and compared as Python values. Those cases
were written against the documented T-SQL grammar; the scenario servers
(11433/11434/11435) were unreachable this session, so they are waiting for
a reachable server and are excluded from local offline runs.
"""

import datetime
import uuid as uuid_module

import pytest

from rhosocial.activerecord.backend.expression.core import Literal
from rhosocial.activerecord.backend.expression.execution_testing import (
    ExecutionOutcome,
    classify_execution,
)
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.mixins.literal import (
    SQLServerLiteralValueMixin,
)


UUID_TEXT = "01234567-89ab-cdef-0123-456789abcdef"


# ---------------------------------------------------------------------------
# Wiring: the intercept must resolve ahead of the base class
# ---------------------------------------------------------------------------


class TestWiring:
    """The dialect composes SQL Server's literal mixin ahead of the base."""

    def test_format_literal_resolves_on_the_sqlserver_intercept(self):
        """The override wins over SQLDialectBase's portable ladder.

        ``SQLServerLiteralValueMixin`` precedes ``SQLDialectBase`` in the
        base list; if that position were lost, ``format_literal(True)``
        would render the portable keyword T-SQL cannot parse and bytes
        would render as nothing at all (the base refuses them to a
        backend, which is what makes the tier-2 override the backend's
        obligation).
        """
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert (
            type(dialect).format_literal
            is SQLServerLiteralValueMixin.format_literal
        )


# ---------------------------------------------------------------------------
# Offline: both answers of the one question a literal owns
# ---------------------------------------------------------------------------


class TestDataPositionBindsTheHostValue:
    """``inline=False`` emits a placeholder and hands pyodbc the host value."""

    @pytest.mark.parametrize(
        "value",
        [
            b"\x01\x02",
            True,
            uuid_module.UUID(UUID_TEXT),
            datetime.date(2026, 10, 17),
            datetime.timedelta(days=1),
        ],
        ids=["bytes", "bool", "uuid", "date", "timedelta"],
    )
    def test_the_value_binds_untouched(self, value):
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert Literal(dialect, value).to_sql() == ("?", (value,))


class TestInlinePositionSpellings:
    """``inline=True`` writes the exact literal text, no parameters."""

    def test_boolean_is_numeric(self):
        """T-SQL has no TRUE/FALSE keywords; BIT takes 1/0 (see the mixin)."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert Literal(dialect, True, inline=True).to_sql() == ("1", ())
        assert Literal(dialect, False, inline=True).to_sql() == ("0", ())

    def test_binary_is_an_unquoted_hex_constant(self):
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert Literal(dialect, b"\x01\x02", inline=True).to_sql() == ("0x0102", ())

    def test_binary_accepts_a_bytearray(self):
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert (
            Literal(dialect, bytearray(b"\xff\x00"), inline=True).to_sql()
            == ("0xFF00", ())
        )

    def test_uuid_is_the_quoted_canonical_text(self):
        dialect = SQLServerDialect(version=(16, 0, 0))
        value = uuid_module.UUID(UUID_TEXT)
        assert Literal(dialect, value, inline=True).to_sql() == (f"'{UUID_TEXT}'", ())

    def test_tier_one_kinds_keep_the_base_spelling(self):
        """The portable scalars fall through to the base implementation."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert (
            Literal(dialect, datetime.date(2026, 10, 17), inline=True).to_sql()
            == ("'2026-10-17'", ())
        )
        assert Literal(dialect, "it's", inline=True).to_sql() == ("'it''s'", ())
        assert Literal(dialect, 42, inline=True).to_sql() == ("42", ())

    def test_interval_refuses_explicitly(self):
        """No interval literal exists in T-SQL; the refusal names the type.

        The base implementation's ladder is the refusal: this dialect adds
        no ``timedelta`` branch, so the value reaches the tier that fails
        loudly rather than a spelling that guesses.
        """
        dialect = SQLServerDialect(version=(16, 0, 0))
        with pytest.raises(TypeError, match="timedelta"):
            Literal(dialect, datetime.timedelta(days=1), inline=True).to_sql()


# ---------------------------------------------------------------------------
# Live: the rendered literals are accepted and read back by the server
# ---------------------------------------------------------------------------


class TestLiveLiteralRoundTrip:
    """Execution confirmation on every configured scenario server.

    The defaults are rendered by the dialect's own literal construction,
    then executed, then read back as Python values. Written against the
    documented T-SQL grammar -- the ``0x<hex>`` constant form and the
    string-to-UNIQUEIDENTIFIER/BIT conversions -- and waiting on a
    reachable server: the scenario ports were refused (~31 s per dial)
    while this wave was developed, so CI's live scenarios are what
    exercises this class.
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
        b_default = dialect.format_literal(self.BINARY)
        u_default = dialect.format_literal(self.UUID)
        f_default = dialect.format_literal(True)

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
