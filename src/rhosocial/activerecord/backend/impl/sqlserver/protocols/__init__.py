# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/__init__.py
from .identity import SQLServerIdentitySupport
from .indexed_view import SQLServerIndexedViewSupport
from .table_hint import SQLServerTableHintSupport
from .output import SQLServerOutputSupport
from .table import SQLServerTableSupport
from .locking import SQLServerLockingSupport
from .json_support import SQLServerJSONSupport
from .temporal import SQLServerTemporalTableSupport
from .sequence import SQLServerSequenceSupport
from .fulltext import SQLServerFullTextSearchSupport
from .try_cast import SQLServerTryCastSupport
from .pagination import SQLServerPaginationSupport
from .merge import SQLServerMergeSupport
from .partition import SQLServerPartitionSupport

__all__ = [
    "SQLServerIdentitySupport",
    "SQLServerIndexedViewSupport",
    "SQLServerTableHintSupport",
    "SQLServerOutputSupport",
    "SQLServerTableSupport",
    "SQLServerLockingSupport",
    "SQLServerJSONSupport",
    "SQLServerTemporalTableSupport",
    "SQLServerSequenceSupport",
    "SQLServerFullTextSearchSupport",
    "SQLServerTryCastSupport",
    "SQLServerPaginationSupport",
    "SQLServerMergeSupport",
    "SQLServerPartitionSupport",
]