# src/rhosocial/activerecord/backend/impl/sqlserver/expression/__init__.py
"""SQL Server-specific expression classes."""

from .output import SQLServerOutputInsertedExpression, SQLServerOutputDeletedExpression
from .locking import SQLServerTableHintClause, SQLServerTableHint, SQLServerReadPastHint
from .temporal import SQLServerTemporalPeriodDefinition, SQLServerSystemVersioningClause
from .openjson import SQLServerOpenJsonExpression, OpenJsonColumn
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
    "SQLServerTryCastExpression",
    "SQLServerTryConvertExpression",
    "SQLServerContainsPredicate",
    "SQLServerFreetextPredicate",
]