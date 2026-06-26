# src/rhosocial/activerecord/backend/impl/sqlserver/protocols.py
"""Backward-compatible re-exports from protocols/ package."""

from .protocols import (
    SQLServerIdentitySupport,
    SQLServerIndexedViewSupport,
    SQLServerTableHintSupport,
    SQLServerOutputSupport,
    SQLServerTableSupport,
    SQLServerLockingSupport,
    SQLServerJSONSupport,
    SQLServerTemporalTableSupport,
    SQLServerSequenceSupport,
    SQLServerFullTextSearchSupport,
    SQLServerTryCastSupport,
    SQLServerPaginationSupport,
    SQLServerMergeSupport,
)

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
]