# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_master_probes_guard_sqlserver.py
"""Guard: the four master probes that gate clauses SQL Server cannot spell.

The round gated three previously-decorative master probes behind real call
sites in core (``format_cte_expression`` consults ``supports_materialized_cte``,
``format_truncate_statement`` consults ``supports_truncate``, and the new
``supports_with_data_clause`` decides ``WITH [NO] DATA`` on CTAS / materialized
view create / materialized view refresh), and added ``supports_transaction_wait``
for the ``wait`` / ``no_wait`` pair on the two transaction expressions.  A
dialect that leaves these probes undeclared inherits a core default rather than
stating its own contract.

A probe is **load-bearing** when the formatter's decision follows its answer:
flip the probe and the rendered statement (or the refusal) flips with it.  A
master probe is **declared** when a class in this backend's package answers it,
so a change to a core default cannot silently move SQL Server's contract.

Measured answers (SQL Server 2019 / 2022 / 2025, port 11433 / 11434 / 11435,
``{SQL Server}`` driver; raw output in
``.claude/plan/2026-10-08/measure_master_probes.txt``):

* ``supports_truncate()`` -> **True**: ``TRUNCATE TABLE dbo.t`` accepted and
  empties the table; ``TRUNCATE TABLE dbo.t CASCADE`` rejected.
* ``supports_with_data_clause()`` -> **False**: ``SELECT ... INTO dbo.t``
  accepted, but the same statement with ``WITH DATA`` or ``WITH NO DATA`` is a
  syntax error near ``with``; ``CREATE TABLE ... AS`` is a syntax error too.
* ``supports_materialized_cte()`` -> **False**: ``WITH c AS (...)`` accepted;
  ``AS MATERIALIZED`` and ``AS NOT MATERIALIZED`` are syntax errors.
* ``supports_transaction_wait()`` -> **False**: ``BEGIN TRANSACTION WAIT`` is
  accepted, but the word is taken as the transaction *name*
  (``sys.dm_tran_active_transactions.name`` = ``'WAIT'``; a control name
  behaves the same), ``BEGIN TRANSACTION NO WAIT``, ``SET TRANSACTION WAIT``
  and ``SET TRANSACTION NO WAIT`` are syntax errors.  No lock-wait clause exists.

Scope notes:

* ``supports_materialized_cte`` and ``supports_with_data_clause`` are consulted
  by core formatters this dialect inherits (``format_cte_expression``,
  ``format_create_table_as_statement``), so the load-bearing walk flips them
  through a subclass and checks the core render/refuse paths.
* Materialized view create / refresh are refused *as statements* by this
  dialect before any ``WITH [NO] DATA`` gate could run; the walk therefore
  covers CTAS and the focused test below documents the subsumption instead of
  pretending a clause-level refusal exists for a statement that does not exist.
* ``supports_truncate`` and ``supports_transaction_wait`` are consulted by this
  backend's own formatters (``format_truncate_statement``,
  ``format_begin_transaction`` / ``format_set_transaction``), which is where the
  pre-fix defects lived: the probes' answers could not change the behaviour.

The guard is deliberately able to fail: ``TestTheGuardCanSeeADroppingFormatter``
feeds the walk dialects whose formatter ignores a probe (the shape this backend
had before the round) and asserts it reports the probe decorative.
"""

import re
from typing import Callable, NamedTuple

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.expression.objects import MaterializedView, Table
from rhosocial.activerecord.backend.expression.query_sources import CTEExpression
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    CreateTableAsExpression,
)
from rhosocial.activerecord.backend.expression.statements.ddl_truncate import (
    TruncateExpression,
)
from rhosocial.activerecord.backend.expression.statements.ddl_view import (
    CreateMaterializedViewExpression,
    RefreshMaterializedViewExpression,
)
from rhosocial.activerecord.backend.expression.statements.dql import QueryExpression
from rhosocial.activerecord.backend.expression.transaction import (
    BeginTransactionExpression,
    SetTransactionExpression,
)
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

