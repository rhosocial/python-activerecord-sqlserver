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

import re
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional, Sequence, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams
from rhosocial.activerecord.backend.expression.introspection import IntrospectionExpression
from rhosocial.activerecord.backend.expression.statements import PartitionClause, PartitionStrategy

if TYPE_CHECKING:
    from ..dialect import SQLServerDialect


#: The type spellings a partition function accepts: a name, optionally with
#: one or two non-negative integers as its parameters. The type is written
#: into the catalog question that compares a boundary against it, so the
#: spelling is refused at construction rather than pasted into SQL.
_PARTITION_DATA_TYPE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(\(\s*\d+(\s*,\s*\d+)?\s*\))?$"
)


def validate_partition_data_type(data_type: str) -> str:
    """Return *data_type* if it is a safe partition-function type spelling.

    Args:
        data_type: The declared type of a partition function column,
            e.g. ``DATE``, ``INT``, ``NVARCHAR(50)`` or ``DECIMAL(10, 2)``.

    Raises:
        ValueError: The spelling is not a plain SQL type with optional
            parameters.
    """
    if not isinstance(data_type, str) or not _PARTITION_DATA_TYPE.match(data_type.strip()):
        raise ValueError(
            f"invalid partition-function data type {data_type!r}; expected e.g. "
            f"DATE, INT, NVARCHAR(50) or DECIMAL(10, 2)"
        )
    return data_type.strip()


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


class _SQLServerPartitionFunctionRangeExpression(BaseExpression, ABC):
    """Shared shape of the two ``ALTER PARTITION FUNCTION`` range verbs.

    SQL Server removes or adds one boundary at a time: there is no
    ``DROP PARTITION`` and no way to create an empty partition on its own. The
    two statements differ only by the verb, so the rendering is shared in the
    dialect and each concrete class carries its own renderer.

    Abstract so the expression matrix does not take this shape for a statement
    of its own: it has no verb, and only the two concrete classes do.
    """

    KIND_RESERVED = ("SQLServer",)

    #: ``SPLIT`` or ``MERGE``; each concrete subclass fixes it.
    verb: str = ""

    def __init__(
        self,
        dialect: "SQLServerDialect",
        function_name: str,
        boundary_value: Any,
    ):
        """Record one range operation.

        Args:
            dialect: The dialect that renders the statement.
            function_name: Partition function name, optionally dotted.
            boundary_value: The boundary the operation acts on. SQL Server
                accepts only a constant here, so the value is rendered as an
                inline literal rather than as a bind parameter.
        """
        super().__init__(dialect)
        if not isinstance(function_name, str) or not function_name.strip():
            raise ValueError("function_name must be a non-empty string")
        self.function_name = function_name
        self.boundary_value = boundary_value

    @abstractmethod
    def to_sql(self) -> SQLQueryAndParams:
        """Render the concrete range statement."""


class SQLServerPartitionFunctionSplitExpression(
    _SQLServerPartitionFunctionRangeExpression
):
    """``ALTER PARTITION FUNCTION ... SPLIT RANGE`` -- adds one boundary.

    Splitting an existing partition at a new boundary is how a partitioned
    table gains a partition in SQL Server; the partition function itself is
    created with a fixed number of boundaries and the scheme must have a
    ``NEXT USED`` filegroup before a split can consume one.
    """

    verb = "SPLIT"

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_partition_function_split_expression(self)


class SQLServerPartitionFunctionMergeExpression(
    _SQLServerPartitionFunctionRangeExpression
):
    """``ALTER PARTITION FUNCTION ... MERGE RANGE`` -- removes one boundary.

    Merging two adjacent partitions is the only way to remove a partition:
    SQL Server has no ``DROP PARTITION``. The rows before the boundary become
    part of the partition on their left, so this is a data-affecting
    operation, not metadata-only.
    """

    verb = "MERGE"

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_partition_function_merge_expression(self)


