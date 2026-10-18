# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_classed_function_entries.py
"""The classed function entries and the bare VALUES cells (guide wave M1).

Two follow-ups the core has already landed and this backend owed:

* **Classed entries** (core 9b559030 + c5210245): the standard functions
  stopped riding the generic ``FunctionCall`` -- each has its own node,
  its own kind and its own dialect formatter, and ``FunctionCall`` is
  reserved for UDFs. This backend's factories build the classed nodes for
  MAX / MIN / AVG / COALESCE / TRIM, its dialect spells CHAR_LENGTH as
  ``LEN`` (the core docstring names SQL Server as the backend whose length
  function answers in UTF-16 code units, excluding trailing blanks), and
  NOW / CURRENT_DATE / CURRENT_TIME keep their T-SQL spellings through the
  classed formatters that replaced the deleted rename tables.
* **Bare VALUES cells** (core 8e2e4d82): an INSERT's VALUES cell may be a
  plain host value, which binds; the dialect's INSERT override now
  delegates that decision to the core's ``format_insert_values_source``
  instead of re-implementing the loop and failing on a bare scalar.
"""

import pytest

from rhosocial.activerecord.backend.expression import Column, TrimExpression
from rhosocial.activerecord.backend.expression.core import FunctionCall, Literal
from rhosocial.activerecord.backend.expression.functions.datetime import (
    current_date,
    current_time,
    current_timestamp,
    now,
)
from rhosocial.activerecord.backend.expression.functions.string import CharLengthFunction
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import (
    InsertStatement,
    ValuesSource,
)
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.functions.aggregate import (
    avg,
    max_,
    min_,
)
from rhosocial.activerecord.backend.impl.sqlserver.functions.string import trim
from rhosocial.activerecord.backend.impl.sqlserver.functions.utility import coalesce
from rhosocial.activerecord.backend.expression.functions import (
    AvgFunction,
    MaxFunction,
    MinFunction,
)
from rhosocial.activerecord.backend.expression.functions.string import CoalesceFunction


DIALECT = SQLServerDialect(version=(16, 0, 0))


class TestClassedAggregateFactories:
    """max_/min_/avg build the classed aggregates, not generic calls."""

    def test_max_builds_the_class_node(self):
        node = max_(DIALECT, "price")
        assert isinstance(node, MaxFunction)
        assert node.to_sql() == ("MAX([price])", ())

    def test_min_builds_the_class_node(self):
        node = min_(DIALECT, Column(DIALECT, "age"))
        assert isinstance(node, MinFunction)
        assert node.to_sql() == ("MIN([age])", ())

    def test_avg_builds_the_class_node(self):
        node = avg(DIALECT, Column(DIALECT, "score"))
        assert isinstance(node, AvgFunction)
        assert node.to_sql() == ("AVG([score])", ())


class TestCharLengthSpellsLen:
    """CHAR_LENGTH is LEN here -- UTF-16 units, trailing blanks excluded."""

    def test_char_length_renders_len(self):
        assert CharLengthFunction(DIALECT, Column(DIALECT, "name")).to_sql() == (
            "LEN([name])",
            (),
        )

    def test_the_override_lives_on_the_dialect_body(self):
        """The MRO must find this spelling, not the core's portable one.

        ``format_char_length_function`` rides into the MRO early through
        ``ExpressionMixin`` -> ``FunctionCallMixin``; the dialect body is
        the one position guaranteed ahead of it (see the method's
        docstring), and this pins that resolution.
        """
        assert (
            type(DIALECT).format_char_length_function
            is SQLServerDialect.format_char_length_function
        )


