# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/explain/test_sqlserver_explain_deep.py
"""Backend-local, deep EXPLAIN tests for SQL Server (construction level).

The shared testsuite contracts only assert that EXPLAIN *can* execute. Deep
semantic interpretation cannot be generalised across backends, and SQL Server
is a special case: ``SET SHOWPLAN_*`` / ``SET STATISTICS *`` must be the only
statement in an exclusive batch, which the generic ``explain()`` execution
flow cannot guarantee. Real-DB EXPLAIN execution is therefore deliberately
avoided here (see ``feature/backend/execute/query/test_backend_explain.py``,
which tests only the result-parsing hook for the same reason).

What this file pins down instead is everything that is *observable without a
connection*:

* the capability gates (``supports_explain_plan`` / ``supports_explain_analyze``
  / the per-format and per-option ``supports_explain_*`` switches) and the
  format matrix they advertise;
* the **exact SQL** ``format_explain_statement`` emits for every option
  combination -- estimated plan (``SET SHOWPLAN_TEXT`` / ``SHOWPLAN_XML``)
  versus actual plan (``SET STATISTICS PROFILE`` / ``STATISTICS XML``),
  including the ``ON; ...; OFF`` bracketing of the actual-plan forms;
* that ``ExplainStatement.to_sql()`` delegates to that formatter and passes
  the inner statement's parameters through unchanged.

The statement being explained is always built with the expression system
(``QueryStatement`` / ``Column`` / ``Literal`` / predicates / ``Table``), never
from a hand-written SQL string. SQL text appears only as assertion expectations.
All rendering assertions run against several explicit server versions so the
output is proven version-invariant and no server probe ever happens.
"""

from typing import Optional, Tuple

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import (
    Column,
    ComparisonPredicate,
    ExplainFormat,
    ExplainOptions,
    ExplainStatement,
    Literal,
    LogicalPredicate,
    QueryStatement,
)
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.query_parts import WhereClause
from rhosocial.activerecord.backend.expression.sources import NamedRelationRef
from rhosocial.activerecord.backend.impl.sqlserver.dialect import (
    SQL_SERVER_2012,
    SQL_SERVER_2016,
    SQL_SERVER_2019,
    SQL_SERVER_2022,
    SQLServerDialect,
)

VERSIONS = {
    "2008": (10, 0, 0),
    "2012": SQL_SERVER_2012,
    "2016": SQL_SERVER_2016,
    "2019": SQL_SERVER_2019,
    "2022": SQL_SERVER_2022,
}


@pytest.fixture(params=list(VERSIONS.values()), ids=list(VERSIONS.keys()))
def dialect(request) -> SQLServerDialect:
    """An offline dialect at each supported server version (no probe, no DB)."""
    return SQLServerDialect(request.param)


def _build_query(dialect: SQLServerDialect) -> QueryStatement:
    """Build the statement to EXPLAIN entirely from expression objects.

    Two literals give the wrapper two bound parameters, so parameter
    pass-through is observable without any hand-written SQL text.
    """
    return QueryStatement(
        dialect,
        select=[Column(dialect, "id")],
        from_=NamedRelationRef(dialect, Table(dialect, "users")),
        where=WhereClause(
            dialect,
            condition=LogicalPredicate(
                dialect,
                "AND",
                ComparisonPredicate(dialect, ">", Column(dialect, "price"), Literal(dialect, 100)),
                ComparisonPredicate(
                    dialect, "=", Column(dialect, "name"), Literal(dialect, "alice")
                ),
            ),
        ),
    )


def _render(
    dialect: SQLServerDialect, options: Optional[ExplainOptions], statement=None
) -> Tuple[str, tuple]:
    """Render an ExplainStatement through the dialect's public to_sql() path."""
    expr = ExplainStatement(dialect, statement=statement or _build_query(dialect), options=options)
    return expr.to_sql()


