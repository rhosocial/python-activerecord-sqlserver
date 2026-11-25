# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/ddl_extras.py
"""SQL Server ``sp_rename`` and named-default-constraint formatters.

Both are the mechanisms T-SQL uses where core's vocabulary spells a clause this
server does not have:

* a rename is the ``sp_rename`` procedure, not ``RENAME COLUMN`` / ``RENAME TO``;
* a column default is a *named* ``ADD CONSTRAINT ... DEFAULT ... FOR col``,
  not ``ALTER COLUMN ... SET DEFAULT``.

The capability probes for rename stay ``False`` (core's actions carry no table
for the column form, so they cannot express ``sp_rename``); the statements here
are the honest carrier. The default probe is separate and True because the
action carries everything the clause needs.
"""

from typing import Tuple, TYPE_CHECKING

from ..expression.rename import RENAME_OBJECT_KINDS, SQLServerRenameObjectStatement
from ..expression.default_constraint import SQLServerAddDefaultConstraintAction

if TYPE_CHECKING:  # pragma: no cover
    pass


class SQLServerDDLExtrasMixin:
    """Formatters for ``sp_rename`` and the named default constraint."""

    def supports_default_constraint_add(self) -> bool:
        """True: T-SQL attaches a column default as a named constraint.

        ``ALTER TABLE ... ADD CONSTRAINT df DEFAULT ... FOR col`` is the
        documented spelling (Microsoft Learn, ALTER TABLE). It is not a
        version- or edition-gated feature: every supported release has it, so
        the probe simply states the family's presence and the formatter refuses
        by name only if a caller withdraws it.
        """
        return True

    def format_rename_object_statement(
        self, expr: "SQLServerRenameObjectStatement"
    ) -> Tuple[str, tuple]:
        """Render ``EXEC sp_rename N'old', N'new', N'kind'``.

        Validation lives here: the kind must be one of the documented words,
        both names must be non-empty, and a column rename's old address must be
        dotted (``schema.table.column``) because ``sp_rename`` resolves the
        column through the table. Arguments are DDL literals, so they are inlined
        with their quotes doubled.
        """
        if not isinstance(expr, SQLServerRenameObjectStatement):
            raise TypeError(
                "format_rename_object_statement requires a "
                f"SQLServerRenameObjectStatement, got {type(expr).__name__}"
            )
        kind = expr.kind.upper() if isinstance(expr.kind, str) else expr.kind
        if kind not in RENAME_OBJECT_KINDS:
            raise ValueError(
                f"unknown sp_rename object kind {expr.kind!r}; expected one of "
                f"{RENAME_OBJECT_KINDS}"
            )
        old = self._rename_literal(expr.old_name, "old_name")
        new = self._rename_literal(expr.new_name, "new_name")
        if kind == "COLUMN" and old.count(".") < 2:
            raise ValueError(
                "sp_rename renames a column through its table: pass the dotted "
                "address 'schema.table.column' as old_name"
            )
        return f"EXEC sp_rename {old}, {new}, {self._rename_literal(kind, 'kind')}", ()

    def _rename_literal(self, value: object, field: str) -> str:
        """Quote one ``sp_rename`` argument as an ``N'...'`` literal."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"sp_rename {field} must be a non-empty string")
        return "N'" + value.replace("'", "''") + "'"

    def format_add_default_constraint_action(
        self, expr: "SQLServerAddDefaultConstraintAction"
    ) -> Tuple[str, tuple]:
        """Render ``ADD CONSTRAINT [name] DEFAULT <literal> FOR [column]``.

        The value is inlined because DDL carries no bind parameters; a
        non-string value is refused by name rather than coerced, so an
        accidental numeric does not silently become a quoted string.
        """
        if not isinstance(expr, SQLServerAddDefaultConstraintAction):
            raise TypeError(
                "format_add_default_constraint_action requires a "
                f"SQLServerAddDefaultConstraintAction, got {type(expr).__name__}"
            )
        self.check_feature_support(  # type: ignore[attr-defined]
            "supports_default_constraint_add",
            "ADD DEFAULT CONSTRAINT",
            "requires ALTER TABLE ... ADD CONSTRAINT ... DEFAULT ... FOR col.",
        )
        if not isinstance(expr.column, str) or not expr.column.strip():
            raise ValueError("ADD DEFAULT CONSTRAINT requires a non-empty column")
        if not isinstance(expr.value, str):
            raise TypeError(
                "ADD DEFAULT CONSTRAINT value must be a string, got "
                f"{type(expr.value).__name__}"
            )
        literal = "N'" + expr.value.replace("'", "''") + "'"
        column = self.format_identifier(expr.column)  # type: ignore[attr-defined]
        if expr.constraint_name is None:
            return f"ADD DEFAULT {literal} FOR {column}", ()
        if not isinstance(expr.constraint_name, str) or not expr.constraint_name.strip():
            raise ValueError(
                "ADD DEFAULT CONSTRAINT constraint_name must be a non-empty "
                "string when supplied"
            )
        name = self.format_identifier(expr.constraint_name)  # type: ignore[attr-defined]
        return f"ADD CONSTRAINT {name} DEFAULT {literal} FOR {column}", ()
