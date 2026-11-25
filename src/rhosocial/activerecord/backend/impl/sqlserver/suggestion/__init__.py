# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/__init__.py
"""SQL Server's concrete backend suggestions.

The suggestion data classes live in :mod:`rhosocial.activerecord.backend.suggestion`;
this package holds the backend's own answers to the suggestion protocols.

There is one module per partition-lifecycle point, mirroring the SQLite
suggestion package, plus one module for each of the four migration change-point
protocols (column reorder, table constraint change, table index change and
partition scheme change). Shared plan-reading helpers and their common base
live in ``_common.py``; the change-point projection readers live in
``_change_common.py``.
"""

from ._common import SQLServerPartitionSuggestionBase
from .column_reorder_suggestion import SQLServerColumnReorderSuggestionMixin
from .table_constraint_change_suggestion import SQLServerTableConstraintChangeSuggestionMixin
from .table_index_change_suggestion import SQLServerTableIndexChangeSuggestionMixin
from .partition_scheme_change_suggestion import SQLServerPartitionSchemeChangeSuggestionMixin
from .create_table_layout_suggestion import SQLServerCreateTableLayoutSuggestionMixin
from .data_type_suggestions import (
    SQLSERVER_DATA_TYPE_SUGGESTIONS,
    SQLServerDataTypeSuggestionsMixin,
)
from .generated_value_suggestion import SQLServerGeneratedValueSuggestionMixin
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
    "SQLServerColumnReorderSuggestionMixin",
    "SQLServerTableConstraintChangeSuggestionMixin",
    "SQLServerTableIndexChangeSuggestionMixin",
    "SQLServerPartitionSchemeChangeSuggestionMixin",
    "SQLServerCreateTableLayoutSuggestionMixin",
    "SQLServerGeneratedValueSuggestionMixin",
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