class TestExplainCapabilityGates:
    """The ``supports_explain_*`` switches SQL Server advertises."""

    def test_supports_explain_plan(self, dialect: SQLServerDialect) -> None:
        assert dialect.supports_explain_plan() is True

    def test_supports_explain_analyze(self, dialect: SQLServerDialect) -> None:
        # SQL Server implements ANALYZE via STATISTICS PROFILE / STATISTICS XML.
        assert dialect.supports_explain_analyze() is True

    @pytest.mark.parametrize(
        ("probe", "expected"),
        [
            ("supports_explain_format_text", True),
            ("supports_explain_format_xml", True),
            ("supports_explain_format_json", False),
            ("supports_explain_format_yaml", False),
            ("supports_explain_format_tree", False),
            ("supports_explain_format_traditional", False),
        ],
    )
    def test_explain_format_switches(
        self, dialect: SQLServerDialect, probe, expected
    ) -> None:
        assert getattr(dialect, probe)() is expected

    @pytest.mark.parametrize(
        "probe",
        [
            "supports_explain_verbose",
            "supports_explain_costs",
            "supports_explain_buffers",
            "supports_explain_timing",
            "supports_explain_settings",
            "supports_explain_wal",
        ],
    )
    def test_explain_option_switches_are_false(self, dialect: SQLServerDialect, probe) -> None:
        """T-SQL has SET settings, not EXPLAIN options, so none are accepted."""
        assert getattr(dialect, probe)() is False

    def test_analyze_gate_agrees_with_rendered_actual_plan(self, dialect: SQLServerDialect) -> None:
        """The gate's True answer is backed by a real STATISTICS PROFILE rendering."""
        assert dialect.supports_explain_analyze() is True
        sql, _ = _render(dialect, ExplainOptions(analyze=True))
        assert sql.startswith("SET STATISTICS PROFILE ON;")


