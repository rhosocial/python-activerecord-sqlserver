# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/extended_property.py
"""SQL Server extended-property write capability and formatter.

Microsoft Learn documents the three write procedures with the same object
address (``@name`` plus ``@level0type``/``@level0name``, ``@level1type``/
``@level1name``, ``@level2type``/``@level2name``):

* `sys.sp_addextendedproperty
  <https://learn.microsoft.com/en-us/sql/relational-databases/system-stored-procedures/sp-addextendedproperty-transact-sql>`_
  -- ``@name``, ``@value``, six level arguments; ``@value`` defaults to
  ``NULL`` and may not exceed 7500 bytes;
* `sys.sp_updateextendedproperty
  <https://learn.microsoft.com/en-us/sql/relational-databases/system-stored-procedures/sp-updateextendedproperty-transact-sql>`_
  -- the same eight arguments;
* `sys.sp_dropextendedproperty
  <https://learn.microsoft.com/en-us/sql/relational-databases/system-stored-procedures/sp-dropextendedproperty-transact-sql>`_
  -- ``@name`` and the six level arguments, with **no** ``@value``.

The read side is ``SQLServerExtendedPropertyListQueryStatement``. This mixin
owns the write side: one probe, and one public formatter for the one node that
carries the operation word. There is deliberately no private renderer shared
between operations -- a formatter is the only rendering seam a backend can
override.
"""

from typing import Tuple

from ..expression.extended_property import (
    EXTENDED_PROPERTY_OPERATIONS,
    SQLServerExtendedPropertyWriteStatement,
)
from .version_constants import SQL_SERVER_2005


_PROCEDURES = {
    "ADD": "sp_addextendedproperty",
    "UPDATE": "sp_updateextendedproperty",
    "DROP": "sp_dropextendedproperty",
}


class SQLServerExtendedPropertyMixin:
    """Extended-property write support and its one formatter."""

    def supports_extended_properties_write(self) -> bool:
        """True on SQL Server 2005+; ``sp_addextendedproperty`` is the floor.

        Microsoft Learn lists all three procedures for SQL Server, Azure SQL
        Database, Azure SQL Managed Instance and SQL database in Microsoft
        Fabric. The measured instance behind this backend's capability tests
        is SQL Server 2019 (15.0.4465.1, Developer Edition), where
        ``sp_addextendedproperty`` is used by the live introspection probe to
        install ``MS_Description`` and the catalogue read succeeds.

        An unadapted dialect (no version) answers ``False``: nobody has told
        it which server it is talking to. Extended properties are also
        rejected by the engine on memory-optimized tables -- a target-level
        fact, not a server-level probe, so it is not encoded here.
        """
        return self.version_at_least(SQL_SERVER_2005)  # type: ignore[attr-defined]

    def format_extended_property_write_statement(
        self, expr: "SQLServerExtendedPropertyWriteStatement"
    ) -> Tuple[str, tuple]:
        """Render one ``EXEC sys.sp_*extendedproperty @name = ...`` call.

        Every value is inlined as an ``N'...'`` literal with its single quotes
        doubled; this is a DDL/administration call, so there is no bind
        parameter to carry. Validation lives here rather than in the node's
        constructor:

        * the operation must be one of ``ADD`` / ``UPDATE`` / ``DROP``;
        * ``@name`` must be a non-empty string (``sysname`` cannot be NULL);
        * DROP must not be handed a ``@value`` -- its signature has none;
        * a level's type and name must be supplied together, and a lower
          level cannot be addressed while its parent is missing. Omitting all
          three levels is legal and addresses the database itself, exactly as
          Microsoft Learn documents.
        """
        if not isinstance(expr, SQLServerExtendedPropertyWriteStatement):
            raise TypeError(
                "format_extended_property_write_statement requires a "
                "SQLServerExtendedPropertyWriteStatement, got "
                f"{type(expr).__name__}"
            )
        self.check_feature_support(  # type: ignore[attr-defined]
            "supports_extended_properties_write",
            "extended-property write",
            "requires SQL Server 2005+ (sp_addextendedproperty).",
        )

        operation = expr.operation.upper() if isinstance(expr.operation, str) else expr.operation
        if operation not in EXTENDED_PROPERTY_OPERATIONS:
            raise ValueError(
                f"unknown extended-property operation {expr.operation!r}; "
                f"expected one of {EXTENDED_PROPERTY_OPERATIONS}"
            )

        def nvarchar(value: object, field: str, *, allow_empty: bool = False) -> str:
            if not isinstance(value, str) or (not allow_empty and not value.strip()):
                raise ValueError(f"{field} must be a non-empty string")
            return "N'" + value.replace("'", "''") + "'"

        arguments = [f"@name = {nvarchar(expr.name, '@name')}"]
        if operation == "DROP":
            if expr.value is not None:
                raise ValueError(
                    "sp_dropextendedproperty has no @value argument; "
                    "DROP cannot carry a value"
                )
        else:
            value = (
                "NULL"
                if expr.value is None
                else nvarchar(expr.value, "@value", allow_empty=True)
            )
            arguments.append(f"@value = {value}")

        levels = (
            ("level0type", expr.level0type, "level0name", expr.level0name),
            ("level1type", expr.level1type, "level1name", expr.level1name),
            ("level2type", expr.level2type, "level2name", expr.level2name),
        )
        parent_present = False
        for index, (type_field, type_value, name_field, name_value) in enumerate(levels):
            has_type = type_value is not None
            has_name = name_value is not None
            if has_type != has_name:
                raise ValueError(
                    f"@{name_field} and @{type_field} must be supplied together"
                )
            if not has_type:
                continue
            if index > 0 and not parent_present:
                raise ValueError(
                    f"@level{index} requires @level{index - 1} when it is "
                    f"addressed by name"
                )
            parent_present = True
            arguments.append(f"@{type_field} = {nvarchar(type_value, '@' + type_field)}")
            arguments.append(f"@{name_field} = {nvarchar(name_value, '@' + name_field)}")

        call = f"EXEC sys.{_PROCEDURES[operation]} " + ", ".join(arguments)
        return call, ()
