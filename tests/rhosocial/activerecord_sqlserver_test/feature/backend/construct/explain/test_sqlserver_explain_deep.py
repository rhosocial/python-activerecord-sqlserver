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
  / ``supports_explain_format``) and the format matrix they advertise;
* the **exact SQL** ``format_explain_statement`` emits for every option
  combination -- estimated plan (``SET SHOWPLAN_TEXT`` / ``SHOWPLAN_XML``)
  versus actual plan (``SET STATISTICS PROFILE`` / ``STATISTICS XML``),
  including the ``ON; ...; OFF`` bracketing of the actual-plan forms;
* that ``ExplainStatement.to_sql()`` delegates to that formatter and passes
  the inner statement's parameters through unchanged.

All rendering assertions run against several explicit server versions so the
output is proven version-invariant and no server probe ever happens.
"""

from typing import Optional, Tuple

import pytest
from rhosocial.activerecord.backend.expression import (
    AllColumnsWildcard,
    ExplainFormat,
    ExplainOptions,
    ExplainStatement,
    QueryStatement,
)
from rhosocial.activerecord.backend.expression.objects import Table

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


class _SelectOne:
    """Minimal inner statement so rendered SQL and params are easy to pin.

    Returning fixed SQL plus a tuple of params lets us assert both the exact
    surrounding SHOWPLAN text and that parameters are passed through untouched.
    """

    def to_sql(self) -> Tuple[str, tuple]:
        return "SELECT 1", (42, 7)


def _render(
    dialect: SQLServerDialect, options: Optional[ExplainOptions], statement=None
) -> Tuple[str, tuple]:
    """Render an ExplainStatement through the dialect's public to_sql() path."""
    expr = ExplainStatement(dialect, statement=statement or _SelectOne(), options=options)
    return expr.to_sql()


class TestExplainCapabilityGates:
    """The ``supports_explain_*`` switches SQL Server advertises."""

    def test_supports_explain_plan(self, dialect: SQLServerDialect) -> None:
        assert dialect.supports_explain_plan() is True

    def test_supports_explain_analyze(self, dialect: SQLServerDialect) -> None:
        # SQL Server implements ANALYZE via STATISTICS PROFILE / STATISTICS XML.
        assert dialect.supports_explain_analyze() is True

    @pytest.mark.parametrize(
        ("format_name", "expected"),
        [
            ("TEXT", True),
            ("XML", True),
            ("xml", True),  # gate is case-insensitive
            (ExplainFormat.TEXT, True),  # enum members are str subclasses
            (ExplainFormat.XML, True),
            ("JSON", False),
            ("YAML", False),
            ("", False),
        ],
    )
    def test_supports_explain_format_matrix(
        self, dialect: SQLServerDialect, format_name, expected
    ) -> None:
        assert dialect.supports_explain_format(format_name) is expected

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
        assert sql == "SET SHOWPLAN_TEXT ON; SELECT 1"

    def test_empty_options_default_to_showplan_text(self, dialect: SQLServerDialect) -> None:
        sql, _ = _render(dialect, ExplainOptions())
        assert sql == "SET SHOWPLAN_TEXT ON; SELECT 1"

    def test_format_text_renders_showplan_text(self, dialect: SQLServerDialect) -> None:
        sql, _ = _render(dialect, ExplainOptions(format=ExplainFormat.TEXT))
        assert sql == "SET SHOWPLAN_TEXT ON; SELECT 1"

    def test_format_xml_renders_showplan_xml_without_off(self, dialect: SQLServerDialect) -> None:
        """Estimated XML plan is a single batch; no OFF toggle is emitted."""
        sql, _ = _render(dialect, ExplainOptions(format=ExplainFormat.XML))
        assert sql == "SET SHOWPLAN_XML ON; SELECT 1"
        assert "OFF" not in sql

    # -- actual plan (ANALYZE=True), with ON/OFF bracketing -------------------------

    def test_analyze_without_format_renders_statistics_profile(
        self, dialect: SQLServerDialect
    ) -> None:
        sql, _ = _render(dialect, ExplainOptions(analyze=True))
        assert sql == "SET STATISTICS PROFILE ON; SELECT 1; SET STATISTICS PROFILE OFF"

    def test_analyze_text_renders_statistics_profile(self, dialect: SQLServerDialect) -> None:
        """TEXT is not the XML branch, so ANALYZE falls back to PROFILE."""
        sql, _ = _render(dialect, ExplainOptions(analyze=True, format=ExplainFormat.TEXT))
        assert sql == "SET STATISTICS PROFILE ON; SELECT 1; SET STATISTICS PROFILE OFF"

    def test_analyze_xml_renders_statistics_xml(self, dialect: SQLServerDialect) -> None:
        sql, _ = _render(dialect, ExplainOptions(analyze=True, format=ExplainFormat.XML))
        assert sql == "SET STATISTICS XML ON; SELECT 1; SET STATISTICS XML OFF"

    def test_unsupported_format_is_ignored_by_renderer(self, dialect: SQLServerDialect) -> None:
        """Rendering does not validate format names; callers must use the gate."""
        assert dialect.supports_explain_format("JSON") is False
        estimated, _ = _render(dialect, ExplainOptions(format=ExplainFormat.JSON))
        assert estimated == "SET SHOWPLAN_TEXT ON; SELECT 1"
        actual, _ = _render(dialect, ExplainOptions(analyze=True, format=ExplainFormat.JSON))
        assert actual == "SET STATISTICS PROFILE ON; SELECT 1; SET STATISTICS PROFILE OFF"

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
        assert params == (42, 7)

    def test_real_query_statement_sql_is_embedded_verbatim(self, dialect: SQLServerDialect) -> None:
        query = QueryStatement(
            dialect, select=[AllColumnsWildcard(dialect)], from_=Table(dialect, "t")
        )
        assert query.to_sql()[0] == "SELECT * FROM [t]"
        sql, params = _render(dialect, ExplainOptions(format=ExplainFormat.XML), statement=query)
        assert sql == "SET SHOWPLAN_XML ON; SELECT * FROM [t]"
        assert params == ()

    def test_to_sql_delegates_to_format_explain_statement(self, dialect: SQLServerDialect) -> None:
        options = ExplainOptions(analyze=True, format=ExplainFormat.XML)
        expr = ExplainStatement(dialect, statement=_SelectOne(), options=options)
        assert expr.format_method == "format_explain_statement"
        direct = dialect.format_explain_statement(expr)
        assert expr.to_sql() == direct
        assert direct == ("SET STATISTICS XML ON; SELECT 1; SET STATISTICS XML OFF", (42, 7))
