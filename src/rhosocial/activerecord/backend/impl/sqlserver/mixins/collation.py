# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/collation.py
from enum import Enum
from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from ..collation import validate_sqlserver_collation_name

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.collation import CollateFunction


class SQLServerCollationMixin:
    """SQL Server COLLATE expression support."""

    def supports_collate_expression(self) -> bool:
        """SQL Server supports expression-level COLLATE."""
        return True

    def validate_collation_name(self, expr: "CollateFunction") -> str:
        """Validate SQL Server collation names and return their SQL representation."""
        # Schema-qualified COLLATE (``schema.collation``) is the one option
        # the core node names; SQL Server's grammar does not accept a
        # qualified collation here, so the field is refused rather than
        # silently dropped.
        if expr.schema is not None:
            raise UnsupportedFeatureError(self.name, "schema-qualified COLLATE")
        # The core accepts a bare string or an enum member; the validator
        # speaks strings, so a member is read through its value.
        collation = expr.collation
        if isinstance(collation, Enum):
            collation = collation.value
        return validate_sqlserver_collation_name(collation, getattr(self, "version", None))
