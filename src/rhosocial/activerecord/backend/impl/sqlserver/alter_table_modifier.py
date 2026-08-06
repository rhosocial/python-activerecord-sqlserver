# src/rhosocial/activerecord/backend/impl/sqlserver/alter_table_modifier.py
"""SQL Server ALTER TABLE column IF EXISTS handling.

Kept as a sibling module of ``dialect.py`` (like ``collation.py``) to avoid
the circular import triggered by the eager ``mixins/__init__.py`` chain
(``mixins/backend_mixin`` -> ``dialect``).
"""

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class SQLServerAlterColumnModifierMixin:
    """SQL Server ALTER TABLE column modifiers.

    SQL Server supports ``DROP COLUMN IF EXISTS`` and
    ``DROP CONSTRAINT IF EXISTS`` since 2016, but **not**
    ``ADD COLUMN IF NOT EXISTS``. Applications opt in via
    ``if_exists`` / ``if_not_exists``; ``None`` (default) renders the
    plain form.
    """

    def supports_add_column_if_not_exists(self) -> bool:
        """SQL Server does not support ``ADD COLUMN IF NOT EXISTS``."""
        return False

    def supports_drop_column_if_exists(self) -> bool:
        """``DROP COLUMN IF EXISTS`` is supported since SQL Server 2016."""
        return True

    def supports_drop_constraint_if_exists(self) -> bool:
        """``DROP CONSTRAINT IF EXISTS`` is supported since SQL Server 2016."""
        return True

    def format_add_column_action(self, action):
        if getattr(action, "if_not_exists", None) is True:
            raise UnsupportedFeatureError(
                self.name,
                "ADD COLUMN IF NOT EXISTS",
                suggestion="SQL Server does not support ADD COLUMN IF NOT EXISTS. "
                           "Pre-check sys.columns / information_schema.COLUMNS.",
            )
        column_sql, column_params = self.format_column_definition(action.column)
        # SQL Server ALTER TABLE ... ADD takes the column without a COLUMN literal.
        return f"ADD {column_sql}", column_params

    def format_drop_column_action(self, action):
        name = self.format_identifier(action.column_name)
        if getattr(action, "if_exists", None) is True:
            return f"DROP COLUMN IF EXISTS {name}", ()
        return f"DROP COLUMN {name}", ()

    def format_drop_table_constraint_action(self, action):
        name = self.format_identifier(action.constraint_name)
        if getattr(action, "if_exists", None) is True:
            result = f"DROP CONSTRAINT IF EXISTS {name}"
        else:
            result = f"DROP CONSTRAINT {name}"
        if getattr(action, "cascade", None):
            result += " CASCADE"
        return result, ()