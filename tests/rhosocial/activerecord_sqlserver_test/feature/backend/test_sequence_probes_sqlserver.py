# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_sequence_probes_sqlserver.py
"""Every SQL Server sequence option probe must be load-bearing.

A capability probe is *load-bearing* when the formatter's decision follows its
answer: flip the probe and the rendered statement (or the refusal) flips with
it. A probe whose answer can change while the behaviour does not is
*decorative* -- a capability declaration nobody consults.

This file exists because ``format_alter_sequence_statement`` refused ``ORDER``
and ``OWNED BY`` unconditionally, without asking
``supports_sequence_order()`` / ``supports_sequence_owned_by()``, while every
neighbouring option in the same method was gated on its own probe. Both probes
answer ``False`` for SQL Server, so the rendered output was correct by
accident: the refusal did not follow the declaration, and the declaration
could not be corrected by a subclass without editing the formatter. The two
gates added in this round make the probes load-bearing; this guard keeps them
that way.

The walk covers every option probe on the dialect. ``CREATE`` and ``DROP``
SEQUENCE render through core's ``SequenceMixin`` (this backend has no local
copy); ``ALTER`` renders through this dialect's override. The probes are the
dialect's in all three cases, so all three statements are walked. Probes that
answer about the statement or object rather than one of its options are named
in :data:`NON_OPTION_PROBES` and are outside the walk.

The guard is deliberately able to fail: ``test_hardcoded_order_refusal_...``
feeds the comparison a dialect whose formatter ignores a probe (the shape this
method had before the gates existed) and asserts the guard reports it
decorative.
"""

from typing import NamedTuple

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Sequence
from rhosocial.activerecord.backend.expression.statements.ddl_sequence import (
    AlterSequenceExpression,
    CreateSequenceExpression,
    DropSequenceExpression,
)
from rhosocial.activerecord.backend.impl.sqlserver.dialect import (
    SQL_SERVER_2022,
    SQLServerDialect,
)


@pytest.fixture
def dialect():
    return SQLServerDialect(SQL_SERVER_2022)


def _seq(dialect):
    return Sequence(dialect, "probe_seq")


class _ProbeCase(NamedTuple):
    """One option request and the probe that must decide it.

    ``statement`` and ``expression_cls`` say which formatter renders the
    request; ``feature`` is the name the refusal must carry when the probe
    answers ``False``; ``kwargs`` request the option; ``probe_name`` is the
    capability that must answer for it.
    """

    label: str
    statement: str
    expression_cls: type
    option: str
    feature: str
    probe_name: str
    kwargs: dict


