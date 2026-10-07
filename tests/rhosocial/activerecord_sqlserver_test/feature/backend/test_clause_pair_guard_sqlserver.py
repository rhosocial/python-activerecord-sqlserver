# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_clause_pair_guard_sqlserver.py
"""Guard: every two-spelling clause pair the SQL Server dialect consumes.

The rule this file enforces (the round's rules 1/2/3/4):

* each spellable alternative has its own parameter;
* "unspecified" is the state where none of the group's parameters is set;
* setting more than one of them is API misuse and raises ``ValueError`` at
  construction time;
* no ``Optional[bool]`` tri-state and no sentinel value.

For every clause pair the four states must be pairwise distinguishable:

====================  =============================================
neither parameter     neither spelling rendered
parameter A           A's spelling rendered (and not B's)
parameter B           B's spelling rendered (and not A's)
both parameters       ``ValueError``
====================  =============================================

Two kinds of pair appear here, and both are checked the same way:

* **spellable** (``AlterSequenceExpression.cycle`` and friends): the dialect
  has a spelling for both sides, so the render asserts the spelling.
* **unspellable** (``IdentityClause.cycle`` and friends): the server refuses
  the spelling, so an explicitly set parameter must be refused by name --
  never dropped, never rendered as invalid SQL. The refusal must name the
  *requested* spelling, so state A and state B stay distinguishable.

Which pairs the dialect consumes was read from the source, not guessed:
``format_alter_sequence_statement`` and ``format_identity_clause`` read the
sequence/identity pairs; ``format_set_operation_expression`` reads ``all_``;
the SQL Server overrides of the core TRUNCATE / DROP VIEW / DROP SCHEMA /
constraint / transaction formatters *replace* core's gated versions, so they
carry the gates for the pairs those nodes grew.

Every "unspellable" verdict is backed by a live-server measurement (SQL Server
2019 / 2022 / 2025, ``{SQL Server}`` driver), recorded in the round's plan
directory; e.g. ``TRUNCATE TABLE t CASCADE``, ``DROP VIEW v RESTRICT``,
``UNION DISTINCT`` and ``CHECK (...) ENFORCED`` are all server-refused.

The file is deliberately able to fail: ``TestTheGuardCanSeeADroppingFormatter``
feeds the comparison a dialect that ignores one of the new parameters (the
shape this backend had before the round) and asserts the guard reports it.
"""

import re

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.expression.objects import Schema, Sequence, Table, View
from rhosocial.activerecord.backend.expression.query_sources import SetOperationExpression
from rhosocial.activerecord.backend.expression.statements.ddl_schema import (
    DropSchemaExpression,
)
from rhosocial.activerecord.backend.expression.statements.ddl_sequence import (
    AlterSequenceExpression,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnConstraint,
    ColumnConstraintType,
    ColumnDefinition,
    ForeignKeyConstraint,
    IdentityClause,
    TableConstraint,
    TableConstraintType,
)
from rhosocial.activerecord.backend.expression.statements.ddl_truncate import (
    TruncateExpression,
)
from rhosocial.activerecord.backend.expression.statements.ddl_view import (
    DropViewExpression,
)
from rhosocial.activerecord.backend.expression.statements.dql import QueryExpression
from rhosocial.activerecord.backend.expression.transaction import (
    BeginTransactionExpression,
    SetTransactionExpression,
)
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression.alter_column import (
    SQLServerAlterColumn,
)
from rhosocial.activerecord.backend.impl.sqlserver.expression.columnstore import (
    SQLServerColumnstoreIndexExpression,
)


def _dialect():
    return SQLServerDialect((16, 0, 0))


def _seq(d):
    return Sequence(d, "s")


def _table(d, name="t"):
    return Table(d, name)


def _query(d, table="t1"):
    return QueryExpression(d, select=[Column(d, "a")], from_=_table(d, table))


def _union(d, **kw):
    return SetOperationExpression(
        d, left=_query(d, "t1"), right=_query(d, "t2"), operation="UNION", **kw
    )


def _predicate(d):
    from rhosocial.activerecord.backend.expression.predicates import (
        ComparisonPredicate,
    )

    return ComparisonPredicate(d, "=", Column(d, "a"), Column(d, "b"))


def _fk(d, **kw):
    return ForeignKeyConstraint(
        d,
        columns=["a"],
        foreign_key_table=_table(d, "t2"),
        foreign_key_columns=["b"],
        name="fk",
        **kw,
    )


