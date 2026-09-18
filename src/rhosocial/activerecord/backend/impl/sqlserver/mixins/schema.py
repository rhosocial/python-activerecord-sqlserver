# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/schema.py
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import (
        CreateSchemaExpression,
        DropSchemaExpression,
    )


class SQLServerSchemaMixin:
    """SQL Server schema capability declarations and formatting."""

    def supports_create_schema(self) -> bool:
        """SQL Server supports CREATE SCHEMA."""
        return True

    def supports_drop_schema(self) -> bool:
        """SQL Server supports DROP SCHEMA."""
        return True

    def supports_schema(self) -> bool:
        """SQL Server models named schema namespaces natively (e.g. dbo)."""
        return True

    def supports_schema_authorization(self) -> bool:
        """SQL Server accepts CREATE SCHEMA ... AUTHORIZATION owner."""
        return True

    def format_create_schema_statement(self, expr: "CreateSchemaExpression") -> Tuple[str, tuple]:
        """Format CREATE SCHEMA for SQL Server.

        SQL Server uses CREATE SCHEMA schema_name [AUTHORIZATION owner_name].
        Does not support IF NOT EXISTS.
        """
        parts = ["CREATE SCHEMA"]
        parts.append(self.format_identifier(expr.schema_name))
        if expr.authorization:
            parts.append(f"AUTHORIZATION {self.format_identifier(expr.authorization)}")
        return " ".join(parts), ()

    def format_drop_schema_statement(self, expr: "DropSchemaExpression") -> Tuple[str, tuple]:
        """Format DROP SCHEMA for SQL Server.

        SQL Server requires schema to be empty before dropping.
        Does not support IF EXISTS or CASCADE.
        """
        parts = ["DROP SCHEMA"]
        parts.append(self.format_identifier(expr.schema_name))
        return " ".join(parts), ()
