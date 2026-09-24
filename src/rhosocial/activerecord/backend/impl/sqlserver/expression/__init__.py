# src/rhosocial/activerecord/backend/impl/sqlserver/expression/__init__.py
"""SQL Server-specific expression classes."""

from .output import SQLServerOutputInsertedExpression, SQLServerOutputDeletedExpression
from .locking import SQLServerTableHintClause, SQLServerTableHint, SQLServerReadPastHint
from .temporal import SQLServerTemporalPeriodDefinition, SQLServerSystemVersioningClause
from .openjson import SQLServerOpenJsonExpression, OpenJsonColumn
from .sequence import SQLServerNextValueForExpression
from .option_hint import (
    SQLServerOptionHintClause,
    recompile_hint,
    maxdop_hint,
    optimize_for_hint,
    hash_join_hint,
    loop_join_hint,
    merge_join_hint,
)
from .pivot import SQLServerPivotExpression, SQLServerUnpivotExpression
from .graph import (
    SQLServerGraphDirection,
    SQLServerGraphPseudoColumn,
    SQLServerGraphNodeRef,
    SQLServerGraphEdgeRef,
    SQLServerGraphPattern,
    SQLServerMatchPredicate,
    SQLServerShortestPathExpression,
    SQLServerGraphPathAggregate,
    SQLServerForPathTable,
)
from .column import SQLServerColumnDefinition, SQLServerColumnOptions
from .alter_column import SQLServerAlterColumn
from .table_options import SQLServerCreateTableOptions
from .index import SQLServerIndexDefinition
from .create_table import SQLServerCreateTableExpression
from .dml import SQLServerMergeExpression, SQLServerSelectIntoExpression
from .columnstore import SQLServerColumnstoreIndexExpression
from .fulltext import (
    SQLServerCreateFullTextCatalogExpression,
    SQLServerDropFullTextCatalogExpression,
    SQLServerCreateFullTextIndexExpression,
    SQLServerDropFullTextIndexExpression,
)
from .ddl import (
    SQLServerCreateProcedureExpression,
    SQLServerCreateFunctionExpression,
    SQLServerDropRoutineExpression,
    SQLServerCreateTriggerExpression,
    SQLServerDropTriggerExpression,
    SQLServerTypeNullability,
    SQLServerAliasTypeDefinition,
    SQLServerTableTypeDefinition,
    SQLServerClrTypeDefinition,
    SQLServerDropTypeExpression,
    SQLServerRenameTypeExpression,
)
from .functions import (
    SQLServerTryCastExpression,
    SQLServerTryConvertExpression,
    SQLServerContainsPredicate,
    SQLServerFreetextPredicate,
)

__all__ = [
    "SQLServerOutputInsertedExpression",
    "SQLServerOutputDeletedExpression",
    "SQLServerTableHintClause",
    "SQLServerTableHint",
    "SQLServerReadPastHint",
    "SQLServerTemporalPeriodDefinition",
    "SQLServerSystemVersioningClause",
    "SQLServerOpenJsonExpression",
    "OpenJsonColumn",
    "SQLServerNextValueForExpression",
    "SQLServerMergeExpression",
    "SQLServerSelectIntoExpression",
    "SQLServerOptionHintClause",
    "recompile_hint",
    "maxdop_hint",
    "optimize_for_hint",
    "hash_join_hint",
    "loop_join_hint",
    "merge_join_hint",
    "SQLServerPivotExpression",
    "SQLServerGraphDirection",
    "SQLServerGraphPseudoColumn",
    "SQLServerGraphNodeRef",
    "SQLServerGraphEdgeRef",
    "SQLServerGraphPattern",
    "SQLServerMatchPredicate",
    "SQLServerShortestPathExpression",
    "SQLServerGraphPathAggregate",
    "SQLServerForPathTable",
    "SQLServerUnpivotExpression",
    "SQLServerCreateTableOptions",
    "SQLServerColumnDefinition",
    "SQLServerColumnOptions",
    "SQLServerAlterColumn",
    "SQLServerIndexDefinition",
    "SQLServerCreateTableExpression",
    "SQLServerColumnstoreIndexExpression",
    "SQLServerCreateFullTextCatalogExpression",
    "SQLServerDropFullTextCatalogExpression",
    "SQLServerCreateFullTextIndexExpression",
    "SQLServerDropFullTextIndexExpression",
    "SQLServerCreateProcedureExpression",
    "SQLServerCreateFunctionExpression",
    "SQLServerDropRoutineExpression",
    "SQLServerCreateTriggerExpression",
    "SQLServerDropTriggerExpression",
    "SQLServerTypeNullability",
    "SQLServerAliasTypeDefinition",
    "SQLServerTableTypeDefinition",
    "SQLServerClrTypeDefinition",
    "SQLServerDropTypeExpression",
    "SQLServerRenameTypeExpression",
    "SQLServerTryCastExpression",
    "SQLServerTryConvertExpression",
    "SQLServerContainsPredicate",
    "SQLServerFreetextPredicate",
]