def _check(d, **kw):
    return TableConstraint(
        d,
        TableConstraintType.CHECK,
        name="ck",
        check_condition=_predicate(d),
        **kw,
    )


def _column_check(d, **kw):
    """A CHECK constraint rendered through the column-definition path.

    SQL Server's ``format_column_definition`` override walks the constraints
    itself, so this is the path a user's column takes -- not the standalone
    ``ColumnConstraint.to_sql()`` dispatch, which would bypass the override.
    """
    return ColumnDefinition(
        d,
        "a",
        IntegerType(d),
        constraints=[
            ColumnConstraint(
                d,
                ColumnConstraintType.CHECK,
                name="ck",
                check_condition=_predicate(d),
                **kw,
            )
        ],
    )


def _alter_column(d, **kw):
    return SQLServerAlterColumn(d, "c", data_type="INT", **kw)


def _columnstore(d, **kw):
    """A columnstore index; NONCLUSTERED takes its key list, the rest do not."""
    if kw.get("nonclustered"):
        kw.setdefault("columns", ["c"])
    return SQLServerColumnstoreIndexExpression(d, "ix", "t", **kw)


class PairCase:
    """One two-spelling clause and how to render it in each state.

    ``a_error`` / ``b_error`` are ``None`` for a spellable pair, or a
    ``(feature, message_fragment)`` tuple for a pair the server cannot spell:
    the refusal must carry both fragments, and the fragments must differ
    between A and B so the two refusals stay distinguishable.
    """

    def __init__(
        self,
        case_id,
        builder,
        a,
        b,
        a_pattern,
        b_pattern,
        a_value=True,
        b_value=True,
        a_error=None,
        b_error=None,
        neither_error=None,
    ):
        self.case_id = case_id
        self.builder = builder
        self.a = a
        self.b = b
        self.a_pattern = re.compile(a_pattern)
        self.b_pattern = re.compile(b_pattern)
        self.a_value = a_value
        self.b_value = b_value
        self.a_error = a_error
        self.b_error = b_error
        self.neither_error = neither_error

    def render(self, dialect, **kwargs):
        sql, _params = self.builder(dialect, **kwargs).to_sql()
        return sql


