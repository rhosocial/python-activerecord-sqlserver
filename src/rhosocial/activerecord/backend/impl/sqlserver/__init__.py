# src/rhosocial/activerecord/backend/impl/sqlserver/__init__.py
"""SQL Server backend implementation for the Python ORM."""

from .backend import SQLServerBackend
from .config import SQLServerConnectionConfig
from .collation import SQLServerCollation
from .dialect import SQLServerDialect
from .transaction import SQLServerTransactionManager
from .adapters import (
    SQLServerUUIDAdapter,
    SQLServerDateTimeAdapter,
    SQLServerDateTimeOffsetAdapter,
    SQLServerDateAdapter,
    SQLServerTimeAdapter,
    SQLServerJSONAdapter,
    SQLServerXMLAdapter,
    SQLServerSpatialAdapter,
    SQLServerHierarchyIdAdapter,
)

from .explain import SQLServerExplainResult, SQLServerExplainRow

from .expression import (
    SQLServerOutputInsertedExpression,
    SQLServerOutputDeletedExpression,
    SQLServerTableHintClause,
    SQLServerTableHint,
    SQLServerReadPastHint,
    SQLServerTemporalPeriodDefinition,
    SQLServerSystemVersioningClause,
    SQLServerOpenJsonExpression,
    OpenJsonColumn,
    SQLServerTryCastExpression,
    SQLServerTryConvertExpression,
    SQLServerContainsPredicate,
    SQLServerFreetextPredicate,
)

from .expression.types import (
    SQLServerNVarCharType,
    SQLServerNCharType,
    SQLServerNVarCharMaxType,
    SQLServerVarBinaryType,
    SQLServerVarBinaryMaxType,
    SQLServerXmlType,
    SQLServerTinyIntType,
    SQLServerBitType,
    SQLServerImageType,
)

from .mixins import (
    SQLServerBackendMixin,
    SQLServerConcurrencyMixin,
    SQLServerTypeSupportMixin,
)

from .schema import SQLServerSchemaDiffer

from .type_compatibility import (
    DIRECT_COMPATIBLE_CASTS,
    check_cast_compatibility,
    get_compatible_types,
)

__all__ = [
    "SQLServerBackend",
    "SQLServerConnectionConfig",
    "SQLServerDialect",
    "SQLServerCollation",
    "SQLServerTransactionManager",
    "SQLServerUUIDAdapter",
    "SQLServerDateTimeAdapter",
    "SQLServerDateTimeOffsetAdapter",
    "SQLServerDateAdapter",
    "SQLServerTimeAdapter",
    "SQLServerJSONAdapter",
    "SQLServerXMLAdapter",
    "SQLServerSpatialAdapter",
    "SQLServerHierarchyIdAdapter",
    "SQLServerExplainResult",
    "SQLServerExplainRow",
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
    # DDL DataType subclasses
    "SQLServerNVarCharType",
    "SQLServerNCharType",
    "SQLServerNVarCharMaxType",
    "SQLServerVarBinaryType",
    "SQLServerVarBinaryMaxType",
    "SQLServerXmlType",
    "SQLServerTinyIntType",
    "SQLServerBitType",
    "SQLServerImageType",
    # Mixins
    "SQLServerBackendMixin",
    "SQLServerConcurrencyMixin",
    "SQLServerTypeSupportMixin",
    # Schema differ
    "SQLServerSchemaDiffer",
    # Type compatibility
    "DIRECT_COMPATIBLE_CASTS",
    "check_cast_compatibility",
    "get_compatible_types",
]


def __getattr__(name: str):
    _lazy_imports = {
        "AsyncSQLServerBackend": (".async_backend", "AsyncSQLServerBackend"),
        "AsyncSQLServerTransactionManager": (".async_transaction", "AsyncSQLServerTransactionManager"),
    }

    if name in _lazy_imports:
        module_path, class_name = _lazy_imports[name]
        try:
            import importlib
            module = importlib.import_module(module_path, __name__)
            return getattr(module, class_name)
        except ImportError as e:
            raise ImportError(
                f"{name} requires 'aioodbc' package. "
                f"Install it with: pip install rhosocial-activerecord-sqlserver[async] "
                f"or pip install aioodbc"
            ) from e

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")