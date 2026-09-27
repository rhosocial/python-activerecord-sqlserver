# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/type.py
"""SQL Server user-defined TYPE protocol."""

from typing import Any, Protocol, Tuple, runtime_checkable

from rhosocial.activerecord.backend.dialect.protocols import UserDefinedTypeSupport


@runtime_checkable
class SQLServerUserDefinedTypeSupport(UserDefinedTypeSupport, Protocol):
    """SQL Server-specific contract layered on core TYPE support."""

    def supports_clr_type_definition(self) -> bool:
        ...

    def supports_clr_user_defined_type(self) -> bool:
        ...

    def supports_drop_type_cascade(self) -> bool:
        ...

    def supports_drop_type_restrict(self) -> bool:
        ...

    def supports_rename_type(self) -> bool:
        ...

    def supports_memory_optimized_table_types(self) -> bool:
        ...

    def format_rename_type_statement(self, expr: Any) -> Tuple[str, tuple]:
        ...


__all__ = ["SQLServerUserDefinedTypeSupport"]
