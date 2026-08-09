# src/rhosocial/activerecord/backend/impl/sqlserver/functions/bitwise.py
"""
SQL Server bitwise function factories.

Functions: bit_and, bit_or, bit_xor, bit_count, bit_get_bit, bit_shift_left,
bit_shift_right
"""

from typing import Union, Any, TYPE_CHECKING

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


def _arg_list(dialect: "SQLDialectBase", values) -> list:
    return [_convert_to_expression(dialect, v) for v in values]


def bit_and(
    dialect: "SQLServerDialect",
    *values: Any,
) -> "core.FunctionCall":
    """Creates a BIT_AND function call (approximation; SQL Server lacks an aggregate)."""
    return core.FunctionCall(dialect, "BIT_AND", _arg_list(dialect, values))


def bit_or(
    dialect: "SQLServerDialect",
    *values: Any,
) -> "core.FunctionCall":
    """Creates a BIT_OR function call (approximation; SQL Server lacks an aggregate)."""
    return core.FunctionCall(dialect, "BIT_OR", _arg_list(dialect, values))


def bit_xor(
    dialect: "SQLServerDialect",
    *values: Any,
) -> "core.FunctionCall":
    """Creates a BIT_XOR function call (approximation; SQL Server lacks an aggregate)."""
    return core.FunctionCall(dialect, "BIT_XOR", _arg_list(dialect, values))


def bit_count(
    dialect: "SQLServerDialect",
    value: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Creates a BIT_COUNT function call (SQL Server 2022+)."""
    return core.FunctionCall(dialect, "BIT_COUNT", [_convert_to_expression(dialect, value)])


def bit_get_bit(
    dialect: "SQLServerDialect",
    value: Union[str, "bases.BaseExpression"],
    bit: int,
) -> "core.FunctionCall":
    """Creates a GET_BIT function call (SQL Server 2022+)."""
    return core.FunctionCall(
        dialect,
        "GET_BIT",
        [_convert_to_expression(dialect, value), core.Literal(dialect, bit)],
    )


def bit_shift_left(
    dialect: "SQLServerDialect",
    value: Union[str, "bases.BaseExpression"],
    bits: int,
) -> "core.FunctionCall":
    """Creates a LEFT_SHIFT function call (SQL Server 2022+)."""
    return core.FunctionCall(
        dialect,
        "LEFT_SHIFT",
        [_convert_to_expression(dialect, value), core.Literal(dialect, bits)],
    )


def bit_shift_right(
    dialect: "SQLServerDialect",
    value: Union[str, "bases.BaseExpression"],
    bits: int,
) -> "core.FunctionCall":
    """Creates a RIGHT_SHIFT function call (SQL Server 2022+)."""
    return core.FunctionCall(
        dialect,
        "RIGHT_SHIFT",
        [_convert_to_expression(dialect, value), core.Literal(dialect, bits)],
    )
