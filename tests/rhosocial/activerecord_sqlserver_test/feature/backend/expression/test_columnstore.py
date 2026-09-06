# tests/rhosocial/activerecord_sqlserver_test/feature/backend/expression/test_columnstore.py
"""Offline tests for SQL Server columnstore index DDL.

Tests the SQLServerColumnstoreIndexExpression validation rules and the
dialect's version-gated formatter (NONCLUSTERED 2012+, CLUSTERED 2014+,
ORDER (...) 2022+). SQL is rendered directly by SQLServerDialect with no
database connection.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression.columnstore import (
    SQLServerColumnstoreIndexExpression,
)


class TestSQLServerColumnstoreIndexExpressionInit:
    """Test construction and attribute storage of the columnstore expression."""

    @pytest.fixture
    def dialect(self):
        """Provide a SQL Server 2022 dialect instance."""
        return SQLServerDialect(version=(16, 0, 0))

    def test_init_stores_attributes(self, dialect):
        """Test that constructor arguments are stored on the instance."""
        expr = SQLServerColumnstoreIndexExpression(
            dialect=dialect,
            index="cci",
            table="orders",
            columns=["c1", "c2"],
            clustered=True,
            order_columns=["o1"],
        )
        assert expr.index == "cci", "the index name must be preserved"
        assert expr.table == "orders", "the table name must be preserved"
        assert expr.columns == ["c1", "c2"], "the columns must be stored as a list"
        assert expr.clustered is True, "the clustered flag must be preserved"
        assert expr.order_columns == ["o1"], "the order columns must be stored"

    def test_init_defaults(self, dialect):
        """Test that columns, order_columns, and clustered have defaults."""
        expr = SQLServerColumnstoreIndexExpression(
            dialect=dialect, index="cci", table="orders"
        )
        assert expr.columns == [], "columns must default to an empty list"
        assert expr.order_columns == [], "order columns must default to empty"
        assert expr.clustered is None, "clustered must default to None"


class TestSQLServerColumnstoreIndexExpressionValidate:
    """Test validation rules of the columnstore expression."""

    @pytest.fixture
    def dialect(self):
        """Provide a SQL Server 2022 dialect instance."""
        return SQLServerDialect(version=(16, 0, 0))

    def test_validate_accepts_clustered_without_columns(self, dialect):
        """Test that a clustered index without key columns is valid."""
        expr = SQLServerColumnstoreIndexExpression(
            dialect=dialect, index="cci", table="orders", clustered=True
        )
        expr.validate(strict=True)

    def test_validate_rejects_nonclustered_without_columns(self, dialect):
        """Test that a NONCLUSTERED index requires key columns."""
        expr = SQLServerColumnstoreIndexExpression(
            dialect=dialect,
            index="ncci",
            table="orders",
            clustered=False,
        )
        with pytest.raises(ValueError) as excinfo:
            expr.validate(strict=True)
        assert "requires key columns" in str(excinfo.value), (
            "NONCLUSTERED columnstore must require key columns"
        )

    def test_validate_rejects_clustered_with_columns(self, dialect):
        """Test that a clustered index forbids key columns."""
        expr = SQLServerColumnstoreIndexExpression(
            dialect=dialect,
            index="cci",
            table="orders",
            clustered=True,
            columns=["c1"],
        )
        with pytest.raises(ValueError) as excinfo:
            expr.validate(strict=True)
        assert "does not allow key columns" in str(excinfo.value), (
            "clustered columnstore must reject key columns"
        )

    def test_validate_rejects_order_with_nonclustered(self, dialect):
        """Test that ORDER (...) is rejected for NONCLUSTERED indexes."""
        expr = SQLServerColumnstoreIndexExpression(
            dialect=dialect,
            index="ncci",
            table="orders",
            clustered=False,
            columns=["c1"],
            order_columns=["c1"],
        )
        with pytest.raises(ValueError) as excinfo:
            expr.validate(strict=True)
        assert "only valid for clustered" in str(excinfo.value), (
            "ORDER (...) must be rejected for NONCLUSTERED indexes"
        )

    def test_validate_non_strict_skips_rules(self, dialect):
        """Test that non-strict validation skips all rule checks."""
        expr = SQLServerColumnstoreIndexExpression(
            dialect=dialect,
            index="ncci",
            table="orders",
            clustered=False,
        )
        expr.validate(strict=False)


class TestSQLServerColumnstoreDialectSupport:
    """Test the columnstore capability switches by server version."""

    def test_supports_nonclustered_columnstore_2012(self):
        """Test that NONCLUSTERED columnstore is supported on 2012 (11.0)."""
        dialect = SQLServerDialect(version=(11, 0, 0))
        assert dialect.supports_nonclustered_columnstore() is True, (
            "SQL Server 2012 must support NONCLUSTERED columnstore"
        )

    def test_supports_nonclustered_columnstore_2008(self):
        """Test that NONCLUSTERED columnstore is unavailable before 2012."""
        dialect = SQLServerDialect(version=(10, 0, 0))
        assert dialect.supports_nonclustered_columnstore() is False, (
            "SQL Server 2008 must not support NONCLUSTERED columnstore"
        )

    def test_supports_clustered_columnstore_2014(self):
        """Test that CLUSTERED columnstore is supported on 2014 (12.0)."""
        dialect = SQLServerDialect(version=(12, 0, 0))
        assert dialect.supports_clustered_columnstore() is True, (
            "SQL Server 2014 must support CLUSTERED columnstore"
        )

    def test_supports_clustered_columnstore_2012(self):
        """Test that CLUSTERED columnstore is unavailable on 2012."""
        dialect = SQLServerDialect(version=(11, 0, 0))
        assert dialect.supports_clustered_columnstore() is False, (
            "SQL Server 2012 must not support CLUSTERED columnstore"
        )

    def test_supports_columnstore_order_2022(self):
        """Test that ORDER (...) is supported on 2022 (16.0)."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        assert dialect.supports_columnstore_order() is True, (
            "SQL Server 2022 must support ordered columnstore"
        )

    def test_supports_columnstore_order_2019(self):
        """Test that ORDER (...) is unavailable before 2022."""
        dialect = SQLServerDialect(version=(15, 0, 0))
        assert dialect.supports_columnstore_order() is False, (
            "SQL Server 2019 must not support ordered columnstore"
        )


