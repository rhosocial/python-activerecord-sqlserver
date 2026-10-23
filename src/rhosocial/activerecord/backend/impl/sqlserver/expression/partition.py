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
from typing import Any, Optional, Sequence, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams
from rhosocial.activerecord.backend.expression.statements import PartitionClause, PartitionStrategy

if TYPE_CHECKING:
    from ..dialect import SQLServerDialect


class SQLServerPartitionRangeDirection(str, Enum):
    """Which side of each boundary value belongs to the partition.

    A member *is* the word it carries -- ``str.__str__``, not ``Enum.__str__``,
    which would win the base order otherwise -- because the member rides inside
    the partition clauses' params and a param that travels in an artifact must
    be a JSON scalar. Plain ``Enum`` raises "not one of the value kinds" the
    moment anything serialises the node, which is how the spelling was settled.
    """

    __str__ = str.__str__

    LEFT = "LEFT"
    RIGHT = "RIGHT"


def _as_range_direction(value: Any) -> SQLServerPartitionRangeDirection:
    """Read a boundary direction as the member it names.

    A member and the word it carries are the same thing here -- the enum is a
    ``str`` subclass, so a word *is* the member's value -- but only the member
    answers ``.value``, and an artifact hands back the word. Normalising at
    construction keeps one spelling inside the node and lets the formatter read
    a field rather than guess what it was given.
    """
    if isinstance(value, SQLServerPartitionRangeDirection):
        return value
    if isinstance(value, str):
        try:
            return SQLServerPartitionRangeDirection(value.strip().upper())
        except ValueError:
            pass
    raise ValueError(
        f"unknown RANGE direction {value!r}; use LEFT or RIGHT"
    )


class SQLServerPartitionByRangeClause(PartitionClause):
    """SQL Server RANGE partitioning clause with boundary direction.

    SQL Server only supports RANGE partitioning. The direction
    (LEFT or RIGHT) specifies which side of each boundary value
    belongs to the partition. RIGHT is the default in SQL Server.
    """
    KIND_RESERVED = ("SQLServer",)

    strategy_type = PartitionStrategy

    def __init__(
        self,
        dialect: "SQLServerDialect",
        keys: Sequence[BaseExpression],
        partition_scheme: str,
        *,
        range_direction: SQLServerPartitionRangeDirection = SQLServerPartitionRangeDirection.RIGHT,
    ):
        super().__init__(
            dialect,
            PartitionStrategy.RANGE,
            keys,
        )
        self.partition_scheme = partition_scheme
        self.range_direction = _as_range_direction(range_direction)

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_partition_clause(self)


class SQLServerPartitionFunctionExpression(BaseExpression):
    """CREATE PARTITION FUNCTION statement.

    Defines boundary values for partitioning a table.
    Example:
        CREATE PARTITION FUNCTION pf_name (DATE)
        AS RANGE RIGHT FOR VALUES ('2020-01-01', '2021-01-01')
    """
    KIND_RESERVED = ("SQLServer",)

    def __init__(
        self,
        dialect: "SQLServerDialect",
        function_name: str,
        data_type: str,
        boundary_values: Sequence[Any],
        *,
        range_direction: SQLServerPartitionRangeDirection = SQLServerPartitionRangeDirection.RIGHT,
    ):
        super().__init__(dialect)
        self.function_name = function_name
        self.data_type = data_type
        self.boundary_values = list(boundary_values)
        self.range_direction = _as_range_direction(range_direction)

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_partition_function_expression(self)


class SQLServerPartitionSchemeExpression(BaseExpression):
    """CREATE PARTITION SCHEME statement.

    Maps partitions defined by a partition function to filegroups.
    Example:
        CREATE PARTITION SCHEME ps_name
        AS PARTITION pf_name
        TO ([PRIMARY], fg1, fg2)
    """
    KIND_RESERVED = ("SQLServer",)

    def __init__(
        self,
        dialect: "SQLServerDialect",
        scheme_name: str,
        function_name: str,
        filegroups: Sequence[str],
        *,
        all_filegroup: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.scheme_name = scheme_name
        self.function_name = function_name
        self.filegroups = list(filegroups)
        if all_filegroup and filegroups:
            raise ValueError("all_filegroup and filegroups are mutually exclusive")
        self.all_filegroup = all_filegroup

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_partition_scheme_expression(self)
