# src/rhosocial/activerecord/backend/impl/sqlserver/expression/partition.py
"""SQL Server partition DDL expressions.

SQL Server uses a unique three-tier partitioning model:
1. Partition Function - defines boundary values
2. Partition Scheme - maps partitions to filegroups
3. Partitioned Table - uses ON clause referencing a scheme

This module defines:
- SQLServerPartitionByRangeClause — extended PartitionClause with LEFT/RIGHT
- SQLServerPartitionFunctionExpression — CREATE PARTITION FUNCTION
- SQLServerPartitionSchemeExpression — CREATE PARTITION SCHEME
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams
from rhosocial.activerecord.backend.expression.statements import PartitionClause, PartitionStrategy

if TYPE_CHECKING:
    from ..dialect import SQLServerDialect


class SQLServerPartitionRangeDirection(Enum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class SQLServerPartitionByRangeClause(PartitionClause):
    """SQL Server RANGE partitioning clause with boundary direction.

    SQL Server only supports RANGE partitioning. The direction
    (LEFT or RIGHT) specifies which side of each boundary value
    belongs to the partition. RIGHT is the default in SQL Server.
    """

    strategy_type = PartitionStrategy

    def __init__(
        self,
        dialect: "SQLServerDialect",
        keys: Sequence[BaseExpression],
        partition_scheme: str,
        *,
        range_direction: SQLServerPartitionRangeDirection = SQLServerPartitionRangeDirection.RIGHT,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            dialect,
            PartitionStrategy.RANGE,
            keys,
            dialect_options=dialect_options,
        )
        self.partition_scheme = partition_scheme
        self.range_direction = range_direction

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_partition_clause(self)


class SQLServerPartitionFunctionExpression(BaseExpression):
    """CREATE PARTITION FUNCTION statement.

    Defines boundary values for partitioning a table.
    Example:
        CREATE PARTITION FUNCTION pf_name (DATE)
        AS RANGE RIGHT FOR VALUES ('2020-01-01', '2021-01-01')
    """

    def __init__(
        self,
        dialect: "SQLServerDialect",
        function_name: str,
        data_type: str,
        boundary_values: Sequence[Any],
        *,
        range_direction: SQLServerPartitionRangeDirection = SQLServerPartitionRangeDirection.RIGHT,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.function_name = function_name
        self.data_type = data_type
        self.boundary_values = list(boundary_values)
        self.range_direction = range_direction
        self.dialect_options = dict(dialect_options or {})

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_sqlserver_partition_function(self)


class SQLServerPartitionSchemeExpression(BaseExpression):
    """CREATE PARTITION SCHEME statement.

    Maps partitions defined by a partition function to filegroups.
    Example:
        CREATE PARTITION SCHEME ps_name
        AS PARTITION pf_name
        TO ([PRIMARY], fg1, fg2)
    """

    def __init__(
        self,
        dialect: "SQLServerDialect",
        scheme_name: str,
        function_name: str,
        filegroups: Sequence[str],
        *,
        all_filegroup: Optional[str] = None,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.scheme_name = scheme_name
        self.function_name = function_name
        self.filegroups = list(filegroups)
        if all_filegroup and filegroups:
            raise ValueError("all_filegroup and filegroups are mutually exclusive")
        self.all_filegroup = all_filegroup
        self.dialect_options = dict(dialect_options or {})

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_sqlserver_partition_scheme(self)
