# tests/rhosocial/activerecord_sqlserver_test/feature/backend/expression/test_sqlserver_typed_values.py
"""The value literals on SQL Server: bindings and spellings.

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

The live half of the spelling question -- do the servers accept this text and
hand the same value back -- lives with the scenario-driven integration tests,
in ``feature/backend/test_literal_default_execution.py``: an expression test
takes no real connection. That file records what was written and that no
reachable server has confirmed it yet.
"""

import datetime
import uuid as uuid_module

import pytest

from rhosocial.activerecord.backend.expression.core import Literal
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
