# src/rhosocial/activerecord/backend/impl/sqlserver/alter_table_modifier.py
"""SQL Server ALTER TABLE column IF EXISTS handling.

Kept as a sibling module of ``dialect.py`` (like ``collation.py``) to avoid
the circular import triggered by the eager ``mixins/__init__.py`` chain
(``mixins/backend_mixin`` -> ``dialect``).
"""

from typing import Any, Tuple

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
        """``DROP COLUMN IF EXISTS`` is supported since SQL Server 2016.

        The "since 2016" floor comes from the official ``ALTER TABLE``
        grammar page; the instance measured here is 2019 only
        (``tests/config/sqlserver_scenarios.yaml``: ``sqlserver_2019``,
        RTM-CU32-GDR 15.0.4465.1, Developer Edition).
        """
        return True

    def supports_drop_constraint_if_exists(self) -> bool:
        """``DROP CONSTRAINT IF EXISTS`` is supported since SQL Server 2016.

        Measured on 2019 (RTM-CU32-GDR, 15.0.4465.1)::

            ALTER TABLE dbo.probe_t DROP CONSTRAINT IF EXISTS does_not_exist
            -> accepted, silent no-op (no result set, no error)

        so ``IF EXISTS`` is what makes dropping a constraint idempotent on
        this backend — the plain form is *not* a no-op, it raises
        ``'does_not_exist' is not a constraint. (3728)`` followed by
        ``Could not drop constraint. See previous errors. (3727)``.
        Catching that error pair instead of spelling ``IF EXISTS`` would also
        break on MySQL, which has no ``DROP CONSTRAINT IF EXISTS`` at all.

        The "since 2016" floor is from the official ``ALTER TABLE`` grammar
        page; no pre-2019 instance was measured here.
        """
        return True

    def format_add_column_action(self, action: Any) -> Tuple[str, tuple]:
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

    def format_drop_column_action(self, action: Any) -> Tuple[str, tuple]:
        name = self.format_identifier(action.column_name)
        if getattr(action, "if_exists", None) is True:
            return f"DROP COLUMN IF EXISTS {name}", ()
        return f"DROP COLUMN {name}", ()

    def format_drop_table_constraint_action(self, action: Any) -> Tuple[str, tuple]:
        name = self.format_identifier(action.constraint_name)
        if getattr(action, "if_exists", None) is True:
            result = f"DROP CONSTRAINT IF EXISTS {name}"
        else:
            result = f"DROP CONSTRAINT {name}"
        if getattr(action, "cascade", None):
            result += " CASCADE"
        return result, ()

    def format_alter_column_action(self, action: Any) -> Tuple[str, tuple]:
        """Dispatch an ALTER COLUMN action to a SQL Server-specific formatter.

        SQL Server re-specifies the full column rather than applying the
        standard SET/DROP subclauses. The ``operation`` value selects the
        variant:

        - ``SET DATA TYPE`` (or a typed ``data_type`` field) renders the
          T-SQL ``ALTER COLUMN col type [COLLATE ...] [NULL | NOT NULL] [SPARSE]``
          form via ``format_alter_column_type_action``.
        - ``ADD MASKED`` renders dynamic data masking via
          ``format_add_masked_action``.
        - ``DROP MASKED`` renders ``format_drop_masked_action``.
        """
        operation = action.operation
        op_str = operation.value if hasattr(operation, "value") else str(operation)

        if op_str == "ADD MASKED" or getattr(action, "masked_function", None) is not None:
            return self.format_add_masked_action(action)
        if op_str == "DROP MASKED" or getattr(action, "drop_masked", False):
            return self.format_drop_masked_action(action)
        if op_str == "SET DATA TYPE" or getattr(action, "data_type", None) is not None:
            return self.format_alter_column_type_action(action)

        raise UnsupportedFeatureError(
            self.name,
            f"ALTER COLUMN {op_str}",
            "SQL Server requires re-specifying the full column. Use "
            "operation='SET DATA TYPE' with a SQLServerAlterColumn to add "
            "NULL/NOT NULL, COLLATE, SPARSE, or MASKED.",
        )

    def format_alter_column_type_action(self, action: Any) -> Tuple[str, tuple]:
        """Format a T-SQL ALTER COLUMN type change.

        SQL Syntax:
            ALTER COLUMN column data_type [COLLATE collation]
            [NULL | NOT NULL] [SPARSE]

        The data type comes from the typed ``data_type`` field or the
        action's ``new_value``. ``not_null``, ``collate``, and ``sparse``
        are typed fields on ``SQLServerAlterColumn``.
        """
        data_type = getattr(action, "data_type", None) or action.new_value
        if data_type is None:
            raise ValueError("data type is required for ALTER COLUMN")

        from rhosocial.activerecord.backend.expression.types import DataType

        type_sql, _ = DataType.as_type(self, data_type).to_sql()
        parts = [
            "ALTER COLUMN",
            self.format_identifier(action.column_name),
            type_sql,
        ]

        collate = getattr(action, "collate", None)
        if collate:
            parts.append(f"COLLATE {collate}")

        not_null = getattr(action, "not_null", False)
        nullable = getattr(action, "nullable", False)
        if not_null or nullable:
            parts.append("NOT NULL" if not_null else "NULL")

        if getattr(action, "sparse", False):
            if self.version < _SQL_SERVER_SPARSE_COLUMN_VERSION:  # type: ignore[attr-defined]
                raise UnsupportedFeatureError(
                    self.name,
                    "SPARSE column",
                    suggestion="requires SQL Server 2008+.",
                )
            parts.append("SPARSE")

        return " ".join(parts), ()

    def format_add_masked_action(self, action: Any) -> Tuple[str, tuple]:
        """Format ALTER COLUMN ... ADD MASKED (dynamic data masking, 2016+).

        SQL Syntax:
            ALTER COLUMN column ADD MASKED WITH (FUNCTION = 'mask_function')

        The mask function is carried in the typed ``masked_function`` field
        or the action's ``new_value``.
        """
        if self.version < _SQL_SERVER_MASKED_COLUMN_VERSION:  # type: ignore[attr-defined]
            raise UnsupportedFeatureError(
                self.name,
                "ADD MASKED (dynamic data masking)",
                suggestion="requires SQL Server 2016+.",
            )

        function = getattr(action, "masked_function", None) or action.new_value
        if function is None:
            raise ValueError("masked_function is required for ADD MASKED")

        escaped = str(function).replace("'", "''")
        return (
            f"ALTER COLUMN {self.format_identifier(action.column_name)} "
            f"ADD MASKED WITH (FUNCTION = '{escaped}')",
            (),
        )

    def format_drop_masked_action(self, action: Any) -> Tuple[str, tuple]:
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