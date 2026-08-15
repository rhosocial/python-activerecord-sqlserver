# src/rhosocial/activerecord/backend/impl/sqlserver/functions/aggregate.py
"""
SQL Server aggregate function factories.

Functions: max_, min_, avg
"""

from typing import Union, TYPE_CHECKING

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


def max_(
    dialect: "SQLServerDialect",
    expr: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Creates a MAX function call."""
    return core.FunctionCall(dialect, "MAX", [_convert_to_expression(dialect, expr)])


def min_(
    dialect: "SQLServerDialect",
    expr: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Creates a MIN function call."""
    return core.FunctionCall(dialect, "MIN", [_convert_to_expression(dialect, expr)])


def avg(
    dialect: "SQLServerDialect",
    expr: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Creates an AVG function call."""
    return core.FunctionCall(dialect, "AVG", [_convert_to_expression(dialect, expr)])
