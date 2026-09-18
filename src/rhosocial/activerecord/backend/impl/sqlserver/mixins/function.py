# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/function.py
from typing import Dict


class SQLServerFunctionMixin:
    """SQL Server function support detection."""

    def supports_functions(self) -> Dict[str, bool]:
        """Return supported SQL functions as function_name -> bool mapping.

        Combines the core expression function factories with the SQL Server
        function factories in ``functions.__all__``.
        """
        from rhosocial.activerecord.backend.expression.functions import (
            __all__ as core_functions,
        )
        from rhosocial.activerecord.backend.impl.sqlserver import (
            functions as sqlserver_functions,
        )

        result = {}
        for func_name in core_functions:
            result[func_name] = self._is_sqlserver_function_supported(func_name)

        for func_name in getattr(sqlserver_functions, "__all__", []):
            if func_name not in result:
                result[func_name] = self._is_sqlserver_function_supported(func_name)

        for func_name in self._SQLSERVER_FUNCTION_VERSIONS:
            if func_name not in result:
                result[func_name] = self._is_sqlserver_function_supported(func_name)

        return result

    def _is_sqlserver_function_supported(self, func_name: str) -> bool:
        """Check if a SQL Server-specific function is supported based on version."""
        version_range = self._SQLSERVER_FUNCTION_VERSIONS.get(func_name)
        if version_range is None:
            return True

        min_version = version_range[0]
        max_version = version_range[1]

        if min_version is not None and self.version < min_version:
            return False

        if max_version is not None and self.version > max_version:
            return False

        return True