class TestSQLServerColumnstoreFormatting:
    """Test the CREATE COLUMNSTORE INDEX statement formatting."""

    def test_clustered_true_renders_clustered(self):
        """Test that clustered=True renders the CLUSTERED keyword (2014+)."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        expr = SQLServerColumnstoreIndexExpression(
            dialect=dialect, index="cci", table="orders", clustered=True
        )
        sql, params = expr.to_sql()
        assert sql == "CREATE CLUSTERED COLUMNSTORE INDEX [cci] ON [orders]", (
            "clustered=True must render the CLUSTERED keyword"
        )
        assert params == (), "no parameters are expected for DDL"

    def test_clustered_none_omits_keyword(self):
        """Test that clustered=None omits the CLUSTERED/NONCLUSTERED keyword."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        expr = SQLServerColumnstoreIndexExpression(
            dialect=dialect, index="cci", table="orders"
        )
        sql, params = expr.to_sql()
        assert sql == "CREATE COLUMNSTORE INDEX [cci] ON [orders]", (
            "clustered=None must omit the CLUSTERED/NONCLUSTERED keyword"
        )

    def test_clustered_true_rejected_before_2014(self):
        """Test that CLUSTERED columnstore raises before SQL Server 2014."""
        dialect = SQLServerDialect(version=(11, 0, 0))
        expr = SQLServerColumnstoreIndexExpression(
            dialect=dialect, index="cci", table="orders", clustered=True
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_nonclustered_renders_with_columns(self):
        """Test that clustered=False renders NONCLUSTERED with key columns."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        expr = SQLServerColumnstoreIndexExpression(
            dialect=dialect,
            index="ncci",
            table="orders",
            columns=["customer_id", "order_date"],
            clustered=False,
        )
        sql, params = expr.to_sql()
        assert sql == (
            "CREATE NONCLUSTERED COLUMNSTORE INDEX [ncci] ON [orders] "
            "([customer_id], [order_date])"
        ), "NONCLUSTERED must render key columns in parentheses"

    def test_nonclustered_rejected_before_2012(self):
        """Test that NONCLUSTERED columnstore raises before SQL Server 2012."""
        dialect = SQLServerDialect(version=(10, 0, 0))
        expr = SQLServerColumnstoreIndexExpression(
            dialect=dialect,
            index="ncci",
            table="orders",
            columns=["customer_id"],
            clustered=False,
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_order_columns_rendered_on_2022(self):
        """Test that ORDER (...) is rendered for ordered columnstore (2022+)."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        expr = SQLServerColumnstoreIndexExpression(
            dialect=dialect,
            index="cci",
            table="orders",
            clustered=True,
            order_columns=["order_date", "customer_id"],
        )
        sql, params = expr.to_sql()
        assert sql == (
            "CREATE CLUSTERED COLUMNSTORE INDEX [cci] ON [orders] "
            "ORDER ([order_date], [customer_id])"
        ), "ORDER (...) must list the order columns in parentheses"

    def test_order_columns_rejected_before_2022(self):
        """Test that ORDER (...) raises before SQL Server 2022."""
        dialect = SQLServerDialect(version=(15, 0, 0))
        expr = SQLServerColumnstoreIndexExpression(
            dialect=dialect,
            index="cci",
            table="orders",
            clustered=True,
            order_columns=["order_date"],
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_to_sql_delegates_to_formatter(self):
        """Test that the expression delegates SQL generation to the dialect."""
        dialect = SQLServerDialect(version=(16, 0, 0))
        expr = SQLServerColumnstoreIndexExpression(
            dialect=dialect, index="cci", table="orders", clustered=True
        )
        sql, params = expr.to_sql()
        expected, expected_params = dialect.format_create_columnstore_index_statement(expr)
        assert sql == expected, "to_sql must delegate to the dialect formatter"
        assert params == expected_params, "params must match the formatter output"