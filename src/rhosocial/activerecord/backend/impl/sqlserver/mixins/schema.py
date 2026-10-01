# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/schema.py
from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.mixins.ddl_column import DDLColumnMixin

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.core import Column
    from rhosocial.activerecord.backend.expression.statements import (
        CreateSchemaExpression,
        DropSchemaExpression,
    )


class SQLServerSchemaMixin:
    """SQL Server schema capability declarations and formatting."""

    def format_column(self, expr: "Column") -> Tuple[str, tuple]:
        """Render a column reference without the schema part.

        The generic renderer emits ``schema.table.column`` whenever both a
        schema and a table are set. PostgreSQL accepts that; SQL Server does
        not -- a column prefix is a table or an alias, never
        ``[schema].[table]``, so ``[ar_crm].[orders].[id]`` is a syntax error
        and an explicitly selected column on a schema-bound model could not
        be run at all.

        Dropping the schema is what resolves it: the FROM range already
        carries ``[ar_crm]``, so ``[orders].[id]`` binds against it. When the
        range is aliased the column's ``table`` is the alias and the same
        reasoning holds.

        A schema with no table is passed through untouched so the generic
        renderer's error still fires -- a schema-qualified column with nothing
        to qualify is a caller bug on this dialect too.
        """
        if not (expr.schema_name and expr.table):
            return DDLColumnMixin.format_column(self, expr)

        original = expr.schema_name
        expr.schema_name = None
        try:
            return DDLColumnMixin.format_column(self, expr)
        finally:
            expr.schema_name = original

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