class TestExplainStatementRendering:
    """Exact SQL emitted by ``format_explain_statement`` for each option."""

    # -- estimated plan (no ANALYZE) -------------------------------------------------

    def test_no_options_defaults_to_showplan_text(self, dialect: SQLServerDialect) -> None:
        sql, _ = _render(dialect, None)
        assert sql == (
            "SET SHOWPLAN_TEXT ON; " "SELECT [id] FROM [users] WHERE [price] > ? AND [name] = ?"
        )

    def test_empty_options_default_to_showplan_text(self, dialect: SQLServerDialect) -> None:
        sql, _ = _render(dialect, ExplainOptions())
        assert sql == (
            "SET SHOWPLAN_TEXT ON; " "SELECT [id] FROM [users] WHERE [price] > ? AND [name] = ?"
        )

    def test_format_text_renders_showplan_text(self, dialect: SQLServerDialect) -> None:
        sql, _ = _render(dialect, ExplainOptions(format=ExplainFormat.TEXT))
        assert sql == (
            "SET SHOWPLAN_TEXT ON; " "SELECT [id] FROM [users] WHERE [price] > ? AND [name] = ?"
        )

    def test_format_xml_renders_showplan_xml_without_off(self, dialect: SQLServerDialect) -> None:
        """Estimated XML plan is a single batch; no OFF toggle is emitted."""
        sql, _ = _render(dialect, ExplainOptions(format=ExplainFormat.XML))
        assert sql == (
            "SET SHOWPLAN_XML ON; " "SELECT [id] FROM [users] WHERE [price] > ? AND [name] = ?"
        )
        assert "OFF" not in sql

    # -- actual plan (ANALYZE=True), with ON/OFF bracketing -------------------------

    def test_analyze_without_format_renders_statistics_profile(
        self, dialect: SQLServerDialect
    ) -> None:
        sql, _ = _render(dialect, ExplainOptions(analyze=True))
        assert sql == (
            "SET STATISTICS PROFILE ON; "
            "SELECT [id] FROM [users] WHERE [price] > ? AND [name] = ?; "
            "SET STATISTICS PROFILE OFF"
        )

    def test_analyze_text_renders_statistics_profile(self, dialect: SQLServerDialect) -> None:
        """TEXT is not the XML branch, so ANALYZE falls back to PROFILE."""
        sql, _ = _render(dialect, ExplainOptions(analyze=True, format=ExplainFormat.TEXT))
        assert sql == (
            "SET STATISTICS PROFILE ON; "
            "SELECT [id] FROM [users] WHERE [price] > ? AND [name] = ?; "
            "SET STATISTICS PROFILE OFF"
        )

    def test_analyze_xml_renders_statistics_xml(self, dialect: SQLServerDialect) -> None:
        sql, _ = _render(dialect, ExplainOptions(analyze=True, format=ExplainFormat.XML))
        assert sql == (
            "SET STATISTICS XML ON; "
            "SELECT [id] FROM [users] WHERE [price] > ? AND [name] = ?; "
            "SET STATISTICS XML OFF"
        )

    def test_unsupported_format_is_rejected(self, dialect: SQLServerDialect) -> None:
        """An option this dialect cannot map fails instead of being dropped."""
        assert dialect.supports_explain_format_json() is False
        with pytest.raises(UnsupportedFeatureError):
            _render(dialect, ExplainOptions(format=ExplainFormat.JSON))
        with pytest.raises(UnsupportedFeatureError):
            _render(dialect, ExplainOptions(analyze=True, format=ExplainFormat.JSON))

    @pytest.mark.parametrize(
        "options",
        [
            ExplainOptions(costs=False),
            ExplainOptions(buffers=True),
            ExplainOptions(analyze=True, timing=True),
            ExplainOptions(verbose=True),
            ExplainOptions(settings=True),
            ExplainOptions(wal=True),
        ],
        ids=["costs-off", "buffers", "timing", "verbose", "settings", "wal"],
    )
    def test_unmappable_options_are_rejected(self, dialect: SQLServerDialect, options) -> None:
        """No T-SQL setting expresses these, so rendering must refuse them."""
        with pytest.raises(UnsupportedFeatureError):
            _render(dialect, options)

    # -- delegation / parameter handling --------------------------------------------

    @pytest.mark.parametrize(
        "options",
        [
            None,
            ExplainOptions(),
            ExplainOptions(format=ExplainFormat.XML),
            ExplainOptions(analyze=True),
            ExplainOptions(analyze=True, format=ExplainFormat.XML),
        ],
    )
    def test_inner_statement_params_pass_through(self, dialect: SQLServerDialect, options) -> None:
        _, params = _render(dialect, options)
        assert params == (100, "alice")

    def test_expression_built_statement_sql_is_embedded_verbatim(
        self, dialect: SQLServerDialect
    ) -> None:
        query = _build_query(dialect)
        assert query.to_sql()[0] == ("SELECT [id] FROM [users] WHERE [price] > ? AND [name] = ?")
        sql, params = _render(dialect, ExplainOptions(format=ExplainFormat.XML), statement=query)
        assert sql == (
            "SET SHOWPLAN_XML ON; " "SELECT [id] FROM [users] WHERE [price] > ? AND [name] = ?"
        )
        assert params == (100, "alice")

    def test_to_sql_delegates_to_format_explain_statement(self, dialect: SQLServerDialect) -> None:
        options = ExplainOptions(analyze=True, format=ExplainFormat.XML)
        expr = ExplainStatement(dialect, statement=_build_query(dialect), options=options)
        assert expr.format_method == "format_explain_statement"
        direct = dialect.format_explain_statement(expr)
        assert expr.to_sql() == direct
        assert direct == (
            "SET STATISTICS XML ON; "
            "SELECT [id] FROM [users] WHERE [price] > ? AND [name] = ?; "
            "SET STATISTICS XML OFF",
            (100, "alice"),
        )