#: Every declaration this guard certifies must come from this package.
BACKEND_PACKAGE = "rhosocial.activerecord.backend.impl.sqlserver."

SQL_SERVER_2022 = (16, 0, 0)


def _dialect():
    return SQLServerDialect(SQL_SERVER_2022)


def _table(d, name="mp_guard_t"):
    return Table(d, name)


def _query(d):
    return QueryExpression(d, select=[Column(d, "a")], from_=_table(d, "s"))


def _declaring_class(probe_name):
    """The first class in the dialect's MRO that *declares* ``probe_name``."""
    for cls in SQLServerDialect.__mro__:
        if probe_name in cls.__dict__:
            return cls
    raise AssertionError(f"no class in the MRO declares {probe_name}()")


def _declaring_module(probe_name):
    return _declaring_class(probe_name).__module__


class MasterProbeCase(NamedTuple):
    """One master probe and the clause request it decides.

    ``stock_answer`` is the measured answer, hard-coded here on purpose: it is
    the source of truth and must not be read back from the dialect, or the
    guard could never see a flipped default.  ``feature`` is the fragment the
    refusal must name; ``spelled`` is the regex the render must contain when
    the probe accepts the request.
    """

    label: str
    probe_name: str
    stock_answer: bool
    feature: str
    spelled: str
    build: Callable


MASTER_PROBE_CASES = (
    MasterProbeCase(
        "truncate",
        "supports_truncate",
        True,
        "TRUNCATE",
        r"TRUNCATE TABLE",
        lambda d: TruncateExpression(d, _table(d)),
    ),
    MasterProbeCase(
        "materialized-cte",
        "supports_materialized_cte",
        False,
        "MATERIALIZED CTE",
        r"AS MATERIALIZED",
        lambda d: CTEExpression(d, "c", _query(d), materialized=True),
    ),
    MasterProbeCase(
        "not-materialized-cte",
        "supports_materialized_cte",
        False,
        "NOT MATERIALIZED CTE",
        r"AS NOT MATERIALIZED",
        lambda d: CTEExpression(d, "c", _query(d), not_materialized=True),
    ),
    MasterProbeCase(
        "ctas-with-data",
        "supports_with_data_clause",
        False,
        "WITH DATA",
        r"WITH DATA",
        lambda d: CreateTableAsExpression(d, _table(d), _query(d), with_data=True),
    ),
    MasterProbeCase(
        "ctas-no-data",
        "supports_with_data_clause",
        False,
        "WITH NO DATA",
        r"WITH NO DATA",
        lambda d: CreateTableAsExpression(d, _table(d), _query(d), no_data=True),
    ),
    MasterProbeCase(
        "begin-wait",
        "supports_transaction_wait",
        False,
        "transaction WAIT",
        r"(?<!NO )\bWAIT\b",
        lambda d: BeginTransactionExpression(d, wait=True),
    ),
    MasterProbeCase(
        "begin-no-wait",
        "supports_transaction_wait",
        False,
        "transaction NO WAIT",
        r"\bNO WAIT\b",
        lambda d: BeginTransactionExpression(d, no_wait=True),
    ),
    MasterProbeCase(
        "set-wait",
        "supports_transaction_wait",
        False,
        "transaction WAIT",
        r"(?<!NO )\bWAIT\b",
        lambda d: SetTransactionExpression(d, wait=True),
    ),
    MasterProbeCase(
        "set-no-wait",
        "supports_transaction_wait",
        False,
        "transaction NO WAIT",
        r"\bNO WAIT\b",
        lambda d: SetTransactionExpression(d, no_wait=True),
    ),
)

PROBE_NAMES = tuple(
    dict.fromkeys(case.probe_name for case in MASTER_PROBE_CASES)
)


