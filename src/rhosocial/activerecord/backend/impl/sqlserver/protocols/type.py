# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/type.py
"""SQL Server user-defined TYPE protocol."""

from typing import Any, Protocol, Tuple, runtime_checkable

from rhosocial.activerecord.backend.dialect.protocols import (
    CreateTypeSupport,
    DropTypeSupport,
)


@runtime_checkable
class SQLServerUserDefinedTypeSupport(CreateTypeSupport, DropTypeSupport, Protocol):
    """SQL Server-specific contract layered on core TYPE support.

    Core splits TYPE DDL into one protocol per statement, and SQL Server
    implements two of them: it can ``CREATE TYPE`` and ``DROP TYPE``. It has no
    ``ALTER TYPE`` at all, so ``AlterTypeSupport`` is deliberately absent --
    ``sp_rename`` is the SQL Server way to change a type's name, which is this
    backend's own ``format_rename_type_statement``.
    """

    def supports_clr_type_definition(self) -> bool: ...
    def supports_clr_user_defined_type(self) -> bool: ...
    def supports_drop_type_cascade(self) -> bool: ...
    def supports_drop_type_restrict(self) -> bool: ...
    def supports_rename_type(self) -> bool: ...
    def supports_memory_optimized_table_types(self) -> bool: ...
    def format_rename_type_statement(self, expr: Any) -> Tuple[str, tuple]: ...


__all__ = ["SQLServerUserDefinedTypeSupport"]