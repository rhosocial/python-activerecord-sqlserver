# src/rhosocial/activerecord/backend/impl/sqlserver/protocols/json_support.py
from typing import Protocol, Tuple, Optional, Dict, runtime_checkable

from rhosocial.activerecord.backend.dialect.protocols import JSONSupport


@runtime_checkable
class SQLServerJSONSupport(JSONSupport, Protocol):
    def format_openjson_expression(
        self,
        json_doc: str,
        path: Optional[str] = None,
        schema: Optional[Dict[str, str]] = None,
        alias: Optional[str] = None,
    ) -> Tuple[str, tuple]: ...