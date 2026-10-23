# src/rhosocial/activerecord/backend/impl/sqlserver/expression/__init__.py
"""SQL Server-specific expression classes.

One naming rule holds for every class in this package: its **kind** spells the
backend's name as a single word. ``SQLServer`` is a compound name -- the
generic consecutive-capital rule reads it as ``SQL`` + ``Server`` -- so each
node here carries ``KIND_RESERVED = ("SQLServer",)``, which is *data* rather
than behaviour: no class overrides ``kind()``, and the whole backend spells the
same way, exactly as SQLite keeps ``SQLite`` whole (``sqlite_integer_type``) and
MySQL keeps ``MySQL`` (``mysql_big_int_type``). The parallel form here is
therefore ``SQLServerBitType`` -> ``sqlserver_bit_type``, with the ``_type``
suffix kept on both sides of the core/backend seam. The audit that settles the
set is ``scripts/expression_lineage.py``, read off the running code.
"""

from .objects import SQLServerTable, PartitionFunction, PartitionScheme
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
from .create_table import SQLServerCreateTableStatement
from .dml import SQLServerMergeExpression, SQLServerSelectIntoExpression
from .columnstore import SQLServerColumnstoreIndexStatement
from .fulltext import (
    SQLServerCreateFullTextCatalogStatement,
    SQLServerDropFullTextCatalogStatement,
    SQLServerCreateFullTextIndexStatement,
    SQLServerDropFullTextIndexStatement,
)
from .ddl import (
    SQLServerCreateProcedureStatement,
    SQLServerCreateFunctionStatement,
    SQLServerDropRoutineStatement,
    SQLServerCreateTriggerStatement,
    SQLServerDropTriggerStatement,
    SQLServerTypeNullability,
    SQLServerAliasTypeDefinition,
    SQLServerTableTypeDefinition,
    SQLServerClrTypeDefinition,
    SQLServerDropTypeExpression,
    SQLServerRenameTypeStatement,
)
from .functions import (
    SQLServerTryCastExpression,
    SQLServerTryConvertExpression,
    SQLServerContainsPredicate,
    SQLServerFreetextPredicate,
)

__all__ = [
    "SQLServerTable",
    "PartitionFunction",
    "PartitionScheme",
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
    "SQLServerCreateTableStatement",
    "SQLServerColumnstoreIndexStatement",
    "SQLServerCreateFullTextCatalogStatement",
    "SQLServerDropFullTextCatalogStatement",
    "SQLServerCreateFullTextIndexStatement",
    "SQLServerDropFullTextIndexStatement",
    "SQLServerCreateProcedureStatement",
    "SQLServerCreateFunctionStatement",
    "SQLServerDropRoutineStatement",
    "SQLServerCreateTriggerStatement",
    "SQLServerDropTriggerStatement",
    "SQLServerTypeNullability",
    "SQLServerAliasTypeDefinition",
    "SQLServerTableTypeDefinition",
    "SQLServerClrTypeDefinition",
    "SQLServerDropTypeExpression",
    "SQLServerRenameTypeStatement",
    "SQLServerTryCastExpression",
    "SQLServerTryConvertExpression",
    "SQLServerContainsPredicate",
    "SQLServerFreetextPredicate",
]
