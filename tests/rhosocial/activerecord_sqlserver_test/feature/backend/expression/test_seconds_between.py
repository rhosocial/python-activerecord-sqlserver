# tests/rhosocial/activerecord_sqlserver_test/feature/backend/expression/test_seconds_between.py
"""``seconds_between`` on SQL Server: ``DATEDIFF_BIG`` milliseconds over 1000.

The node answers a question -- the signed, fractional distance from one instant
to another -- and this backend spells it as a millisecond count divided by
``1000.0``. The offline cases pin the SQL text, the bind order and the alias;
the live cases execute the same statement so the sign, the zero, the fraction
and the calendar boundary are measured rather than assumed.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import (
    Column,
    Literal,
    QueryStatement,
    seconds_between,
)
from rhosocial.activerecord.backend.expression.column_types import TimestampColumn
from rhosocial.activerecord.backend.expression.datetime import SecondsBetweenExpression
from rhosocial.activerecord.backend.expression.value_types import NumericValue
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

DQL_OPTIONS = ExecutionOptions(stmt_type=StatementType.DQL)


@pytest.fixture
def dialect():
    """A SQL Server 2022 dialect."""
    return SQLServerDialect(version=(16, 0, 0))


class TestSecondsBetweenSqlText:
    """The spelling, without a server."""

    def test_columns(self, dialect):
        expr = seconds_between(
            dialect,
            Column(dialect, "started_at"),
            Column(dialect, "ended_at"),
        )

        sql, params = expr.to_sql()

        assert sql == (
            "DATEDIFF_BIG(MILLISECOND, [started_at], [ended_at]) / 1000.0"
        )
        assert params == ()

    def test_literal_params_follow_sql_order(self, dialect):
        expr = seconds_between(
            dialect,
            Literal(dialect, "2026-01-01 00:00:00"),
            Literal(dialect, "2026-01-02 00:00:00"),
        )

        sql, params = expr.to_sql()

        assert sql == "DATEDIFF_BIG(MILLISECOND, ?, ?) / 1000.0"
        # ``start`` is the first argument ``DATEDIFF_BIG`` takes, so it binds
        # first -- the SQL order, not the constructor's labels.
        assert params == ("2026-01-01 00:00:00", "2026-01-02 00:00:00")

    def test_alias_is_applied_after_the_division(self, dialect):
        expr = seconds_between(
            dialect,
            Column(dialect, "started_at"),
            Column(dialect, "ended_at"),
        ).as_("elapsed")

        sql, params = expr.to_sql()

        assert sql == (
            "DATEDIFF_BIG(MILLISECOND, [started_at], [ended_at]) / 1000.0 "
            "AS [elapsed]"
        )
        assert params == ()

    def test_alias_keeps_bind_order(self, dialect):
        expr = seconds_between(
            dialect,
            Literal(dialect, "2026-01-01 00:00:00"),
            Literal(dialect, "2026-01-02 00:00:00"),
        ).as_("elapsed")

        sql, params = expr.to_sql()

        assert sql == "DATEDIFF_BIG(MILLISECOND, ?, ?) / 1000.0 AS [elapsed]"
        assert params == ("2026-01-01 00:00:00", "2026-01-02 00:00:00")

    def test_factory_coerces_string_to_column(self, dialect):
        expr = seconds_between(dialect, "started_at", "ended_at")

        sql, params = expr.to_sql()

        assert sql == (
            "DATEDIFF_BIG(MILLISECOND, [started_at], [ended_at]) / 1000.0"
        )
        assert params == ()

    def test_column_method(self, dialect):
        started = TimestampColumn(dialect, "started_at")
        ended = TimestampColumn(dialect, "ended_at")

        sql, params = started.seconds_between(ended).to_sql()

        assert sql == (
            "DATEDIFF_BIG(MILLISECOND, [started_at], [ended_at]) / 1000.0"
        )
        assert params == ()

    def test_node_is_a_fractional_number(self, dialect):
        expr = seconds_between(
            dialect,
            Column(dialect, "started_at"),
            Column(dialect, "ended_at"),
        )

        assert isinstance(expr, SecondsBetweenExpression)
        assert isinstance(expr, NumericValue)
        assert expr.format_method == "format_seconds_between_expression"


class TestSecondsBetweenVersionFloor:
    """``DATEDIFF_BIG`` arrived in SQL Server 2016, and the backend says so."""

    def test_before_2016_refuses(self):
        dialect = SQLServerDialect(version=(12, 0, 0))
        expr = seconds_between(
            dialect,
            Column(dialect, "started_at"),
            Column(dialect, "ended_at"),
        )

        with pytest.raises(UnsupportedFeatureError) as excinfo:
            expr.to_sql()

        assert "DATEDIFF_BIG" in str(excinfo.value)
        assert "2016" in str(excinfo.value)

    def test_support_probe_reports_the_floor(self):
        old = SQLServerDialect(version=(12, 0, 0))
        new = SQLServerDialect(version=(13, 0, 0))

        assert old.supports_functions().get("seconds_between") is False
        assert new.supports_functions().get("seconds_between") is True


def _elapsed(backend, start: str, end: str) -> float:
    """Run ``seconds_between(start, end)`` and return the scalar."""
    dialect = backend.dialect
    expr = seconds_between(
        dialect,
        Literal(dialect, start),
        Literal(dialect, end),
    )
    query = QueryStatement(dialect, select=[expr.as_("seconds")])
    sql, params = query.to_sql()
    result = backend.execute(sql, params, options=DQL_OPTIONS)
    # ``DATEDIFF_BIG(...) / 1000.0`` is numeric, which pyodbc returns as
    # ``Decimal``; the assertions compare the value, not the wrapper.
    return float(result.data[0]["seconds"])


class TestSecondsBetweenExecution:
    """The value SQL Server actually produces."""

    @pytest.mark.parametrize(
        "start,end,expected",
        [
            ("2026-06-04 10:00:00", "2026-06-04 10:00:00", 0.0),
            ("2026-06-04 10:00:00", "2026-06-04 11:00:00", 3600.0),
            ("2026-06-04 11:00:00", "2026-06-04 10:00:00", -3600.0),
            ("2026-01-31 23:59:59", "2026-02-01 00:00:00", 1.0),
            ("2025-12-31 12:00:00", "2026-01-01 12:00:00", 86400.0),
            ("2026-06-04 10:00:00.000", "2026-06-04 10:00:00.500", 0.5),
            ("2026-06-04 10:00:00.250", "2026-06-04 10:00:00.000", -0.25),
        ],
    )
    def test_interval(self, sqlserver_backend, start: str, end: str, expected: float):
        assert _elapsed(sqlserver_backend, start, end) == pytest.approx(
            expected, abs=1e-3
        )

    def test_span_longer_than_an_int_millisecond_count(self, sqlserver_backend):
        """``DATEDIFF_BIG`` survives a span plain ``DATEDIFF`` overflows.

        A millisecond count above ``2**31 - 1`` is roughly 24.8 days, so 60
        days is past the limit that makes the ``BIG`` spelling necessary.
        """
        seconds = _elapsed(
            sqlserver_backend,
            "2026-01-01 00:00:00",
            "2026-03-02 00:00:00",
        )

        assert seconds == pytest.approx(60 * 86400.0, abs=1e-3)