def _flipped(probe_name):
    """A stock dialect with exactly one master probe flipped.

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


def _render_outcome(case, dialect):
    """Render one clause request; a refusal is an outcome, not an error."""
    try:
        sql, params = case.build(dialect).to_sql()
    except UnsupportedFeatureError as exc:
        return "refused", str(exc)
    return "rendered", (sql, params)


def _load_bearing_failure(case, stock, flipped):
    """The reason ``case`` fails the load-bearing walk, or ``None``."""
    stock_probe = getattr(stock, case.probe_name)()
    if stock_probe is not case.stock_answer:
        return (
            f"{case.label}: {case.probe_name}() answers {stock_probe!r}, but the "
            f"measurement says {case.stock_answer!r}"
        )

    expected_stock = "rendered" if case.stock_answer else "refused"
    expected_flipped = "refused" if case.stock_answer else "rendered"

    stock_kind, stock_detail = _render_outcome(case, stock)
    if stock_kind != expected_stock:
        return (
            f"{case.label}: the stock dialect answers {case.probe_name}()="
            f"{stock_probe}, so the request must be {expected_stock}; got "
            f"{stock_kind}: {stock_detail!r}"
        )
    if stock_kind == "refused" and case.feature not in stock_detail:
        return (
            f"{case.label}: the refusal does not name {case.feature!r}: "
            f"{stock_detail!r}"
        )
    if stock_kind == "rendered" and not re.search(case.spelled, stock_detail[0]):
        return (
            f"{case.label}: the render does not spell {case.spelled!r}: "
            f"{stock_detail[0]!r}"
        )

    flipped_kind, flipped_detail = _render_outcome(case, flipped)
    if flipped_kind != expected_flipped:
        return (
            f"{case.label}: with {case.probe_name}() flipped to "
            f"{not stock_probe}, the request must be {expected_flipped}; got "
            f"{flipped_kind}: {flipped_detail!r}. The probe is decorative: the "
            f"formatter ignores its answer."
        )
    if flipped_kind == "refused" and case.feature not in flipped_detail:
        return (
            f"{case.label}: the flipped refusal does not name {case.feature!r}: "
            f"{flipped_detail!r}"
        )
    if flipped_kind == "rendered" and not re.search(case.spelled, flipped_detail[0]):
        return (
            f"{case.label}: the flipped render does not spell {case.spelled!r}: "
            f"{flipped_detail[0]!r}"
        )
    return None


class TestTheProbeAnswersAreTheMeasuredOnes:
    """Each master probe answers exactly the value measured on live servers."""

    @pytest.mark.parametrize(
        "case", MASTER_PROBE_CASES, ids=[c.label for c in MASTER_PROBE_CASES]
    )
    def test_probe_answer_matches_the_measurement(self, case):
        answer = getattr(_dialect(), case.probe_name)()
        assert answer is case.stock_answer, (
            f"{case.probe_name}() answered {answer!r}; the measurement says "
            f"{case.stock_answer!r}"
        )

    def test_transaction_wait_is_not_the_protocol_stub(self):
        """The protocol base method returns ``None``; the dialect must say False."""
        answer = _dialect().supports_transaction_wait()
        assert answer is False, (
            f"supports_transaction_wait() answered {answer!r}; the stub in "
            f"TransactionControlSupport leaks through when the dialect does not "
            f"declare its own answer"
        )


class TestTheProbesAreDeclaredByThisBackend:
    """Each probe is declared in this package, not inherited from a core default.

    The core mixins happen to default ``supports_truncate`` to True and the
    other three to False; an inherited value can move with core while
    SQL Server's contract does not.  A declaration here pins the answer.
    """

    @pytest.mark.parametrize("probe_name", PROBE_NAMES)
    def test_probe_is_declared_in_this_backend(self, probe_name):
        declaring = _declaring_class(probe_name)
        assert declaring.__module__.startswith(BACKEND_PACKAGE), (
            f"{probe_name}() resolves to {declaring.__module__}.{declaring.__name__}; "
            f"declare it in this backend so a core default change cannot move "
            f"SQL Server's contract"
        )

    def test_the_declaration_check_can_fail(self):
        """Sentinel: a genuinely inherited probe must not pass the check.

        ``supports_create_table_as`` is a core default this backend does not
        declare (it renders SQL Server CTAS through SELECT INTO instead), so if
        it ever passed, the check would be vacuous.
        """
        module = _declaring_module("supports_create_table_as")
        assert not module.startswith(BACKEND_PACKAGE), module


class TestEveryMasterProbeIsLoadBearing:
    """Flipping any one master probe must change the formatter's answer."""

    @pytest.mark.parametrize(
        "case", MASTER_PROBE_CASES, ids=[c.label for c in MASTER_PROBE_CASES]
    )
    def test_every_master_probe_is_load_bearing(self, case):
        failure = _load_bearing_failure(case, _dialect(), _flipped(case.probe_name))
        assert failure is None, failure


