# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_identity_execution_confirmation.py
"""Execution confirmation for SQL Server's identity column.

Rendering is not execution: a formatter can produce SQL that looks perfect and
is still rejected by the server. Every verdict here is the server's own answer,
and every accepted verdict is guarded by a sentinel that must come back
REJECTED -- a classifier that cannot see a rejection would make the
confirmation vacuous.

The SQL rendered by the dialect is what is executed: the ``CreateTableExpression``
is built with an AR-layer ``IdentityAttribute``, exactly the path an application
uses, and the rendered statement is handed to
:func:`confirm_expression_execution`. Three outcomes stay distinct:

* ACCEPTED -- the server accepted the SQL;
* REJECTED -- raised as ``ExecutionConfirmationError``; this is the defect the
  helper exists to catch;
* NOT_RENDERED -- the dialect refused the expression (``UnsupportedFeatureError``),
  which is fail-closed behaviour working as designed, not a rejection.

Measured on 2019 / 2022 / 2025: ``IDENTITY(seed, increment)`` executes and
honours seed/increment; the standard ``GENERATED ... AS IDENTITY`` grammar is
refused by the server; MINVALUE / MAXVALUE / CYCLE / ORDER / CACHE have no
spelling.
"""

import pytest

from rhosocial.activerecord.base import IdentityAttribute
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import (
    ColumnDefinition,
    CreateTableExpression,
)
from rhosocial.activerecord.backend.expression.execution_testing import (
    ExecutionConfirmationError,
    ExecutionOutcome,
    classify_execution,
    confirm_expression_execution,
)
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import (
    AutoIncrementClause,
    IdentityClause,
)
from rhosocial.activerecord.backend.expression.types import IntegerType, TextType


def _drop_sql(table_name: str) -> str:
    return (
        f"IF OBJECT_ID(N'dbo.{table_name}', N'U') IS NOT NULL "
        f"DROP TABLE dbo.{table_name}"
    )


def _drop(backend, table_name: str) -> None:
    backend.execute(_drop_sql(table_name))


def _create_table(dialect, table_name: str, *, generation=None, **identity_kwargs):
    attribute = IdentityAttribute(
        generation=generation or "BY DEFAULT", **identity_kwargs
    )
    return CreateTableExpression(
        dialect=dialect,
        table=Table(dialect, table_name),
        columns=[
            ColumnDefinition(
                dialect,
                "id",
                IntegerType(dialect),
                attributes=[attribute],
            ),
            ColumnDefinition(dialect, "v", TextType(dialect)),
        ],
    )


class TestSentinelSeesRejection:
    """Before any ACCEPTED verdict, prove the classifier can see a rejection."""

    def test_invalid_sql_is_classified_rejected(self, sqlserver_backend):
        assert (
            classify_execution(sqlserver_backend, "THIS IS NOT SQL")
            is ExecutionOutcome.REJECTED
        )

    def test_helper_raises_on_a_server_rejection(self, sqlserver_backend):
        """A rendered statement the server refuses must raise, not pass.

        The table is created once (ACCEPTED), then the identical statement is
        confirmed again: the server refuses it with "There is already an object
        named ...", and the helper must surface that as
        ``ExecutionConfirmationError`` rather than swallow it.
        """
        dialect = sqlserver_backend.dialect
        table_name = "ar_identity_sentinel"
        create = _create_table(dialect, table_name, start=100, increment=5)
        _drop(sqlserver_backend, table_name)
        try:
            outcome = confirm_expression_execution(sqlserver_backend, create)
            assert outcome is ExecutionOutcome.ACCEPTED
            with pytest.raises(ExecutionConfirmationError):
                confirm_expression_execution(sqlserver_backend, create)
        finally:
            _drop(sqlserver_backend, table_name)


class TestIdentityExecutes:
    """The dialect's identity spelling is accepted and its parameters take."""

    def test_bare_identity_executes(self, sqlserver_backend):
        dialect = sqlserver_backend.dialect
        table_name = "ar_identity_exec_bare"
        create = _create_table(dialect, table_name)
        sql, _ = create.to_sql()
        assert "IDENTITY(1, 1)" in sql
        _drop(sqlserver_backend, table_name)
        try:
            outcome = confirm_expression_execution(
                sqlserver_backend, create, teardown=[(_drop_sql(table_name), ())]
            )
            assert outcome is ExecutionOutcome.ACCEPTED
        finally:
            _drop(sqlserver_backend, table_name)

    def test_seed_and_increment_execute_and_take_effect(self, sqlserver_backend):
        """``IDENTITY(100, 5)`` is accepted *and* the server starts at 100.

        Acceptance alone would not distinguish the property's arguments from
        the defaults, so two rows are inserted and the generated ids are read
        back: they must be 100 and 105.
        """
        dialect = sqlserver_backend.dialect
        table_name = "ar_identity_exec_seed"
        create = _create_table(dialect, table_name, start=100, increment=5)
        sql, _ = create.to_sql()
        assert "IDENTITY(100, 5)" in sql
        _drop(sqlserver_backend, table_name)
        try:
            outcome = confirm_expression_execution(sqlserver_backend, create)
            assert outcome is ExecutionOutcome.ACCEPTED
            sqlserver_backend.execute(
                f"INSERT INTO dbo.{table_name} (v) VALUES (N'a'), (N'b')"
            )
            result = sqlserver_backend.execute(
                f"SELECT id FROM dbo.{table_name} ORDER BY id"
            )
            assert [row["id"] for row in result.data] == [100, 105]
        finally:
            _drop(sqlserver_backend, table_name)