class SQLServerPartitionSchemeNextUsedExpression(BaseExpression):
    """``ALTER PARTITION SCHEME ... NEXT USED`` -- marks a split destination.

    A ``SPLIT RANGE`` consumes one destination from the scheme; the scheme
    must have a filegroup marked ``NEXT USED`` or the split is refused. This
    statement marks one, so the maintenance executor emits it before each
    split rather than relying on the state left by the previous one.
    """

    KIND_RESERVED = ("SQLServer",)

    def __init__(
        self,
        dialect: "SQLServerDialect",
        scheme_name: str,
        filegroup: str,
    ):
        super().__init__(dialect)
        if not isinstance(scheme_name, str) or not scheme_name.strip():
            raise ValueError("scheme_name must be a non-empty string")
        if not isinstance(filegroup, str) or not filegroup.strip():
            raise ValueError("filegroup must be a non-empty string")
        self.scheme_name = scheme_name
        self.filegroup = filegroup

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_partition_scheme_next_used_expression(self)


class SQLServerSwitchPartitionExpression(BaseExpression):
    """``ALTER TABLE ... SWITCH [PARTITION n] TO ... [PARTITION m]``.

    ``SWITCH`` moves a whole partition's storage to another table without
    copying rows. The target must be structurally identical and empty, and
    the source and target must share a filegroup. The statement is the
    SQL Server way to archive or restore one range of a partitioned table.

    A missing source partition means "switch the whole table", which is how a
    non-partitioned table becomes a partition's target; a missing target
    partition means the target is not partitioned.
    """

    KIND_RESERVED = ("SQLServer",)

    def __init__(
        self,
        dialect: "SQLServerDialect",
        table: str,
        target_table: str,
        *,
        source_partition: Optional[int] = None,
        target_partition: Optional[int] = None,
        schema: Optional[str] = None,
        target_schema: Optional[str] = None,
    ):
        """
        Args:
            dialect: The dialect that renders the statement.
            table: Source table name, optionally schema-qualified with dots.
            target_table: Target table name, optionally schema-qualified.
            source_partition: Source partition number, or ``None`` for the
                whole source table.
            target_partition: Target partition number, or ``None`` when the
                target is not partitioned.
            schema: Source schema, when not written into ``table``.
            target_schema: Target schema, when not written into
                ``target_table``.

        Raises:
            ValueError: A name is empty or a partition number is not positive.
        """
        super().__init__(dialect)
        for label, value, table_schema in (
            ("table", table, schema),
            ("target_table", target_table, target_schema),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be a non-empty string")
            if table_schema is not None and "." in value:
                raise ValueError(
                    f"{label} must not carry dots when its schema is passed "
                    f"separately"
                )
        for label, value in (
            ("source_partition", source_partition),
            ("target_partition", target_partition),
        ):
            if value is not None and (not isinstance(value, int) or value < 1):
                raise ValueError(f"{label} must be a positive integer or None")
        self.table = table
        self.target_table = target_table
        self.source_partition = source_partition
        self.target_partition = target_partition
        self.schema = schema
        self.target_schema = target_schema

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_switch_partition_expression(self)


class SQLServerDropPartitionFunctionExpression(BaseExpression):
    """``DROP PARTITION FUNCTION`` -- removes the function itself.

    SQL Server refuses this while any partition scheme uses the function, so
    the maintenance helper checks dependents first; there is no
    ``IF EXISTS`` spelling for these objects.
    """

    KIND_RESERVED = ("SQLServer",)

    def __init__(self, dialect: "SQLServerDialect", function_name: str):
        super().__init__(dialect)
        if not isinstance(function_name, str) or not function_name.strip():
            raise ValueError("function_name must be a non-empty string")
        self.function_name = function_name

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_drop_partition_function_expression(self)


class SQLServerDropPartitionSchemeExpression(BaseExpression):
    """``DROP PARTITION SCHEME`` -- removes the scheme itself.

    A scheme can only be dropped when no table is built ``ON`` it; dropping a
    scheme does not drop the function it maps.
    """

    KIND_RESERVED = ("SQLServer",)

    def __init__(self, dialect: "SQLServerDialect", scheme_name: str):
        super().__init__(dialect)
        if not isinstance(scheme_name, str) or not scheme_name.strip():
            raise ValueError("scheme_name must be a non-empty string")
        self.scheme_name = scheme_name

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_drop_partition_scheme_expression(self)


class _SQLServerPartitionCatalogStatement(IntrospectionExpression, ABC):
    """Shared shape of the catalogue questions partition maintenance asks.

    Every question is a ``SELECT`` over ``sys.partition_*`` / ``sys.tables``,
    optionally narrowed by one name. The statement carries the filter, the
    dialect writes the text, and the maintenance executor only executes what
    comes back -- the same split the rest of this backend's catalogue
    questions use.

    Abstract because it asks no question of its own; each concrete class
    supplies a filter and a renderer.
    """

    KIND_RESERVED = ("SQLServer",)

    @abstractmethod
    def filter_value(self) -> Optional[str]:
        """The one name this statement narrows by, or ``None``."""

    @abstractmethod
    def to_sql(self) -> SQLQueryAndParams:
        """Render this catalogue question."""


class SQLServerPartitionFunctionQueryStatement(_SQLServerPartitionCatalogStatement):
    """Ask for partition functions, their type, direction and boundaries."""

    def __init__(
        self,
        dialect: "SQLServerDialect",
        *,
        function_name: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.function_name = function_name

    @property
    def format_method(self) -> str:
        return "format_partition_function_query_statement"

    def filter_value(self) -> Optional[str]:
        return self.function_name

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_partition_function_query_statement(self)


class SQLServerPartitionSchemeQueryStatement(_SQLServerPartitionCatalogStatement):
    """Ask for partition schemes, their function and destination filegroups."""

    def __init__(
        self,
        dialect: "SQLServerDialect",
        *,
        scheme_name: Optional[str] = None,
        function_name: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.scheme_name = scheme_name
        self.function_name = function_name

    @property
    def format_method(self) -> str:
        return "format_partition_scheme_query_statement"

    def filter_value(self) -> Optional[str]:
        return self.scheme_name

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_partition_scheme_query_statement(self)


class SQLServerPartitionTableQueryStatement(_SQLServerPartitionCatalogStatement):
    """Ask which tables are partitioned, on which scheme and column."""

    def __init__(
        self,
        dialect: "SQLServerDialect",
        *,
        table_name: Optional[str] = None,
        schema: Optional[str] = None,
        scheme_name: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.table_name = table_name
        self.schema = schema
        self.scheme_name = scheme_name

    @property
    def format_method(self) -> str:
        return "format_partition_table_query_statement"

    def filter_value(self) -> Optional[str]:
        return self.table_name

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_partition_table_query_statement(self)


class SQLServerPartitionRangeQueryStatement(_SQLServerPartitionCatalogStatement):
    """Ask for one table's partitions: numbers, row counts, bounds and bytes."""

    def __init__(
        self,
        dialect: "SQLServerDialect",
        *,
        table_name: str,
        schema: Optional[str] = None,
    ):
        super().__init__(dialect)
        if not isinstance(table_name, str) or not table_name.strip():
            raise ValueError("table_name must be a non-empty string")
        self.table_name = table_name
        self.schema = schema

    @property
    def format_method(self) -> str:
        return "format_partition_range_query_statement"

    def filter_value(self) -> Optional[str]:
        return self.table_name

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_partition_range_query_statement(self)


class SQLServerPartitionBoundaryQueryStatement(_SQLServerPartitionCatalogStatement):
    """Ask whether one boundary already exists in a partition function.

    The comparison is made by the server, with the boundary cast to the
    function's declared type. This is what keeps ``ensure`` from splitting at
    a boundary that is already there: ``SPLIT RANGE`` refuses an existing
    boundary, and comparing rendered text is unreliable across date/time
    styles and decimal spellings.
    """

    def __init__(
        self,
        dialect: "SQLServerDialect",
        *,
        function_name: str,
        data_type: str,
        boundary_value: Any,
    ):
        super().__init__(dialect)
        if not isinstance(function_name, str) or not function_name.strip():
            raise ValueError("function_name must be a non-empty string")
        self.function_name = function_name
        self.data_type = validate_partition_data_type(data_type)
        self.boundary_value = boundary_value

    @property
    def format_method(self) -> str:
        return "format_partition_boundary_query_statement"

    def filter_value(self) -> Optional[str]:
        return self.function_name

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_partition_boundary_query_statement(self)
