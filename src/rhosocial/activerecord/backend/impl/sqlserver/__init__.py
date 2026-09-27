# src/rhosocial/activerecord/backend/impl/sqlserver/__init__.py
"""SQL Server backend implementation for the Python ORM."""

# Public names are resolved on first access rather than at package-execution
# time. Importing this package used to import every submodule eagerly, which
# pulled in the DB driver through ``.backend`` and made the expression classes
# unreachable without it: Python executes a parent package's ``__init__`` before
# any submodule, so ``impl.<name>.expression`` could not be imported on its own.
# The exports themselves are unchanged -- attribute access, ``__all__``, ``dir()``
# and ``from ... import *`` all behave as before.
from typing import TYPE_CHECKING

#: Public name -> (submodule that defines it, attribute name within it).
#: The two differ when the original import was aliased.
_EXPORTS = {
    "DIRECT_COMPATIBLE_CASTS": (".type_compatibility", "DIRECT_COMPATIBLE_CASTS"),
    "OpenJsonColumn": (".expression", "OpenJsonColumn"),
    "SQLServerAliasTypeDefinition": (".expression", "SQLServerAliasTypeDefinition"),
    "SQLServerBackend": (".backend", "SQLServerBackend"),
    "SQLServerBackendMixin": (".mixins", "SQLServerBackendMixin"),
    "SQLServerBitType": (".expression.types", "SQLServerBitType"),
    "SQLServerClrTypeDefinition": (".expression", "SQLServerClrTypeDefinition"),
    "SQLServerCollation": (".collation", "SQLServerCollation"),
    "SQLServerConcurrencyMixin": (".mixins", "SQLServerConcurrencyMixin"),
    "SQLServerConnectionConfig": (".config", "SQLServerConnectionConfig"),
    "SQLServerContainsPredicate": (".expression", "SQLServerContainsPredicate"),
    "SQLServerDateAdapter": (".adapters", "SQLServerDateAdapter"),
    "SQLServerDateTimeAdapter": (".adapters", "SQLServerDateTimeAdapter"),
    "SQLServerDateTimeOffsetAdapter": (".adapters", "SQLServerDateTimeOffsetAdapter"),
    "SQLServerDialect": (".dialect", "SQLServerDialect"),
    "SQLServerDropTypeExpression": (".expression", "SQLServerDropTypeExpression"),
    "SQLServerExecutionOptions": (".options", "SQLServerExecutionOptions"),
    "SQLServerExplainResult": (".explain", "SQLServerExplainResult"),
    "SQLServerExplainRow": (".explain", "SQLServerExplainRow"),
    "SQLServerFreetextPredicate": (".expression", "SQLServerFreetextPredicate"),
    "SQLServerHierarchyIdAdapter": (".adapters", "SQLServerHierarchyIdAdapter"),
    "SQLServerImageType": (".expression.types", "SQLServerImageType"),
    "SQLServerJSONAdapter": (".adapters", "SQLServerJSONAdapter"),
    "SQLServerNCharType": (".expression.types", "SQLServerNCharType"),
    "SQLServerNVarCharMaxType": (".expression.types", "SQLServerNVarCharMaxType"),
    "SQLServerNVarCharType": (".expression.types", "SQLServerNVarCharType"),
    "SQLServerNextValueForExpression": (".expression", "SQLServerNextValueForExpression"),
    "SQLServerOpenJsonExpression": (".expression", "SQLServerOpenJsonExpression"),
    "SQLServerOutputDeletedExpression": (".expression", "SQLServerOutputDeletedExpression"),
    "SQLServerOutputInsertedExpression": (".expression", "SQLServerOutputInsertedExpression"),
    "SQLServerReadPastHint": (".expression", "SQLServerReadPastHint"),
    "SQLServerRenameTypeExpression": (".expression", "SQLServerRenameTypeExpression"),
    "SQLServerSchemaDiffer": (".schema", "SQLServerSchemaDiffer"),
    "SQLServerSpatialAdapter": (".adapters", "SQLServerSpatialAdapter"),
    "SQLServerSystemVersioningClause": (".expression", "SQLServerSystemVersioningClause"),
    "SQLServerTableHint": (".expression", "SQLServerTableHint"),
    "SQLServerTableHintClause": (".expression", "SQLServerTableHintClause"),
    "SQLServerTableTypeDefinition": (".expression", "SQLServerTableTypeDefinition"),
    "SQLServerTemporalPeriodDefinition": (".expression", "SQLServerTemporalPeriodDefinition"),
    "SQLServerTimeAdapter": (".adapters", "SQLServerTimeAdapter"),
    "SQLServerTinyIntType": (".expression.types", "SQLServerTinyIntType"),
    "SQLServerTransactionManager": (".transaction", "SQLServerTransactionManager"),
    "SQLServerTryCastExpression": (".expression", "SQLServerTryCastExpression"),
    "SQLServerTryConvertExpression": (".expression", "SQLServerTryConvertExpression"),
    "SQLServerTypeDDLMixin": (".mixins", "SQLServerTypeDDLMixin"),
    "SQLServerTypeNullability": (".expression", "SQLServerTypeNullability"),
    "SQLServerTypeSupportMixin": (".mixins", "SQLServerTypeSupportMixin"),
    "SQLServerUUIDAdapter": (".adapters", "SQLServerUUIDAdapter"),
    "SQLServerUserDefinedTypeSupport": (".protocols", "SQLServerUserDefinedTypeSupport"),
    "SQLServerVarBinaryMaxType": (".expression.types", "SQLServerVarBinaryMaxType"),
    "SQLServerVarBinaryType": (".expression.types", "SQLServerVarBinaryType"),
    "SQLServerXMLAdapter": (".adapters", "SQLServerXMLAdapter"),
    "SQLServerXmlType": (".expression.types", "SQLServerXmlType"),
    "check_cast_compatibility": (".type_compatibility", "check_cast_compatibility"),
    "get_compatible_types": (".type_compatibility", "get_compatible_types"),
}