#: Every sequence option probe, exercised on every statement that carries the
#: option. CREATE and DROP go through core's formatter, ALTER through this
#: dialect's; all three consult this dialect's probes.
SEQUENCE_OPTION_PROBES = [
    _ProbeCase(
        "create-if-not-exists", "CREATE", CreateSequenceExpression,
        "if_not_exists", "CREATE SEQUENCE IF NOT EXISTS",
        "supports_sequence_if_not_exists", {"if_not_exists": True},
    ),
    _ProbeCase(
        "create-start", "CREATE", CreateSequenceExpression,
        "start", "SEQUENCE START",
        "supports_sequence_start", {"start": 1},
    ),
    _ProbeCase(
        "create-increment", "CREATE", CreateSequenceExpression,
        "increment", "SEQUENCE INCREMENT",
        "supports_sequence_increment", {"increment": 1},
    ),
    _ProbeCase(
        "create-minvalue", "CREATE", CreateSequenceExpression,
        "minvalue", "SEQUENCE MINVALUE",
        "supports_sequence_minvalue", {"minvalue": 1},
    ),
    _ProbeCase(
        "create-maxvalue", "CREATE", CreateSequenceExpression,
        "maxvalue", "SEQUENCE MAXVALUE",
        "supports_sequence_maxvalue", {"maxvalue": 1000},
    ),
    _ProbeCase(
        "create-cycle", "CREATE", CreateSequenceExpression,
        "cycle", "SEQUENCE CYCLE",
        "supports_sequence_cycle", {"cycle": True},
    ),
    _ProbeCase(
        "create-cache", "CREATE", CreateSequenceExpression,
        "cache", "SEQUENCE CACHE",
        "supports_sequence_cache", {"cache": 10},
    ),
    _ProbeCase(
        "create-order", "CREATE", CreateSequenceExpression,
        "order", "SEQUENCE ORDER",
        "supports_sequence_order", {"order": True},
    ),
    _ProbeCase(
        "create-owned-by", "CREATE", CreateSequenceExpression,
        "owned_by", "SEQUENCE OWNED BY",
        "supports_sequence_owned_by", {"owned_by": "dbo.orders.id"},
    ),
    _ProbeCase(
        "alter-start", "ALTER", AlterSequenceExpression,
        "start", "ALTER SEQUENCE START",
        "supports_alter_sequence_start", {"start": 1},
    ),
    _ProbeCase(
        "alter-increment", "ALTER", AlterSequenceExpression,
        "increment", "ALTER SEQUENCE INCREMENT",
        "supports_sequence_increment", {"increment": 1},
    ),
    _ProbeCase(
        "alter-minvalue", "ALTER", AlterSequenceExpression,
        "minvalue", "ALTER SEQUENCE MINVALUE",
        "supports_sequence_minvalue", {"minvalue": 1},
    ),
    _ProbeCase(
        "alter-maxvalue", "ALTER", AlterSequenceExpression,
        "maxvalue", "ALTER SEQUENCE MAXVALUE",
        "supports_sequence_maxvalue", {"maxvalue": 1000},
    ),
    _ProbeCase(
        "alter-cycle", "ALTER", AlterSequenceExpression,
        "cycle", "ALTER SEQUENCE CYCLE",
        "supports_sequence_cycle", {"cycle": True},
    ),
    _ProbeCase(
        "alter-cache", "ALTER", AlterSequenceExpression,
        "cache", "ALTER SEQUENCE CACHE",
        "supports_sequence_cache", {"cache": 10},
    ),
    _ProbeCase(
        "alter-order", "ALTER", AlterSequenceExpression,
        "order", "ALTER SEQUENCE ORDER",
        "supports_sequence_order", {"order": True},
    ),
    _ProbeCase(
        "alter-no-order", "ALTER", AlterSequenceExpression,
        "NO ORDER", "ALTER SEQUENCE ORDER",
        "supports_sequence_order", {"order": False},
    ),
    _ProbeCase(
        "alter-owned-by", "ALTER", AlterSequenceExpression,
        "owned_by", "ALTER SEQUENCE OWNED BY",
        "supports_sequence_owned_by", {"owned_by": "dbo.orders.id"},
    ),
    _ProbeCase(
        "drop-if-exists", "DROP", DropSequenceExpression,
        "if_exists", "DROP SEQUENCE IF EXISTS",
        "supports_sequence_if_exists", {"if_exists": True},
    ),
]

#: Sequence probes that answer about the statement or the sequence object, not
#: about one of its options. ``supports_sequence`` is the master switch every
#: sequence formatter consults; the other four are declaration-only answers
#: that no formatter in core or this backend reads, so no option behaviour can
#: follow them. They are named here rather than silently skipped.
NON_OPTION_PROBES = frozenset(
    {
        "supports_sequence",
        "supports_create_sequence",
        "supports_drop_sequence",
        "supports_alter_sequence",
        "supports_sequence_as_data_type",
    }
)

#: Sentinel floor, not the coverage list: the walk must at least see the
#: option probes that existed when it was written. Hard-coded on purpose --
#: deriving it from ``SEQUENCE_OPTION_PROBES`` would let a case and its probe
#: be deleted together without this floor moving.
_OPTION_PROBES_AT_WALK_BIRTH = frozenset(
    {
        "supports_sequence_if_not_exists",
        "supports_sequence_if_exists",
        "supports_sequence_start",
        "supports_alter_sequence_start",
        "supports_sequence_increment",
        "supports_sequence_minvalue",
        "supports_sequence_maxvalue",
        "supports_sequence_cycle",
        "supports_sequence_cache",
        "supports_sequence_order",
        "supports_sequence_owned_by",
    }
)


