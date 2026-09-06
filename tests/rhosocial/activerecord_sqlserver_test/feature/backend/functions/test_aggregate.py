# tests/rhosocial/activerecord_sqlserver_test/feature/backend/functions/test_aggregate.py
"""Offline tests for SQL Server aggregate function factories.

The aggregate module provides ``max_``, ``min_``, and ``avg`` factories plus
the ``_convert_to_expression`` helper that turns raw inputs into
BaseExpression instances (passing expressions through, numeric literals into
Literal, and everything else into Column). SQL is rendered directly by
SQLServerDialect with no database connection.
"""

import pytest

from rhosocial.activerecord.backend.expression import bases, core
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.functions import aggregate


class TestConvertToExpression:
    """Test the _convert_to_expression helper."""

    @pytest.fixture
    def dialect(self):
        """Provide a SQL Server dialect instance."""
        return SQLServerDialect(version=(16, 0, 0))

    def test_expression_passthrough(self, dialect):
        """Test that a BaseExpression is returned unchanged."""
        column = core.Column(dialect, "price")
        result = aggregate._convert_to_expression(dialect, column)
        assert result is column, "an existing BaseExpression must be reused"

    def test_int_literal_converted(self, dialect):
        """Test that an integer becomes a Literal expression."""
        result = aggregate._convert_to_expression(dialect, 10)
        assert isinstance(result, core.Literal), (
            "a numeric literal must be wrapped in Literal"
        )
        sql, params = result.to_sql()
        assert sql == "?", "a literal must render as a placeholder"
        assert params == (10,), "the literal value must be bound as a parameter"

    def test_float_literal_converted(self, dialect):
        """Test that a float becomes a Literal expression."""
        result = aggregate._convert_to_expression(dialect, 10.5)
        assert isinstance(result, core.Literal), (
            "a numeric literal must be wrapped in Literal"
        )

    def test_string_becomes_column(self, dialect):
        """Test that a string becomes a Column expression."""
        result = aggregate._convert_to_expression(dialect, "price")
        assert isinstance(result, core.Column), (
            "a plain string must be wrapped in Column"
        )
        assert result.name == "price", "the column name must be preserved"

    def test_numeric_handling_disabled_uses_column(self, dialect):
        """Test that handle_numeric_literals=False wraps numbers as Column."""
        result = aggregate._convert_to_expression(
            dialect, 10, handle_numeric_literals=False
        )
        assert isinstance(result, core.Column), (
            "with numeric literals disabled a number must become a Column"
        )

    def test_other_types_become_column(self, dialect):
        """Test that non-numeric, non-expression values become Column."""
        result = aggregate._convert_to_expression(dialect, "price")
        assert isinstance(result, bases.BaseExpression), (
            "the result must always be a BaseExpression"
        )


class TestAggregateFunctionFactories:
    """Test the max_, min_, and avg function factories."""

    @pytest.fixture
    def dialect(self):
        """Provide a SQL Server dialect instance."""
        return SQLServerDialect(version=(16, 0, 0))

    def test_max_with_column(self, dialect):
        """Test that max_ with a column renders MAX([column])."""
        result = aggregate.max_(dialect, "price")
        assert isinstance(result, core.FunctionCall), (
            "max_ must return a FunctionCall"
        )
        sql, params = result.to_sql()
        assert sql == "MAX([price])", "max_ must render the MAX function call"
        assert params == (), "a column argument must produce no parameters"

    def test_max_with_literal(self, dialect):
        """Test that max_ with a numeric literal binds it as a parameter."""
        result = aggregate.max_(dialect, 42)
        sql, params = result.to_sql()
        assert sql == "MAX(?)", "a literal argument must render as a placeholder"
        assert params == (42,), "the literal value must be bound"

    def test_min_with_column(self, dialect):
        """Test that min_ with a column renders MIN([column])."""
        result = aggregate.min_(dialect, "price")
        assert isinstance(result, core.FunctionCall), (
            "min_ must return a FunctionCall"
        )
        sql, params = result.to_sql()
        assert sql == "MIN([price])", "min_ must render the MIN function call"
        assert params == (), "a column argument must produce no parameters"

    def test_avg_with_column(self, dialect):
        """Test that avg with a column renders AVG([column])."""
        result = aggregate.avg(dialect, "price")
        assert isinstance(result, core.FunctionCall), (
            "avg must return a FunctionCall"
        )
        sql, params = result.to_sql()
        assert sql == "AVG([price])", "avg must render the AVG function call"
        assert params == (), "a column argument must produce no parameters"

    def test_avg_with_literal(self, dialect):
        """Test that avg with a numeric literal binds it as a parameter."""
        result = aggregate.avg(dialect, 12.5)
        sql, params = result.to_sql()
        assert sql == "AVG(?)", "a literal argument must render as a placeholder"
        assert params == (12.5,), "the literal value must be bound"

    def test_factories_accept_expression(self, dialect):
        """Test that the factories accept an existing BaseExpression."""
        column = core.Column(dialect, "price")
        result = aggregate.max_(dialect, column)
        sql, params = result.to_sql()
        assert sql == "MAX([price])", (
            "an existing expression must be passed through unchanged"
        )

    def test_factories_exported_from_functions_package(self):
        """Test that the factories are exported from the functions package."""
        from rhosocial.activerecord.backend.impl.sqlserver import functions

        assert functions.max_ is aggregate.max_, (
            "the package must export the max_ factory"
        )
        assert functions.min_ is aggregate.min_, (
            "the package must export the min_ factory"
        )
        assert functions.avg is aggregate.avg, "the package must export avg"