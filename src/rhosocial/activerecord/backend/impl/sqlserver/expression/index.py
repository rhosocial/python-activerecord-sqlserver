# src/rhosocial/activerecord/backend/impl/sqlserver/expression/index.py
"""SQL Server-specific index definition.

SQL Server memory-optimized tables use ``NONCLUSTERED HASH`` indexes with a
``BUCKET_COUNT``, which has no generic equivalent. It lives on
``SQLServerIndexDefinition`` (deriving the generic ``IndexDefinition``) and is
rendered inline by the SQL Server ``format_index_definition`` override.
"""

from typing import Any, Optional

from rhosocial.activerecord.backend.expression.statements.ddl_table import IndexDefinition


class SQLServerIndexDefinition(IndexDefinition):
    """A SQL Server index definition extending the generic one.

    Adds the SQL Server-only ``hash_index`` / ``bucket_count`` options for
    memory-optimized (in-memory) tables.
    """

    def __init__(
        self,
        dialect: Any,
        name: str,
        columns: list,
        *,
        unique: bool = False,
        type: Optional[str] = None,
        partial_condition: Any = None,
        include_columns: Optional[list] = None,
        hash_index: bool = False,
        bucket_count: Optional[int] = None,
    ):
        super().__init__(
            dialect,
            name=name,
            columns=columns,
            unique=unique,
            type=type,
            partial_condition=partial_condition,
            include_columns=include_columns,
        )
        self.hash_index = hash_index
        self.bucket_count = bucket_count
