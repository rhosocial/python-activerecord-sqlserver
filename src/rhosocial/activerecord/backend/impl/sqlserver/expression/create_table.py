# src/rhosocial/activerecord/backend/impl/sqlserver/expression/create_table.py
"""SQL Server-specific CREATE TABLE expression.

SQL Server adds table-level graph features with no generic equivalent:

* ``graph_table_kind`` — ``AS NODE`` / ``AS EDGE`` (SQL Server 2017+).
* ``edge_constraints`` — ``CONSTRAINT <name> CONNECTION (...)`` (SQL Server
  2019+).

They live on ``SQLServerCreateTableExpression`` (deriving the generic
``CreateTableExpression``) and are rendered by the SQL Server
``format_create_table_statement`` override.
"""

from typing import Any, List, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnDefinition,
    CreateTableExpression,
    CreateTableOptions,
    IndexDefinition,
    StorageOptionsExpression,
    TableConstraint,
)

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase
    from rhosocial.activerecord.backend.expression.statements.ddl_partition import (
        PartitionClause,
    )


class SQLServerCreateTableExpression(CreateTableExpression):
    """A SQL Server CREATE TABLE statement extending the generic one.

    Adds the SQL Server-only ``graph_table_kind`` / ``edge_constraints`` table
    features.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        table: Any,
        columns: List[ColumnDefinition],
        indexes: Optional[List[IndexDefinition]] = None,
        table_constraints: Optional[List[TableConstraint]] = None,
        temporary: bool = False,
        if_not_exists: bool = False,
        inherits: Optional[List[str]] = None,
        tablespace: Optional[str] = None,
        storage_options: Optional["StorageOptionsExpression"] = None,
        *,
        partition: Optional["PartitionClause"] = None,
        table_options: Optional["CreateTableOptions"] = None,
        graph_table_kind: Any = None,
        edge_constraints: Optional[List[Any]] = None,
    ):
        super().__init__(
            dialect,
            table,
            columns,
            indexes=indexes,
            table_constraints=table_constraints,
            temporary=temporary,
            if_not_exists=if_not_exists,
            inherits=inherits,
            tablespace=tablespace,
            storage_options=storage_options,
            partition=partition,
            table_options=table_options,
        )
        self.graph_table_kind = graph_table_kind
        self.edge_constraints = edge_constraints or []
