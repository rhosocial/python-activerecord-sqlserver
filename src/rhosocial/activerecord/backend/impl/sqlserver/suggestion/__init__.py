# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/__init__.py
"""SQL Server's concrete backend suggestions.

The suggestion data classes live in :mod:`rhosocial.activerecord.backend.suggestion`;
this package holds the backend's own answers to the suggestion protocols.
"""

from .integer_auto_increment import SQLServerIntegerAutoIncrementColumnSuggestionMixin
from .partition import SQLServerPartitionSuggestionMixin
from .data_types import SQLSERVER_DATA_TYPE_SUGGESTIONS, SQLServerDataTypeSuggestionsMixin

__all__ = [
    "SQLServerIntegerAutoIncrementColumnSuggestionMixin",
    "SQLServerPartitionSuggestionMixin",
    "SQLSERVER_DATA_TYPE_SUGGESTIONS",
    "SQLServerDataTypeSuggestionsMixin",
]
