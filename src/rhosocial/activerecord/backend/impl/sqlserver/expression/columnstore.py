# src/rhosocial/activerecord/backend/impl/sqlserver/expression/columnstore.py
"""SQL Server columnstore index DDL expression.

Columnstore indexes are the analytic workload workhorse of SQL Server:

    CREATE CLUSTERED COLUMNSTORE INDEX cci ON t;            -- 2014+, updatable
    CREATE NONCLUSTERED COLUMNSTORE INDEX ncci ON t (c);    -- 2012+, read-only
    CREATE COLUMNSTORE INDEX cci ON t ORDER (c1, c2);       -- 2022+, ordered CCI

SQL generation and version gating are delegated to the dialect's
``format_create_columnstore_index_statement`` formatter.
"""

from typing import Optional, Sequence, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams

if TYPE_CHECKING:
    from ..dialect import SQLServerDialect


class SQLServerColumnstoreIndexExpression(BaseExpression):
    """SQL Server CREATE [CLUSTERED|NONCLUSTERED] COLUMNSTORE INDEX statement.

    Attributes:
        index_name: Name of the columnstore index.
        table_name: Table on which the index is created.
        columns: Key columns. Required for NONCLUSTERED columnstore
            (``clustered=False``), forbidden for clustered columnstore.
        clustered: If ``None`` the CLUSTERED/NONCLUSTERED keyword is omitted
            (defaults to a clustered columnstore); ``True`` renders
            CLUSTERED, ``False`` renders NONCLUSTERED.
        order_columns: Optional ORDER (...) columns for ordered clustered
            columnstore (SQL Server 2022+).

    Example:
        >>> expr = SQLServerColumnstoreIndexExpression(
        ...     dialect, "cci", "t", clustered=True, order_columns=["c1", "c2"]
        ... )
        >>> sql, params = expr.to_sql()
        >>> assert sql == "CREATE CLUSTERED COLUMNSTORE INDEX [cci] ON [t] ORDER ([c1], [c2])"
    """

    def __init__(
        self,
        dialect: "SQLServerDialect",
        index_name: str,
        table_name: str,
        columns: Sequence[str] = (),
        clustered: Optional[bool] = None,
        order_columns: Sequence[str] = (),
    ):
        super().__init__(dialect)
        self.index_name = index_name
        self.table_name = table_name
        self.columns = list(columns)
        self.clustered = clustered
        self.order_columns = list(order_columns)

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if self.clustered is False and not self.columns:
            raise ValueError("NONCLUSTERED columnstore requires key columns")
        if self.clustered is not False and self.columns:
            raise ValueError("clustered columnstore does not allow key columns")
        if self.order_columns and self.clustered is False:
            raise ValueError("ORDER (...) is only valid for clustered columnstore")

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_create_columnstore_index_statement(self)
