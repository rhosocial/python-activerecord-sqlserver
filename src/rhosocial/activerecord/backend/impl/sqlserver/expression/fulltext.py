# src/rhosocial/activerecord/backend/impl/sqlserver/expression/fulltext.py
"""SQL Server FULLTEXT CATALOG / FULLTEXT INDEX DDL expressions.

SQL Server full-text search requires a catalog object that owns the indexes:

    CREATE FULLTEXT CATALOG ftc AS DEFAULT;
    CREATE FULLTEXT INDEX ON t (body) KEY INDEX pk ON ftc;
    DROP FULLTEXT INDEX ON t;
    DROP FULLTEXT CATALOG ftc;

SQL generation and version gating are delegated to the dialect's
``format_create/drop_fulltext_catalog_statement`` and
``format_create/drop_fulltext_index_statement`` formatters.
"""

from typing import List, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams

if TYPE_CHECKING:
    from ..dialect import SQLServerDialect


class SQLServerCreateFullTextCatalogExpression(BaseExpression):
    """SQL Server CREATE FULLTEXT CATALOG statement (2005+).

    Attributes:
        catalog_name: Name of the full-text catalog.
        is_default: Whether to render ``AS DEFAULT`` (sets the default catalog
            for the database).

    Example:
        >>> expr = SQLServerCreateFullTextCatalogExpression(dialect, "ftc", is_default=True)
        >>> sql, params = expr.to_sql()
        >>> assert sql == "CREATE FULLTEXT CATALOG [ftc] AS DEFAULT"
    """

    def __init__(
        self,
        dialect: "SQLServerDialect",
        catalog_name: str,
        is_default: bool = False,
    ):
        super().__init__(dialect)
        self.catalog_name = catalog_name
        self.is_default = is_default

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not self.catalog_name:
            raise ValueError("catalog_name is required")

    def to_sql(self) -> SQLQueryAndParams:
        sql = self.dialect.format_create_fulltext_catalog_statement(
            self.catalog_name, as_default=self.is_default
        )
        return sql, ()


class SQLServerDropFullTextCatalogExpression(BaseExpression):
    """SQL Server DROP FULLTEXT CATALOG statement (2005+).

    Attributes:
        catalog_name: Name of the full-text catalog to drop.

    Example:
        >>> expr = SQLServerDropFullTextCatalogExpression(dialect, "ftc")
        >>> sql, params = expr.to_sql()
        >>> assert sql == "DROP FULLTEXT CATALOG [ftc]"
    """

    def __init__(self, dialect: "SQLServerDialect", catalog_name: str):
        super().__init__(dialect)
        self.catalog_name = catalog_name

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not self.catalog_name:
            raise ValueError("catalog_name is required")

    def to_sql(self) -> SQLQueryAndParams:
        sql = self.dialect.format_drop_fulltext_catalog_statement(self.catalog_name)
        return sql, ()


class SQLServerCreateFullTextIndexExpression(BaseExpression):
    """SQL Server CREATE FULLTEXT INDEX statement (2005+).

    Attributes:
        table: Table to index.
        columns: Columns to include in the full-text index.
        key_index: Unique single-column index used as the full-text key.
        catalog_name: Catalog that owns the full-text index.

    Example:
        >>> expr = SQLServerCreateFullTextIndexExpression(
        ...     dialect, "t", ["body"], key_index="pk", catalog_name="ftc"
        ... )
        >>> sql, params = expr.to_sql()
        >>> assert sql == "CREATE FULLTEXT INDEX ON [t] ([body]) KEY INDEX [pk] ON [ftc]"
    """

    def __init__(
        self,
        dialect: "SQLServerDialect",
        table: str,
        columns: List[str],
        key_index: str,
        catalog_name: str,
    ):
        super().__init__(dialect)
        self.table = table
        self.columns = list(columns)
        self.key_index = key_index
        self.catalog_name = catalog_name

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not self.table:
            raise ValueError("table is required")
        if not self.columns:
            raise ValueError("at least one full-text column is required")
        if not self.key_index:
            raise ValueError("key_index is required")
        if not self.catalog_name:
            raise ValueError("catalog_name is required")

    def to_sql(self) -> SQLQueryAndParams:
        sql = self.dialect.format_create_fulltext_index_statement(
            self.table,
            self.columns,
            self.key_index,
            self.catalog_name,
        )
        return sql, ()


class SQLServerDropFullTextIndexExpression(BaseExpression):
    """SQL Server DROP FULLTEXT INDEX statement (2005+).

    Attributes:
        table: Table whose full-text index should be dropped.

    Example:
        >>> expr = SQLServerDropFullTextIndexExpression(dialect, "t")
        >>> sql, params = expr.to_sql()
        >>> assert sql == "DROP FULLTEXT INDEX ON [t]"
    """

    def __init__(self, dialect: "SQLServerDialect", table: str):
        super().__init__(dialect)
        self.table = table

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not self.table:
            raise ValueError("table is required")

    def to_sql(self) -> SQLQueryAndParams:
        sql = self.dialect.format_drop_fulltext_index_statement(self.table)
        return sql, ()