PAIR_CASES = (
    # --- ALTER SEQUENCE: CYCLE / CACHE are spellable, ORDER is not ---
    PairCase(
        "AlterSequenceExpression.cycle",
        lambda d, **kw: AlterSequenceExpression(d, _seq(d), **kw),
        "cycle",
        "no_cycle",
        r"(?<!NO )CYCLE\b",
        r"NO CYCLE\b",
    ),
    PairCase(
        "AlterSequenceExpression.cache",
        lambda d, **kw: AlterSequenceExpression(d, _seq(d), **kw),
        "cache",
        "no_cache",
        r"CACHE 10\b",
        r"NO CACHE\b",
        a_value=10,
    ),
    PairCase(
        "AlterSequenceExpression.order",
        lambda d, **kw: AlterSequenceExpression(d, _seq(d), **kw),
        "order",
        "no_order",
        r"(?<!NO )ORDER\b",
        r"NO ORDER\b",
        a_error=("ALTER SEQUENCE ORDER", "the ORDER sequence option"),
        b_error=("ALTER SEQUENCE ORDER", "the NO ORDER sequence option"),
    ),
    # --- IdentityClause: none of the three pairs has a spelling ---
    PairCase(
        "IdentityClause.cycle",
        lambda d, **kw: IdentityClause(d, **kw),
        "cycle",
        "no_cycle",
        r"(?<!NO )CYCLE\b",
        r"NO CYCLE\b",
        a_error=("IDENTITY CYCLE", "the CYCLE identity option"),
        b_error=("IDENTITY CYCLE", "the NO CYCLE identity option"),
    ),
    PairCase(
        "IdentityClause.cache",
        lambda d, **kw: IdentityClause(d, **kw),
        "cache",
        "no_cache",
        r"CACHE 10\b",
        r"NO CACHE\b",
        a_value=10,
        a_error=("IDENTITY CACHE", "the CACHE identity option"),
        b_error=("IDENTITY CACHE", "the NO CACHE identity option"),
    ),
    PairCase(
        "IdentityClause.order",
        lambda d, **kw: IdentityClause(d, **kw),
        "order",
        "no_order",
        r"(?<!NO )ORDER\b",
        r"NO ORDER\b",
        a_error=("IDENTITY ORDER", "the ORDER identity option"),
        b_error=("IDENTITY ORDER", "the NO ORDER identity option"),
    ),
    # --- TRUNCATE: the SQL Server override replaces core's gated formatter ---
    PairCase(
        "TruncateExpression.cascade",
        lambda d, **kw: TruncateExpression(d, _table(d), **kw),
        "cascade",
        "restrict",
        r"CASCADE\b",
        r"RESTRICT\b",
        a_error=("TRUNCATE CASCADE", "does not support TRUNCATE with CASCADE"),
        b_error=("TRUNCATE RESTRICT", "does not support TRUNCATE with RESTRICT"),
    ),
    PairCase(
        "TruncateExpression.restart_identity",
        lambda d, **kw: TruncateExpression(d, _table(d), **kw),
        "restart_identity",
        "continue_identity",
        r"RESTART IDENTITY\b",
        r"CONTINUE IDENTITY\b",
        a_error=(
            "TRUNCATE RESTART IDENTITY",
            "does not support TRUNCATE RESTART IDENTITY",
        ),
        b_error=(
            "TRUNCATE CONTINUE IDENTITY",
            "does not support TRUNCATE CONTINUE IDENTITY",
        ),
    ),
    # --- DROP VIEW / DROP SCHEMA: same replacement argument ---
    PairCase(
        "DropViewExpression.cascade",
        lambda d, **kw: DropViewExpression(d, View(d, "v"), **kw),
        "cascade",
        "restrict",
        r"CASCADE\b",
        r"RESTRICT\b",
        a_error=("DROP VIEW CASCADE", "does not support DROP VIEW CASCADE"),
        b_error=("DROP VIEW RESTRICT", "does not support DROP VIEW RESTRICT"),
    ),
    PairCase(
        "DropSchemaExpression.cascade",
        lambda d, **kw: DropSchemaExpression(d, Schema(d, "s"), **kw),
        "cascade",
        "restrict",
        r"CASCADE\b",
        r"RESTRICT\b",
        a_error=("DROP SCHEMA CASCADE", "does not support DROP SCHEMA CASCADE"),
        b_error=("DROP SCHEMA RESTRICT", "does not support DROP SCHEMA RESTRICT"),
    ),
    # --- set operations: ALL is spellable, DISTINCT is not (measured) ---
    PairCase(
        "SetOperationExpression.all_",
        _union,
        "all_",
        "distinct",
        r"\bALL\b",
        r"\bDISTINCT\b",
        b_error=("UNION DISTINCT", "no DISTINCT keyword in set operations"),
    ),
    # --- transactions: [NOT] DEFERRABLE is not a T-SQL transaction mode ---
    PairCase(
        "BeginTransactionExpression.deferrable",
        lambda d, **kw: BeginTransactionExpression(d, **kw),
        "deferrable",
        "not_deferrable",
        r"(?<!NOT )DEFERRABLE\b",
        r"NOT DEFERRABLE\b",
        a_error=("DEFERRABLE transaction", "the DEFERRABLE transaction mode"),
        b_error=("DEFERRABLE transaction", "the NOT DEFERRABLE transaction mode"),
    ),
    PairCase(
        "SetTransactionExpression.deferrable",
        lambda d, **kw: SetTransactionExpression(d, **kw),
        "deferrable",
        "not_deferrable",
        r"(?<!NOT )DEFERRABLE\b",
        r"NOT DEFERRABLE\b",
        a_error=("DEFERRABLE transaction", "the DEFERRABLE transaction mode"),
        b_error=("DEFERRABLE transaction", "the NOT DEFERRABLE transaction mode"),
    ),
    # --- constraints: DEFERRABLE / INITIALLY / ENFORCED are not spellable ---
    PairCase(
        "ForeignKeyConstraint.deferrable",
        _fk,
        "deferrable",
        "not_deferrable",
        r"(?<!NOT )DEFERRABLE\b",
        r"NOT DEFERRABLE\b",
        a_error=("constraint DEFERRABLE", "the DEFERRABLE constraint"),
        b_error=("constraint NOT DEFERRABLE", "the NOT DEFERRABLE constraint"),
    ),
    PairCase(
        "ForeignKeyConstraint.initially_deferred",
        _fk,
        "initially_deferred",
        "initially_immediate",
        r"INITIALLY DEFERRED\b",
        r"INITIALLY IMMEDIATE\b",
        a_error=(
            "constraint INITIALLY DEFERRED",
            "the INITIALLY DEFERRED constraint",
        ),
        b_error=(
            "constraint INITIALLY IMMEDIATE",
            "the INITIALLY IMMEDIATE constraint",
        ),
    ),
    PairCase(
        "TableConstraint.enforced",
        _check,
        "enforced",
        "not_enforced",
        r"(?<!NOT )ENFORCED\b",
        r"NOT ENFORCED\b",
        a_error=("constraint ENFORCED", "the ENFORCED constraint"),
        b_error=("constraint NOT ENFORCED", "the NOT ENFORCED constraint"),
    ),
    PairCase(
        "ColumnConstraint.enforced",
        _column_check,
        "enforced",
        "not_enforced",
        r"(?<!NOT )ENFORCED\b",
        r"NOT ENFORCED\b",
        a_error=("constraint ENFORCED", "the ENFORCED constraint"),
        b_error=("constraint NOT ENFORCED", "the NOT ENFORCED constraint"),
    ),
    # --- dialect-specific gap 1: ALTER COLUMN NULL | NOT NULL ---
    PairCase(
        "SQLServerAlterColumn.not_null",
        _alter_column,
        "not_null",
        "nullable",
        r"NOT NULL\b",
        r"(?<!NOT )NULL\b",
    ),
    # --- dialect-specific gap 2: CLUSTERED | NONCLUSTERED ---
    PairCase(
        "SQLServerColumnstoreIndexExpression.clustered",
        _columnstore,
        "clustered",
        "nonclustered",
        r"(?<!NON)CLUSTERED\b",
        r"NONCLUSTERED\b",
    ),
)

