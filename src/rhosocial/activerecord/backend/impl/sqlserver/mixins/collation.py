# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/collation.py
from typing import Any, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from ..collation import validate_sqlserver_collation_name

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.collation import CollateExpression


class SQLServerCollationMixin:
    """SQL Server COLLATE expression support."""

    def supports_collate_expression(self) -> bool:
        """SQL Server supports expression-level COLLATE."""
        return True

    def validate_collation_name(self, expr: "CollateExpression") -> str:
        """Validate SQL Server collation names and return their SQL representation."""
        if "schema" in expr.collation_options:
            raise UnsupportedFeatureError(self.name, "schema-qualified COLLATE")
        keyword = expr.collation_options.get("keyword", False)
        unsupported = set(expr.collation_options) - {"keyword", "schema"}
        if unsupported:
            options = ", ".join(sorted(unsupported))
            raise UnsupportedFeatureError(self.name, f"COLLATE options: {options}")
        if keyword and expr.collation_name != "DATABASE_DEFAULT":
            raise ValueError(f"Unsupported SQL Server collation keyword: {expr.collation_name!r}")
        return validate_sqlserver_collation_name(expr.collation_name, getattr(self, "version", None))
