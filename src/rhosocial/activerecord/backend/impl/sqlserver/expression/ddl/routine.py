# src/rhosocial/activerecord/backend/impl/sqlserver/expression/ddl/routine.py
"""SQL Server stored procedure / function DDL expressions.

T-SQL routines use a distinctive syntax compared to SQL/PSM:

    CREATE PROCEDURE [dbo].[p] @x INT AS BEGIN SET NOCOUNT ON; SELECT @x + 1; END;
    CREATE FUNCTION dbo.f (@x INT) RETURNS INT AS BEGIN RETURN @x * 2; END;
    DROP PROCEDURE p;  DROP FUNCTION f;

SQL generation and version gating are delegated to the dialect's
``format_create_procedure_statement`` / ``format_create_function_statement``
/ ``format_drop_routine_statement`` formatters. Bodies are passed through
verbatim as raw T-SQL strings.
"""

from typing import Any, List, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression, SQLQueryAndParams

if TYPE_CHECKING:
    from ...dialect import SQLServerDialect


class SQLServerCreateProcedureExpression(BaseExpression):
    """SQL Server CREATE PROCEDURE statement (2005+).

    Attributes:
        name: Procedure name (may be schema-qualified like ``dbo.p``).
        parameters: List of parameters. Each entry is either a raw
            ``"@x INT"`` string or a ``{"name": "@x", "type": "INT"}`` dict.
        body: Raw T-SQL body passed through verbatim.
        schema: Optional schema qualifier (rendered as ``[schema].[name]``).
        or_alter: Whether to render ``CREATE OR ALTER PROCEDURE``.

    Example:
        >>> expr = SQLServerCreateProcedureExpression(
        ...     dialect, "p", ["@x INT"], body="SET NOCOUNT ON; SELECT @x + 1;",
        ...     schema="dbo",
        ... )
        >>> sql, params = expr.to_sql()
        >>> assert sql == "CREATE PROCEDURE [dbo].[p] @x INT AS BEGIN SET NOCOUNT ON; SELECT @x + 1; END;"
    """

    def __init__(
        self,
        dialect: "SQLServerDialect",
        name: str,
        parameters: Optional[List[Any]] = None,
        body: str = "",
        *,
        schema: Optional[str] = None,
        or_alter: bool = False,
    ):
        super().__init__(dialect)
        self.name = name
        self.parameters = list(parameters or [])
        self.body = body
        self.schema = schema
        self.or_alter = or_alter

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not self.name:
            raise ValueError("procedure name is required")
        if not self.body:
            raise ValueError("procedure body is required")

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_create_procedure_statement(self)


class SQLServerCreateFunctionExpression(BaseExpression):
    """SQL Server CREATE FUNCTION (scalar) statement (2005+).

    Attributes:
        name: Function name (may be schema-qualified like ``dbo.f``).
        parameters: List of parameters (see
            ``SQLServerCreateProcedureExpression``).
        returns: Scalar return data type, e.g. ``INT``.
        body: Raw T-SQL body passed through verbatim.
        schema: Optional schema qualifier.
        or_alter: Whether to render ``CREATE OR ALTER FUNCTION``.

    Example:
        >>> expr = SQLServerCreateFunctionExpression(
        ...     dialect, "f", ["@x INT"], returns="INT",
        ...     body="RETURN @x * 2;", schema="dbo",
        ... )
        >>> sql, params = expr.to_sql()
        >>> assert sql == "CREATE FUNCTION [dbo].[f] (@x INT) RETURNS INT AS BEGIN RETURN @x * 2; END;"
    """

    def __init__(
        self,
        dialect: "SQLServerDialect",
        name: str,
        parameters: Optional[List[Any]] = None,
        returns: Optional[str] = None,
        body: str = "",
        *,
        schema: Optional[str] = None,
        or_alter: bool = False,
    ):
        super().__init__(dialect)
        self.name = name
        self.parameters = list(parameters or [])
        self.returns = returns
        self.body = body
        self.schema = schema
        self.or_alter = or_alter

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not self.name:
            raise ValueError("function name is required")
        if not self.returns:
            raise ValueError("RETURNS type is required for a scalar function")
        if not self.body:
            raise ValueError("function body is required")

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_create_function_statement(self)


class SQLServerDropRoutineExpression(BaseExpression):
    """SQL Server DROP PROCEDURE / DROP FUNCTION statement (2005+).

    Attributes:
        name: Routine name (may be schema-qualified).
        kind: Either ``PROCEDURE`` or ``FUNCTION``.
        schema: Optional schema qualifier.
        if_exists: Render ``IF EXISTS`` (SQL Server 2016+ only).

    Example:
        >>> expr = SQLServerDropRoutineExpression(dialect, "p", "PROCEDURE")
        >>> sql, params = expr.to_sql()
        >>> assert sql == "DROP PROCEDURE [p]"
    """

    def __init__(
        self,
        dialect: "SQLServerDialect",
        name: str,
        kind: str = "PROCEDURE",
        *,
        schema: Optional[str] = None,
        if_exists: bool = False,
    ):
        super().__init__(dialect)
        self.name = name
        self.kind = kind
        self.schema = schema
        self.if_exists = if_exists

    def validate(self, strict: bool = True) -> None:
        if not strict:
            return
        if not self.name:
            raise ValueError("routine name is required")
        if self.kind.upper() not in ("PROCEDURE", "FUNCTION"):
            raise ValueError("kind must be either PROCEDURE or FUNCTION")

    def to_sql(self) -> SQLQueryAndParams:
        return self.dialect.format_drop_routine_statement(self)