PAIR_IDS = [case.case_id for case in PAIR_CASES]


def _expect_refusal(case, dialect, param, value, feature, fragment):
    """Assert that setting ``param`` refuses by name; raise AssertionError if not.

    A manual check rather than ``pytest.raises`` so the live-guard tests below
    can catch the failure as an ``AssertionError``.
    """
    try:
        case.render(dialect, **{param: value})
    except UnsupportedFeatureError as exc:
        message = str(exc)
        assert feature in message, (
            f"{case.case_id}: the refusal does not name {feature!r}: {message!r}"
        )
        assert fragment in message, (
            f"{case.case_id}: the refusal does not name the requested spelling "
            f"{fragment!r}: {message!r}"
        )
        return
    raise AssertionError(
        f"{case.case_id}: setting {param!r} was neither rendered nor refused"
    )


def _check_neither(case, dialect):
    if case.neither_error is not None:
        with pytest.raises(ValueError, match=case.neither_error):
            case.render(dialect)
        return
    sql = case.render(dialect)
    assert not case.a_pattern.search(sql), (
        f"{case.case_id}: with neither parameter set the SQL still spells "
        f"{case.a!r}: {sql!r}"
    )
    assert not case.b_pattern.search(sql), (
        f"{case.case_id}: with neither parameter set the SQL still spells "
        f"{case.b!r}: {sql!r}"
    )


def _check_a(case, dialect):
    if case.a_error is None:
        sql = case.render(dialect, **{case.a: case.a_value})
        assert case.a_pattern.search(sql), (
            f"{case.case_id}: {case.a!r} was not rendered: {sql!r}"
        )
        assert not case.b_pattern.search(sql), (
            f"{case.case_id}: setting {case.a!r} also rendered {case.b!r}: {sql!r}"
        )
        return
    feature, fragment = case.a_error
    _expect_refusal(case, dialect, case.a, case.a_value, feature, fragment)


def _check_b(case, dialect):
    if case.b_error is None:
        sql = case.render(dialect, **{case.b: case.b_value})
        assert case.b_pattern.search(sql), (
            f"{case.case_id}: {case.b!r} was not rendered: {sql!r}"
        )
        assert not case.a_pattern.search(sql), (
            f"{case.case_id}: setting {case.b!r} also rendered {case.a!r}: {sql!r}"
        )
        return
    feature, fragment = case.b_error
    _expect_refusal(case, dialect, case.b, case.b_value, feature, fragment)


class TestFourStatesArePairwiseDistinguishable:
    """The four states of every pair are pairwise distinguishable."""

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_neither_set_renders_neither_spelling(self, case):
        _check_neither(case, _dialect())

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_a_set_renders_or_refuses_a(self, case):
        _check_a(case, _dialect())

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_b_set_renders_or_refuses_b(self, case):
        _check_b(case, _dialect())

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_both_set_is_refused(self, case):
        with pytest.raises(
            ValueError, match=f"{case.a} and {case.b} are mutually exclusive options"
        ):
            case.render(
                _dialect(), **{case.a: case.a_value, case.b: case.b_value}
            )


