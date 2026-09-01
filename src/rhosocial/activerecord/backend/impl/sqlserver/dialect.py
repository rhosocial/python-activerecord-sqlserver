# src/rhosocial/activerecord/backend/impl/sqlserver/dialect.py
"""
SQL Server backend SQL dialect implementation.

This dialect implements protocols for features that SQL Server actually supports,
based on the SQL Server version provided at initialization.
"""

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING, Union
import copy

from rhosocial.activerecord.backend.dialect.base import SQLDialectBase
from rhosocial.activerecord.backend.expression import bases
from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.dialect.protocols import (
    CollationSupport,
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
from .protocols import (
    SQLServerTableSupport,
    SQLServerLockingSupport,
    SQLServerJSONSupport,
    SQLServerTemporalTableSupport,
    SQLServerSequenceSupport,
    SQLServerFullTextSearchSupport,
    SQLServerPaginationSupport,
    SQLServerMergeSupport,
    SQLServerPartitionSupport,
    SQLServerOutputSupport,
    SQLServerTableHintSupport,
    SQLServerTryCastSupport,
    SQLServerIdentitySupport,
    SQLServerIndexedViewSupport,
)
from rhosocial.activerecord.backend.dialect.mixins import (
    CollationMixin,
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
    IdentifierMixin,
    PredicateMixin,
    ExpressionMixin,
    DateTimeMixin,
    DQLMixin,
    DMLMixin,
    DDLColumnMixin,
    DDLTypeMixin,
)
# SQLServerTypeSupportMixin is imported lazily in _register_type_formatters()
from rhosocial.activerecord.backend.dialect.protocols import PartitionSupport
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from .collation import validate_sqlserver_collation_name
from .alter_table_modifier import SQLServerAlterColumnModifierMixin
from .mixins.sequence import SQLServerSequenceMixin
from .mixins.pivot import SQLServerPivotMixin
from .mixins.columnstore import SQLServerColumnstoreIndexMixin
from .mixins.memory_optimized import SQLServerMemoryOptimizedMixin
from .mixins.routine import SQLServerRoutineMixin
from .mixins.trigger import SQLServerTriggerDdlMixin
from .mixins.protocol_support import SQLServerProtocolSupportMixin
from .mixins.types import SQLServerTypeSupportMixin, SQLServerTypeSuggestionMixin
# SQLServerPartitionMixin is registered lazily in _register_partition_formatters()

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression import bases
    from rhosocial.activerecord.backend.expression.collation import CollateExpression
    from rhosocial.activerecord.backend.expression.advanced_functions import ArrayExpression, OrderedSetAggregation, JSONExpression
    from rhosocial.activerecord.backend.expression.graph import MatchClause
    from rhosocial.activerecord.backend.expression.query_parts import (
        OrderByClause,
        LimitOffsetClause,
        ForUpdateClause,
        QualifyClause,
        JoinExpression,
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
        UpdateExpression,
        DeleteExpression,
        ColumnDefinition,
        TableConstraint,
        IndexDefinition,
        CreateTableExpression,
        DropTableExpression,
        AlterTableExpression,
        CreateSchemaExpression,
        DropSchemaExpression,
        CreateSequenceExpression,
        DropSequenceExpression,
        AlterSequenceExpression,
        MergeExpression,
        TruncateExpression,
    )
    from rhosocial.activerecord.backend.expression.transaction import (
        BeginTransactionExpression,
        SetTransactionExpression,
    )


SQL_SERVER_2005 = (9, 0, 0)
SQL_SERVER_2008 = (10, 0, 0)
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
    # Core infrastructure mixins (provide base implementations
    # that the dialect overrides as needed)
    IdentifierMixin,
    ExpressionMixin,
    PredicateMixin,
    DateTimeMixin,
    DQLMixin,
    DMLMixin,
    SQLServerAlterColumnModifierMixin,  # Before DDLColumnMixin to override format_*_action
    SQLServerProtocolSupportMixin,  # SQL Server protocol contract implementations
    SQLServerSequenceMixin,  # NEXT VALUE FOR formatter (2012+)
    SQLServerPivotMixin,  # PIVOT / UNPIVOT formatters (2005+)
    SQLServerColumnstoreIndexMixin,  # columnstore index DDL (2012+/2014+/2022+)
    SQLServerMemoryOptimizedMixin,  # In-Memory OLTP table options (2014+)
    SQLServerRoutineMixin,  # PROCEDURE / FUNCTION DDL (2005+)
    SQLServerTriggerDdlMixin,  # TRIGGER DDL (2005+)
    DDLColumnMixin,
    SQLServerTypeSupportMixin,  # DataType formatting & parsing (standard MRO registration)
    SQLServerTypeSuggestionMixin,  # Python -> SQL DataType suggestions (DDL generation)
    DDLTypeMixin,
    # Feature mixins
    CollationMixin,
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
    # Protocols for isinstance() checks
    CollationSupport,
    CTESupport,
    FilterClauseSupport,
    WindowFunctionSupport,
    SQLServerJSONSupport,  # Before JSONSupport (subclass must precede its base)
    JSONSupport,
    ReturningSupport,
    AdvancedGroupingSupport,
    ArraySupport,
    ExplainSupport,
    GraphSupport,
    SQLServerLockingSupport,  # Before LockingSupport
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
    SQLServerTableSupport,  # Before TableSupport
    TableSupport,
    ConstraintSupport,
    IntrospectionSupport,
    TransactionControlSupport,
    SQLFunctionSupport,
    # SQL Server-specific protocols (marker classes for isinstance() checks;
    # implementations live in SQLServerProtocolSupportMixin / SQLServerSequenceMixin)
    SQLServerOutputSupport,
    SQLServerPaginationSupport,
    SQLServerFullTextSearchSupport,
    SQLServerTryCastSupport,
    SQLServerTableHintSupport,
    SQLServerTemporalTableSupport,
    SQLServerMergeSupport,
    SQLServerSequenceSupport,
    SQLServerIdentitySupport,
    SQLServerIndexedViewSupport,
    SQLServerPartitionSupport,  # Before PartitionSupport
    PartitionSupport,
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

    _NILADIC_FUNCTION_EQUIVALENTS = {
        "NOW": "SYSDATETIME()",
        "CURRENT_DATE": "CAST(GETDATE() AS DATE)",
        "CURRENT_TIME": "CAST(GETDATE() AS TIME)",
    }

    _FUNCTION_NAME_EQUIVALENTS = {
        "LENGTH": "LEN",
        "CHAR_LENGTH": "LEN",
    }

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
        # JSON compat functions (SQL Server 2016+; JSON_OBJECT/JSON_ARRAY
        # are 2022+, covered above by the JSON_* entries)
        "json_extract": (SQL_SERVER_2016, None),
        "json_unquote": (SQL_SERVER_2016, None),
        "json_contains": (SQL_SERVER_2016, None),
        "json_set": (SQL_SERVER_2016, None),
        "json_remove": (SQL_SERVER_2016, None),
        "json_type": (SQL_SERVER_2016, None),
        "json_valid": (SQL_SERVER_2016, None),
        "json_search": (SQL_SERVER_2016, None),
        # Spatial functions (SQL Server 2008+)
        "st_geom_from_text": (SQL_SERVER_2008, None),
        "st_geom_from_wkb": (SQL_SERVER_2008, None),
        "st_as_text": (SQL_SERVER_2008, None),
        "st_as_geojson": (SQL_SERVER_2008, None),
        "st_distance": (SQL_SERVER_2008, None),
        "st_within": (SQL_SERVER_2008, None),
        "st_contains": (SQL_SERVER_2008, None),
        "st_intersects": (SQL_SERVER_2008, None),
        # Full-text search (SQL Server 2005+)
        "match_against": (SQL_SERVER_2005, None),
        # Bitwise functions (SQL Server 2022+ for the new ones)
        "bit_count": (SQL_SERVER_2022, None),
        "bit_get_bit": (SQL_SERVER_2022, None),
        "bit_shift_left": (SQL_SERVER_2022, None),
        "bit_shift_right": (SQL_SERVER_2022, None),
    }
    
    def __init__(self, version: Optional[Tuple[int, int, int]] = None):
        """
        Initialize SQL Server dialect with specific version.

        Args:
            version: SQL Server version tuple (major, minor, patch).
                If None, the dialect must be adapted via
                backend.introspect_and_adapt() before version-dependent
                features can be used.
        """
        super().__init__()
        if version is not None:
            self.version = version
    
    def get_parameter_placeholder(self, position: int = 0) -> str:
        """SQL Server uses ? for placeholders (ODBC/qmark style)."""
        return "?"
    
    def get_server_version(self) -> Tuple[int, int, int]:
        """Return the SQL Server version this dialect is configured for."""
        return self.version

    def create_schema_differ(self):
        """Return the SQL Server schema differ (ordinal-position aware)."""
        from rhosocial.activerecord.backend.impl.sqlserver.schema.differ import (
            SQLServerSchemaDiffer,
        )

        return SQLServerSchemaDiffer()

    def format_date_trunc_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        source_sql, source_params = expr.source.to_sql()
        field = expr.field.value.upper()
        if field in {"YEAR", "MONTH", "DAY", "HOUR", "MINUTE", "SECOND"}:
            sql = f"DATETRUNC({field}, {source_sql})"
        else:
            raise UnsupportedFeatureError(self.name, f"date_trunc({expr.field.value})")
        return self._apply_value_expression_modifiers(sql, source_params, expr)

    def format_interval_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        raise UnsupportedFeatureError(
            self.name,
            "standalone INTERVAL expression",
            "Use date_add() or date_sub() for SQL Server date arithmetic.",
        )

    def format_datetime_add_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        source_sql, source_params = expr.source.to_sql()
        unit = expr.interval.unit.value.upper()
        sql = f"DATEADD({unit}, ?, {source_sql})"
        return self._apply_value_expression_modifiers(
            sql, (expr.interval.value,) + source_params, expr
        )

    def format_datetime_subtract_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        source_sql, source_params = expr.source.to_sql()
        unit = expr.interval.unit.value.upper()
        sql = f"DATEADD({unit}, ?, {source_sql})"
        return self._apply_value_expression_modifiers(
            sql, (-expr.interval.value,) + source_params, expr
        )

    def format_datetime_diff_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        start_sql, start_params = expr.start.to_sql()
        end_sql, end_params = expr.end.to_sql()
        sql = f"DATEDIFF({expr.unit.value.upper()}, {start_sql}, {end_sql})"
        return self._apply_value_expression_modifiers(sql, start_params + end_params, expr)

    def supports_collate_expression(self) -> bool:
        """SQL Server supports expression-level COLLATE."""
        return True

    def validate_collation_name(self, expr: "CollateExpression") -> str:
        """Validate SQL Server collation names and return their SQL representation."""
        if "schema" in expr.collation_options:
            raise UnsupportedFeatureError(self.name, "schema-qualified COLLATE")
        keyword = expr.collation_options.get("keyword", False)
        unsupported = set(expr.collation_options) - {"keyword", "schema"}
        if unsupported:
            options = ", ".join(sorted(unsupported))
            raise UnsupportedFeatureError(self.name, f"COLLATE options: {options}")
        if keyword and expr.collation_name != "DATABASE_DEFAULT":
            raise ValueError(f"Unsupported SQL Server collation keyword: {expr.collation_name!r}")
        return validate_sqlserver_collation_name(expr.collation_name, getattr(self, "version", None))

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
    
    def supports_returning_insert(self) -> bool:
        """SQL Server supports OUTPUT clause for INSERT."""
        return True

    def supports_returning_update(self) -> bool:
        """SQL Server supports OUTPUT clause for UPDATE."""
        return True

    def supports_returning_delete(self) -> bool:
        """SQL Server supports OUTPUT clause for DELETE."""
        return True

    def supports_constraint_enforced(self) -> bool:
        """SQL Server does not support ENFORCED/NOT ENFORCED constraint control."""
        return False

    def supports_fk_match(self) -> bool:
        """SQL Server does not support MATCH {SIMPLE|PARTIAL|FULL}."""
        return False

    def supports_deferrable_constraint(self) -> bool:
        """SQL Server does not support DEFERRABLE constraints."""
        return False

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

    def format_json_function_expression(self, expr) -> Tuple[str, tuple]:
        """Format JSON extraction using SQL Server's JSON_VALUE built-in.

        The base implementation renders ``JSON_UNQUOTE(JSON_EXTRACT(...))``
        which is MySQL syntax. SQL Server uses ``JSON_VALUE(column, 'path')``,
        which already returns a scalar value without surrounding quotes.

        Args:
            expr: The JSONExpression to format.

        Returns:
            (SQL string, params tuple).
        """
        if isinstance(expr.column, bases.BaseExpression):
            col_sql, col_params = expr.column.to_sql()
        else:
            col_sql, col_params = self.format_identifier(str(expr.column)), ()

        escaped_path = self._escape_sql_string(expr.path)
        sql = f"JSON_VALUE({col_sql}, '{escaped_path}')"
        params = col_params

        if expr.cast_types:
            for target_type in expr.cast_types:
                sql, params = self.format_cast_expression(sql, target_type, params, None)

        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"

        return sql, params
    
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

    def format_limit_offset_clause(self, clause: "LimitOffsetClause") -> Tuple[str, tuple]:
        """Format LIMIT/OFFSET clause for SQL Server using OFFSET FETCH syntax."""
        if clause.limit is None and clause.offset is None:
            return "", ()

        if self.version < SQL_SERVER_2012:
            raise UnsupportedFeatureError(
                self.name,
                "OFFSET FETCH pagination",
                "SQL Server 2012+ required for OFFSET FETCH. Use ROW_NUMBER() for older versions."
            )

        parts = []
        params = []

        offset_val = clause.offset if clause.offset is not None else 0
        parts.append(f"OFFSET {offset_val} ROWS")

        if clause.limit is not None:
            parts.append(f"FETCH NEXT {clause.limit} ROWS ONLY")

        return " ".join(parts), tuple(params)

    def format_query_statement(self, expr: "QueryExpression") -> Tuple[str, tuple]:
        sql, params = super().format_query_statement(expr)
        if expr.limit_offset is not None and expr.order_by is None:
            lo_sql = expr.limit_offset.to_sql()[0]
            if lo_sql and lo_sql in sql:
                sql = sql.replace(lo_sql, f"ORDER BY (SELECT NULL) {lo_sql}")
            else:
                sql += " ORDER BY (SELECT NULL)"
        return sql, tuple(params)

    def format_returning_clause(self, clause: "ReturningClause", default_table: str = "INSERTED") -> Tuple[str, tuple]:
        """
        Format RETURNING as OUTPUT clause for SQL Server.

        SQL Server OUTPUT syntax:
        - INSERT: OUTPUT inserted.column, inserted.column2
        - UPDATE: OUTPUT deleted.old_column, inserted.new_column
        - DELETE: OUTPUT deleted.column

        Args:
            clause: The ReturningClause with expressions to output.
            default_table: The default virtual table prefix ("INSERTED" for
                INSERT/UPDATE, "DELETED" for DELETE).
        """
        all_params = []
        expr_parts = []

        for expr in clause.expressions:
            if hasattr(expr, 'table') and expr.table:
                expr_sql, expr_params = expr.to_sql()
                expr_parts.append(f"{default_table}.{expr_sql}")
            else:
                expr_sql, expr_params = expr.to_sql()
                expr_parts.append(f"{default_table}.{expr_sql}")
            all_params.extend(expr_params)

        output_sql = f"OUTPUT {', '.join(expr_parts)}"

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

        # Add OUTPUT clause before VALUES/SELECT (SQL Server requirement)
        if expr.returning:
            returning_sql, returning_params = self.format_returning_clause(expr.returning)
            parts.append(returning_sql)
            all_params.extend(returning_params)

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
        for col, val in expr.assignments.items():
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
            parts.append(where_sql)
            all_params.extend(where_params)

        return " ".join(parts), tuple(all_params)
    
    def format_delete_statement(self, expr) -> Tuple[str, tuple]:
        """Format DELETE statement with OUTPUT clause support."""
        if self.strict_validation:
            expr.validate(strict=True)
        
        all_params: List[Any] = []
        
        # DeleteExpression has .tables (list), not .table
        if expr.tables:
            table_refs = []
            for tbl in expr.tables:
                tbl_sql, tbl_params = tbl.to_sql()
                table_refs.append(tbl_sql)
                all_params.extend(tbl_params)
            table_sql = ", ".join(table_refs)
        else:
            table_sql = ""
        
        parts = ["DELETE FROM", table_sql]
        
        if expr.returning:
            returning_sql, returning_params = self.format_returning_clause(expr.returning, default_table="DELETED")
            parts.append(returning_sql)
            all_params.extend(returning_params)
        
        if expr.where:
            where_sql, where_params = expr.where.to_sql()
            parts.append(where_sql)
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
        return self.version >= SQL_SERVER_2005
    
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
        as_sql = f"AS {query_sql}"
        if expr.options and getattr(expr.options, "schemabinding", False):
            as_sql = f"WITH SCHEMABINDING {as_sql}"
        parts.append(as_sql)
        
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
        """SQL Server supports triggers (since 2005)."""
        return self.version >= SQL_SERVER_2005

    def supports_create_trigger(self) -> bool:
        """SQL Server supports CREATE TRIGGER (since 2005)."""
        return self.version >= SQL_SERVER_2005

    def supports_drop_trigger(self) -> bool:
        """SQL Server supports DROP TRIGGER (since 2005)."""
        return self.version >= SQL_SERVER_2005
    
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

    def supports_schema(self) -> bool:
        """SQL Server models named schema namespaces natively (e.g. dbo)."""
        return True

    def supports_schema_authorization(self) -> bool:
        """SQL Server accepts CREATE SCHEMA ... AUTHORIZATION owner."""
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
        """Return supported SQL functions as function_name -> bool mapping.

        Combines the core expression function factories with the SQL Server
        function factories in ``functions.__all__``.
        """
        from rhosocial.activerecord.backend.expression.functions import (
            __all__ as core_functions,
        )
        from rhosocial.activerecord.backend.impl.sqlserver import (
            functions as sqlserver_functions,
        )

        result = {}
        for func_name in core_functions:
            result[func_name] = self._is_sqlserver_function_supported(func_name)

        for func_name in getattr(sqlserver_functions, "__all__", []):
            if func_name not in result:
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

    def format_create_table_statement(
        self, expr: "CreateTableExpression"
    ) -> Tuple[str, tuple]:
        """Format CREATE TABLE statement for SQL Server.

        SQL Server doesn't support ``IF NOT EXISTS`` syntax for CREATE TABLE
        (until SQL Server 2016 for DROP, but not CREATE). When
        ``if_not_exists`` is True and the target is not a temporary table, the
        statement is wrapped in an ``IF OBJECT_ID(...) IS NULL`` existence
        guard so repeated creation is idempotent.
        SQL Server has no CREATE TABLE ... LIKE; ``like_table`` raises
        ``UnsupportedFeatureError``. Temporary tables use a ``#``-prefixed
        table name instead of the ``TEMPORARY`` keyword.
        """
        all_params: List[Any] = []

        dialect_options = getattr(expr, "dialect_options", {}) or {}
        if dialect_options.get("like_table"):
            raise UnsupportedFeatureError(
                self.name,
                "CREATE TABLE ... LIKE",
                "SQL Server has no CREATE TABLE ... LIKE syntax; use SELECT INTO or an explicit CREATE TABLE statement.",
            )

        # Build CREATE TABLE header
        parts = ["CREATE TABLE"]

        if expr.temporary:
            temp_name = expr.table.name
            if not temp_name.startswith("#"):
                temp_name = f"#{temp_name}"
            table_sql = self.format_identifier(temp_name)
            if expr.table.schema_name:
                table_sql = f"{self.format_identifier(expr.table.schema_name)}.{table_sql}"
            table_params = ()
        else:
            table_sql, table_params = expr.table.to_sql()
        all_params.extend(table_params)
        parts.append(table_sql)

        # Build column definitions
        from rhosocial.activerecord.backend.expression.statements import (
            ColumnConstraintType,
        )
        column_parts = []
        for col_def in expr.columns:
            col_sql, col_params = self.format_column_definition(col_def, ColumnConstraintType)
            column_parts.append(col_sql)
            all_params.extend(col_params)

        # Build table constraints
        for t_const in expr.table_constraints:
            const_sql, const_params = self.format_table_constraint(t_const)
            if const_sql:
                column_parts.append(const_sql)
                all_params.extend(const_params)

        # Build inline indexes (SQL Server specific)
        for idx_def in expr.indexes:
            idx_sql = self.format_inline_index(idx_def)
            column_parts.append(idx_sql)

        parts.append(f"({', '.join(column_parts)})")

        # Handle table partitioning clause
        if expr.partition is not None:
            partition_sql, partition_params = expr.partition.to_sql()
            parts.append(partition_sql)
            all_params.extend(partition_params)

        # Handle In-Memory OLTP table options (2014+)
        if dialect_options.get("memory_optimized"):
            durability = dialect_options.get("durability", "SCHEMA_ONLY")
            parts.append(self.format_memory_optimized_option(durability))

        statement = ' '.join(parts)

        if expr.if_not_exists and not expr.temporary:
            # T-SQL has no CREATE TABLE IF NOT EXISTS; guard with an
            # OBJECT_ID existence check instead.
            guard_name = self.format_identifier(expr.table.name)
            if expr.table.schema_name:
                guard_name = (
                    f"{self.format_identifier(expr.table.schema_name)}.{guard_name}"
                )
            statement = (
                f"IF OBJECT_ID(N'{guard_name}', N'U') IS NULL {statement}"
            )

        return statement, tuple(all_params)

    def format_column_definition(self, col_def: "ColumnDefinition", constraint_type=None) -> Tuple[str, List[Any]]:
        """Format a column definition for SQL Server.

        ``constraint_type`` is the ``ColumnConstraintType`` enum used for
        comparisons; it defaults to ``None`` so the generic 1-arg call
        (ALTER TABLE ADD COLUMN path) also resolves here.
        """
        from rhosocial.activerecord.backend.expression.statements.ddl_table import (
            ColumnConstraintType,
        )
        if constraint_type is None:
            from rhosocial.activerecord.backend.expression.statements.ddl_table import (
                ColumnConstraintType as _CCT,
            )
            constraint_type = _CCT
        from rhosocial.activerecord.backend.expression.types._base import DataType
        if isinstance(col_def.data_type, DataType):
            type_sql, type_params = col_def.data_type.to_sql(self)
            parts = [self.format_identifier(col_def.name), type_sql]
            params: List[Any] = list(type_params)
        else:
            parts = [self.format_identifier(col_def.name), str(col_def.data_type)]
            params: List[Any] = []
        tuple_params = tuple(params)

        constraint_parts = []
        for constraint in col_def.constraints:
            if constraint.constraint_type == ColumnConstraintType.PRIMARY_KEY:
                constraint_parts.append("PRIMARY KEY")
            elif constraint.constraint_type == ColumnConstraintType.NOT_NULL:
                constraint_parts.append("NOT NULL")
            elif constraint.constraint_type == ColumnConstraintType.UNIQUE:
                constraint_parts.append("UNIQUE")
            elif constraint.constraint_type == ColumnConstraintType.DEFAULT:
                if constraint.default_value is not None:
                    from rhosocial.activerecord.backend.expression import bases
                    if isinstance(constraint.default_value, bases.BaseExpression):
                        default_sql, default_params = constraint.default_value.to_sql()
                        constraint_parts.append(f"DEFAULT {default_sql}")
                        params.extend(default_params)
                    elif isinstance(constraint.default_value, str):
                        escaped = self._escape_sql_string(constraint.default_value)
                        constraint_parts.append(f"DEFAULT '{escaped}'")
                    else:
                        constraint_parts.append(f"DEFAULT {constraint.default_value}")
            elif constraint.constraint_type == ColumnConstraintType.NULL:
                constraint_parts.append("NULL")

            # Handle IDENTITY (auto-increment)
            if constraint.is_auto_increment:
                constraint_parts.append("IDENTITY(1,1)")

        if constraint_parts:
            parts.append(' '.join(constraint_parts))

        return ' '.join(parts), tuple(params)

    def format_table_constraint(self, t_const: "TableConstraint") -> Tuple[str, List[Any]]:
        """Format a table constraint for SQL Server."""
        from rhosocial.activerecord.backend.expression.statements import (
            TableConstraintType,
            ForeignKeyConstraint,
            ReferentialAction,
        )

        parts = []
        params: List[Any] = []

        if t_const.name:
            parts.append(f"CONSTRAINT {self.format_identifier(t_const.name)}")

        if t_const.constraint_type == TableConstraintType.PRIMARY_KEY:
            if t_const.columns:
                cols_str = ', '.join(self.format_identifier(c) for c in t_const.columns)
                parts.append(f"PRIMARY KEY ({cols_str})")
        elif t_const.constraint_type == TableConstraintType.UNIQUE:
            if t_const.columns:
                cols_str = ', '.join(self.format_identifier(c) for c in t_const.columns)
                parts.append(f"UNIQUE ({cols_str})")
        elif t_const.constraint_type == TableConstraintType.FOREIGN_KEY:
            if t_const.columns and t_const.foreign_key_table and t_const.foreign_key_columns:
                cols_str = ', '.join(self.format_identifier(c) for c in t_const.columns)
                ref_cols_str = ', '.join(
                    self.format_identifier(c) for c in t_const.foreign_key_columns
                )
                ref_table = self.format_identifier(t_const.foreign_key_table)
                parts.append(
                    f"FOREIGN KEY ({cols_str}) REFERENCES {ref_table} ({ref_cols_str})"
                )
                if isinstance(t_const, ForeignKeyConstraint):
                    if t_const.on_delete != ReferentialAction.NO_ACTION:
                        parts.append(f"ON DELETE {t_const.on_delete.value}")
                    if t_const.on_update != ReferentialAction.NO_ACTION:
                        parts.append(f"ON UPDATE {t_const.on_update.value}")
        elif t_const.constraint_type == TableConstraintType.CHECK and t_const.check_condition:
            check_sql, check_params = t_const.check_condition.to_sql()
            parts.append(f"CHECK ({check_sql})")
            params.extend(check_params)

        return ' '.join(parts), params

    def format_inline_index(self, idx_def: "IndexDefinition") -> str:
        """Format an inline index definition for SQL Server."""
        parts = []

        if idx_def.unique:
            parts.append("UNIQUE")

        parts.append("INDEX")
        parts.append(self.format_identifier(idx_def.name))

        cols_str = ', '.join(self.format_identifier(c) for c in idx_def.columns)

        idx_options = getattr(idx_def, "dialect_options", None) or {}
        if idx_options.get("hash_index"):
            self.check_feature_support(
                "supports_memory_optimized_tables",
                "NONCLUSTERED HASH index",
                "requires SQL Server 2014+ (memory-optimized tables).",
            )
            bucket_count = idx_options.get("bucket_count")
            if bucket_count is None:
                raise ValueError("bucket_count is required for a NONCLUSTERED HASH index")
            parts.append(f"NONCLUSTERED HASH ({cols_str}) WITH (BUCKET_COUNT = {bucket_count})")
        else:
            parts.append(f"({cols_str})")

        return ' '.join(parts)

    def format_drop_table_statement(
        self, expr: "DropTableExpression"
    ) -> Tuple[str, tuple]:
        """Format DROP TABLE statement for SQL Server."""
        parts = ["DROP TABLE"]

        if expr.if_exists and self.supports_if_exists_table():
            parts.append("IF EXISTS")

        table_sql, table_params = expr.table.to_sql()
        parts.append(table_sql)

        return ' '.join(parts), table_params

    def format_create_index_statement(self, expr: "CreateIndexExpression") -> Tuple[str, tuple]:
        """Format CREATE INDEX statement for SQL Server.

        SQL Server doesn't support IF NOT EXISTS for CREATE INDEX.
        We ignore the if_not_exists flag and generate standard CREATE INDEX.
        """
        from rhosocial.activerecord.backend.expression.bases import ToSQLProtocol

        all_params = []
        parts = ["CREATE"]

        if expr.unique:
            parts.append("UNIQUE")

        # SQL Server supports clustered/nonclustered indexes
        if hasattr(expr, 'index_type') and expr.index_type:
            index_type = expr.index_type.upper()
            if index_type in ('CLUSTERED', 'NONCLUSTERED'):
                parts.append(index_type)

        parts.append("INDEX")
        # Note: SQL Server doesn't support IF NOT EXISTS for CREATE INDEX
        # We ignore if_not_exists flag
        parts.append(self.format_identifier(expr.index_name))
        parts.append("ON")
        parts.append(self.format_identifier(expr.table_name))

        col_parts = []
        for col in expr.columns:
            if isinstance(col, ToSQLProtocol):
                col_sql, col_params = col.to_sql()
                col_parts.append(col_sql)
                all_params.extend(col_params)
            else:
                col_parts.append(self.format_identifier(str(col)))
        parts.append(f"({', '.join(col_parts)})")

        # SQL Server uses INCLUDE for covering indexes
        if expr.include:
            include_cols = ", ".join(self.format_identifier(c) for c in expr.include)
            parts.append(f"INCLUDE ({include_cols})")

        # SQL Server uses WHERE for filtered indexes
        if expr.where:
            where_sql, where_params = expr.where.to_sql()
            parts.append(where_sql)
            all_params.extend(where_params)

        return " ".join(parts), tuple(all_params)

    # --- SQL Server-specific format overrides ---

    def format_create_sequence_statement(self, expr: "CreateSequenceExpression") -> Tuple[str, tuple]:
        """Format CREATE SEQUENCE for SQL Server (2012+).

        SQL Server uses:
        - CREATE SEQUENCE [schema.]name
        - START WITH, INCREMENT BY, MINVALUE, MAXVALUE
        - CYCLE | NO CYCLE, CACHE, NO ORDER (ORDER not supported)
        - No IF NOT EXISTS support, no OWNED BY
        """
        parts = ["CREATE SEQUENCE"]
        parts.append(self.format_identifier(expr.sequence_name))
        if expr.start is not None:
            parts.append(f"START WITH {expr.start}")
        if expr.increment is not None:
            parts.append(f"INCREMENT BY {expr.increment}")
        if expr.minvalue is not None:
            parts.append(f"MINVALUE {expr.minvalue}")
        if expr.maxvalue is not None:
            parts.append(f"MAXVALUE {expr.maxvalue}")
        if expr.cycle:
            parts.append("CYCLE")
        else:
            parts.append("NO CYCLE")
        if expr.cache is not None:
            parts.append(f"CACHE {expr.cache}")
        return " ".join(parts), ()

    def format_drop_sequence_statement(self, expr: "DropSequenceExpression") -> Tuple[str, tuple]:
        """Format DROP SEQUENCE for SQL Server (2012+)."""
        parts = ["DROP SEQUENCE"]
        if expr.if_exists and self.version >= SQL_SERVER_2012:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.sequence_name))
        return " ".join(parts), ()

    def format_alter_sequence_statement(self, expr: "AlterSequenceExpression") -> Tuple[str, tuple]:
        """Format ALTER SEQUENCE for SQL Server."""
        parts = [f"ALTER SEQUENCE {self.format_identifier(expr.sequence_name)}"]
        if expr.restart is not None:
            parts.append(f"RESTART WITH {expr.restart}")
        if expr.increment is not None:
            parts.append(f"INCREMENT BY {expr.increment}")
        if expr.minvalue is not None:
            parts.append(f"MINVALUE {expr.minvalue}")
        if expr.maxvalue is not None:
            parts.append(f"MAXVALUE {expr.maxvalue}")
        if expr.cycle is not None:
            parts.append("CYCLE" if expr.cycle else "NO CYCLE")
        if expr.cache is not None:
            parts.append(f"CACHE {expr.cache}")
        return " ".join(parts), ()

    def format_create_schema_statement(self, expr: "CreateSchemaExpression") -> Tuple[str, tuple]:
        """Format CREATE SCHEMA for SQL Server.

        SQL Server uses CREATE SCHEMA schema_name [AUTHORIZATION owner_name].
        Does not support IF NOT EXISTS.
        """
        parts = ["CREATE SCHEMA"]
        parts.append(self.format_identifier(expr.schema_name))
        if expr.authorization:
            parts.append(f"AUTHORIZATION {self.format_identifier(expr.authorization)}")
        return " ".join(parts), ()

    def format_drop_schema_statement(self, expr: "DropSchemaExpression") -> Tuple[str, tuple]:
        """Format DROP SCHEMA for SQL Server.

        SQL Server requires schema to be empty before dropping.
        Does not support IF EXISTS or CASCADE.
        """
        parts = ["DROP SCHEMA"]
        parts.append(self.format_identifier(expr.schema_name))
        return " ".join(parts), ()

    def format_truncate_statement(self, expr: "TruncateExpression") -> Tuple[str, tuple]:
        """Format TRUNCATE TABLE for SQL Server.

        TRUNCATE TABLE is a DDL operation (minimal logging).
        Does not support RESTART IDENTITY or CASCADE.
        """
        sql = f"TRUNCATE TABLE {self.format_identifier(expr.table_name)}"
        return sql, ()

    def format_merge_statement(self, expr: "MergeExpression") -> Tuple[str, tuple]:
        """Format MERGE statement for SQL Server (2008+).

        SQL Server MERGE syntax:
        MERGE INTO target USING source ON condition
        WHEN MATCHED [AND condition] THEN UPDATE/DELETE
        WHEN NOT MATCHED [BY TARGET] [AND condition] THEN INSERT
        WHEN NOT MATCHED BY SOURCE [AND condition] THEN UPDATE/DELETE
        """
        from rhosocial.activerecord.backend.expression.statements import MergeActionType

        all_params: list = []

        target_sql, target_params = expr.target_table.to_sql()
        all_params.extend(target_params)

        source_sql, source_params = expr.source.to_sql()
        all_params.extend(source_params)

        on_sql, on_params = expr.on_condition.to_sql()
        all_params.extend(on_params)

        dialect_options = getattr(expr, "dialect_options", {}) or {}
        output_columns = dialect_options.get("output")
        output_action = dialect_options.get("output_action", False)
        holdlock = dialect_options.get("holdlock", False)

        parts = [
            f"MERGE INTO {target_sql}",
            f"USING {source_sql}",
            f"ON {on_sql}",
        ]

        if holdlock and self.supports_merge_holdlock():
            parts[0] = f"MERGE INTO {target_sql} WITH (HOLDLOCK)"

        for action in expr.when_matched:
            action_parts = []
            if action.condition:
                cond_sql, cond_params = action.condition.to_sql()
                action_parts.append(f"WHEN MATCHED AND {cond_sql}")
                all_params.extend(cond_params)
            else:
                action_parts.append("WHEN MATCHED")

            if action.action_type == MergeActionType.UPDATE:
                assignments = []
                for col, as_expr in action.assignments.items():
                    as_sql, as_params = as_expr.to_sql()
                    assignments.append(f"{self.format_identifier(col)} = {as_sql}")
                    all_params.extend(as_params)
                action_parts.append(f"THEN UPDATE SET {', '.join(assignments)}")
            elif action.action_type == MergeActionType.DELETE:
                action_parts.append("THEN DELETE")
            parts.append(" ".join(action_parts))

        for action in expr.when_not_matched:
            action_parts = []
            if action.condition:
                cond_sql, cond_params = action.condition.to_sql()
                action_parts.append(f"WHEN NOT MATCHED AND {cond_sql}")
                all_params.extend(cond_params)
            else:
                action_parts.append("WHEN NOT MATCHED BY TARGET")

            if action.action_type == MergeActionType.INSERT:
                insert_cols, insert_vals = [], []
                for col, val_expr in action.assignments.items():
                    insert_cols.append(self.format_identifier(col))
                    val_sql, val_params = val_expr.to_sql()
                    insert_vals.append(val_sql)
                    all_params.extend(val_params)
                if insert_cols:
                    action_parts.append(
                        f"THEN INSERT ({', '.join(insert_cols)}) VALUES ({', '.join(insert_vals)})"
                    )
                else:
                    action_parts.append("THEN INSERT DEFAULT VALUES")
            parts.append(" ".join(action_parts))

        if output_columns and self.supports_merge_output():
            action_type = "$action" if output_action else None
            output_sql, output_params = self.format_merge_output_clause(
                list(output_columns), action_type=action_type
            )
            parts.append(output_sql)
            all_params.extend(output_params)

        # T-SQL requires a MERGE statement to be terminated by a semi-colon.
        return " ".join(parts) + ";", tuple(all_params)

    def format_set_transaction(self, expr: "SetTransactionExpression") -> Tuple[str, tuple]:
        """Format SET TRANSACTION for SQL Server.

        SQL Server requires SET TRANSACTION ISOLATION LEVEL before BEGIN TRANSACTION.
        """
        from rhosocial.activerecord.backend.errors import UnsupportedTransactionModeError
        from rhosocial.activerecord.backend.transaction import TransactionMode

        params = expr.get_params()
        mode = params.get("mode")

        if mode == TransactionMode.READ_ONLY:
            raise UnsupportedTransactionModeError(
                feature="READ ONLY transactions",
                backend="SQL Server",
                message="SQL Server does not support READ ONLY transactions.",
            )

        isolation_level = params.get("isolation_level")
        if isolation_level:
            level_name = self.get_isolation_level_name(isolation_level)
            return f"SET TRANSACTION ISOLATION LEVEL {level_name}", ()

        return "", ()

    def format_lateral_expression(
        self,
        expr_sql: str,
        expr_params: tuple,
        alias: str,
        join_type: str = "CROSS APPLY",
    ) -> Tuple[str, tuple]:
        """Format LATERAL as CROSS APPLY / OUTER APPLY for SQL Server.

        SQL Server uses CROSS APPLY (equivalent to INNER LATERAL) and
        OUTER APPLY (equivalent to LEFT LATERAL) instead of LATERAL.
        """
        if join_type.upper() in ("LEFT", "LEFT JOIN", "LEFT OUTER JOIN"):
            apply_type = "OUTER APPLY"
        else:
            apply_type = "CROSS APPLY"

        sql = f"{apply_type} ({expr_sql})"
        if alias:
            sql += f" AS {self.format_identifier(alias)}"
        return sql, expr_params

    def format_for_update_clause(self, clause: "ForUpdateClause") -> Tuple[str, tuple]:
        """Format FOR UPDATE for SQL Server using table hints.

        SQL Server does not support FOR UPDATE syntax. Instead, locking
        is achieved through table hints: WITH (UPDLOCK, ROWLOCK) etc.
        """
        all_params: list = []

        sql_parts = ["WITH (UPDLOCK, ROWLOCK)"]

        if clause.skip_locked and self.supports_for_update_skip_locked():
            sql_parts[0] = "WITH (UPDLOCK, ROWLOCK, READPAST)"

        return " ".join(sql_parts), tuple(all_params)

    def format_set_operation_expression(
        self,
        left: "bases.BaseExpression",
        right: "bases.BaseExpression",
        operation: str,
        alias: str,
        all_: bool,
        order_by_clause: "OrderByClause" = None,
        limit_offset_clause: "LimitOffsetClause" = None,
        for_update_clause: "ForUpdateClause" = None,
    ) -> Tuple[str, tuple]:
        """Format set operation for SQL Server.

        SQL Server supports UNION, UNION ALL, INTERSECT, EXCEPT.
        ORDER BY and OFFSET FETCH apply to the entire set operation result.
        """
        left_sql, left_params = left.to_sql()
        right_sql, right_params = right.to_sql()
        all_str = " ALL" if all_ else ""

        base_sql = f"{left_sql} {operation}{all_str} {right_sql}"

        all_params = list(left_params + right_params)

        sql_parts = [base_sql]

        if alias:
            sql_parts.append(f"AS {self.format_identifier(alias)}")

        if order_by_clause:
            order_by_sql, order_by_params = order_by_clause.to_sql()
            sql_parts.append(order_by_sql)
            all_params.extend(order_by_params)

        if limit_offset_clause:
            limit_offset_sql, limit_offset_params = limit_offset_clause.to_sql()
            sql_parts.append(limit_offset_sql)
            all_params.extend(limit_offset_params)

        return " ".join(sql_parts), tuple(all_params)

    def format_alter_table_statement(self, expr: "AlterTableExpression") -> Tuple[str, tuple]:
        """Format ALTER TABLE for SQL Server.

        SQL Server supports:
        - ADD column
        - DROP COLUMN
        - ALTER COLUMN (modify data type)
        - ADD CONSTRAINT (PRIMARY KEY, UNIQUE, CHECK, FOREIGN KEY)
        - DROP CONSTRAINT
        - Single action per ALTER TABLE statement
        """
        all_params: list = []
        parts = [f"ALTER TABLE {self.format_identifier(expr.table_name)}"]

        action_parts = []
        for action in expr.actions:
            action_part, action_params = action.to_sql()
            action_parts.append(action_part)
            all_params.extend(action_params)

        if action_parts:
            parts.append(" ".join(action_parts))

        return " ".join(parts), tuple(all_params)

    def format_function_call(
        self, expr, filter_predicate=None
    ) -> Tuple[str, tuple]:
        """Format a function call, mapping MySQL/generic function names to
        their SQL Server equivalents.

        SQL Server has no NOW(), CURRENT_DATE or CURRENT_TIME:
        - NOW() is replaced by SYSDATETIME()
        - CURRENT_DATE is replaced by CAST(GETDATE() AS DATE)
        - CURRENT_TIME is replaced by CAST(GETDATE() AS TIME)

        SQL Server also has no generic ``LENGTH`` function; it uses ``LEN``.
        Generic JSON operators/functions (``json_extract_text`` etc.) are
        mapped to ``JSON_VALUE`` (see ``format_json_function_expression``).
        """
        name = getattr(expr, "func_name", None)
        if name and name.upper() in self._NILADIC_FUNCTION_EQUIVALENTS:
            sql = self._NILADIC_FUNCTION_EQUIVALENTS[name.upper()]
            return self._apply_value_expression_modifiers(sql, (), expr)
        if name and name.upper() in self._FUNCTION_NAME_EQUIVALENTS:
            renamed_expr = self._clone_with_func_name(expr, self._FUNCTION_NAME_EQUIVALENTS[name.upper()])
            return super().format_function_call(renamed_expr, filter_predicate)
        return super().format_function_call(expr, filter_predicate)

    def _clone_with_func_name(self, expr, new_name: str):
        """Return a shallow copy of ``expr`` with ``func_name`` replaced.

        The base ``format_function_call`` renders ``expr.func_name.upper()``,
        so remapping generic names (e.g. ``LENGTH`` -> ``LEN``) only requires
        a shallow copy with the target name substituted.
        """
        clone = copy.copy(expr)
        clone.func_name = new_name
        return clone

    def format_expression(self, expr) -> Tuple[str, tuple]:
        """Format an arbitrary expression to SQL."""
        if isinstance(expr, BaseExpression):
            return expr.to_sql()
        return str(expr), ()

    def format_fulltext_match(
        self, columns: list, search_string: str, language: str = None
    ) -> Tuple[str, tuple]:
        """Format SQL Server CONTAINS full-text search.

        CONTAINS supports:
        - Simple terms: CONTAINS(column, 'term')
        - Prefix: CONTAINS(column, '"term*"')
        - Proximity: CONTAINS(column, 'NEAR((term1, term2))')
        - Inflectional: CONTAINS(column, 'FORMSOF(INFLECTIONAL, term)')
        - Thesaurus: CONTAINS(column, 'FORMSOF(THESAURUS, term)')
        """
        escaped = search_string.replace("'", "''")
        cols = ", ".join(self.format_identifier(c) if isinstance(c, str) else c for c in columns)

        sql = f"CONTAINS({cols}, '{escaped}'"
        if language:
            sql += f", LANGUAGE '{language}'"
        sql += ")"

        return sql, ()

    def format_top_n_clause(self, n: int, percentage: bool = False) -> str:
        """Format TOP n clause for SQL Server.

        SELECT TOP n / SELECT TOP n PERCENT
        Only valid for SELECT statements.
        """
        if percentage:
            return f"TOP {n} PERCENT"
        return f"TOP {n}"

    def format_query_option_clause(self, clause) -> Tuple[str, tuple]:
        """Format an OPTION query hint clause.

        SQL Server exposes optimizer hints through the query-level OPTION
        clause (available in all versions):

            OPTION (hint1, hint2, ...)

        The clause holds pre-rendered hint strings (see
        ``expression.option_hint`` factories such as ``recompile_hint``,
        ``maxdop_hint``, and ``optimize_for_hint``).
        """
        return f"OPTION ({', '.join(clause.hints)})", ()


def _register_partition_formatters():
    from .mixins.partition import SQLServerPartitionMixin

    for member_name in dir(SQLServerPartitionMixin):
        if member_name.startswith(("supports_", "format_")):
            member = getattr(SQLServerPartitionMixin, member_name)
            if callable(member):
                setattr(SQLServerDialect, member_name, member)


_register_partition_formatters()
