# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/__init__.py
"""SQL Server's concrete backend suggestions.

The suggestion data classes live in :mod:`rhosocial.activerecord.backend.suggestion`;
this package holds the backend's own answers to the suggestion protocols.

There is one module per partition-lifecycle point, mirroring the SQLite
suggestion package. Shared plan-reading helpers and their common base live in
``_common.py``.
"""

from ._common import SQLServerPartitionSuggestionBase
from .create_table_layout_suggestion import SQLServerCreateTableLayoutSuggestionMixin
from .data_type_suggestions import (
    SQLSERVER_DATA_TYPE_SUGGESTIONS,
    SQLServerDataTypeSuggestionsMixin,
)
from .integer_auto_increment_column_suggestion import (
    SQLServerIntegerAutoIncrementColumnSuggestionMixin,
)
from .partition_add_suggestion import SQLServerPartitionAddSuggestionMixin
from .partition_build_suggestion import SQLServerPartitionBuildSuggestionMixin
from .partition_drop_suggestion import SQLServerPartitionDropSuggestionMixin
from .partition_merge_suggestion import SQLServerPartitionMergeSuggestionMixin
from .partition_retention_suggestion import SQLServerPartitionRetentionSuggestionMixin
from .partition_split_suggestion import SQLServerPartitionSplitSuggestionMixin
from .partition_table_alter_suggestion import SQLServerPartitionTableAlterSuggestionMixin
from .partition_table_drop_suggestion import SQLServerPartitionTableDropSuggestionMixin

__all__ = [
    "SQLServerPartitionSuggestionBase",
    "SQLServerCreateTableLayoutSuggestionMixin",
    "SQLServerIntegerAutoIncrementColumnSuggestionMixin",
    "SQLSERVER_DATA_TYPE_SUGGESTIONS",
    "SQLServerDataTypeSuggestionsMixin",
    "SQLServerPartitionAddSuggestionMixin",
    "SQLServerPartitionBuildSuggestionMixin",
    "SQLServerPartitionDropSuggestionMixin",
    "SQLServerPartitionMergeSuggestionMixin",
    "SQLServerPartitionRetentionSuggestionMixin",
    "SQLServerPartitionSplitSuggestionMixin",
    "SQLServerPartitionTableAlterSuggestionMixin",
    "SQLServerPartitionTableDropSuggestionMixin",
]