class TestTheWaitPairHasFourDistinguishableStates:
    """The round's rule applied to ``wait`` / ``no_wait``.

    Neither set renders no clause; each explicit spelling is either rendered or
    refused *by name*; setting both is API misuse and raises ``ValueError``.
    SQL Server has no clause, so both explicit spellings are refusals -- and the
    two refusals must stay distinguishable (the requested spelling is named).
    """

    @pytest.mark.parametrize(
        "expression_cls",
        [BeginTransactionExpression, SetTransactionExpression],
        ids=["begin", "set"],
    )
    def test_wait_is_refused_by_name(self, expression_cls):
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            expression_cls(_dialect(), wait=True).to_sql()
        message = str(excinfo.value)
        assert "transaction WAIT" in message, message
        assert "transaction NO WAIT" not in message, message

    @pytest.mark.parametrize(
        "expression_cls",
        [BeginTransactionExpression, SetTransactionExpression],
        ids=["begin", "set"],
    )
    def test_no_wait_is_refused_by_name(self, expression_cls):
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            expression_cls(_dialect(), no_wait=True).to_sql()
        message = str(excinfo.value)
        assert "transaction NO WAIT" in message, message

    @pytest.mark.parametrize(
        "expression_cls",
        [BeginTransactionExpression, SetTransactionExpression],
        ids=["begin", "set"],
    )
    def test_both_wait_and_no_wait_are_mutually_exclusive(self, expression_cls):
        with pytest.raises(
            ValueError, match="wait and no_wait are mutually exclusive options"
        ):
            expression_cls(_dialect(), wait=True, no_wait=True)

    def test_neither_set_renders_no_clause(self):
        sql, _params = BeginTransactionExpression(_dialect()).to_sql()
        assert "WAIT" not in sql, sql


class TestTheTruncateFormatterFollowsTheProbe:
    """The SQL Server TRUNCATE override must consult ``supports_truncate()``."""

    def test_stock_renders_truncate_table(self):
        sql, params = TruncateExpression(_dialect(), _table(_dialect())).to_sql()
        assert sql == "TRUNCATE TABLE [mp_guard_t]", sql
        assert params == ()

    def test_flipped_false_refuses_by_name(self):
        class NoTruncateDialect(SQLServerDialect):
            def supports_truncate(self) -> bool:
                return False

        with pytest.raises(UnsupportedFeatureError) as excinfo:
            TruncateExpression(NoTruncateDialect(SQL_SERVER_2022), _table(_dialect())).to_sql()
        assert "TRUNCATE" in str(excinfo.value), str(excinfo.value)


