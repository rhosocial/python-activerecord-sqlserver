# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/schema.py
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
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
        There is no IF NOT EXISTS clause, so asking for one is refused rather
        than dropped: a caller who set the flag would otherwise get a statement
        that fails on an existing schema instead of the no-op it asked for.
        """
        if expr.if_not_exists and not self.supports_schema_if_not_exists():
            raise UnsupportedFeatureError(
                self.name,
                "CREATE SCHEMA IF NOT EXISTS",
                f"{self.name} has no IF NOT EXISTS clause for CREATE SCHEMA. "
                f"Drop the flag, or guard the call yourself.",
            )

        parts = ["CREATE SCHEMA"]
        parts.append(self.format_identifier(expr.schema_name))
        if expr.authorization:
            parts.append(f"AUTHORIZATION {self.format_identifier(expr.authorization)}")
        return " ".join(parts), ()

    def format_drop_schema_statement(self, expr: "DropSchemaExpression") -> Tuple[str, tuple]:
        """Format DROP SCHEMA for SQL Server.

        SQL Server requires schema to be empty before dropping.
        There is neither an IF EXISTS nor a CASCADE clause, so asking for one
        is refused rather than dropped: a caller who set the flag would
        otherwise get a statement that fails instead of the no-op it asked for.
        """
        if expr.if_exists and not self.supports_schema_if_exists():
            raise UnsupportedFeatureError(
                self.name,
                "DROP SCHEMA IF EXISTS",
                f"{self.name} has no IF EXISTS clause for DROP SCHEMA. "
                f"Drop the flag, or guard the call yourself.",
            )
        if expr.cascade and not self.supports_schema_cascade():
            raise UnsupportedFeatureError(
                self.name,
                "DROP SCHEMA CASCADE",
                f"{self.name} cannot drop a schema together with its contents. "
                f"Empty it first, or drop the flag.",
            )

        parts = ["DROP SCHEMA"]
        parts.append(self.format_identifier(expr.schema_name))
        return " ".join(parts), ()
