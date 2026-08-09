# src/rhosocial/activerecord/backend/impl/sqlserver/functions/math.py
"""
SQL Server math function factories.

Functions: round_, pow, power, sqrt, mod, ceil, floor, trunc
"""

from typing import Union, Optional, TYPE_CHECKING

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


def round_(
    dialect: "SQLServerDialect",
    value: Union[str, "bases.BaseExpression"],
    digits: Optional[int] = None,
) -> "core.FunctionCall":
    """Creates a ROUND function call."""
    args = [_convert_to_expression(dialect, value)]
    if digits is not None:
        args.append(core.Literal(dialect, digits))
    return core.FunctionCall(dialect, "ROUND", args)


def pow(
    dialect: "SQLServerDialect",
    base: Union[str, "bases.BaseExpression"],
    exponent: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Creates a POWER function call (SQL Server equivalent of POW)."""
    return core.FunctionCall(
        dialect,
        "POWER",
        [_convert_to_expression(dialect, base), _convert_to_expression(dialect, exponent)],
    )


def power(
    dialect: "SQLServerDialect",
    base: Union[str, "bases.BaseExpression"],
    exponent: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Creates a POWER function call."""
    return core.FunctionCall(
        dialect,
        "POWER",
        [_convert_to_expression(dialect, base), _convert_to_expression(dialect, exponent)],
    )


def sqrt(
    dialect: "SQLServerDialect",
    value: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Creates a SQRT function call."""
    return core.FunctionCall(dialect, "SQRT", [_convert_to_expression(dialect, value)])


def mod(
    dialect: "SQLServerDialect",
    dividend: Union[str, "bases.BaseExpression"],
    divisor: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Creates a MOD function call (SQL Server uses the % operator)."""
    return core.FunctionCall(
        dialect,
        "MOD",
        [_convert_to_expression(dialect, dividend), _convert_to_expression(dialect, divisor)],
    )


def ceil(
    dialect: "SQLServerDialect",
    value: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Creates a CEILING function call (SQL Server equivalent of CEIL)."""
    return core.FunctionCall(dialect, "CEILING", [_convert_to_expression(dialect, value)])


def floor(
    dialect: "SQLServerDialect",
    value: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Creates a FLOOR function call."""
    return core.FunctionCall(dialect, "FLOOR", [_convert_to_expression(dialect, value)])


def trunc(
    dialect: "SQLServerDialect",
    value: Union[str, "bases.BaseExpression"],
    digits: Optional[int] = None,
) -> "core.FunctionCall":
    """Creates a TRUNC function call (approximation; SQL Server has no TRUNC)."""
    args = [_convert_to_expression(dialect, value)]
    if digits is not None:
        args.append(core.Literal(dialect, digits))
    return core.FunctionCall(dialect, "TRUNC", args)
