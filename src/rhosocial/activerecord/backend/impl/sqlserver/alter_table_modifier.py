# src/rhosocial/activerecord/backend/impl/sqlserver/alter_table_modifier.py
"""SQL Server ALTER TABLE column IF EXISTS handling.

Kept as a sibling module of ``dialect.py`` (like ``collation.py``) to avoid
the circular import triggered by the eager ``mixins/__init__.py`` chain
(``mixins/backend_mixin`` -> ``dialect``).
"""

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


_SQL_SERVER_SPARSE_COLUMN_VERSION = (10, 0, 0)
_SQL_SERVER_MASKED_COLUMN_VERSION = (13, 0, 0)


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

    def format_alter_column_action(self, action):
        """Dispatch an ALTER COLUMN action to a SQL Server-specific formatter.

        SQL Server re-specifies the full column rather than applying the
        standard SET/DROP subclauses. The ``operation`` value selects the
        variant:

        - ``SET DATA TYPE`` (or ``dialect_options["data_type"]``) renders the
          T-SQL ``ALTER COLUMN col type [COLLATE ...] [NULL | NOT NULL] [SPARSE]``
          form via ``format_alter_column_type_action``.
        - ``ADD MASKED`` renders dynamic data masking via
          ``format_add_masked_action``.
        - ``DROP MASKED`` renders ``format_drop_masked_action``.
        """
        operation = action.operation
        op_str = operation.value if hasattr(operation, "value") else str(operation)
        dialect_options = getattr(action, "dialect_options", None) or {}

        if op_str == "ADD MASKED" or "masked_function" in dialect_options:
            return self.format_add_masked_action(action)
        if op_str == "DROP MASKED" or dialect_options.get("drop_masked"):
            return self.format_drop_masked_action(action)
        if op_str == "SET DATA TYPE" or "data_type" in dialect_options:
            return self.format_alter_column_type_action(action)

        raise UnsupportedFeatureError(
            self.name,
            f"ALTER COLUMN {op_str}",
            "SQL Server requires re-specifying the full column. Use "
            "operation='SET DATA TYPE' with dialect_options to add "
            "NULL/NOT NULL, COLLATE, SPARSE, or MASKED.",
        )

    def format_alter_column_type_action(self, action):
        """Format a T-SQL ALTER COLUMN type change.

        SQL Syntax:
            ALTER COLUMN column data_type [COLLATE collation]
            [NULL | NOT NULL] [SPARSE]

        The data type comes from ``dialect_options["data_type"]`` or the
        action's ``new_value``. ``not_null``, ``collate``, and ``sparse``
        are carried in ``dialect_options``.
        """
        dialect_options = getattr(action, "dialect_options", None) or {}
        data_type = dialect_options.get("data_type") or action.new_value
        if data_type is None:
            raise ValueError("data type is required for ALTER COLUMN")

        parts = [
            "ALTER COLUMN",
            self.format_identifier(action.column_name),
            str(data_type),
        ]

        collate = dialect_options.get("collate")
        if collate:
            parts.append(f"COLLATE {collate}")

        not_null = dialect_options.get("not_null")
        if not_null is not None:
            parts.append("NOT NULL" if not_null else "NULL")

        if dialect_options.get("sparse"):
            if self.version < _SQL_SERVER_SPARSE_COLUMN_VERSION:  # type: ignore[attr-defined]
                raise UnsupportedFeatureError(
                    self.name,
                    "SPARSE column",
                    suggestion="requires SQL Server 2008+.",
                )
            parts.append("SPARSE")

        return " ".join(parts), ()

    def format_add_masked_action(self, action):
        """Format ALTER COLUMN ... ADD MASKED (dynamic data masking, 2016+).

        SQL Syntax:
            ALTER COLUMN column ADD MASKED WITH (FUNCTION = 'mask_function')

        The mask function is carried in ``dialect_options["masked_function"]``
        or the action's ``new_value``.
        """
        if self.version < _SQL_SERVER_MASKED_COLUMN_VERSION:  # type: ignore[attr-defined]
            raise UnsupportedFeatureError(
                self.name,
                "ADD MASKED (dynamic data masking)",
                suggestion="requires SQL Server 2016+.",
            )

        dialect_options = getattr(action, "dialect_options", None) or {}
        function = dialect_options.get("masked_function") or action.new_value
        if function is None:
            raise ValueError("masked_function is required for ADD MASKED")

        escaped = str(function).replace("'", "''")
        return (
            f"ALTER COLUMN {self.format_identifier(action.column_name)} "
            f"ADD MASKED WITH (FUNCTION = '{escaped}')",
            (),
        )

    def format_drop_masked_action(self, action):
        """Format ALTER COLUMN ... DROP MASKED (dynamic data masking, 2016+).

        SQL Syntax:
            ALTER COLUMN column DROP MASKED
        """
        if self.version < _SQL_SERVER_MASKED_COLUMN_VERSION:  # type: ignore[attr-defined]
            raise UnsupportedFeatureError(
                self.name,
                "DROP MASKED (dynamic data masking)",
                suggestion="requires SQL Server 2016+.",
            )

        return (
            f"ALTER COLUMN {self.format_identifier(action.column_name)} DROP MASKED",
            (),
        )