class TestUnsupportedRequestsAreNotRendered:
    """A refused expression is NOT_RENDERED -- never REJECTED, never executed."""

    def test_always_request_is_not_rendered(self, sqlserver_backend):
        """The behaviour change: ALWAYS fails closed instead of degrading."""
        dialect = sqlserver_backend.dialect
        expr = _create_table(dialect, "ar_identity_exec_always", generation="ALWAYS")
        outcome = confirm_expression_execution(sqlserver_backend, expr)
        assert outcome is ExecutionOutcome.NOT_RENDERED
        with pytest.raises(UnsupportedFeatureError, match="IDENTITY GENERATED ALWAYS"):
            expr.to_sql()

    @pytest.mark.parametrize(
        "identity_kwargs,feature",
        [
            ({"minvalue": 1}, "IDENTITY MINVALUE"),
            ({"maxvalue": 100}, "IDENTITY MAXVALUE"),
            ({"cycle": True}, "IDENTITY CYCLE"),
            ({"cycle": False}, "IDENTITY CYCLE"),
        ],
        ids=["minvalue", "maxvalue", "cycle", "nocycle"],
    )
    def test_unspellable_option_is_not_rendered(
        self, sqlserver_backend, identity_kwargs, feature
    ):
        dialect = sqlserver_backend.dialect
        expr = _create_table(
            dialect, "ar_identity_exec_option", **identity_kwargs
        )
        outcome = confirm_expression_execution(sqlserver_backend, expr)
        assert outcome is ExecutionOutcome.NOT_RENDERED
        with pytest.raises(UnsupportedFeatureError, match=feature):
            expr.to_sql()

    def test_auto_increment_marker_is_not_rendered(self, sqlserver_backend):
        dialect = sqlserver_backend.dialect
        assert dialect.supports_auto_increment_column() is False
        outcome = confirm_expression_execution(
            sqlserver_backend, AutoIncrementClause(dialect)
        )
        assert outcome is ExecutionOutcome.NOT_RENDERED

    @pytest.mark.parametrize(
        "identity_kwargs,feature",
        [
            ({"order": True}, "IDENTITY ORDER"),
            ({"no_order": True}, "IDENTITY ORDER"),
            ({"cache": 10}, "IDENTITY CACHE"),
            ({"no_cache": True}, "IDENTITY CACHE"),
        ],
        ids=["order", "no-order", "cache", "no-cache"],
    )
    def test_order_and_cache_requests_are_not_rendered(
        self, sqlserver_backend, identity_kwargs, feature
    ):
        """ORDER / CACHE have no spelling in ``IDENTITY(seed, increment)``.

        The AR-layer ``IdentityAttribute`` does not carry these fields yet, so
        the request is built at the clause level -- the unit the formatter
        gates. The verdict is NOT_RENDERED: the dialect refuses before the
        server is ever asked, and the refusal names the option.
        """
        dialect = sqlserver_backend.dialect
        expr = IdentityClause(dialect, **identity_kwargs)
        outcome = confirm_expression_execution(sqlserver_backend, expr)
        assert outcome is ExecutionOutcome.NOT_RENDERED
        with pytest.raises(UnsupportedFeatureError, match=feature):
            expr.to_sql()


class TestServerRefusesTheStandardSpellings:
    """The declarations are measured, not assumed: the server's own answers.

    These raw statements are the candidates the dialect refuses to render. The
    server must refuse them too -- otherwise refusing them would be a false
    negative, and the corresponding probe would have to be ``True``.
    """

    @pytest.mark.parametrize(
        "table_name,statement",
        [
            (
                "ar_identity_std_always",
                "CREATE TABLE dbo.{name} (id INT GENERATED ALWAYS AS IDENTITY)",
            ),
            (
                "ar_identity_std_default",
                "CREATE TABLE dbo.{name} (id INT GENERATED BY DEFAULT AS IDENTITY)",
            ),
            (
                "ar_identity_std_minvalue",
                "CREATE TABLE dbo.{name} (id INT IDENTITY(1,1) MINVALUE 1)",
            ),
            (
                "ar_identity_std_maxvalue",
                "CREATE TABLE dbo.{name} (id INT IDENTITY(1,1) MAXVALUE 100)",
            ),
            (
                "ar_identity_std_cycle",
                "CREATE TABLE dbo.{name} (id INT IDENTITY(1,1) CYCLE)",
            ),
            (
                "ar_identity_std_order",
                "CREATE TABLE dbo.{name} (id INT IDENTITY(1,1) ORDER)",
            ),
            (
                "ar_identity_std_no_order",
                "CREATE TABLE dbo.{name} (id INT IDENTITY(1,1) NO ORDER)",
            ),
            (
                "ar_identity_std_cache",
                "CREATE TABLE dbo.{name} (id INT IDENTITY(1,1) CACHE 10)",
            ),
            (
                "ar_identity_std_no_cache",
                "CREATE TABLE dbo.{name} (id INT IDENTITY(1,1) NO CACHE)",
            ),
        ],
        ids=[
            "always",
            "by-default",
            "minvalue",
            "maxvalue",
            "cycle",
            "order",
            "no-order",
            "cache",
            "no-cache",
        ],
    )
    def test_standard_spelling_is_rejected(self, sqlserver_backend, table_name, statement):
        _drop(sqlserver_backend, table_name)
        try:
            assert (
                classify_execution(sqlserver_backend, statement.format(name=table_name))
                is ExecutionOutcome.REJECTED
            )
        finally:
            _drop(sqlserver_backend, table_name)
