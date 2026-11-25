# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/extended_property.py
"""SQL Server extended-property write capability contract.

One probe answers whether the server can write the catalogue; one formatter
renders the single node that carries the operation word. The read side is a
different family (``supports_extended_property_introspection``) and is not
part of this protocol.
"""

from typing import Protocol, Tuple, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - import only for type checkers
    from ..expression.extended_property import SQLServerExtendedPropertyWriteStatement


@runtime_checkable
class SQLServerExtendedPropertyWriteSupport(Protocol):
    def supports_extended_properties_write(self) -> bool: ...

    def format_extended_property_write_statement(
        self, expr: "SQLServerExtendedPropertyWriteStatement"
    ) -> Tuple[str, tuple]: ...
