# src/rhosocial/activerecord/backend/impl/sqlserver/functions/datetime.py
"""
SQL Server datetime function factories.

Functions: eomonth, datefromparts, datetime2fromparts, datediff_big
"""

from typing import Union, Any, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression import bases, core

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase
    from .dialect import SQLServerDialect


def _convert_to_expression(
    dialect: "SQLDialectBase",
    expr: Union[str, "bases.BaseExpression"],
    handle_numeric_literals: bool = True,
) -> "bases.BaseExpression":
    """Convert an input value to a BaseExpression."""
    if isinstance(expr, bases.BaseExpression):
        return expr
    elif handle_numeric_literals and isinstance(expr, (int, float)):
        return core.Literal(dialect, expr)
    else:
        return core.Column(dialect, expr)


def eomonth(
    dialect: "SQLServerDialect",
    date: Union[str, "bases.BaseExpression"],
    month_offset: Optional[int] = None,
) -> "core.FunctionCall":
    """Creates an EOMONTH function call (SQL Server 2012+)."""
    date_expr = _convert_to_expression(dialect, date)
    
    if month_offset is not None:
        offset = core.Literal(dialect, month_offset)
        return core.FunctionCall(dialect, "EOMONTH", [date_expr, offset])
    
    return core.FunctionCall(dialect, "EOMONTH", [date_expr])


def datefromparts(
    dialect: "SQLServerDialect",
    year: int,
    month: int,
    day: int,
) -> "core.FunctionCall":
    """Creates a DATEFROMPARTS function call (SQL Server 2012+)."""
    return core.FunctionCall(
        dialect,
        "DATEFROMPARTS",
        [core.Literal(dialect, year), core.Literal(dialect, month), core.Literal(dialect, day)],
    )


def datetime2fromparts(
    dialect: "SQLServerDialect",
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    fractions: int = 0,
    precision: Optional[int] = None,
) -> "core.FunctionCall":
    """Creates a DATETIME2FROMPARTS function call (SQL Server 2012+)."""
    args = [
        core.Literal(dialect, year),
        core.Literal(dialect, month),
        core.Literal(dialect, day),
        core.Literal(dialect, hour),
        core.Literal(dialect, minute),
        core.Literal(dialect, second),
        core.Literal(dialect, fractions),
    ]
    
    if precision is not None:
        args.append(core.Literal(dialect, precision))
    
    return core.FunctionCall(dialect, "DATETIME2FROMPARTS", args)


def timefromparts(
    dialect: "SQLServerDialect",
    hour: int,
    minute: int,
    second: int,
    fractions: int = 0,
    precision: Optional[int] = None,
) -> "core.FunctionCall":
    """Creates a TIMEFROMPARTS function call (SQL Server 2012+)."""
    args = [
        core.Literal(dialect, hour),
        core.Literal(dialect, minute),
        core.Literal(dialect, second),
        core.Literal(dialect, fractions),
    ]
    
    if precision is not None:
        args.append(core.Literal(dialect, precision))
    
    return core.FunctionCall(dialect, "TIMEFROMPARTS", args)


def datediff_big(
    dialect: "SQLServerDialect",
    start_date: Union[str, "bases.BaseExpression"],
    end_date: Union[str, "bases.BaseExpression"],
    datepart: str,
) -> "core.FunctionCall":
    """Creates a DATEDIFF_BIG function call (SQL Server 2016+)."""
    start_expr = _convert_to_expression(dialect, start_date)
    end_expr = _convert_to_expression(dialect, end_date)
    part = core.Literal(dialect, datepart)
    
    return core.FunctionCall(dialect, "DATEDIFF_BIG", [part, start_expr, end_expr])