def _declared_sequence_probes() -> set:
    """Every ``supports_*sequence*`` capability declared on the dialect."""
    declared = set()
    for name in dir(SQLServerDialect):
        if not name.startswith("supports_"):
            continue
        tail = name[len("supports_"):]
        if not tail.startswith(
            ("sequence", "create_sequence", "drop_sequence", "alter_sequence")
        ):
            continue
        if callable(getattr(SQLServerDialect, name, None)):
            declared.add(name)
    return declared


def _flipped_dialect(probe_name: str) -> SQLServerDialect:
    """A stock dialect with exactly one capability probe flipped.

    The flip is the only difference from the stock dialect, so any behaviour
    change between the two is attributable to that probe alone.
    """
    stock_value = getattr(SQLServerDialect(SQL_SERVER_2022), probe_name)()
    flipped = type(
        f"SQLServerDialectFlipped_{probe_name}",
        (SQLServerDialect,),
        {probe_name: lambda self: not stock_value},
    )
    return flipped(SQL_SERVER_2022)


def _render_outcome(expression_cls, dialect, kwargs):
    """Render one statement; a refusal is an outcome, not an error.

    Returns ``("rendered", (sql, params))`` or ``("refused", message)`` so the
    guard can compare the two dialects' behaviour without ``pytest.raises``.
    """
    try:
        sql, params = expression_cls(dialect, _seq(dialect), **kwargs).to_sql()
    except UnsupportedFeatureError as exc:
        return "refused", str(exc)
    return "rendered", (sql, params)


def _load_bearing_failure(case: _ProbeCase, stock, flipped):
    """The reason ``case`` fails the load-bearing walk, or ``None``.

    The stock dialect's outcome must follow its own probe answer: rendered
    when the probe accepts the option, refused (naming it) when it does not.
    The flipped dialect must then answer the opposite. If both dialects behave
    the same, the probe is decorative.
    """
    stock_probe = getattr(stock, case.probe_name)()
    stock_kind, stock_detail = _render_outcome(case.expression_cls, stock, case.kwargs)
    flipped_kind, flipped_detail = _render_outcome(
        case.expression_cls, flipped, case.kwargs
    )
    expected_stock = "rendered" if stock_probe else "refused"
    expected_flipped = "refused" if stock_probe else "rendered"

    if stock_kind != expected_stock:
        return (
            f"{case.statement} SEQUENCE {case.option}: the stock dialect answers "
            f"{case.probe_name}()={stock_probe}, so the option must be "
            f"{expected_stock}; got {stock_kind}: {stock_detail!r}"
        )
    if stock_kind == "refused" and case.feature not in stock_detail:
        return (
            f"{case.statement} SEQUENCE {case.option}: the refusal does not name "
            f"{case.feature!r}: {stock_detail!r}"
        )
    if flipped_kind != expected_flipped:
        return (
            f"{case.statement} SEQUENCE {case.option}: with "
            f"{case.probe_name}() flipped to {not stock_probe}, the option must be "
            f"{expected_flipped}; got {flipped_kind}: {flipped_detail!r}. The "
            f"probe is decorative: the formatter ignores its answer."
        )
    if flipped_kind == "refused" and case.feature not in flipped_detail:
        return (
            f"{case.statement} SEQUENCE {case.option}: the flipped refusal does "
            f"not name {case.feature!r}: {flipped_detail!r}"
        )
    return None


