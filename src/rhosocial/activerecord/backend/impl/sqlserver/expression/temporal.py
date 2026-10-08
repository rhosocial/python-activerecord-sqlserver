# src/rhosocial/activerecord/backend/impl/sqlserver/expression/temporal.py
"""SQL Server temporal table expressions (2016+)."""

from typing import Optional, Union, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams
from rhosocial.activerecord.backend.expression.objects import Table

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class SQLServerTemporalPeriodDefinition(BaseExpression):
    """SQL Server PERIOD FOR SYSTEM_TIME definition for temporal tables.

    Defines the period columns used for system-versioned temporal tables.

    Example:
        >>> expr = SQLServerTemporalPeriodDefinition(dialect, "SysStartTime", "SysEndTime")
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        start_column: str = "SysStartTime",
        end_column: str = "SysEndTime",
    ):
        super().__init__(dialect)
        self.start_column = start_column
        self.end_column = end_column

    def to_sql(self) -> SQLQueryAndParams:
        start = self.dialect.format_identifier(self.start_column)
        end = self.dialect.format_identifier(self.end_column)
        return f"PERIOD FOR SYSTEM_TIME ({start}, {end})", ()


class SQLServerSystemVersioningClause(BaseExpression):
    """SQL Server SYSTEM_VERSIONING clause for temporal tables.

    Enables system-versioning on a temporal table.

    The history table is one schema object, not a name plus a parallel schema
    string: ``WITH (SYSTEM_VERSIONING = ON, HISTORY_TABLE = dbo.TestTableHistory)``
    names a single object living in a namespace, and splitting that into two
    constructor parameters was the same namespace-smuggling the schema-object
    layer exists to remove.

    Example:
        >>> from rhosocial.activerecord.backend.expression.objects import Table
        >>> clause = SQLServerSystemVersioningClause(
        ...     dialect, Table(dialect, "TestTableHistory", schema_name="dbo")
        ... )
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        history_table: Optional[Union[Table, str]] = None,
    ):
        """Record the history table this clause points at.

        Args:
            dialect: The SQL Server dialect.
            history_table: The history table, as a
                :class:`~rhosocial.activerecord.backend.expression.objects.Table`.
                A bare string is accepted as shorthand for an unqualified name;
                pass the object to place the table in a schema or catalog.
        """
        super().__init__(dialect)
        if history_table is None:
            self.history_table: Optional[Table] = None
        elif isinstance(history_table, str):
            self.history_table = Table(dialect, history_table)
        elif isinstance(history_table, Table):
            self.history_table = history_table
        else:
            raise TypeError(
                f"history_table must be a Table or a string, "
                f"got {type(history_table).__name__}"
            )

    def to_sql(self) -> SQLQueryAndParams:
        sql = "WITH (SYSTEM_VERSIONING = ON"
        if self.history_table is not None:
            sql += f", HISTORY_TABLE = {self.history_table.to_sql()[0]}"
        sql += ")"
        return sql, ()