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
from .columnstore import SQLServerColumnstoreIndexExpression
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
    "SQLServerOptionHintClause",
    "recompile_hint",
    "maxdop_hint",
    "optimize_for_hint",
    "hash_join_hint",
    "loop_join_hint",
    "merge_join_hint",
    "SQLServerPivotExpression",
    "SQLServerUnpivotExpression",
    "SQLServerColumnstoreIndexExpression",
    "SQLServerTryCastExpression",
    "SQLServerTryConvertExpression",
    "SQLServerContainsPredicate",
    "SQLServerFreetextPredicate",
]
