import pytest
import pytest_asyncio

from rhosocial.activerecord.backend.explain import SyncExplainBackendProtocol
from rhosocial.activerecord.backend.expression import (
    QueryExpression, TableExpression, Column, WildcardExpression, Literal, WhereClause,
)

from rhosocial.activerecord.backend.impl.sqlserver.explain import SQLServerExplainResult, SQLServerExplainRow


class TestExplainProtocol:
    def test_sync_backend_implements_protocol(self, sqlserver_backend_single):
        assert isinstance(sqlserver_backend_single, SyncExplainBackendProtocol)


class TestSyncExplainResultParsing:
    """Test _parse_explain_result directly without executing explain().

    SQL Server requires SET SHOWPLAN_TEXT ON to be the only statement in a
    batch, which the current generic explain() flow cannot guarantee.
    We therefore test the result-parsing hook in isolation.
    """

    def test_parse_result_returns_sqlserver_explain_result(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        raw_rows = [
            {"execute_count": 1, "rows": 0, "stmt_text": "SELECT * FROM t",
             "estimate_rows": 100.0, "estimate_io": 0.5, "estimate_cpu": 0.1,
             "total_subtree_cost": 1.5, "avg_row_size": 100, "warnings": None}
        ]
        result = backend._parse_explain_result(raw_rows, "SELECT * FROM t", 0.05)
        assert isinstance(result, SQLServerExplainResult)

    def test_parse_result_rows_type(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        raw_rows = [
            {"execute_count": 1, "rows": 0, "stmt_text": "SELECT * FROM t",
             "estimate_rows": 100.0, "estimate_io": 0.5, "estimate_cpu": 0.1,
             "total_subtree_cost": 1.5, "avg_row_size": 100, "warnings": None}
        ]
        result = backend._parse_explain_result(raw_rows, "SELECT * FROM t", 0.05)
        for row in result.rows:
            assert isinstance(row, SQLServerExplainRow)

    def test_parse_result_has_expected_attributes(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        raw_rows = [
            {"execute_count": 1, "rows": 0, "stmt_text": "SELECT * FROM t",
             "estimate_rows": 100.0, "estimate_io": 0.5, "estimate_cpu": 0.1,
             "total_subtree_cost": 1.5, "avg_row_size": 100, "warnings": None}
        ]
        result = backend._parse_explain_result(raw_rows, "SELECT * FROM t", 0.05)
        summary = result.get_summary()
        assert "total_cost" in summary
        assert "total_rows" in summary
        assert "row_count" in summary
        assert "has_warnings" in summary
        assert "duration" in summary
        assert summary["total_cost"] > 0

    def test_parse_result_get_operations(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        raw_rows = [
            {"execute_count": 1, "rows": 0, "stmt_text": "SELECT",
             "estimate_rows": 100.0, "estimate_io": 0.5, "estimate_cpu": 0.1,
             "total_subtree_cost": 1.5, "avg_row_size": 100, "warnings": None}
        ]
        result = backend._parse_explain_result(raw_rows, "SELECT * FROM t", 0.05)
        operations = result.get_operations()
        assert isinstance(operations, list)

    def test_parse_result_missing_indexes(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        raw_rows = [
            {"execute_count": 1, "rows": 0, "stmt_text": "SELECT",
             "estimate_rows": 100.0, "estimate_io": 0.5, "estimate_cpu": 0.1,
             "total_subtree_cost": 1.5, "avg_row_size": 100, "warnings": None}
        ]
        result = backend._parse_explain_result(raw_rows, "SELECT * FROM t", 0.05)
        assert isinstance(result.raw_rows, list)
        assert len(result.raw_rows) == len(result.rows)


class TestSyncExplainBuildSQL:
    """Test SQL construction for EXPLAIN statements."""

    def test_build_explain_sql_structure(self, sqlserver_backend_single):
        backend = sqlserver_backend_single
        dialect = backend.dialect
        expr = QueryExpression(
            dialect,
            select=[WildcardExpression(dialect)],
            from_=TableExpression(dialect, "t")
        )
        sql, params = backend._build_explain_sql(expr)
        assert isinstance(sql, str)
        assert isinstance(params, tuple)
        assert len(sql) > 0
        assert "SHOWPLAN" in sql or "SET " in sql