class TestTheOtherThreeFormattersConsumeTheSpelling:
    """Focused checks that the request is never silently dropped."""

    def test_plain_cte_is_not_gated_by_the_materialized_probe(self):
        sql, _params = CTEExpression(_dialect(), "c", _query(_dialect())).to_sql()
        assert "MATERIALIZED" not in sql, sql

    def test_ctas_without_the_clause_is_not_gated(self):
        sql, _params = CreateTableAsExpression(
            _dialect(), _table(_dialect()), _query(_dialect())
        ).to_sql()
        assert "WITH DATA" not in sql, sql

    def test_materialized_view_statements_subsume_the_with_data_gate(self):
        """CREATE / REFRESH are refused as statements; the clause gate never runs.

        A clause-level refusal for a statement the engine does not have would
        be a fiction: the request is refused by the statement name instead, and
        that refusal is what the caller must see (never a silent render).
        """
        for builder, feature in (
            (
                lambda d: CreateMaterializedViewExpression(
                    d, MaterializedView(d, "mv"), _query(d), with_data=True
                ),
                "CREATE MATERIALIZED VIEW",
            ),
            (
                lambda d: RefreshMaterializedViewExpression(
                    d, MaterializedView(d, "mv"), with_data=True
                ),
                "REFRESH MATERIALIZED VIEW",
            ),
        ):
            with pytest.raises(UnsupportedFeatureError) as excinfo:
                builder(_dialect()).to_sql()
            assert feature in str(excinfo.value), str(excinfo.value)


class TestTheGuardIsNotVacuous:
    """Guards so the checks above cannot pass by accident."""

    def test_case_list_covers_every_probe(self):
        assert set(PROBE_NAMES) == {
            "supports_truncate",
            "supports_materialized_cte",
            "supports_with_data_clause",
            "supports_transaction_wait",
        }

    def test_both_probe_polarities_are_walked(self):
        answers = {case.stock_answer for case in MASTER_PROBE_CASES}
        assert answers == {True, False}, (
            "the walk only exercises one polarity; a formatter that hard-codes "
            "one outcome would pass"
        )

    def test_every_case_names_a_feature_and_a_spelling(self):
        for case in MASTER_PROBE_CASES:
            assert case.feature, case.label
            assert case.spelled, case.label
            assert callable(case.build), case.label


class TestTheGuardCanSeeADroppingFormatter:
    """The guard is live: the pre-fix shapes must fail it.

    Each dialect below is the shape this backend had before the round for that
    probe: the declaration is present (or flipped) but the formatter ignores
    the probe and renders the bare statement.  If the walk could not report
    that as decorative, it could not certify the defect it was written to catch.
    """

    def test_truncate_ignoring_the_probe_is_reported(self):
        case = next(c for c in MASTER_PROBE_CASES if c.label == "truncate")

        class DroppingTruncateDialect(SQLServerDialect):
            def supports_truncate(self) -> bool:
                return False

            def format_truncate_statement(self, expr):
                # The pre-fix shape: no probe branch at all.
                return f"TRUNCATE TABLE {expr.table.to_sql()[0]}", ()

        failure = _load_bearing_failure(
            case, _dialect(), DroppingTruncateDialect(SQL_SERVER_2022)
        )
        assert failure is not None, (
            "the walk did not notice a formatter that ignores supports_truncate()"
        )
        assert "decorative" in failure, failure

    def test_transaction_formatter_ignoring_the_wait_pair_is_reported(self):
        case = next(c for c in MASTER_PROBE_CASES if c.label == "begin-wait")

        class DroppingWaitDialect(SQLServerDialect):
            def supports_transaction_wait(self) -> bool:
                # The declaration says yes; the formatter below ignores it.
                return True

            def format_begin_transaction(self, expr):
                # The pre-fix shape: the wait pair was not read at all, so no
                # spelling followed the declaration.
                return "BEGIN TRANSACTION", ()

        failure = _load_bearing_failure(
            case, _dialect(), DroppingWaitDialect(SQL_SERVER_2022)
        )
        assert failure is not None, (
            "the walk did not notice a formatter that drops the wait pair"
        )
        assert "does not spell" in failure or "decorative" in failure, failure
