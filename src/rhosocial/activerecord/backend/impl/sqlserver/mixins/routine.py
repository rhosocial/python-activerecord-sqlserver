# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/routine.py
"""SQL Server stored procedure / function DDL mixin.

T-SQL ``CREATE PROCEDURE`` and ``CREATE FUNCTION`` use a distinctive syntax
(parameters with leading ``@``, ``RETURNS``, ``AS BEGIN ... END`` bodies)
that differs from the SQL/PSM form used by other backends. This mixin
provides the capability switches and the formatters used by the
``SQLServerCreateProcedureExpression`` / ``SQLServerCreateFunctionExpression``
/ ``SQLServerDropRoutineExpression`` expressions.
"""

from typing import Any, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.ddl.routine import (
        SQLServerCreateFunctionExpression,
        SQLServerCreateProcedureExpression,
        SQLServerDropRoutineExpression,
    )


_SQL_SERVER_ROUTINE_VERSION = (9, 0, 0)

_SQL_SERVER_DROP_IF_EXISTS_VERSION = (13, 0, 0)

_ROUTINE_KINDS = ("PROCEDURE", "FUNCTION")


class SQLServerRoutineMixin:
    """SQL Server stored procedure / function capability and formatting."""

    def supports_create_procedure(self) -> bool:
        """CREATE PROCEDURE is supported since SQL Server 2005."""
        return self.version >= _SQL_SERVER_ROUTINE_VERSION  # type: ignore[attr-defined]

    def supports_create_function(self) -> bool:
        """CREATE FUNCTION is supported since SQL Server 2005."""
        return self.version >= _SQL_SERVER_ROUTINE_VERSION  # type: ignore[attr-defined]

    def supports_drop_procedure(self) -> bool:
        """DROP PROCEDURE is supported since SQL Server 2005."""
        return self.version >= _SQL_SERVER_ROUTINE_VERSION  # type: ignore[attr-defined]

    def supports_drop_function(self) -> bool:
        """DROP FUNCTION is supported since SQL Server 2005."""
        return self.version >= _SQL_SERVER_ROUTINE_VERSION  # type: ignore[attr-defined]

    def format_sqlserver_object_name(self, name: str, schema: Optional[str] = None) -> str:
        """Quote a (possibly schema-qualified) object name with brackets."""
        parts = []
        if schema:
            parts.append(self.format_identifier(schema))  # type: ignore[attr-defined]
        if "." in name:
            parts.extend(
                self.format_identifier(part)  # type: ignore[attr-defined]
                for part in name.split(".")
            )
        else:
            parts.append(self.format_identifier(name))  # type: ignore[attr-defined]
        return ".".join(parts)

    @staticmethod
    def format_sqlserver_params(parameters: List[Any]) -> str:
        """Normalize procedure/function parameters into a SQL fragment.

        Accepts either raw parameter strings (``"@x INT"``) or dictionaries
        with ``name`` / ``type`` keys (matching the core
        ``CreateFunctionExpression`` convention).
        """
        parts = []
        for param in parameters:
            if isinstance(param, str):
                parts.append(param)
            elif isinstance(param, dict):
                name = param.get("name", "")
                param_type = param.get("type", "")
                if name and param_type:
                    parts.append(f"{name} {param_type}")
                elif param_type:
                    parts.append(param_type)
                else:
                    raise ValueError(f"parameter dict requires name/type, got {param!r}")
            else:
                raise TypeError(
                    f"parameters must be str or dict, got {type(param).__name__}"
                )
        return ", ".join(parts)

    def _get_routine_name(self, expr: Any) -> str:
        return getattr(expr, "name", None) or getattr(expr, "function_name", "")

    def format_create_procedure_statement(
        self, expr: "SQLServerCreateProcedureExpression"
    ) -> Tuple[str, tuple]:
        """Format CREATE PROCEDURE for SQL Server (2005+).

        SQL Syntax:
            CREATE [OR ALTER] PROCEDURE [schema.]name @x INT, ...
            AS BEGIN <body> END;

        Args:
            expr: The procedure expression. ``parameters`` may be raw
                ``"@x INT"`` strings or ``{"name": ..., "type": ...}`` dicts;
                ``body`` is passed through verbatim.
        """
        self.check_feature_support(  # type: ignore[attr-defined]
            "supports_create_procedure",
            "CREATE PROCEDURE",
            "requires SQL Server 2005+.",
        )
        name = self._get_routine_name(expr)
        if not name:
            raise ValueError("procedure name is required")

        parts = ["CREATE"]
        if getattr(expr, "or_alter", False):
            parts.append("OR ALTER")
        parts.append("PROCEDURE")
        parts.append(self.format_sqlserver_object_name(name, getattr(expr, "schema", None)))

        parameters = getattr(expr, "parameters", None) or []
        if parameters:
            parts.append(self.format_sqlserver_params(list(parameters)))

        if not getattr(expr, "body", None):
            raise ValueError("routine body is required")
        parts.append(f"AS BEGIN {expr.body} END;")
        return " ".join(parts), ()

    def format_create_function_statement(
        self, expr: "SQLServerCreateFunctionExpression"
    ) -> Tuple[str, tuple]:
        """Format CREATE FUNCTION for SQL Server (2005+).

        SQL Syntax:
            CREATE [OR ALTER] FUNCTION [schema.]name (@x INT, ...)
            RETURNS data_type AS BEGIN <body> END;

        Args:
            expr: The function expression. ``returns`` holds the scalar
                return type; ``body`` is passed through verbatim.
        """
        self.check_feature_support(  # type: ignore[attr-defined]
            "supports_create_function",
            "CREATE FUNCTION",
            "requires SQL Server 2005+.",
        )
        name = self._get_routine_name(expr)
        if not name:
            raise ValueError("function name is required")
        if not getattr(expr, "returns", None):
            raise ValueError("RETURNS type is required for a scalar function")

        parts = ["CREATE"]
        if getattr(expr, "or_alter", False):
            parts.append("OR ALTER")
        parts.append("FUNCTION")
        parts.append(self.format_sqlserver_object_name(name, getattr(expr, "schema", None)))

        parameters = getattr(expr, "parameters", None) or []
        parts.append(f"({self.format_sqlserver_params(list(parameters))})")
        parts.append(f"RETURNS {expr.returns}")
        if not getattr(expr, "body", None):
            raise ValueError("function body is required")
        parts.append(f"AS BEGIN {expr.body} END;")
        return " ".join(parts), ()

    def format_drop_routine_statement(
        self, expr: "SQLServerDropRoutineExpression"
    ) -> Tuple[str, tuple]:
        """Format DROP PROCEDURE / DROP FUNCTION for SQL Server (2005+).

        SQL Syntax:
            DROP PROCEDURE [IF EXISTS] [schema.]name;
            DROP FUNCTION  [IF EXISTS] [schema.]name;

        ``IF EXISTS`` is rendered only on SQL Server 2016+.
        """
        kind = getattr(expr, "kind", "PROCEDURE").upper()
        if kind not in _ROUTINE_KINDS:
            raise ValueError(f"kind must be one of {_ROUTINE_KINDS}, got {kind!r}")

        support_method = f"supports_drop_{kind.lower()}"
        self.check_feature_support(  # type: ignore[attr-defined]
            support_method,
            f"DROP {kind}",
            "requires SQL Server 2005+.",
        )

        name = self._get_routine_name(expr)
        if not name:
            raise ValueError("routine name is required")

        parts = ["DROP", kind]
        if getattr(expr, "if_exists", False) and self.version >= _SQL_SERVER_DROP_IF_EXISTS_VERSION:  # type: ignore[attr-defined]
            parts.append("IF EXISTS")
        parts.append(self.format_sqlserver_object_name(name, getattr(expr, "schema", None)))
        return " ".join(parts), ()