if TYPE_CHECKING:  # pragma: no cover - re-exports for type checkers
    from .backend import SQLServerBackend
    from .config import SQLServerConnectionConfig
    from .collation import SQLServerCollation
    from .dialect import SQLServerDialect
    from .options import SQLServerExecutionOptions
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
        SQLServerNextValueForExpression,
        SQLServerTryCastExpression,
        SQLServerTryConvertExpression,
        SQLServerContainsPredicate,
        SQLServerFreetextPredicate,
        SQLServerTypeNullability,
        SQLServerAliasTypeDefinition,
        SQLServerTableTypeDefinition,
        SQLServerClrTypeDefinition,
        SQLServerDropTypeExpression,
        SQLServerRenameTypeExpression,
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
        SQLServerTypeDDLMixin,
    )
    from .protocols import SQLServerUserDefinedTypeSupport
    from .schema import SQLServerSchemaDiffer
    from .type_compatibility import (
        DIRECT_COMPATIBLE_CASTS,
        check_cast_compatibility,
        get_compatible_types,
    )

__all__ = [
    "SQLServerBackend",
    "SQLServerConnectionConfig",
    "SQLServerExecutionOptions",
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
    "SQLServerNextValueForExpression",
    "SQLServerTryCastExpression",
    "SQLServerTryConvertExpression",
    "SQLServerContainsPredicate",
    "SQLServerFreetextPredicate",
    "SQLServerTypeNullability",
    "SQLServerAliasTypeDefinition",
    "SQLServerTableTypeDefinition",
    "SQLServerClrTypeDefinition",
    "SQLServerDropTypeExpression",
    "SQLServerRenameTypeExpression",
    "SQLServerNVarCharType",
    "SQLServerNCharType",
    "SQLServerNVarCharMaxType",
    "SQLServerVarBinaryType",
    "SQLServerVarBinaryMaxType",
    "SQLServerXmlType",
    "SQLServerTinyIntType",
    "SQLServerBitType",
    "SQLServerImageType",
    "SQLServerBackendMixin",
    "SQLServerConcurrencyMixin",
    "SQLServerTypeSupportMixin",
    "SQLServerTypeDDLMixin",
    "SQLServerUserDefinedTypeSupport",
    "SQLServerSchemaDiffer",
    "DIRECT_COMPATIBLE_CASTS",
    "check_cast_compatibility",
    "get_compatible_types",
]


def __getattr__(name: str):
    """Resolve a public name by importing its defining submodule once."""
    target = _EXPORTS.get(name)
    if target is not None:
        import importlib

        module_name, attr = target
        value = getattr(importlib.import_module(module_name, __name__), attr)
        globals()[name] = value  # cache, so __getattr__ runs at most once per name
        return value
    return _optional_dependency_getattr(name)


def _optional_dependency_getattr(name: str):
    # Preserved from the previous eager loader: optional async backends get a
    # helpful install hint instead of a bare ImportError.
    _lazy_imports = {'AsyncSQLServerBackend': ('.async_backend', 'AsyncSQLServerBackend'), 'AsyncSQLServerTransactionManager': ('.async_transaction', 'AsyncSQLServerTransactionManager')}
    if name in _lazy_imports:
        module_path, class_name = _lazy_imports[name]
        try:
            import importlib
            module = importlib.import_module(module_path, __name__)
            return getattr(module, class_name)
        except ImportError as e:
            raise ImportError(f"{name} requires 'aioodbc' package. Install it with: pip install rhosocial-activerecord-sqlserver[async] or pip install aioodbc") from e
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def __dir__():
    return sorted(set(globals()) | set(_EXPORTS))
