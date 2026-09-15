# src/rhosocial/activerecord/backend/impl/sqlserver/dialect.py
"""
SQL Server backend SQL dialect implementation.

This dialect implements protocols for features that SQL Server actually supports,
based on the SQL Server version provided at initialization.
"""

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
import copy

from rhosocial.activerecord.backend.dialect.base import SQLDialectBase
from rhosocial.activerecord.backend.expression import bases
from rhosocial.activerecord.backend.expression.bases import BaseExpression, ToSQLProtocol
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
    DDLTypeSupport,
)
from .protocols import (
    SQLServerTableSupport,
    SQLServerLockingSupport,
    SQLServerJSONSupport,
    SQLServerSetTypeSupport,
    SQLServerSpatialSupport,
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
    WindowFunctionMixin,
    JSONMixin,
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
    PredicateMixin,
    ExpressionMixin,
    DateTimeMixin,
    DQLMixin,
    DMLMixin,
    DDLColumnMixin,
    DDLTypeMixin,
    FilterClauseMixin,
    TransactionControlMixin,
    AutoIncrementMixin,
    GeneratedColumnMixin,
    TriggerMixin,
    PartitionMixin,
    ILIKEMixin,
    FunctionMixin,
)
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
from .mixins.datetime import SQLServerDateTimeMixin
from .mixins.collation import SQLServerCollationMixin
from .mixins.cte import SQLServerCTEMixin
from .mixins.returning import SQLServerReturningMixin
from .mixins.constraint import SQLServerConstraintMixin
from .mixins.window import SQLServerWindowMixin
from .mixins.json import SQLServerJSONMixin
from .mixins.grouping import SQLServerGroupingMixin
from .mixins.locking import SQLServerLockingMixin
from .mixins.merge import SQLServerMergeMixin
from .mixins.temporal import SQLServerTemporalMixin
from .mixins.upsert import SQLServerUpsertMixin
from .mixins.lateral import SQLServerLateralMixin
from .mixins.explain import SQLServerExplainMixin
from .mixins.dql import SQLServerDQLMixin
from .mixins.dml import SQLServerDMLMixin
from .mixins.ddl_view import SQLServerViewMixin
from .mixins.schema import SQLServerSchemaMixin
from .mixins.index import SQLServerIndexMixin
from .mixins.generated_column import SQLServerGeneratedColumnMixin
from .mixins.set_operation import SQLServerSetOperationMixin
from .mixins.ddl_table import SQLServerTableMixin
from .mixins.identifier import SQLServerIdentifierMixin
from .mixins.transaction import SQLServerTransactionMixin
from .mixins.function import SQLServerFunctionMixin
from .mixins.version_constants import (
    SQL_SERVER_2005,
    SQL_SERVER_2008,
    SQL_SERVER_2012,
    SQL_SERVER_2014,
    SQL_SERVER_2016,
    SQL_SERVER_2017,
    SQL_SERVER_2019,
    SQL_SERVER_2022,
)
from .reserved_words import SQLSERVER_RESERVED_WORDS
# SQLServerPartitionMixin is registered lazily in _register_partition_formatters()

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression import bases
    from rhosocial.activerecord.backend.expression.collation import CollateExpression
    from rhosocial.activerecord.backend.expression.advanced_functions import ArrayExpression, OrderedSetAggregation
    from rhosocial.activerecord.backend.expression.graph import MatchClause
    from rhosocial.activerecord.backend.expression.query_parts import (
        LimitOffsetClause,
        ForUpdateClause,
        QualifyClause,
    )
    from rhosocial.activerecord.backend.expression.statements import (
        ExplainExpression,
        CreateViewExpression,
        DropViewExpression,
        CreateMaterializedViewExpression,
        ReturningClause,
        InsertExpression,
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
    from rhosocial.activerecord.backend.expression.statements.fulltext_match import (
        FulltextMatchExpression,
    )


_SUGGESTION_ARRAY_TYPES = "SQL Server does not support native array types. Consider using JSON or comma-separated values."
_SUGGESTION_JSON_TABLE = "SQL Server uses OPENJSON for JSON table functionality (2016+)."
_SUGGESTION_GRAPH_MATCH = "SQL Server does not support graph MATCH clause."
_SUGGESTION_ORDERED_SET_AGG = "SQL Server does not support ordered-set aggregate functions (WITHIN GROUP)."
_SUGGESTION_QUALIFY = "SQL Server does not support QUALIFY clause. Use a subquery or CTE instead."


class SQLServerDialect(
    SQLDialectBase,
    # Core infrastructure mixins (provide base implementations
    # that the dialect overrides as needed)
    PredicateMixin,
    ExpressionMixin,
    # SQL Server-specific mixins (must precede their global counterparts
    # to ensure SQL Server methods take precedence in MRO)
    SQLServerAlterColumnModifierMixin,  # Before DDLColumnMixin to override format_*_action
    SQLServerProtocolSupportMixin,  # SQL Server protocol contract implementations
    SQLServerSequenceMixin,  # NEXT VALUE FOR formatter (2012+)
    SQLServerPivotMixin,  # PIVOT / UNPIVOT formatters (2005+)
    SQLServerColumnstoreIndexMixin,  # columnstore index DDL (2012+/2014+/2022+)
    SQLServerMemoryOptimizedMixin,  # In-Memory OLTP table options (2014+)
    SQLServerRoutineMixin,  # PROCEDURE / FUNCTION DDL (2005+)
    SQLServerTriggerDdlMixin,  # TRIGGER DDL (2005+)
    DDLColumnMixin,
    DDLTypeMixin,
    SQLServerIdentifierMixin,
    SQLServerCollationMixin,
    CollationMixin,
    SQLServerCTEMixin,
    SQLServerWindowMixin,
    SQLServerJSONMixin,
    SQLServerReturningMixin,
    SQLServerConstraintMixin,
    SQLServerGroupingMixin,
    SQLServerLockingMixin,
    SQLServerMergeMixin,
    SQLServerTemporalMixin,
    SQLServerUpsertMixin,
    SQLServerLateralMixin,
    SQLServerExplainMixin,
    SQLServerDQLMixin,
    SQLServerDMLMixin,
    SQLServerViewMixin,
    SQLServerSchemaMixin,
    SQLServerIndexMixin,
    SQLServerGeneratedColumnMixin,
    SQLServerSetOperationMixin,
    SQLServerTableMixin,
    SQLServerTransactionMixin,
    SQLServerFunctionMixin,
    SQLServerDateTimeMixin,
    # Global feature mixins (after SQL Server mixins so SQL Server methods win)
    DateTimeMixin,
    DQLMixin,
    DMLMixin,
    CTEMixin,
    WindowFunctionMixin,
    JSONMixin,
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
    # Newly added global mixins (previously missing from inheritance)
    FilterClauseMixin,
    TransactionControlMixin,
    AutoIncrementMixin,
    GeneratedColumnMixin,
    TriggerMixin,
    PartitionMixin,
    ILIKEMixin,
    FunctionMixin,
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
    # DataType Support Protocol
    DDLTypeSupport,
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
    SQLServerSetTypeSupport,
    SQLServerSpatialSupport,
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

    def format_identifier(self, identifier: str, need_quote: bool = True) -> str:
        """Format an identifier with SQL Server square brackets.

        Declared on the dialect so it is not shadowed by ``SQLDialectBase``
        (double quotes), which precedes the feature mixins in the MRO.
        """
        return SQLServerIdentifierMixin.format_identifier(self, identifier, need_quote)

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
        self._reserved_words = SQLSERVER_RESERVED_WORDS
        if version is not None:
            self.version = version

    def get_server_version(self) -> Tuple[int, int, int]:
        """Return the SQL Server version this dialect is configured for."""
        return self.version

    def create_schema_differ(self):
        """Return the SQL Server schema differ (ordinal-position aware)."""
        from rhosocial.activerecord.backend.impl.sqlserver.schema.differ import (
            SQLServerSchemaDiffer,
        )

        return SQLServerSchemaDiffer()

    def format_auto_increment(self) -> Tuple[str, tuple]:
        """Return IDENTITY(1,1) for auto-increment columns."""
        return "IDENTITY(1,1)", ()

    def format_array_expression(self, _expr: "ArrayExpression") -> Tuple[str, tuple]:
        """Format array expression - not supported."""
        raise UnsupportedFeatureError(self.name, "Array operations", _SUGGESTION_ARRAY_TYPES)

    def format_json_table_expression(self, _expr: "BaseExpression") -> Tuple[str, tuple]:
        """Format JSON_TABLE - SQL Server uses OPENJSON."""
        raise UnsupportedFeatureError(self.name, "JSON_TABLE", _SUGGESTION_JSON_TABLE)

    def format_match_clause(self, _clause: "MatchClause") -> Tuple[str, tuple]:
        """Format MATCH clause - not supported."""
        raise UnsupportedFeatureError(self.name, "graph MATCH clause", _SUGGESTION_GRAPH_MATCH)

    def format_ordered_set_aggregation(self, _aggregation: "OrderedSetAggregation") -> Tuple[str, tuple]:
        """Format ordered-set aggregation - not supported."""
        raise UnsupportedFeatureError(self.name, "ordered-set aggregate functions", _SUGGESTION_ORDERED_SET_AGG)

    def format_qualify_clause(self, _clause: "QualifyClause") -> Tuple[str, tuple]:
        """Format QUALIFY clause - not supported."""
        raise UnsupportedFeatureError(self.name, "QUALIFY clause", _SUGGESTION_QUALIFY)

    def format_grouping_clause(
        self, expr: "bases.BaseExpression"
    ) -> Tuple[str, tuple]:
        """Format grouping clause (ROLLUP, CUBE, GROUPING SETS)."""
        from rhosocial.activerecord.backend.expression.query_parts import GroupingClause
        if not isinstance(expr, GroupingClause):
            raise TypeError(f"Expected GroupingClause, got {type(expr)}")
        operation = expr.operation
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

        SQL Server doesn't support IF NOT EXISTS syntax for CREATE TABLE
        (until SQL Server 2016 for DROP, but not CREATE). When if_not_exists
        is True, we simply skip the IF NOT EXISTS clause since it's not supported.
        SQL Server has no CREATE TABLE ... LIKE (``supports_create_table_like``
        stays ``False``), so the gated
        ``format_create_table_like_statement`` raises
        ``UnsupportedFeatureError``. Temporary tables use a ``#``-prefixed
        table name instead of the ``TEMPORARY`` keyword.
        """
        all_params: List[Any] = []

        dialect_options = getattr(expr, "dialect_options", {}) or {}

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

        column_parts = []
        for col_def in expr.columns:
            col_sql, col_params = self.format_column_definition(col_def)
            column_parts.append(col_sql)
            all_params.extend(col_params)

        for t_const in expr.table_constraints:
            const_sql, const_params = self.format_table_constraint(t_const)
            if const_sql:
                column_parts.append(const_sql)
                all_params.extend(const_params)

        for idx_def in expr.indexes:
            idx_sql, idx_params = self.format_inline_index(idx_def)
            column_parts.append(idx_sql)
            all_params.extend(idx_params)

        parts.append(f"({', '.join(column_parts)})")

        if expr.partition is not None:
            partition_sql, partition_params = expr.partition.to_sql()
            parts.append(partition_sql)
            all_params.extend(partition_params)

        table_options = getattr(expr, "table_options", None)
        memory_optimized = getattr(table_options, "memory_optimized", None) if table_options else None
        if memory_optimized is None:
            memory_optimized = dialect_options.get("memory_optimized")
        if memory_optimized:
            durability = getattr(table_options, "durability", None) if table_options else None
            if durability is None:
                durability = dialect_options.get("durability", "SCHEMA_ONLY")
            parts.append(self.format_memory_optimized_option(durability))

        return ' '.join(parts), tuple(all_params)

    def format_column_definition(self, col_def: "ColumnDefinition") -> Tuple[str, tuple]:
        """Format a column definition for SQL Server."""
        from rhosocial.activerecord.backend.expression.statements import (
            ColumnConstraintType,
        )
        type_sql, type_params = col_def.data_type.to_sql()
        parts = [self.format_identifier(col_def.name), type_sql]
        params: List[Any] = list(type_params)

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

            if constraint.is_auto_increment:
                constraint_parts.append("IDENTITY(1,1)")

        if constraint_parts:
            parts.append(' '.join(constraint_parts))

        return ' '.join(parts), tuple(params)

    def format_table_constraint(self, t_const: "TableConstraint") -> Tuple[str, tuple]:
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

        return ' '.join(parts), tuple(params)

    def format_inline_index(self, idx_def: "IndexDefinition") -> Tuple[str, tuple]:
        """Format an inline index definition for SQL Server."""
        parts = []

        if idx_def.unique:
            parts.append("UNIQUE")

        parts.append("INDEX")
        parts.append(self.format_identifier(idx_def.name))

        col_parts = []
        for col in idx_def.columns:
            if isinstance(col, ToSQLProtocol):
                col_sql, col_params = col.to_sql()
                col_parts.append(col_sql)
            else:
                col_parts.append(self.format_identifier(str(col)))
        cols_str = ', '.join(col_parts)

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

        return ' '.join(parts), ()

    def format_create_index_statement(self, expr: "CreateIndexExpression") -> Tuple[str, tuple]:
        """Format CREATE INDEX statement for SQL Server.

        SQL Server doesn't support IF NOT EXISTS for CREATE INDEX.
        We ignore the if_not_exists flag and generate standard CREATE INDEX.
        """
        all_params = []
        parts = ["CREATE"]

        if expr.unique:
            parts.append("UNIQUE")

        if hasattr(expr, 'index_type') and expr.index_type:
            index_type = expr.index_type.upper()
            if index_type in ('CLUSTERED', 'NONCLUSTERED'):
                parts.append(index_type)

        parts.append("INDEX")
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

        if expr.include:
            include_cols = ", ".join(self.format_identifier(c) for c in expr.include)
            parts.append(f"INCLUDE ({include_cols})")

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

    def format_function_call(self, expr: "bases.BaseExpression") -> Tuple[str, tuple]:
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
            return self.apply_alias(sql, (), expr)
        if name and name.upper() in self._FUNCTION_NAME_EQUIVALENTS:
            renamed_expr = self._clone_with_func_name(expr, self._FUNCTION_NAME_EQUIVALENTS[name.upper()])
            return super().format_function_call(renamed_expr)
        return super().format_function_call(expr)

    def _clone_with_func_name(self, expr: "bases.BaseExpression", new_name: str) -> "bases.BaseExpression":
        """Return a shallow copy of ``expr`` with ``func_name`` replaced.

        The base ``format_function_call`` renders ``expr.func_name.upper()``,
        so remapping generic names (e.g. ``LENGTH`` -> ``LEN``) only requires
        a shallow copy with the target name substituted.
        """
        clone = copy.copy(expr)
        clone.func_name = new_name
        return clone

    def format_expression(self, expr: Any) -> Tuple[str, tuple]:
        """Format an arbitrary expression to SQL."""
        if isinstance(expr, BaseExpression):
            return expr.to_sql()
        return str(expr), ()

    def format_fulltext_match(
        self, expr: "FulltextMatchExpression"
    ) -> Tuple[str, tuple]:
        """Format SQL Server CONTAINS full-text search.

        CONTAINS supports:
        - Simple terms: CONTAINS(column, 'term')
        - Prefix: CONTAINS(column, '"term*"')
        - Proximity: CONTAINS(column, 'NEAR((term1, term2))')
        - Inflectional: CONTAINS(column, 'FORMSOF(INFLECTIONAL, term)')
        - Thesaurus: CONTAINS(column, 'FORMSOF(THESAURUS, term)')
        """
        columns = expr.columns
        search_term = expr.search_term
        language = expr.mode

        escaped = search_term.replace("'", "''")
        cols = ", ".join(c.to_sql()[0] if hasattr(c, 'to_sql') else self.format_identifier(c) for c in columns)

        sql = f"CONTAINS({cols}, '{escaped}'"
        if language:
            sql += f", LANGUAGE '{language}'"
        sql += ")"

        return sql, ()

    def format_top_n_clause(self, n: int, percentage: bool = False) -> Tuple[str, tuple]:
        """Format TOP n clause for SQL Server.

        SELECT TOP n / SELECT TOP n PERCENT
        Only valid for SELECT statements.
        """
        if percentage:
            return f"TOP {n} PERCENT", ()
        return f"TOP {n}", ()

    def format_query_option_clause(self, clause: "bases.BaseExpression") -> Tuple[str, tuple]:
        """Format an OPTION query hint clause.

        SQL Server exposes optimizer hints through the query-level OPTION
        clause (available in all versions):

            OPTION (hint1, hint2, ...)

        The clause holds pre-rendered hint strings (see
        ``expression.option_hint`` factories such as ``recompile_hint``,
        ``maxdop_hint``, and ``optimize_for_hint``).
        """
        return f"OPTION ({', '.join(clause.hints)})", ()

    # ------------------------------------------------------------------
    # DataType protocol — suggestions
    # ------------------------------------------------------------------

    def suggested_data_types(self) -> Dict[str, type]:
        """Types SQL Server does not natively support, with best-effort replacements.

        Returns a mapping ``{<generic name>: DataType class}`` for every
        core type that has **no** ``format_data_type_<name>`` on this
        dialect.  Keys are disjoint from ``supports_data_types()``.
        """
        from rhosocial.activerecord.backend.expression.types import (
            UUIDType,
            IntervalType,
            ArrayType,
            EnumType,
            JsonBType,
            TimestampTzType,
            TimeTzType,
        )
        return {
            "uuid": UUIDType,
            "interval": IntervalType,
            "array": ArrayType,
            "enum": EnumType,
            "jsonb": JsonBType,
            "timestamptz": TimestampTzType,
            "timetz": TimeTzType,
        }


# Lazy import to avoid circular dependency (backend → dialect → mixins.types → backend)
def _register_type_formatters():
    """Copy ``format_data_type_*`` / ``supports_data_type_*`` / ``parse_type``
    methods from the mixin to the dialect class so that the naming-convention
    dispatch in ``DDLTypeMixin.format_data_type()`` and
    ``DDLTypeMixin.supports_data_types()`` find them.

    Also copies the ``_SQLSERVER_*`` regex class attributes needed by
    ``parse_type`` at runtime.
    """
    from .mixins.types import SQLServerTypeSupportMixin

    for member_name in dir(SQLServerTypeSupportMixin):
        if (member_name.startswith("format_data_type_")
                or member_name.startswith("supports_data_type_")
                or member_name == "parse_type"):
            member = getattr(SQLServerTypeSupportMixin, member_name, None)
            if callable(member):
                setattr(SQLServerDialect, member_name, member)

    for attr_name in dir(SQLServerTypeSupportMixin):
        if attr_name.startswith("_SQLSERVER_"):
            val = getattr(SQLServerTypeSupportMixin, attr_name, None)
            if val is not None and not callable(val):
                setattr(SQLServerDialect, attr_name, val)


def _register_partition_formatters():
    from .mixins.partition import SQLServerPartitionMixin

    for member_name in dir(SQLServerPartitionMixin):
        if member_name.startswith(("supports_", "format_")):
            member = getattr(SQLServerPartitionMixin, member_name)
            if callable(member):
                setattr(SQLServerDialect, member_name, member)


_register_type_formatters()
_register_partition_formatters()
