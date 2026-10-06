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
from rhosocial.activerecord.backend.expression.objects import Index, Sequence, Table
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
    SetOperationSupport,
    TruncateSupport,
    NamespaceSupport,
    TableObjectSupport,
    ViewObjectSupport,
    MaterializedViewObjectSupport,
    ForeignTableObjectSupport,
    IndexObjectSupport,
    SequenceObjectSupport,
    TriggerObjectSupport,
    RoutineObjectSupport,
    TypeObjectSupport,
    SynonymObjectSupport,
    ConstraintSupport,
    IntrospectionSupport,
    TransactionControlSupport,
    SQLFunctionSupport,
    DDLTypeSupport,
    CreateTypeSupport,
    DropTypeSupport,
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
    SQLServerGraphSupport,
    SQLServerMergeSupport,
    SQLServerPartitionSupport,
    SQLServerOutputSupport,
    SQLServerTableHintSupport,
    SQLServerTryCastSupport,
    SQLServerIdentitySupport,
    SQLServerIndexedViewSupport,
    SQLServerUserDefinedTypeSupport,
)
from rhosocial.activerecord.backend.dialect.mixins import (
    CollationMixin,
    CTEMixin,
    # Named objects: each *NameMixin renders one object kind through
    # NamespaceMixin.format_qualified_name, so they precede it. A statement that
    # now holds an object -- CREATE INDEX's index and table, TRUNCATE's table --
    # has nowhere else to render it.
    TableNameMixin,
    ViewNameMixin,
    MaterializedViewNameMixin,
    ForeignTableNameMixin,
    IndexNameMixin,
    SequenceNameMixin,
    TriggerNameMixin,
    FunctionNameMixin,
    ProcedureNameMixin,
    TypeNameMixin,
    DomainNameMixin,
    SynonymNameMixin,
    SchemaNameMixin,
    DatabaseNameMixin,
    PropertyGraphNameMixin,
    # NamespaceMixin itself: what every *NameMixin above falls back on, and
    # what SQLServerNamespaceMixin refines.
    NamespaceMixin,
    WindowFunctionMixin,
    JSONMixin,

    ArrayMixin,
    ExplainMixin,
    GraphMixin,

    MergeMixin,

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
    UserDefinedTypeMixin,

    TransactionControlMixin,
    AutoIncrementMixin,
    GeneratedColumnMixin,
    TriggerMixin,
    PartitionMixin,
    ILIKEMixin,
    FunctionMixin,
    # The FROM side of a named object: an alias and a temporal clause, which the
    # relation itself has no room for. The name comes from the relation.
    RelationSourceMixin,
)
from rhosocial.activerecord.backend.dialect.protocols import PartitionSupport
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from .collation import validate_sqlserver_collation_name
from .alter_table_modifier import SQLServerAlterColumnModifierMixin
from .mixins.sequence import SQLServerSequenceMixin
from .mixins.pivot import SQLServerPivotMixin
from .mixins.graph import SQLServerGraphMixin
from .mixins.columnstore import SQLServerColumnstoreIndexMixin
from .mixins.memory_optimized import SQLServerMemoryOptimizedMixin
from .mixins.ddl_type import SQLServerTypeDDLMixin
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
from .mixins.ddl_database import SQLServerDatabaseMixin
from .mixins.schema import SQLServerSchemaMixin
from .mixins.index import SQLServerIndexMixin
from .mixins.generated_column import SQLServerGeneratedColumnMixin
from .mixins.set_operation import SQLServerSetOperationMixin
from .mixins.ddl_table import SQLServerTableMixin
from .mixins.namespace import SQLServerNamespaceMixin
from .mixins.identifier import SQLServerIdentifierMixin
from .expression.objects import SQLServerTable
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
        CreateIndexExpression,
        DropTableExpression,
        CreateSchemaExpression,
        DropSchemaExpression,
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
_SUGGESTION_GRAPH_MATCH = (
    "SQL Server does not support the SQL/PGQ MATCH clause. Use its own SQL Graph API "
    "(CREATE TABLE ... AS NODE/AS EDGE + SQLServerMatchPredicate) instead."
)
_SUGGESTION_ORDERED_SET_AGG = "SQL Server does not support ordered-set aggregate functions (WITHIN GROUP)."
_SUGGESTION_QUALIFY = "SQL Server does not support QUALIFY clause. Use a subquery or CTE instead."


