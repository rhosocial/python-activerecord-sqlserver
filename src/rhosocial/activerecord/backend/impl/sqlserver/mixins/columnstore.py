# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/columnstore.py
"""SQL Server columnstore index mixin.

Implements the ``format_create_columnstore_index_statement`` formatter used
by ``SQLServerColumnstoreIndexExpression`` with version gating:

- NONCLUSTERED COLUMNSTORE INDEX: SQL Server 2012+ (read-only)
- CLUSTERED COLUMNSTORE INDEX: SQL Server 2014+ (updatable)
- ORDER (...) ordered columnstore: SQL Server 2022+
"""

from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.columnstore import SQLServerColumnstoreIndexExpression


_SQL_SERVER_NONCLUSTERED_COLUMNSTORE_VERSION = (11, 0, 0)
_SQL_SERVER_CLUSTERED_COLUMNSTORE_VERSION = (12, 0, 0)
_SQL_SERVER_COLUMNSTORE_ORDER_VERSION = (16, 0, 0)


class SQLServerColumnstoreIndexMixin:
    """SQL Server columnstore index creation implementation."""

    def supports_nonclustered_columnstore(self) -> bool:
        """NONCLUSTERED columnstore requires SQL Server 2012+."""
        return self.version >= _SQL_SERVER_NONCLUSTERED_COLUMNSTORE_VERSION  # type: ignore[attr-defined]

    def supports_clustered_columnstore(self) -> bool:
        """CLUSTERED columnstore requires SQL Server 2014+."""
        return self.version >= _SQL_SERVER_CLUSTERED_COLUMNSTORE_VERSION  # type: ignore[attr-defined]

    def supports_columnstore_order(self) -> bool:
        """ORDER (...) requires SQL Server 2022+."""
        return self.version >= _SQL_SERVER_COLUMNSTORE_ORDER_VERSION  # type: ignore[attr-defined]

    def format_create_columnstore_index_statement(
        self, expr: "SQLServerColumnstoreIndexExpression"
    ) -> Tuple[str, tuple]:
        """Format a CREATE COLUMNSTORE INDEX statement with version gating.

        SQL Syntax:
            CREATE [CLUSTERED | NONCLUSTERED] COLUMNSTORE INDEX name ON table
            [ (columns) ] [ ORDER (order_columns) ]
        """
        parts = ["CREATE"]

        if expr.clustered is False:
            self.check_feature_support(  # type: ignore[attr-defined]
                "supports_nonclustered_columnstore",
                "NONCLUSTERED COLUMNSTORE INDEX",
                "requires SQL Server 2012+ (read-only; updatable columnstore "
                "requires SQL Server 2014+).",
            )
            parts.append("NONCLUSTERED")
        else:
            self.check_feature_support(  # type: ignore[attr-defined]
                "supports_clustered_columnstore",
                "CLUSTERED COLUMNSTORE INDEX",
                "requires SQL Server 2014+.",
            )
            if expr.clustered is True:
                parts.append("CLUSTERED")

        parts.append("COLUMNSTORE")
        parts.append("INDEX")
        parts.append(self.format_identifier(expr.index_name))  # type: ignore[attr-defined]
        parts.append("ON")
        parts.append(self.format_identifier(expr.table_name))  # type: ignore[attr-defined]

        if expr.columns:
            columns_str = ", ".join(
                self.format_identifier(col)  # type: ignore[attr-defined]
                for col in expr.columns
            )
            parts.append(f"({columns_str})")

        if expr.order_columns:
            self.check_feature_support(  # type: ignore[attr-defined]
                "supports_columnstore_order",
                "ORDER (...) ordered columnstore index",
                "requires SQL Server 2022+.",
            )
            order_str = ", ".join(
                self.format_identifier(col)  # type: ignore[attr-defined]
                for col in expr.order_columns
            )
            parts.append(f"ORDER ({order_str})")

        return " ".join(parts), ()
