# src/rhosocial/activerecord/backend/impl/sqlserver/functions/aggregate.py
"""
SQL Server aggregate function factories.

Functions: max_, min_, avg

Each factory builds the core's classed aggregate node, which owns its kind
and dispatches to its own dialect formatter (core 9b559030); the generic
``FunctionCall`` is reserved for UDFs (core c5210245).
"""

from typing import Union, TYPE_CHECKING

from rhosocial.activerecord.backend.expression import bases, core
from rhosocial.activerecord.backend.expression.functions import (
    AvgFunction,
    MaxFunction,
    MinFunction,
)

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase
    from ..dialect import SQLServerDialect


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
) -> "MaxFunction":
    """Creates a MAX aggregate through its class."""
    return MaxFunction(dialect, _convert_to_expression(dialect, expr))


def min_(
    dialect: "SQLServerDialect",
    expr: Union[str, "bases.BaseExpression"],
) -> "MinFunction":
    """Creates a MIN aggregate through its class."""
    return MinFunction(dialect, _convert_to_expression(dialect, expr))


def avg(
    dialect: "SQLServerDialect",
    expr: Union[str, "bases.BaseExpression"],
) -> "AvgFunction":
    """Creates an AVG aggregate through its class."""
    return AvgFunction(dialect, _convert_to_expression(dialect, expr))
