# src/rhosocial/activerecord/backend/impl/sqlserver/dialect.py
"""
SQL Server backend SQL dialect implementation.

This dialect implements protocols for features that SQL Server actually supports,
based on the SQL Server version provided at initialization.
"""

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING, Union

from rhosocial.activerecord.backend.dialect.base import SQLDialectBase
from rhosocial.activerecord.backend.dialect.protocols import (
    CTESupport,
    FilterClauseSupport,
    WindowFunctionSupport,
    JSONSupport,
    ReturningSupport,
    AdvancedGroupingSupport,
    ArraySupport,
    ExplainSupport,
    GraphSupport,
    LockingSupport,
    MergeSupport,
    OrderedSetAggregationSupport,
    QualifyClauseSupport,
    TemporalTableSupport,
    UpsertSupport,
    LateralJoinSupport,
    WildcardSupport,
    JoinSupport,
    ViewSupport,
    SetOperationSupport,
    TruncateSupport,
    SchemaSupport,
    IndexSupport,
    SequenceSupport,
    TableSupport,
    ConstraintSupport,
    IntrospectionSupport,
    TransactionControlSupport,
    SQLFunctionSupport,
)
from rhosocial.activerecord.backend.dialect.mixins import (
    CTEMixin,
    FilterClauseMixin,
    WindowFunctionMixin,
    JSONMixin,
    ReturningMixin,
    AdvancedGroupingMixin,
    ArrayMixin,
    ExplainMixin,
    GraphMixin,
    LockingMixin,
    MergeMixin,
    OrderedSetAggregationMixin,
    QualifyClauseMixin,
    TemporalTableMixin,
    UpsertMixin,
    LateralJoinMixin,
    JoinMixin,
    ViewMixin,
    SetOperationMixin,
    TruncateMixin,
    SchemaMixin,
    IndexMixin,
    SequenceMixin,
    TableMixin,
    ConstraintMixin,
    IntrospectionMixin,
)
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression import bases
    from rhosocial.activerecord.backend.expression.advanced_functions import ArrayExpression, OrderedSetAggregation
    from rhosocial.activerecord.backend.expression.graph import MatchClause
    from rhosocial.activerecord.backend.expression.query_parts import (
        OrderByClause,
        LimitOffsetClause,
        ForUpdateClause,
        QualifyClause,
    )
    from rhosocial.activerecord.backend.expression.statements import (
        ExplainExpression,
        CreateViewExpression,
        DropViewExpression,
        CreateMaterializedViewExpression,
        DropMaterializedViewExpression,
        RefreshMaterializedViewExpression,
        ReturningClause,
        InsertExpression,
        ColumnDefinition,
        TableConstraint,
        IndexDefinition,
    )
    from rhosocial.activerecord.backend.expression.transaction import (
        BeginTransactionExpression,
        SetTransactionExpression,
    )


SQL_SERVER_2012 = (11, 0, 0)
SQL_SERVER_2014 = (12, 0, 0)
SQL_SERVER_2016 = (13, 0, 0)
SQL_SERVER_2017 = (14, 0, 0)
SQL_SERVER_2019 = (15, 0, 0)
SQL_SERVER_2022 = (16, 0, 0)


_SUGGESTION_ARRAY_TYPES = "SQL Server does not support native array types. Consider using JSON or comma-separated values."
_SUGGESTION_JSON_TABLE = "SQL Server uses OPENJSON for JSON table functionality (2016+)."
_SUGGESTION_GRAPH_MATCH = "SQL Server does not support graph MATCH clause."
_SUGGESTION_ORDERED_SET_AGG = "SQL Server does not support ordered-set aggregate functions (WITHIN GROUP)."
_SUGGESTION_QUALIFY = "SQL Server does not support QUALIFY clause. Use a subquery or CTE instead."
_SUGGESTION_MATERIALIZED_VIEW = "SQL Server does not support materialized views. Consider using indexed views."
_SUGGESTION_LATERAL = "SQL Server uses CROSS APPLY or OUTER APPLY instead of LATERAL."


