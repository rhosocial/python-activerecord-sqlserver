# tests/rhosocial/activerecord_sqlserver_test/feature/backend/expression/test_pivot.py
"""Offline tests for SQL Server PIVOT / UNPIVOT formatting.

PIVOT and UNPIVOT have been available since SQL Server 2005. These tests
verify the dialect capability switches and the SQL rendering of both clauses
through SQLServerPivotExpression / SQLServerUnpivotExpression, with no
database connection required.
"""

import pytest

from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression.pivot import (
    SQLServerPivotExpression,
    SQLServerUnpivotExpression,
)


class TestSQLServerPivotSupport:
    """Test the PIVOT / UNPIVOT capability switches by server version."""

    def test_supports_pivot_2005(self):
        """Test that PIVOT is supported on SQL Server 2005 (9.0)."""
        dialect = SQLServerDialect(version=(9, 0, 0))
        assert dialect.supports_pivot() is True, (
            "SQL Server 2005 must support PIVOT"
        )

    def test_supports_pivot_2000(self):
        """Test that PIVOT is unavailable before SQL Server 2005."""
        dialect = SQLServerDialect(version=(8, 0, 0))
        assert dialect.supports_pivot() is False, (
            "SQL Server 2000 must not support PIVOT"
        )

    def test_supports_unpivot_2005(self):
        """Test that UNPIVOT is supported on SQL Server 2005 (9.0)."""
        dialect = SQLServerDialect(version=(9, 0, 0))
        assert dialect.supports_unpivot() is True, (
            "SQL Server 2005 must support UNPIVOT"
        )

    def test_supports_unpivot_2000(self):
        """Test that UNPIVOT is unavailable before SQL Server 2005."""
        dialect = SQLServerDialect(version=(8, 0, 0))
        assert dialect.supports_unpivot() is False, (
            "SQL Server 2000 must not support UNPIVOT"
        )


class TestSQLServerPivotFormatting:
    """Test the PIVOT clause formatting."""

    @pytest.fixture
    def dialect(self):
        """Provide a SQL Server 2016 dialect instance."""
        return SQLServerDialect(version=(13, 0, 0))

    def test_pivot_without_alias(self, dialect):
        """Test that PIVOT renders without an alias when omitted."""
        expr = SQLServerPivotExpression(
            dialect=dialect,
            aggregate_function="SUM",
            value_column="sales",
            pivot_column="quarter",
            values=["Q1", "Q2"],
        )
        sql, params = expr.to_sql()
        assert sql == (
            "PIVOT (SUM([sales]) FOR [quarter] IN (Q1, Q2))"
        ), "PIVOT must render the aggregate and pivot columns"
        assert params == (), "PIVOT values are rendered verbatim, no params"

    def test_pivot_with_alias(self, dialect):
        """Test that PIVOT appends the alias when provided."""
        expr = SQLServerPivotExpression(
            dialect=dialect,
            aggregate_function="COUNT",
            value_column="order_id",
            pivot_column="status",
            values=["SHIPPED", "PENDING"],
            alias="p",
        )
        sql, params = expr.to_sql()
        assert sql == (
            "PIVOT (COUNT([order_id]) FOR [status] IN (SHIPPED, PENDING)) [p]"
        ), "PIVOT must append the bracketed alias"
        assert params == (), "PIVOT values are rendered verbatim, no params"

    def test_pivot_numeric_values(self, dialect):
        """Test that numeric pivot values are rendered verbatim."""
        expr = SQLServerPivotExpression(
            dialect=dialect,
            aggregate_function="MAX",
            value_column="amount",
            pivot_column="year",
            values=[2021, 2022],
            alias="p",
        )
        sql, params = expr.to_sql()
        assert sql == (
            "PIVOT (MAX([amount]) FOR [year] IN (2021, 2022)) [p]"
        ), "numeric pivot values must be rendered without quotes"


class TestSQLServerUnpivotFormatting:
    """Test the UNPIVOT clause formatting."""

    @pytest.fixture
    def dialect(self):
        """Provide a SQL Server 2016 dialect instance."""
        return SQLServerDialect(version=(13, 0, 0))

    def test_unpivot_without_alias(self, dialect):
        """Test that UNPIVOT renders without an alias when omitted."""
        expr = SQLServerUnpivotExpression(
            dialect=dialect,
            value_column="val",
            pivot_column="col",
            columns=["a", "b"],
        )
        sql, params = expr.to_sql()
        assert sql == "UNPIVOT ([val] FOR [col] IN ([a], [b]))", (
            "UNPIVOT must render the value, pivot, and column list"
        )
        assert params == (), "UNPIVOT columns are identifiers, no params"

    def test_unpivot_with_alias(self, dialect):
        """Test that UNPIVOT appends the alias when provided."""
        expr = SQLServerUnpivotExpression(
            dialect=dialect,
            value_column="val",
            pivot_column="col",
            columns=["q1", "q2", "q3"],
            alias="u",
        )
        sql, params = expr.to_sql()
        assert sql == (
            "UNPIVOT ([val] FOR [col] IN ([q1], [q2], [q3])) [u]"
        ), "UNPIVOT must append the bracketed alias"
        assert params == (), "UNPIVOT columns are identifiers, no params"

    def test_unpivot_multiple_columns(self, dialect):
        """Test that multiple UNPIVOT columns are comma-separated."""
        expr = SQLServerUnpivotExpression(
            dialect=dialect,
            value_column="amount",
            pivot_column="region",
            columns=["east", "west", "north", "south"],
            alias="u",
        )
        sql, params = expr.to_sql()
        assert sql == (
            "UNPIVOT ([amount] FOR [region] IN ([east], [west], [north], [south])) [u]"
        ), "multiple columns must be joined with ', '"