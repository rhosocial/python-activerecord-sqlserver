# src/rhosocial/activerecord/backend/impl/sqlserver/functions/utility.py
"""
SQL Server utility function factories.

Functions: iif, choose, try_cast, try_convert, try_parse, choose
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


def iif(
    dialect: "SQLServerDialect",
    condition: Union[str, "bases.BaseExpression"],
    true_value: Any,
    false_value: Any,
) -> "core.FunctionCall":
    """Creates an IIF function call (SQL Server 2012+)."""
    cond_expr = _convert_to_expression(dialect, condition)
    true_expr = _convert_to_expression(dialect, true_value)
    false_expr = _convert_to_expression(dialect, false_value)
    
    return core.FunctionCall(dialect, "IIF", [cond_expr, true_expr, false_expr])


def choose(
    dialect: "SQLServerDialect",
    index: Union[int, "bases.BaseExpression"],
    *choices: Any,
) -> "core.FunctionCall":
    """Creates a CHOOSE function call (SQL Server 2012+)."""
    idx_expr = _convert_to_expression(dialect, index)
    choice_exprs = [_convert_to_expression(dialect, c) for c in choices]
    
    return core.FunctionCall(dialect, "CHOOSE", [idx_expr, *choice_exprs])


def try_cast(
    dialect: "SQLServerDialect",
    expression: Any,
    data_type: str,
) -> "core.FunctionCall":
    """Creates a TRY_CAST function call (SQL Server 2012+)."""
    expr = _convert_to_expression(dialect, expression)
    type_expr = core.Literal(dialect, data_type)
    
    return core.FunctionCall(dialect, "TRY_CAST", [expr, type_expr])


def try_convert(
    dialect: "SQLServerDialect",
    data_type: str,
    expression: Any,
    style: Optional[int] = None,
) -> "core.FunctionCall":
    """Creates a TRY_CONVERT function call (SQL Server 2012+)."""
    type_expr = core.Literal(dialect, data_type)
    expr = _convert_to_expression(dialect, expression)
    args = [type_expr, expr]
    
    if style is not None:
        args.append(core.Literal(dialect, style))
    
    return core.FunctionCall(dialect, "TRY_CONVERT", args)


def try_parse(
    dialect: "SQLServerDialect",
    expression: Any,
    data_type: str,
    culture: Optional[str] = None,
) -> "core.FunctionCall":
    """Creates a TRY_PARSE function call (SQL Server 2012+)."""
    expr = _convert_to_expression(dialect, expression)
    type_expr = core.Literal(dialect, data_type)
    args = [expr, type_expr]
    
    if culture:
        culture_expr = core.Literal(dialect, culture)
        args.append(culture_expr)
    
    return core.FunctionCall(dialect, "TRY_PARSE", args)


def coalesce(
    dialect: "SQLServerDialect",
    *expressions: Any,
) -> "core.FunctionCall":
    """Creates a COALESCE function call."""
    exprs = [_convert_to_expression(dialect, e) for e in expressions]
    return core.FunctionCall(dialect, "COALESCE", exprs)


def nullif(
    dialect: "SQLServerDialect",
    expression: Any,
    compare_value: Any,
) -> "core.FunctionCall":
    """Creates a NULLIF function call."""
    expr = _convert_to_expression(dialect, expression)
    compare_expr = _convert_to_expression(dialect, compare_value)
    return core.FunctionCall(dialect, "NULLIF", [expr, compare_expr])