class TestClassedNiladicSpellings:
    """NOW / CURRENT_DATE / CURRENT_TIME through the classed formatters.

    These used to be rename entries in the deleted ``format_function_call``
    tables; the classed nodes dispatch straight to the dialect formatters
    now, so the spellings live here (CURRENT_TIMESTAMP stays the standard
    niladic keyword T-SQL accepts as-is).
    """

    def test_now_is_sysdatetime(self):
        assert now(DIALECT).to_sql() == ("SYSDATETIME()", ())

    def test_current_date_is_cast_getdate(self):
        assert current_date(DIALECT).to_sql() == ("CAST(GETDATE() AS DATE)", ())

    def test_current_time_is_cast_getdate(self):
        assert current_time(DIALECT).to_sql() == ("CAST(GETDATE() AS TIME)", ())

    def test_current_timestamp_keeps_the_standard_keyword(self):
        assert current_timestamp(DIALECT).to_sql() == ("CURRENT_TIMESTAMP", ())

    @pytest.mark.parametrize(
        "factory",
        [now, current_date, current_time],
        ids=["now", "current_date", "current_time"],
    )
    def test_a_precision_is_refused_rather_than_dropped(self, factory):
        """No T-SQL spelling takes a precision, so one is an explicit error."""
        with pytest.raises(UnsupportedFeatureError, match="precision"):
            factory(DIALECT, precision=Literal(DIALECT, 3)).to_sql()


class TestClassedStringEntries:
    """trim and coalesce build the classed nodes with this factory's semantics."""

    def test_trim_without_characters(self):
        node = trim(DIALECT, "name")
        assert isinstance(node, TrimExpression)
        assert node.to_sql() == ("TRIM([name])", ())

    def test_trim_puts_the_characters_first(self):
        """T-SQL spells the character set before the operand (2017+)."""
        node = trim(DIALECT, "name", "x")
        assert isinstance(node, TrimExpression)
        assert node.to_sql() == ("TRIM(? FROM [name])", ("x",))

    def test_coalesce_builds_the_class_node(self):
        """The factory's conversion (bare string names a column) is kept."""
        node = coalesce(DIALECT, "a", 1)
        assert isinstance(node, CoalesceFunction)
        assert node.to_sql() == ("COALESCE([a], ?)", (1,))


class TestFunctionCallIsUdfOnly:
    """With the rename tables gone, a generic call renders as written.

    ``FunctionCall`` is the UDF escape hatch (core c5210245); the standard
    names it used to remap have their own classed formatters, so a call
    constructed here reaches the server verbatim -- which is the contract
    a UDF caller needs.
    """

    def test_a_udf_call_renders_as_written(self):
        """The core spells the name uppercased, as it did through the old
        override's passthrough; T-SQL names are case-insensitive."""
        call = FunctionCall(DIALECT, "dbo.my_udf", Column(DIALECT, "x"))
        assert call.to_sql() == ("DBO.MY_UDF([x])", ())


class TestInsertBareValuesCells:
    """An INSERT's VALUES cell may be a bare host value (core 8e2e4d82)."""

    def test_bare_cells_bind(self):
        insert = InsertStatement(
            dialect=DIALECT,
            into=Table(DIALECT, "t"),
            columns=["a", "b"],
            source=ValuesSource(DIALECT, [[1, "x"]]),
        )
        assert insert.to_sql() == ("INSERT INTO [t] ([a], [b]) VALUES (?, ?)", (1, "x"))

    def test_bare_and_expression_cells_mix(self):
        """An expression cell renders its own SQL; a bare cell binds."""
        insert = InsertStatement(
            dialect=DIALECT,
            into=Table(DIALECT, "t"),
            columns=["a", "b"],
            source=ValuesSource(
                DIALECT,
                [[1, "x"], [Column(DIALECT, "c"), None]],
            ),
        )
        assert insert.to_sql() == (
            "INSERT INTO [t] ([a], [b]) VALUES (?, ?), ([c], ?)",
            (1, "x", None),
        )

    def test_expression_cells_render_their_own_sql(self):
        insert = InsertStatement(
            dialect=DIALECT,
            into=Table(DIALECT, "t"),
            columns=["a"],
            source=ValuesSource(DIALECT, [[Literal(DIALECT, 7)]]),
        )
        assert insert.to_sql() == ("INSERT INTO [t] ([a]) VALUES (?)", (7,))