class TestSentinelIsGone:
    """``cache=0`` is no longer a spelling of NO CACHE."""

    def test_alter_sequence_cache_zero_is_refused(self):
        with pytest.raises(ValueError, match="cache must be a positive integer"):
            AlterSequenceExpression(_dialect(), _seq(_dialect()), cache=0)

    def test_identity_cache_zero_is_refused(self):
        with pytest.raises(ValueError, match="cache must be a positive integer"):
            IdentityClause(_dialect(), cache=0)


class TestDialectGapValueConstraints:
    """The two dialect-specific pairs keep their value constraints."""

    def test_nonclustered_columnstore_requires_key_columns(self):
        with pytest.raises(ValueError, match="NONCLUSTERED columnstore requires key columns"):
            SQLServerColumnstoreIndexExpression(
                _dialect(), "ix", "t", nonclustered=True
            ).validate()

    def test_clustered_columnstore_forbids_key_columns(self):
        with pytest.raises(ValueError, match="clustered columnstore does not allow key columns"):
            _columnstore(_dialect(), clustered=True, columns=["c"]).validate()

    def test_order_columns_are_only_for_clustered(self):
        with pytest.raises(ValueError, match="ORDER .* only valid for clustered"):
            _columnstore(
                _dialect(), nonclustered=True, order_columns=["c1"]
            ).validate()


class TestGuardIsNotVacuous:
    """Guards so the checks above cannot pass by accident."""

    def test_every_case_has_two_distinct_parameters(self):
        for case in PAIR_CASES:
            assert case.a != case.b, case.case_id

    def test_every_pair_is_covered(self):
        """The pairs the dialect consumes are all in this table."""
        expected = {
            "AlterSequenceExpression.cycle",
            "AlterSequenceExpression.cache",
            "AlterSequenceExpression.order",
            "IdentityClause.cycle",
            "IdentityClause.cache",
            "IdentityClause.order",
            "TruncateExpression.cascade",
            "TruncateExpression.restart_identity",
            "DropViewExpression.cascade",
            "DropSchemaExpression.cascade",
            "SetOperationExpression.all_",
            "BeginTransactionExpression.deferrable",
            "SetTransactionExpression.deferrable",
            "ForeignKeyConstraint.deferrable",
            "ForeignKeyConstraint.initially_deferred",
            "TableConstraint.enforced",
            "ColumnConstraint.enforced",
            "SQLServerAlterColumn.not_null",
            "SQLServerColumnstoreIndexExpression.clustered",
        }
        covered = {case.case_id for case in PAIR_CASES}
        missing = expected - covered
        assert not missing, f"pairs in scope but not guarded: {sorted(missing)}"


class TestTheGuardCanSeeADroppingFormatter:
    """The guard is live: the pre-fix shape must fail it.

    The dialect below is the shape this backend had before the round -- the
    formatter ignores the new parameters and renders the bare statement. If the
    checks could not report that, they could not certify the defect they were
    written to catch.
    """

    def test_alter_sequence_dropping_cycle_is_reported(self):
        case = next(
            c for c in PAIR_CASES if c.case_id == "AlterSequenceExpression.cycle"
        )

        class DroppingCycleDialect(SQLServerDialect):
            def format_alter_sequence_statement(self, expr):
                # The pre-round shape: no cycle branch at all.
                return f"ALTER SEQUENCE {expr.sequence.to_sql()[0]}", ()

        with pytest.raises(AssertionError, match="was not rendered"):
            _check_a(case, DroppingCycleDialect((16, 0, 0)))

    def test_identity_dropping_no_cache_is_reported(self):
        case = next(c for c in PAIR_CASES if c.case_id == "IdentityClause.cache")

        class DroppingCacheDialect(SQLServerDialect):
            def format_identity_clause(self, expr):
                return " IDENTITY(1, 1)", ()

        with pytest.raises(AssertionError):
            _check_b(case, DroppingCacheDialect((16, 0, 0)))

    def test_truncate_dropping_cascade_is_reported(self):
        case = next(
            c for c in PAIR_CASES if c.case_id == "TruncateExpression.cascade"
        )

        class DroppingTruncateDialect(SQLServerDialect):
            def format_truncate_statement(self, expr):
                return f"TRUNCATE TABLE {expr.table.to_sql()[0]}", ()

        with pytest.raises(AssertionError, match="neither rendered nor refused"):
            _check_a(case, DroppingTruncateDialect((16, 0, 0)))
