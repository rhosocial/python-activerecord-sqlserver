# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/ddl_database.py
"""SQL Server database DDL mixin."""
from __future__ import annotations

from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.objects import Database

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_database import (
        AlterDatabaseExpression,
        CreateDatabaseExpression,
        DropDatabaseExpression,
    )


class SQLServerDatabaseMixin:
    """SQL Server database DDL support.

    SQL Server supports CREATE/DROP/ALTER DATABASE with AUTHORIZATION,
    COLLATE, file groups, and rich ALTER options.
    """

    def supports_database(self) -> bool:
        return True

    def supports_create_database(self) -> bool:
        return True

    def supports_drop_database(self) -> bool:
        return True

    def supports_alter_database(self) -> bool:
        return True

    def supports_database_owner(self) -> bool:
        """SQL Server supports AUTHORIZATION."""
        return True

    def supports_database_collation(self) -> bool:
        """SQL Server supports COLLATE."""
        return True

    def supports_database_tablespace(self) -> bool:
        """SQL Server supports FILEGROUP."""
        return True

    def format_create_database_statement(
        self, expr: CreateDatabaseExpression
    ) -> Tuple[str, tuple]:
        """Format CREATE DATABASE for SQL Server.

        Raises:
            TypeError: ``expr.database`` is not a Database. A schema or a table
                handed here would render as a well-formed ``CREATE DATABASE``
                over that object's name.
        """
        if not isinstance(expr.database, Database):
            raise TypeError(
                f"CreateDatabaseExpression.database must be a Database, "
                f"got {type(expr.database).__name__}"
            )
        parts = ["CREATE DATABASE"]
        parts.append(expr.database.to_sql()[0])
        if expr.collation:
            parts.append(f"COLLATE {expr.collation}")
        if expr.owner:
            parts.append(f"AUTHORIZATION {self.format_identifier(expr.owner)}")
        return " ".join(parts), ()

    def format_drop_database_statement(
        self, expr: DropDatabaseExpression
    ) -> Tuple[str, tuple]:
        """Format DROP DATABASE for SQL Server.

        Raises:
            TypeError: ``expr.database`` is not a Database. A schema handed here
                would render as a well-formed ``DROP DATABASE`` over that
                schema's name.
        """
        if not isinstance(expr.database, Database):
            raise TypeError(
                f"DropDatabaseExpression.database must be a Database, "
                f"got {type(expr.database).__name__}"
            )
        return f"DROP DATABASE {expr.database.to_sql()[0]}", ()

    def format_alter_database_statement(
        self, expr: AlterDatabaseExpression
    ) -> Tuple[str, tuple]:
        """Format ALTER DATABASE for SQL Server.

        Raises:
            TypeError: ``expr.database`` is not a Database. A schema handed here
                would render as a well-formed ``ALTER DATABASE`` over that
                schema's name.
        """
        from rhosocial.activerecord.backend.expression.statements.ddl_database import AlterDatabaseAction

        if not isinstance(expr.database, Database):
            raise TypeError(
                f"AlterDatabaseExpression.database must be a Database, "
                f"got {type(expr.database).__name__}"
            )
        database = expr.database.to_sql()[0]
        if expr.action == AlterDatabaseAction.OWNER_TO:
            owner = self.format_identifier(expr.target)
            return f"ALTER AUTHORIZATION ON DATABASE::{database} TO {owner}", ()
        parts = ["ALTER DATABASE"]
        parts.append(database)
        if expr.action == AlterDatabaseAction.RENAME_TO:
            parts.append(f"MODIFY NAME = {self.format_identifier(expr.target)}")
        elif expr.action == AlterDatabaseAction.COLLATION:
            parts.append(f"COLLATE {expr.target}")
        return " ".join(parts), ()


__all__ = ['SQLServerDatabaseMixin']