class SQLServerDialect(
    # ``SQLDialectBase`` quotes identifiers with double quotes. Python resolves
    # base classes left to right, so the bracket-quoting mixin has to precede it
    # to win. This is also why the dialect body declares no ``format_identifier``
    # of its own: there is exactly one, and it lives in the mixin.
    SQLServerIdentifierMixin,
    # Which namespace levels a name carries, and what SQL Server will accept as
    # one. The per-kind rendering lives in the core *NameMixin classes listed
    # below, which is where every object kind is spelled.
    SQLServerNamespaceMixin,
    # A JOIN side is a row source, not an object: it carries the alias the
    # object has no room for, and renders the relation's name through that
    # relation's own format_<kind>_object.
    RelationSourceMixin,
    # One renderer per object kind. Each inherits NamespaceMixin, which is what
    # SQLServerNamespaceMixin refines, so they follow it here and precede it in
    # the MRO -- and a statement that holds a Table or an Index has somewhere to
    # render it without a formatter of its own.
    TableNameMixin,
    ViewNameMixin,
    MaterializedViewNameMixin,
    ForeignTableNameMixin,
    IndexNameMixin,
    SequenceNameMixin,
    TriggerNameMixin,
    FunctionNameMixin,
    ProcedureNameMixin,
    TypeNameMixin,
    DomainNameMixin,
    SynonymNameMixin,
    SchemaNameMixin,
    DatabaseNameMixin,
    PropertyGraphNameMixin,
    # NamespaceMixin itself: the base every *NameMixin above falls back on,
    # and the one SQLServerNamespaceMixin refines.
    NamespaceMixin,
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
    SQLServerGraphMixin,  # SQL Graph: node/edge tables + MATCH predicate (2017+/2019+)
    SQLServerColumnstoreIndexMixin,  # columnstore index DDL (2012+/2014+/2022+)
    SQLServerMemoryOptimizedMixin,  # In-Memory OLTP table options (2014+)
    SQLServerRoutineMixin,  # PROCEDURE / FUNCTION DDL (2005+)
    SQLServerTriggerDdlMixin,  # TRIGGER DDL (2005+)
    SQLServerTypeDDLMixin,
    DDLColumnMixin,
    DDLTypeMixin,
    UserDefinedTypeMixin,
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
    SQLServerDatabaseMixin,
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

    ArrayMixin,
    ExplainMixin,
    GraphMixin,

    MergeMixin,

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
    SetOperationSupport,
    TruncateSupport,
    # The object protocols: one per kind, each naming its format_<kind>_object
    # method and inheriting NamespaceSupport, so a subclass precedes its base and
    # NamespaceSupport follows every one of them. SQL Server has all three
    # namespace levels and renders every one of them, which is what
    # NamespaceSupport says.
    SQLServerTableSupport,  # Before TableObjectSupport (subclass precedes base)
    TableObjectSupport,
    ViewObjectSupport,
    MaterializedViewObjectSupport,
    ForeignTableObjectSupport,
    IndexObjectSupport,
    SequenceObjectSupport,
    TriggerObjectSupport,
    RoutineObjectSupport,
    TypeObjectSupport,
    SynonymObjectSupport,
    NamespaceSupport,
    ConstraintSupport,
    IntrospectionSupport,
    TransactionControlSupport,
    SQLFunctionSupport,
    # DataType Support Protocol
    DDLTypeSupport,
    # TYPE DDL: SQL Server has CREATE TYPE and DROP TYPE but no ALTER TYPE.
    SQLServerUserDefinedTypeSupport,  # Before its core bases (subclass precedes base)
    CreateTypeSupport,
    DropTypeSupport,
    # SQL Server-specific protocols (marker classes for isinstance() checks;
    # implementations live in SQLServerProtocolSupportMixin / SQLServerSequenceMixin)
    SQLServerOutputSupport,
    SQLServerPaginationSupport,
    SQLServerGraphSupport,
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

    def __init__(
        self,
        version: Optional[Tuple[int, int, int]] = None,
        *,
        deployment_target: str = "sqlserver",
    ) -> None:
        """
        Initialize SQL Server dialect with specific version.

        Args:
            version: SQL Server version tuple (major, minor, patch).
                If None, the dialect must be adapted via
                backend.introspect_and_adapt() before version-dependent
                features can be used.
            deployment_target: Deployment target label used for CLR capability
                gating; the default is on-premises SQL Server.
        """
        super().__init__()
        self._reserved_words = SQLSERVER_RESERVED_WORDS
        self.deployment_target = deployment_target
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
        ``UnsupportedFeatureError``.

        ``expr.table`` is already the object being named, so the only decision
        left here is whether it is the temporary form: SQL Server spells a
        temporary table by prefixing its *name* with ``#``, which is a fact
        about the table rather than a rendering choice. Both places the name
        appears -- the ``OBJECT_ID`` guard and the ``CREATE TABLE`` header --
        then render that one object, so the temporary and ordinary paths cannot
        disagree about what they named.

        Raises:
            TypeError: ``expr.table`` is not a Table. A view or an index handed
                here would render as a well-formed ``CREATE TABLE`` over that
                object's name, because the object carries its own
                ``format_method`` and the dialect has no other way to tell.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        if not isinstance(expr.table, Table):
            raise TypeError(
                f"CreateTableExpression.table must be a Table, "
                f"got {type(expr.table).__name__}"
            )
        if getattr(expr, "tablespace", None):
            raise UnsupportedFeatureError(
                self.name,
                "TABLESPACE",
                "SQL Server does not support table tablespaces.",
            )
        if getattr(expr, "inherits", None):
            raise UnsupportedFeatureError(
                self.name,
                "table INHERITS",
                "SQL Server does not support table inheritance.",
            )
        if getattr(getattr(expr, "table_options", None), "comment", None):
            # SQL Server has no inline table comment (its native
            # mechanism is sp_addextendedproperty, not implemented here); a
            # comment on the table options is never silently dropped.
            raise UnsupportedFeatureError(
                self.name, "TABLE COMMENT",
                "SQL Server has no inline table comment; comments are "
                "annotated through sp_addextendedproperty (not implemented).",
            )

        # The caller may hand over a plain ``Table`` even for a temporary, so
        # the temporary form is settled here: one ``SQLServerTable`` whose name
        # already carries the ``#``. Nothing below reads ``expr.temporary``
        # again.
        table = expr.table
        if expr.temporary and not isinstance(table, SQLServerTable):
            table = SQLServerTable(
                self,
                table.name,
                catalog_name=table.catalog_name,
                schema_name=table.schema_name,
                catalog_need_quote=table.catalog_need_quote,
                schema_need_quote=table.schema_need_quote,
                name_need_quote=table.name_need_quote,
                temporary=True,
            )

        if_not_exists_guard = ""
        if expr.if_not_exists:
            # SQL Server has no CREATE TABLE IF NOT EXISTS syntax; the
            # idempotent form is the IF OBJECT_ID(...) IS NULL batch guard.
            # OBJECT_ID names an object rather than quoting an identifier, so
            # this is the one unbracketed shape -- see format_object_id_name.
            target = self.format_object_id_name(table).replace("'", "''")
            if_not_exists_guard = f"IF OBJECT_ID(N'{target}', N'U') IS NULL\n"
        all_params: List[Any] = []

        parts = ["CREATE TABLE"]

        table_sql, table_params = table.to_sql()
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

        # SQL Graph edge constraints (CONNECTION) are table-level constraints.
        edge_constraints = getattr(expr, "edge_constraints", None)
        if edge_constraints:
            for edge_constraint in edge_constraints:
                ec_sql, ec_params = edge_constraint.to_sql()
                column_parts.append(ec_sql)
                all_params.extend(ec_params)

        parts.append(f"({', '.join(column_parts)})")

        if expr.partition is not None:
            partition_sql, partition_params = expr.partition.to_sql()
            parts.append(partition_sql)
            all_params.extend(partition_params)

        from .expression.table_options import SQLServerCreateTableOptions
        table_options = getattr(expr, "table_options", None)
        if isinstance(table_options, SQLServerCreateTableOptions) and table_options.memory_optimized:
            durability = table_options.durability or "SCHEMA_ONLY"
            parts.append(self.format_memory_optimized_option(durability))

        # SQL Graph table kind (AS NODE / AS EDGE), if requested.
        graph_kind = getattr(expr, "graph_table_kind", None)
        if graph_kind is not None:
            from .expression.ddl.graph import (
                SQLServerAsGraphTableExpression,
                SQLServerGraphTableKind,
            )

            if isinstance(graph_kind, SQLServerGraphTableKind):
                graph_kind = SQLServerAsGraphTableExpression(self, graph_kind)
            kind_sql, kind_params = graph_kind.to_sql()
            parts.append(kind_sql)
            all_params.extend(kind_params)

        return if_not_exists_guard + ' '.join(parts), tuple(all_params)

    def format_identity_clause(self, expr) -> Tuple[str, tuple]:
        """SQL Server renders identity as ``IDENTITY(seed, increment)``."""
        seed = expr.start if expr.start is not None else 1
        increment = expr.increment if expr.increment is not None else 1
        return f" IDENTITY({seed}, {increment})", ()

    def format_column_definition(
        self,
        col_def: "ColumnDefinition",
        *,
        memory_optimized: bool = False,
    ) -> Tuple[str, tuple]:
        """Format a column definition for SQL Server.

        Accepts both the generic ``ColumnDefinition`` and the SQL Server
        ``SQLServerColumnDefinition``; the latter's SQL Server-only attributes
        (``sparse`` / ``rowguidcol``) are rendered here.
        """
        from rhosocial.activerecord.backend.expression.statements import (
            ColumnConstraintType,
        )
        from rhosocial.activerecord.backend.impl.sqlserver.expression.column import (
            SQLServerColumnDefinition,
        )
        if getattr(col_def, "comment", None):
            # SQL Server has no inline column comment (its native
            # mechanism is sp_addextendedproperty, not implemented here); a
            # comment on a column definition is never silently dropped.
            from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
            raise UnsupportedFeatureError(
                self.name, "COLUMN COMMENT",
                "SQL Server has no inline column comment; comments are "
                "annotated through sp_addextendedproperty (not implemented).",
            )
        type_sql, type_params = col_def.data_type.to_sql()
        parts = [self.format_identifier(col_def.name), type_sql]
        params: List[Any] = list(type_params)

        constraint_parts = []
        for constraint in col_def.constraints:
            if constraint.constraint_type == ColumnConstraintType.PRIMARY_KEY:
                constraint_parts.append(
                    "PRIMARY KEY NONCLUSTERED" if memory_optimized else "PRIMARY KEY"
                )
            elif constraint.constraint_type == ColumnConstraintType.NOT_NULL:
                constraint_parts.append("NOT NULL")
            elif constraint.constraint_type == ColumnConstraintType.UNIQUE:
                constraint_parts.append("UNIQUE NONCLUSTERED" if memory_optimized else "UNIQUE")
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
            elif constraint.constraint_type == ColumnConstraintType.CHECK:
                if constraint.check_condition is None:
                    raise ValueError("CHECK constraint must have a check condition")
                check_sql, check_params = constraint.check_condition.to_sql()
                constraint_parts.append(f"CHECK ({check_sql})")
                params.extend(check_params)

            if constraint.is_auto_increment:
                constraint_parts.append("IDENTITY(1,1)")

        if constraint_parts:
            parts.append(' '.join(constraint_parts))

        attr_sql, attr_params = self.format_column_attributes(col_def)
        if attr_sql:
            parts.append(attr_sql.strip())
        params.extend(attr_params)

        if col_def.generated_expression is not None:
            gen_sql, gen_params = col_def.generated_expression.to_sql()
            parts.append(gen_sql.lstrip())
            params.extend(gen_params)

        if isinstance(col_def, SQLServerColumnDefinition):
            if col_def.rowguidcol:
                parts.append("ROWGUIDCOL")
            if col_def.sparse:
                parts.append("SPARSE")

        return ' '.join(parts), tuple(params)

    def format_table_constraint(
        self,
        t_const: "TableConstraint",
        *,
        memory_optimized: bool = False,
    ) -> Tuple[str, tuple]:
        """Format a table constraint for SQL Server.

        The memory-optimized variants are why this overrides core's formatter at
        all: ``PRIMARY KEY NONCLUSTERED`` and ``UNIQUE NONCLUSTERED`` are the
        spellings a memory-optimized table needs.

        Raises:
            TypeError: ``t_const.foreign_key_table`` is not a Table. Another
                object kind would have had its own name rendered as the
                referenced relation, because the constraint renders that slot
                through ``to_sql()``.
        """
        if t_const.foreign_key_table is not None and not isinstance(
            t_const.foreign_key_table, Table
        ):
            raise TypeError(
                f"TableConstraint.foreign_key_table must be a Table, "
                f"got {type(t_const.foreign_key_table).__name__}"
            )
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
                if memory_optimized:
                    parts.append(f"PRIMARY KEY NONCLUSTERED ({cols_str})")
                else:
                    parts.append(f"PRIMARY KEY ({cols_str})")
        elif t_const.constraint_type == TableConstraintType.UNIQUE:
            if t_const.columns:
                cols_str = ', '.join(self.format_identifier(c) for c in t_const.columns)
                if memory_optimized:
                    parts.append(f"UNIQUE NONCLUSTERED ({cols_str})")
                else:
                    parts.append(f"UNIQUE ({cols_str})")
        elif t_const.constraint_type == TableConstraintType.FOREIGN_KEY:
            if t_const.columns and t_const.foreign_key_table and t_const.foreign_key_columns:
                cols_str = ', '.join(self.format_identifier(c) for c in t_const.columns)
                ref_cols_str = ', '.join(
                    self.format_identifier(c) for c in t_const.foreign_key_columns
                )
                ref_table = t_const.foreign_key_table.to_sql()[0]
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
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        for option, value in (
            ("if_not_exists", getattr(idx_def, "if_not_exists", False)),
            ("tablespace", getattr(idx_def, "tablespace", None)),
            ("include_columns", getattr(idx_def, "include_columns", None)),
            ("partial_condition", getattr(idx_def, "partial_condition", None)),
        ):
            if value:
                raise UnsupportedFeatureError(
                    self.name, f"inline index {option}",
                    "SQL Server's inline index definition does not render "
                    f"'{option}'; use a standalone CREATE INDEX statement.",
                )
        parts = []

        if idx_def.unique:
            parts.append("UNIQUE")

        parts.append("INDEX")
        parts.append(self.qualified_object_name(Index, idx_def.name))

        col_parts = []
        for col in idx_def.columns:
            if isinstance(col, ToSQLProtocol):
                col_sql, col_params = col.to_sql()
                col_parts.append(col_sql)
            else:
                col_parts.append(self.format_identifier(str(col)))
        cols_str = ', '.join(col_parts)

        if getattr(idx_def, "hash_index", False):
            self.check_feature_support(
                "supports_memory_optimized_tables",
                "NONCLUSTERED HASH index",
                "requires SQL Server 2014+ (memory-optimized tables).",
            )
            bucket_count = getattr(idx_def, "bucket_count", None)
            if bucket_count is None:
                raise ValueError("bucket_count is required for a NONCLUSTERED HASH index")
            parts.append(f"NONCLUSTERED HASH ({cols_str}) WITH (BUCKET_COUNT = {bucket_count})")
        else:
            parts.append(f"({cols_str})")

        return ' '.join(parts), ()

    def format_create_index_statement(self, expr: "CreateIndexExpression") -> Tuple[str, tuple]:
        """Format CREATE INDEX statement for SQL Server.

        SQL Server doesn't support IF NOT EXISTS for CREATE INDEX, and has no
        index TABLESPACE concept; declared values are never silently dropped.

        Raises:
            TypeError: ``expr.index`` is not an Index. A table handed here would
                render as a well-formed ``CREATE INDEX`` over that table's name.
            TypeError: ``expr.table`` is not a Table. An index handed here would
                render as a well-formed ``CREATE INDEX ... ON <index>``.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

        if not isinstance(expr.index, Index):
            raise TypeError(
                f"CreateIndexExpression.index must be an Index, "
                f"got {type(expr.index).__name__}"
            )
        if not isinstance(expr.table, Table):
            raise TypeError(
                f"CreateIndexExpression.table must be a Table, "
                f"got {type(expr.table).__name__}"
            )
        if getattr(expr, "if_not_exists", False):
            raise UnsupportedFeatureError(
                self.name, "CREATE INDEX IF NOT EXISTS",
                "SQL Server has no CREATE INDEX IF NOT EXISTS syntax.",
            )
        if getattr(expr, "tablespace", None):
            raise UnsupportedFeatureError(
                self.name, "index TABLESPACE",
                "SQL Server has no index tablespace; use a filegroup instead.",
            )
        all_params = []
        parts = ["CREATE"]

        if expr.unique:
            parts.append("UNIQUE")

        if hasattr(expr, 'index_type') and expr.index_type:
            index_type = expr.index_type.upper()
            if index_type in ('CLUSTERED', 'NONCLUSTERED'):
                parts.append(index_type)

        parts.append("INDEX")
        parts.append(expr.index.to_sql()[0])
        parts.append("ON")
        parts.append(expr.table.to_sql()[0])

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

    # CREATE SEQUENCE and DROP SEQUENCE have no local copy: SQL Server's
    # spelling is exactly the one core's SequenceMixin emits, and that mixin now
    # consults supports_sequence() and the option probes before every clause.
    # Answering the probes in SQLServerSequenceMixin is therefore the whole
    # implementation, and one renderer serves every dialect.

    def format_alter_sequence_statement(self, expr: "AlterSequenceExpression") -> Tuple[str, tuple]:
        """Format ALTER SEQUENCE for SQL Server.

        SQL Server's ALTER SEQUENCE grammar differs from the standard form core
        renders: it changes the start point with ``RESTART WITH`` and has no
        ``START WITH`` clause -- the engine rejects that argument with error
        11710 -- and it has no ``ORDER``/``OWNED BY`` clause either. The
        formatter is kept here rather than deferred to ``SequenceMixin`` so
        those words are never emitted, while the option probes still decide
        which of the shared options this version accepts.

        Raises:
            TypeError: ``expr.sequence`` is not a Sequence. A table handed here
                would render as a well-formed ``ALTER SEQUENCE`` over that
                table's name.
            UnsupportedFeatureError: If the dialect has no sequence object, or
                the expression asks for an option SQL Server's ALTER SEQUENCE
                cannot spell.
        """
        if not isinstance(expr.sequence, Sequence):
            raise TypeError(
                f"AlterSequenceExpression.sequence must be a Sequence, "
                f"got {type(expr.sequence).__name__}"
            )
        if not self.supports_sequence():
            raise UnsupportedFeatureError(
                self.name, "ALTER SEQUENCE",
                f"{self.name} has no sequence object to alter."
            )
        parts = [f"ALTER SEQUENCE {expr.sequence.to_sql()[0]}"]
        if expr.restart is not None:
            parts.append(f"RESTART WITH {expr.restart}")
        if expr.start is not None:
            # ALTER SEQUENCE changes the start point with RESTART WITH, not
            # START WITH; ``supports_sequence_start`` answers for CREATE, where
            # the words are legal, so this is a statement-grammar fact.
            raise UnsupportedFeatureError(
                self.name, "ALTER SEQUENCE START",
                "SQL Server's ALTER SEQUENCE has no START WITH clause; use "
                "RESTART WITH to change the start point.",
            )
        if expr.increment is not None:
            if not self.supports_sequence_increment():
                raise UnsupportedFeatureError(
                    self.name, "ALTER SEQUENCE INCREMENT",
                    f"{self.name} does not support the INCREMENT BY sequence option."
                )
            parts.append(f"INCREMENT BY {expr.increment}")
        if expr.minvalue is not None:
            if not self.supports_sequence_minvalue():
                raise UnsupportedFeatureError(
                    self.name, "ALTER SEQUENCE MINVALUE",
                    f"{self.name} does not support the MINVALUE sequence option."
                )
            parts.append(f"MINVALUE {expr.minvalue}")
        if expr.maxvalue is not None:
            if not self.supports_sequence_maxvalue():
                raise UnsupportedFeatureError(
                    self.name, "ALTER SEQUENCE MAXVALUE",
                    f"{self.name} does not support the MAXVALUE sequence option."
                )
            parts.append(f"MAXVALUE {expr.maxvalue}")
        if expr.cycle is not None:
            if expr.cycle:
                if not self.supports_sequence_cycle():
                    raise UnsupportedFeatureError(
                        self.name, "ALTER SEQUENCE CYCLE",
                        f"{self.name} does not support the CYCLE sequence option."
                    )
                parts.append("CYCLE")
            elif self.supports_sequence_cycle():
                # NO CYCLE is the default; only spell it where it is legal.
                parts.append("NO CYCLE")
        if expr.cache is not None:
            if not self.supports_sequence_cache():
                raise UnsupportedFeatureError(
                    self.name, "ALTER SEQUENCE CACHE",
                    f"{self.name} does not support the CACHE sequence option."
                )
            parts.append(f"CACHE {expr.cache}")
        if expr.order is not None:
            raise UnsupportedFeatureError(
                self.name, "ALTER SEQUENCE ORDER",
                f"{self.name} does not support the ORDER sequence option."
            )
        if expr.owned_by is not None:
            raise UnsupportedFeatureError(
                self.name, "ALTER SEQUENCE OWNED BY",
                f"{self.name} does not support the OWNED BY sequence option."
            )
        return " ".join(parts), ()

    def format_truncate_statement(self, expr: "TruncateExpression") -> Tuple[str, tuple]:
        """Format TRUNCATE TABLE for SQL Server.

        SQL Server's TRUNCATE TABLE is a DDL operation (minimal logging) with
        no modifiers, so the statement renders the table object and nothing
        else.

        Raises:
            TypeError: ``expr.table`` is not a Table. A view or a sequence
                handed here would render as a well-formed ``TRUNCATE TABLE``
                over that object's name.
        """
        if not isinstance(expr.table, Table):
            raise TypeError(
                f"TruncateExpression.table must be a Table, "
                f"got {type(expr.table).__name__}"
            )
        return f"TRUNCATE TABLE {expr.table.to_sql()[0]}", ()

    def format_merge_statement(self, expr: "MergeExpression") -> Tuple[str, tuple]:
        """Format MERGE statement for SQL Server (2008+).

        SQL Server MERGE syntax:
        MERGE INTO target USING source ON condition
        WHEN MATCHED [AND condition] THEN UPDATE/DELETE
        WHEN NOT MATCHED [BY TARGET] [AND condition] THEN INSERT
        WHEN NOT MATCHED BY SOURCE [AND condition] THEN UPDATE/DELETE

        Raises:
            TypeError: ``expr.target_table`` is not a Table. Any other object kind
                would have its own name rendered as the MERGE target.
        """
        from rhosocial.activerecord.backend.expression.statements import MergeActionType

        if not isinstance(expr.target_table, Table):
            raise TypeError(
                f"MergeExpression.target_table must be a Table, "
                f"got {type(expr.target_table).__name__}"
            )

        all_params: list = []

        target_sql, target_params = expr.target_table.to_sql()
        all_params.extend(target_params)

        source_sql, source_params = expr.source.to_sql()
        all_params.extend(source_params)

        on_sql, on_params = expr.on_condition.to_sql()
        all_params.extend(on_params)

        output_columns = getattr(expr, "output", None)
        output_action = getattr(expr, "output_action", False)
        holdlock = getattr(expr, "holdlock", False)

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