class TestEverySequenceOptionProbeIsLoadBearing:
    """Flipping any one sequence-option probe must change the formatter's answer.

    Each case subclasses the stock dialect with exactly one probe flipped and
    renders the same expression through the same formatter. The stock dialect
    answers ``False`` for ``order`` and ``owned_by``, so those cases must
    refuse on the stock dialect and render on the flipped one; the other probes
    answer ``True`` (or ``False`` for the IF NOT EXISTS spellings), so their
    cases must flip the other way.
    """

    @pytest.mark.parametrize(
        "case",
        SEQUENCE_OPTION_PROBES,
        ids=[case.label for case in SEQUENCE_OPTION_PROBES],
    )
    def test_every_sequence_option_probe_is_load_bearing(self, dialect, case):
        flipped_dialect = _flipped_dialect(case.probe_name)
        failure = _load_bearing_failure(case, dialect, flipped_dialect)
        assert failure is None, failure


class TestTheWalkCoversEveryProbe:
    """The case list cannot silently shrink while the dialect grows."""

    def test_every_declared_sequence_probe_is_walked_or_named(self):
        covered = {case.probe_name for case in SEQUENCE_OPTION_PROBES}
        declared = _declared_sequence_probes()
        unaccounted = declared - covered - NON_OPTION_PROBES
        assert not unaccounted, (
            f"sequence probes {sorted(unaccounted)} are declared but neither "
            f"walked nor listed as non-option; extend the guard or say why they "
            f"are outside it"
        )
        # Sentinel: the walk must still see the probes that existed when it was
        # written, or a shrinking MRO could hide a dropped probe.
        assert covered >= _OPTION_PROBES_AT_WALK_BIRTH


class TestTheDefaultPolarityAlsoFollowsTheProbe:
    """``cycle=False`` changes the SQL while both dialects keep rendering.

    Flipping ``supports_sequence_cycle`` must remove the ``NO CYCLE`` clause,
    not just flip a refusal: this is the "different SQL" half of load-bearing,
    which the rendered/refused walk alone cannot see.
    """

    @pytest.mark.parametrize(
        "statement,expression_cls",
        [
            ("CREATE", CreateSequenceExpression),
            ("ALTER", AlterSequenceExpression),
        ],
        ids=["create", "alter"],
    )
    def test_no_cycle_clause_follows_the_probe(
        self, dialect, statement, expression_cls
    ):
        flipped = _flipped_dialect("supports_sequence_cycle")
        stock_kind, stock_detail = _render_outcome(
            expression_cls, dialect, {"cycle": False}
        )
        flipped_kind, flipped_detail = _render_outcome(
            expression_cls, flipped, {"cycle": False}
        )
        assert stock_kind == "rendered", (statement, stock_detail)
        assert flipped_kind == "rendered", (statement, flipped_detail)
        stock_sql = stock_detail[0]
        flipped_sql = flipped_detail[0]
        assert stock_sql != flipped_sql, (statement, stock_sql)
        assert "NO CYCLE" in stock_sql, (statement, stock_sql)
        assert "NO CYCLE" not in flipped_sql, (statement, flipped_sql)


class TestTheGuardCanSeeADecorativeProbe:
    """The guard is live: the pre-fix shape must fail it.

    The dialect below is the shape ``format_alter_sequence_statement`` had
    before the gates existed -- ``supports_sequence_order()`` answers ``True``
    while the formatter refuses ``ORDER`` unconditionally. If the walk could
    not report that as decorative, it could not certify the defect it was
    written to catch.
    """

    def test_hardcoded_order_refusal_is_reported_decorative(self, dialect):
        case = next(c for c in SEQUENCE_OPTION_PROBES if c.label == "alter-order")

        class HardcodedOrderDialect(SQLServerDialect):
            def supports_sequence_order(self) -> bool:
                return True

            def format_alter_sequence_statement(self, expr):
                if expr.order is not None:
                    raise UnsupportedFeatureError(
                        self.name,
                        "ALTER SEQUENCE ORDER",
                        "hard-coded refusal, ignoring the probe",
                    )
                return super().format_alter_sequence_statement(expr)

        flipped = HardcodedOrderDialect(SQL_SERVER_2022)
        failure = _load_bearing_failure(case, dialect, flipped)
        assert failure is not None, (
            "the walk did not notice a probe the formatter ignores"
        )
        assert "decorative" in failure, failure
