# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/schema.py
from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Schema

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

        Raises:
            TypeError: ``expr.schema`` is not a Schema. A table handed here
                would render as a well-formed ``CREATE SCHEMA`` over that
                table's name.
        """
        if not isinstance(expr.schema, Schema):
            raise TypeError(
                f"CreateSchemaExpression.schema must be a Schema, "
                f"got {type(expr.schema).__name__}"
            )
        parts = ["CREATE SCHEMA"]
        parts.append(expr.schema.to_sql()[0])
        if expr.authorization:
            parts.append(f"AUTHORIZATION {self.format_identifier(expr.authorization)}")
        return " ".join(parts), ()

    def format_drop_schema_statement(self, expr: "DropSchemaExpression") -> Tuple[str, tuple]:
        """Format DROP SCHEMA for SQL Server.

        SQL Server requires schema to be empty before dropping.
        Does not support IF EXISTS or CASCADE. Neither ``CASCADE`` nor
        ``RESTRICT`` is in the T-SQL grammar (measured refused on 2019 / 2022 /
        2025); this override replaces core's gated formatter, so an explicitly
        requested behavior is refused by name rather than silently dropped.

        Raises:
            TypeError: ``expr.schema`` is not a Schema. A table handed here
                would render as a well-formed ``DROP SCHEMA`` over that table's
                name.
            UnsupportedFeatureError: If CASCADE or RESTRICT was requested.
        """
        if not isinstance(expr.schema, Schema):
            raise TypeError(
                f"DropSchemaExpression.schema must be a Schema, "
                f"got {type(expr.schema).__name__}"
            )
        if expr.cascade and not self.supports_schema_cascade():
            raise UnsupportedFeatureError(
                self.name, "DROP SCHEMA CASCADE",
                f"{self.name} does not support DROP SCHEMA CASCADE."
            )
        if expr.restrict and not self.supports_schema_restrict():
            raise UnsupportedFeatureError(
                self.name, "DROP SCHEMA RESTRICT",
                f"{self.name} does not support DROP SCHEMA RESTRICT."
            )
        return f"DROP SCHEMA {expr.schema.to_sql()[0]}", ()
