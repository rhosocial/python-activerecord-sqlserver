# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/schema.py
from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Schema
from .version_constants import SQL_SERVER_2016

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import (
        CreateSchemaStatement,
        DropSchemaStatement,
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

    def supports_schema_if_not_exists(self) -> bool:
        """``CREATE SCHEMA`` has no ``IF NOT EXISTS`` in T-SQL."""
        return False

    def supports_schema_if_exists(self) -> bool:
        """``DROP SCHEMA IF EXISTS`` arrived in SQL Server 2016 (13.x).

        The ``DROP SCHEMA`` reference documents the ``IF EXISTS`` argument as
        applying from SQL Server 2016 onwards; earlier releases have no such
        clause on ``DROP SCHEMA``.
        """
        return self.version_at_least(SQL_SERVER_2016)  # type: ignore[attr-defined]

    def format_create_schema_statement(self, expr: "CreateSchemaStatement") -> Tuple[str, tuple]:
        """Format CREATE SCHEMA for SQL Server.

        SQL Server uses CREATE SCHEMA schema_name [AUTHORIZATION owner_name]
        and has no ``IF NOT EXISTS``, so a request for it is refused by name
        rather than dropped.

        Raises:
            TypeError: ``expr.schema`` is not a Schema. A table handed here
                would render as a well-formed ``CREATE SCHEMA`` over that
                table's name.
            UnsupportedFeatureError: If ``IF NOT EXISTS`` was requested.
        """
        if not isinstance(expr.schema, Schema):
            raise TypeError(
                f"CreateSchemaStatement.schema must be a Schema, "
                f"got {type(expr.schema).__name__}"
            )
        if expr.if_not_exists:
            raise UnsupportedFeatureError(
                self.name,
                "CREATE SCHEMA IF NOT EXISTS",
                "SQL Server has no CREATE SCHEMA IF NOT EXISTS syntax; "
                "check sys.schemas first.",
            )
        parts = ["CREATE SCHEMA"]
        parts.append(expr.schema.to_sql()[0])
        if expr.authorization:
            parts.append(f"AUTHORIZATION {self.format_identifier(expr.authorization)}")
        return " ".join(parts), ()

    def format_drop_schema_statement(self, expr: "DropSchemaStatement") -> Tuple[str, tuple]:
        """Format DROP SCHEMA for SQL Server.

        SQL Server requires schema to be empty before dropping. ``IF EXISTS``
        is rendered on SQL Server 2016+ and refused below that floor, where
        the clause does not exist; neither ``CASCADE`` nor ``RESTRICT`` is in
        the T-SQL grammar (measured refused on 2019 / 2022 / 2025), and this
        override replaces core's gated formatter, so an explicitly requested
        behavior is refused by name rather than silently dropped.

        Raises:
            TypeError: ``expr.schema`` is not a Schema. A table handed here
                would render as a well-formed ``DROP SCHEMA`` over that table's
                name.
            UnsupportedFeatureError: If ``IF EXISTS`` was requested below
                SQL Server 2016, or if CASCADE or RESTRICT was requested.
        """
        if not isinstance(expr.schema, Schema):
            raise TypeError(
                f"DropSchemaStatement.schema must be a Schema, "
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
        parts = ["DROP SCHEMA"]
        if expr.if_exists:
            if not self.supports_schema_if_exists():
                raise UnsupportedFeatureError(
                    self.name,
                    "DROP SCHEMA IF EXISTS",
                    "requires SQL Server 2016+.",
                )
            parts.append("IF EXISTS")
        parts.append(expr.schema.to_sql()[0])
        return " ".join(parts), ()