class SQLServerDialect(
    SQLDialectBase,
    CTEMixin,
    WindowFunctionMixin,
    JSONMixin,
    ReturningMixin,
    AdvancedGroupingMixin,
    ArrayMixin,
    ExplainMixin,
    GraphMixin,
    LockingMixin,
    MergeMixin,
    OrderedSetAggregationMixin,
    QualifyClauseMixin,
    TemporalTableMixin,
    UpsertMixin,
    LateralJoinMixin,
    JoinMixin,
    ViewMixin,
    SetOperationMixin,
    TruncateMixin,
    SchemaMixin,
    IndexMixin,
    SequenceMixin,
    TableMixin,
    ConstraintMixin,
    IntrospectionMixin,
    CTESupport,
    FilterClauseSupport,
    WindowFunctionSupport,
    JSONSupport,
    ReturningSupport,
    AdvancedGroupingSupport,
    ArraySupport,
    ExplainSupport,
    GraphSupport,
    LockingSupport,
    MergeSupport,
    OrderedSetAggregationSupport,
    QualifyClauseSupport,
    TemporalTableSupport,
    UpsertSupport,
    LateralJoinSupport,
    WildcardSupport,
    JoinSupport,
    ViewSupport,
    SetOperationSupport,
    TruncateSupport,
    SchemaSupport,
    IndexSupport,
    SequenceSupport,
    TableSupport,
    ConstraintSupport,
    IntrospectionSupport,
    TransactionControlSupport,
    SQLFunctionSupport,
):
    """
    SQL Server dialect implementation that adapts to the SQL Server version.
    
    SQL Server features and support based on version:
    - CTEs: All versions (recursive since 2008)
    - Window functions: All versions (enhanced in 2012)
    - MERGE statement: All versions (2008+)
    - JSON functions: SQL Server 2016+
    - STRING_AGG: SQL Server 2017+
    - OFFSET FETCH pagination: SQL Server 2012+
    - TRY_CAST/TRY_CONVERT: SQL Server 2012+
    - SEQUENCE objects: SQL Server 2012+
    """
    
    name = "SQL Server"
    
    _SQLSERVER_FUNCTION_VERSIONS = {
        "json_value": (SQL_SERVER_2016, None),
        "json_query": (SQL_SERVER_2016, None),
        "json_modify": (SQL_SERVER_2016, None),
        "isjson": (SQL_SERVER_2016, None),
        "openjson": (SQL_SERVER_2016, None),
        "string_agg": (SQL_SERVER_2017, None),
        "string_split": (SQL_SERVER_2016, None),
        "concat_ws": (SQL_SERVER_2017, None),
        "trim": (SQL_SERVER_2017, None),
        "iif": (SQL_SERVER_2012, None),
        "choose": (SQL_SERVER_2012, None),
        "try_cast": (SQL_SERVER_2012, None),
        "try_convert": (SQL_SERVER_2012, None),
        "try_parse": (SQL_SERVER_2012, None),
        "eomonth": (SQL_SERVER_2012, None),
        "datefromparts": (SQL_SERVER_2012, None),
        "datetime2fromparts": (SQL_SERVER_2012, None),
        "datetimeoffsetfromparts": (SQL_SERVER_2012, None),
        "timefromparts": (SQL_SERVER_2012, None),
        "datediff_big": (SQL_SERVER_2016, None),
        "approx_count_distinct": (SQL_SERVER_2019, None),
        "json_path_exists": (SQL_SERVER_2022, None),
        "json_object": (SQL_SERVER_2022, None),
        "json_array": (SQL_SERVER_2022, None),
    }
    
    def __init__(self, version: Tuple[int, int, int] = (16, 0, 0)):
        """
        Initialize SQL Server dialect with specific version.
        
        Args:
            version: SQL Server version tuple (major, minor, patch)
        """
        self.version = version
        super().__init__()
    
    def get_parameter_placeholder(self, position: int = 0) -> str:
        """SQL Server uses ? for placeholders (ODBC/qmark style)."""
        return "?"
    
    def get_server_version(self) -> Tuple[int, int, int]:
        """Return the SQL Server version this dialect is configured for."""
        return self.version
    
    def format_identifier(self, identifier: str) -> str:
        """
        Format identifier using SQL Server's brackets.
        
        SQL Server uses square brackets [] for identifiers, escaping
        internal brackets by doubling them.
        
        Args:
            identifier: Raw identifier string
        
        Returns:
            Quoted identifier with escaped internal brackets
        """
        escaped = identifier.replace("]", "]]")
        return f"[{escaped}]"
    
    def supports_basic_cte(self) -> bool:
        """Basic CTEs are supported in all modern SQL Server versions."""
        return True
    
    def supports_recursive_cte(self) -> bool:
        """Recursive CTEs are supported since SQL Server 2005."""
        return True
    
    def supports_materialized_cte(self) -> bool:
        """SQL Server doesn't support MATERIALIZED hint for CTEs."""
        return False
    
    def supports_returning_clause(self) -> bool:
        """SQL Server supports OUTPUT clause (similar to RETURNING)."""
        return True
    
    def supports_window_functions(self) -> bool:
        """Window functions are supported since SQL Server 2005."""
        return True
    
    def supports_window_frame_clause(self) -> bool:
        """Window frame clauses are supported since SQL Server 2012."""
        return self.version >= SQL_SERVER_2012
    
    def supports_filter_clause(self) -> bool:
        """FILTER clause for aggregate functions is not supported in SQL Server."""
        return False
    
    def supports_json_type(self) -> bool:
        """JSON functions are supported since SQL Server 2016."""
        return self.version >= SQL_SERVER_2016
    
    def get_json_access_operator(self) -> Optional[str]:
        """SQL Server doesn't have -> operator, uses JSON_VALUE/JSON_QUERY."""
        return None
    
    def supports_json_table(self) -> bool:
        """OPENJSON provides JSON table functionality since SQL Server 2016."""
        return self.version >= SQL_SERVER_2016
    
    def supports_rollup(self) -> bool:
        """ROLLUP is supported using WITH ROLLUP syntax."""
        return True
    
    def supports_cube(self) -> bool:
        """CUBE is supported using WITH CUBE syntax."""
        return True
    
    def supports_grouping_sets(self) -> bool:
        """GROUPING SETS is supported since SQL Server 2008."""
        return True
    
    def supports_array_type(self) -> bool:
        """SQL Server does not have native array types."""
        return False
    
    def supports_array_constructor(self) -> bool:
        """SQL Server does not have ARRAY constructor."""
        return False
    
    def supports_array_access(self) -> bool:
        """SQL Server does not support array subscript access."""
        return False
    
    def supports_graph_match(self) -> bool:
        """SQL Server does not support graph MATCH clause."""
        return False
    
    def supports_for_update(self) -> bool:
        """SQL Server supports FOR UPDATE via table hints."""
        return True
    
    def supports_for_update_skip_locked(self) -> bool:
        """SQL Server 2019+ supports READPAST with UPDLOCK."""
        return self.version >= SQL_SERVER_2019
    
    def supports_merge_statement(self) -> bool:
        """SQL Server has native MERGE support since 2008."""
        return True
    
    def supports_temporal_tables(self) -> bool:
        """SQL Server 2016+ supports temporal tables."""
        return self.version >= SQL_SERVER_2016
    
    def supports_qualify_clause(self) -> bool:
        """SQL Server does not have QUALIFY clause."""
        return False
    
    def supports_upsert(self) -> bool:
        """SQL Server uses MERGE for upsert operations."""
        return True
    
    def get_upsert_syntax_type(self) -> str:
        """Return 'MERGE' for SQL Server."""
        return "MERGE"
    
    def supports_lateral_join(self) -> bool:
        """SQL Server uses CROSS APPLY/OUTER APPLY instead of LATERAL."""
        return True
    
    def supports_ordered_set_aggregation(self) -> bool:
        """SQL Server does not support WITHIN GROUP (ORDER BY ...) syntax."""
        return False
    
    def supports_explain_analyze(self) -> bool:
        """SQL Server uses STATISTICS PROFILE for actual execution."""
        return True
    
    def supports_explain_format(self, format_type: str) -> bool:
        """Check if specific EXPLAIN format is supported."""
        return format_type.upper() in ["XML", "TEXT"]
    
    def format_explain_statement(self, explain_expr: "ExplainExpression") -> Tuple[str, tuple]:
        """
        Format EXPLAIN for SQL Server.
        
        SQL Server uses:
        - SET SHOWPLAN_XML ON (estimated plan)
        - SET STATISTICS PROFILE ON (actual plan with statistics)
        - SET STATISTICS XML ON (actual plan in XML)
        """
        statement_sql, statement_params = explain_expr.statement.to_sql()
        options = explain_expr.options
        
        if options is None:
            return f"SET SHOWPLAN_TEXT ON; {statement_sql}", statement_params
        
        if options.analyze:
            if options.format and options.format.name == "XML":
                return f"SET STATISTICS XML ON; {statement_sql}; SET STATISTICS XML OFF", statement_params
            return f"SET STATISTICS PROFILE ON; {statement_sql}; SET STATISTICS PROFILE OFF", statement_params
        
        if options.format and options.format.name == "XML":
            return f"SET SHOWPLAN_XML ON; {statement_sql}", statement_params
        
        return f"SET SHOWPLAN_TEXT ON; {statement_sql}", statement_params
    
    def format_limit_offset(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> Tuple[Optional[str], List[Any]]:
        """
        Format LIMIT/OFFSET as OFFSET FETCH for SQL Server 2012+.
        
        SQL Server 2012+ uses OFFSET FETCH syntax for pagination.
        Note: ORDER BY is required when using OFFSET FETCH.
        """
        if limit is None and offset is None:
            return None, []
        
        if self.version < SQL_SERVER_2012:
            raise UnsupportedFeatureError(
                self.name,
                "OFFSET FETCH pagination",
                "SQL Server 2012+ required for OFFSET FETCH. Use ROW_NUMBER() for older versions."
            )
        
        sql_parts = []
        params = []
        
        offset_val = offset or 0
        sql_parts.append(f"OFFSET {offset_val} ROWS")
        
        if limit is not None:
            sql_parts.append(f"FETCH NEXT {limit} ROWS ONLY")
        
        return " ".join(sql_parts), params
    
    def format_returning_clause(self, clause: "ReturningClause") -> Tuple[str, tuple]:
        """
        Format RETURNING as OUTPUT clause for SQL Server.
        
        SQL Server OUTPUT syntax:
        - INSERT: OUTPUT inserted.column, inserted.column2
        - UPDATE: OUTPUT deleted.old_column, inserted.new_column
        - DELETE: OUTPUT deleted.column
        """
        all_params = []
        expr_parts = []
        
        for expr in clause.expressions:
            expr_sql, expr_params = expr.to_sql()
            expr_parts.append(expr_sql)
            all_params.extend(expr_params)
        
        output_sql = f"OUTPUT {', '.join(expr_parts)}"
        
        if clause.alias:
            output_sql += f" AS {self.format_identifier(clause.alias)}"
        
        return output_sql, tuple(all_params)
    
    def format_insert_statement(self, expr: "InsertExpression") -> Tuple[str, tuple]:
        """
        Format INSERT statement with SQL Server-specific options.
        
        SQL Server supports:
        - OUTPUT clause for returning inserted rows
        - INSERT TOP (n) for limiting rows
        - DEFAULT VALUES
        """
        if self.strict_validation:
            expr.validate(strict=True)
        
        all_params: List[Any] = []
        
        table_sql, table_params = expr.into.to_sql()
        all_params.extend(table_params)
        
        parts = ["INSERT INTO", table_sql]
        
        if expr.columns:
            columns_sql = "(" + ", ".join([self.format_identifier(c) for c in expr.columns]) + ")"
            parts.append(columns_sql)
        
        from rhosocial.activerecord.backend.expression.statements import (
            DefaultValuesSource,
            ValuesSource,
            SelectSource,
        )
        
        if isinstance(expr.source, DefaultValuesSource):
            parts.append("DEFAULT VALUES")
        elif isinstance(expr.source, ValuesSource):
            all_rows_sql = []
            for row in expr.source.values_list:
                row_sql = []
                row_params = []
                for val in row:
                    s, p = val.to_sql()
                    row_sql.append(s)
                    row_params.extend(p)
                all_rows_sql.append(f"({', '.join(row_sql)})")
                all_params.extend(row_params)
            parts.append("VALUES " + ", ".join(all_rows_sql))
        elif isinstance(expr.source, SelectSource):
            s_sql, s_params = expr.source.select_query.to_sql()
            parts.append(s_sql)
            all_params.extend(s_params)
        
        sql = " ".join(parts)
        
        if expr.returning:
            returning_sql, returning_params = self.format_returning_clause(expr.returning)
            sql += f" {returning_sql}"
            all_params.extend(returning_params)
        
        return sql, tuple(all_params)
    
    def format_update_statement(self, expr) -> Tuple[str, tuple]:
        """Format UPDATE statement with OUTPUT clause support."""
        if self.strict_validation:
            expr.validate(strict=True)
        
        all_params: List[Any] = []
        
        table_sql, table_params = expr.table.to_sql()
        all_params.extend(table_params)
        
        parts = ["UPDATE", table_sql]
        
        set_parts = []
        for col, val in expr.values.items():
            col_sql = self.format_identifier(col)
            val_sql, val_params = val.to_sql()
            set_parts.append(f"{col_sql} = {val_sql}")
            all_params.extend(val_params)
        parts.append("SET " + ", ".join(set_parts))
        
        if expr.returning:
            returning_sql, returning_params = self.format_returning_clause(expr.returning)
            parts.append(returning_sql)
            all_params.extend(returning_params)
        
        if expr.where:
            where_sql, where_params = expr.where.to_sql()
            parts.append(f"WHERE {where_sql}")
            all_params.extend(where_params)
        
        return " ".join(parts), tuple(all_params)
    
    def format_delete_statement(self, expr) -> Tuple[str, tuple]:
        """Format DELETE statement with OUTPUT clause support."""
        if self.strict_validation:
            expr.validate(strict=True)
        
        all_params: List[Any] = []
        
        table_sql, table_params = expr.table.to_sql()
        all_params.extend(table_params)
        
        parts = ["DELETE FROM", table_sql]
        
        if expr.returning:
            returning_sql, returning_params = self.format_returning_clause(expr.returning)
            parts.append(returning_sql)
            all_params.extend(returning_params)
        
        if expr.where:
            where_sql, where_params = expr.where.to_sql()
            parts.append(f"WHERE {where_sql}")
            all_params.extend(where_params)
        
        return " ".join(parts), tuple(all_params)
    
    def supports_create_view(self) -> bool:
        """SQL Server supports CREATE VIEW."""
        return True
    
    def supports_drop_view(self) -> bool:
        """SQL Server supports DROP VIEW."""
        return True
    
    def supports_or_replace_view(self) -> bool:
        """SQL Server doesn't have OR REPLACE, uses ALTER or DROP + CREATE."""
        return False
    
    def supports_temporary_view(self) -> bool:
        """SQL Server doesn't support TEMPORARY views."""
        return False
    
    def supports_materialized_view(self) -> bool:
        """SQL Server doesn't have materialized views (uses indexed views)."""
        return False
    
    def supports_indexed_view(self) -> bool:
        """SQL Server supports indexed views (similar to materialized views)."""
        return True
    
    def supports_if_exists_view(self) -> bool:
        """SQL Server supports DROP VIEW IF EXISTS (2016+)."""
        return self.version >= SQL_SERVER_2016
    
    def supports_view_check_option(self) -> bool:
        """SQL Server supports WITH CHECK OPTION."""
        return True
    
    def supports_cascade_view(self) -> bool:
        """SQL Server doesn't support CASCADE for DROP VIEW."""
        return False
    
    def format_create_view_statement(
        self, expr: "CreateViewExpression"
    ) -> Tuple[str, tuple]:
        """Format CREATE VIEW statement for SQL Server."""
        parts = ["CREATE VIEW"]
        
        if expr.replace:
            parts = ["CREATE OR ALTER VIEW"]
        
        parts.append(self.format_identifier(expr.view_name))
        
        if expr.column_aliases:
            cols = ", ".join(self.format_identifier(c) for c in expr.column_aliases)
            parts.append(f"({cols})")
        
        query_sql, query_params = expr.query.to_sql()
        parts.append(f"AS {query_sql}")
        
        if expr.options and hasattr(expr.options, 'check_option') and expr.options.check_option:
            parts.append(f"WITH {expr.options.check_option.value} CHECK OPTION")
        
        return " ".join(parts), query_params
    
    def format_drop_view_statement(
        self, expr: "DropViewExpression"
    ) -> Tuple[str, tuple]:
        """Format DROP VIEW statement for SQL Server."""
        parts = ["DROP VIEW"]
        
        if expr.if_exists and self.supports_if_exists_view():
            parts.append("IF EXISTS")
        
        parts.append(self.format_identifier(expr.view_name))
        
        return " ".join(parts), ()
    
    def format_create_materialized_view_statement(
        self, expr: "CreateMaterializedViewExpression"
    ) -> Tuple[str, tuple]:
        """Format CREATE MATERIALIZED VIEW - not supported."""
        raise UnsupportedFeatureError(self.name, "CREATE MATERIALIZED VIEW", _SUGGESTION_MATERIALIZED_VIEW)
    
    def supports_trigger(self) -> bool:
        """SQL Server supports triggers."""
        return True
    
    def supports_create_trigger(self) -> bool:
        """SQL Server supports CREATE TRIGGER."""
        return True
    
    def supports_drop_trigger(self) -> bool:
        """SQL Server supports DROP TRIGGER."""
        return True
    
    def supports_instead_of_trigger(self) -> bool:
        """SQL Server supports INSTEAD OF triggers."""
        return True
    
    def supports_statement_trigger(self) -> bool:
        """SQL Server supports FOR EACH STATEMENT triggers."""
        return True
    
    def supports_trigger_referencing(self) -> bool:
        """SQL Server supports referencing OLD and NEW via inserted/deleted tables."""
        return True
    
    def supports_trigger_when(self) -> bool:
        """SQL Server supports WHEN condition in triggers (IF clause)."""
        return True
    
    def supports_trigger_if_not_exists(self) -> bool:
        """SQL Server doesn't support CREATE TRIGGER IF NOT EXISTS."""
        return False
    
    def supports_if_not_exists_table(self) -> bool:
        """SQL Server doesn't support CREATE TABLE IF NOT EXISTS."""
        return False
    
    def supports_if_exists_table(self) -> bool:
        """SQL Server supports DROP TABLE IF EXISTS (2016+)."""
        return self.version >= SQL_SERVER_2016
    
    def supports_temporary_table(self) -> bool:
        """SQL Server supports TEMPORARY tables (# prefix)."""
        return True
    
    def supports_rename_table(self) -> bool:
        """SQL Server uses sp_rename for table renaming."""
        return True
    
    def supports_rename_column(self) -> bool:
        """SQL Server uses sp_rename for column renaming."""
        return True
    
    def supports_drop_column(self) -> bool:
        """SQL Server supports ALTER TABLE DROP COLUMN."""
        return True
    
    def supports_add_column(self) -> bool:
        """SQL Server supports ALTER TABLE ADD COLUMN."""
        return True
    
    def supports_table_partitioning(self) -> bool:
        """SQL Server supports table partitioning."""
        return True
    
    def supports_create_schema(self) -> bool:
        """SQL Server supports CREATE SCHEMA."""
        return True
    
    def supports_drop_schema(self) -> bool:
        """SQL Server supports DROP SCHEMA."""
        return True
    
    def supports_schema_if_not_exists(self) -> bool:
        """SQL Server doesn't support CREATE SCHEMA IF NOT EXISTS."""
        return False
    
    def supports_schema_if_exists(self) -> bool:
        """SQL Server doesn't support DROP SCHEMA IF EXISTS."""
        return False
    
    def supports_create_index(self) -> bool:
        """SQL Server supports CREATE INDEX."""
        return True
    
    def supports_drop_index(self) -> bool:
        """SQL Server supports DROP INDEX."""
        return True
    
    def supports_unique_index(self) -> bool:
        """SQL Server supports UNIQUE indexes."""
        return True
    
    def supports_index_if_not_exists(self) -> bool:
        """SQL Server doesn't support CREATE INDEX IF NOT EXISTS."""
        return False
    
    def supports_index_if_exists(self) -> bool:
        """SQL Server supports DROP INDEX IF EXISTS (2016+)."""
        return self.version >= SQL_SERVER_2016
    
    def supports_partial_index(self) -> bool:
        """SQL Server supports filtered indexes (WHERE clause)."""
        return True
    
    def supports_functional_index(self) -> bool:
        """SQL Server supports indexes on computed columns."""
        return True
    
    def supports_concurrent_index(self) -> bool:
        """SQL Server supports ONLINE index creation (Enterprise edition)."""
        return True
    
    def supports_fulltext_index(self) -> bool:
        """SQL Server supports FULLTEXT indexes."""
        return True
    
    def supports_create_sequence(self) -> bool:
        """SQL Server 2012+ supports SEQUENCE objects."""
        return self.version >= SQL_SERVER_2012
    
    def supports_drop_sequence(self) -> bool:
        """SQL Server 2012+ supports DROP SEQUENCE."""
        return self.version >= SQL_SERVER_2012
    
    def supports_auto_increment(self) -> bool:
        """SQL Server uses IDENTITY for auto-increment."""
        return True
    
    def format_auto_increment(self) -> str:
        """Return IDENTITY(1,1) for auto-increment columns."""
        return "IDENTITY(1,1)"
    
    def supports_generated_column(self) -> bool:
        """SQL Server supports computed columns."""
        return True
    
    def supports_stored_generated_columns(self) -> bool:
        """SQL Server supports PERSISTED computed columns."""
        return True
    
    def supports_virtual_generated_columns(self) -> bool:
        """SQL Server computed columns are virtual by default."""
        return True
    
    def supports_union(self) -> bool:
        """UNION is supported."""
        return True
    
    def supports_union_all(self) -> bool:
        """UNION ALL is supported."""
        return True
    
    def supports_intersect(self) -> bool:
        """INTERSECT is supported."""
        return True
    
    def supports_except(self) -> bool:
        """EXCEPT is supported."""
        return True
    
    def supports_set_operation_order_by(self) -> bool:
        """Set operations support ORDER BY."""
        return True
    
    def supports_set_operation_limit_offset(self) -> bool:
        """Set operations support OFFSET FETCH."""
        return True
    
    def supports_set_operation_for_update(self) -> bool:
        """Set operations don't support FOR UPDATE."""
        return False
    
    def supports_savepoint(self) -> bool:
        """SQL Server supports savepoints."""
        return True
    
    def supports_transaction_mode(self) -> bool:
        """SQL Server doesn't support READ ONLY transactions."""
        return False
    
    def supports_isolation_level_in_begin(self) -> bool:
        """SQL Server requires SET TRANSACTION ISOLATION LEVEL before BEGIN."""
        return False
    
    def supports_read_only_transaction(self) -> bool:
        """SQL Server doesn't support READ ONLY transactions."""
        return False
    
    def supports_deferrable_transaction(self) -> bool:
        """SQL Server doesn't support DEFERRABLE mode."""
        return False
    
    def format_begin_transaction(
        self, expr: "BeginTransactionExpression"
    ) -> Tuple[str, tuple]:
        """Format BEGIN TRANSACTION for SQL Server."""
        from rhosocial.activerecord.backend.errors import UnsupportedTransactionModeError
        from rhosocial.activerecord.backend.transaction import TransactionMode
        
        params = expr.get_params()
        mode = params.get("mode")
        
        if mode == TransactionMode.READ_ONLY:
            raise UnsupportedTransactionModeError(
                feature="READ ONLY transactions",
                backend="SQL Server",
                message="SQL Server does not support READ ONLY transactions."
            )
        
        return "BEGIN TRANSACTION", ()
    
    def supports_functions(self) -> Dict[str, bool]:
        """Return supported SQL functions as function_name -> bool mapping."""
        from rhosocial.activerecord.backend.expression.functions import __all__ as core_functions
        
        result = {}
        for func_name in core_functions:
            result[func_name] = self._is_sqlserver_function_supported(func_name)
        
        for func_name in self._SQLSERVER_FUNCTION_VERSIONS:
            if func_name not in result:
                result[func_name] = self._is_sqlserver_function_supported(func_name)
        
        return result
    
    def _is_sqlserver_function_supported(self, func_name: str) -> bool:
        """Check if a SQL Server-specific function is supported based on version."""
        version_range = self._SQLSERVER_FUNCTION_VERSIONS.get(func_name)
        if version_range is None:
            return True
        
        min_version = version_range[0]
        max_version = version_range[1]
        
        if min_version is not None and self.version < min_version:
            return False
        
        if max_version is not None and self.version > max_version:
            return False
        
        return True
    
    def format_array_expression(self, _expr: "ArrayExpression") -> Tuple[str, Tuple]:
        """Format array expression - not supported."""
        raise UnsupportedFeatureError(self.name, "Array operations", _SUGGESTION_ARRAY_TYPES)
    
    def format_json_table_expression(
        self,
        _json_col_sql: str,
        _path: str,
        _columns: List[Dict[str, Any]],
        _alias: Optional[str],
        _params: tuple
    ) -> Tuple[str, Tuple]:
        """Format JSON_TABLE - SQL Server uses OPENJSON."""
        raise UnsupportedFeatureError(self.name, "JSON_TABLE", _SUGGESTION_JSON_TABLE)
    
    def format_match_clause(self, _clause: "MatchClause") -> Tuple[str, tuple]:
        """Format MATCH clause - not supported."""
        raise UnsupportedFeatureError(self.name, "graph MATCH clause", _SUGGESTION_GRAPH_MATCH)
    
    def format_ordered_set_aggregation(self, _aggregation: "OrderedSetAggregation") -> Tuple[str, Tuple]:
        """Format ordered-set aggregation - not supported."""
        raise UnsupportedFeatureError(self.name, "ordered-set aggregate functions", _SUGGESTION_ORDERED_SET_AGG)
    
    def format_qualify_clause(self, _clause: "QualifyClause") -> Tuple[str, tuple]:
        """Format QUALIFY clause - not supported."""
        raise UnsupportedFeatureError(self.name, "QUALIFY clause", _SUGGESTION_QUALIFY)
    
    def format_grouping_expression(
        self, operation: str, _expressions: List["bases.BaseExpression"]
    ) -> Tuple[str, tuple]:
        """Format grouping expression (ROLLUP, CUBE, GROUPING SETS)."""
        if operation.upper() == "ROLLUP":
            return "WITH ROLLUP", ()
        elif operation.upper() == "CUBE":
            return "WITH CUBE", ()
        elif operation.upper() == "GROUPING SETS":
            return "GROUPING SETS", ()
        
        raise UnsupportedFeatureError(self.name, f"{operation} grouping operation")
