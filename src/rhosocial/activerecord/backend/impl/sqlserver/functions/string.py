# src/rhosocial/activerecord/backend/impl/sqlserver/functions/string.py
"""
SQL Server string function factories.

Functions: string_agg, concat_ws, trim, format
"""

from typing import Union, Any, TYPE_CHECKING, List, Optional

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


def string_agg(
    dialect: "SQLServerDialect",
    expression: Union[str, "bases.BaseExpression"],
    separator: str,
    order_by: Optional[List[Union[str, "bases.BaseExpression"]]] = None,
    within_group: bool = False,
) -> "core.FunctionCall":
    """Creates a STRING_AGG function call (SQL Server 2017+)."""
    expr = _convert_to_expression(dialect, expression)
    sep = core.Literal(dialect, separator)
    
    args = [expr, sep]
    
    if order_by:
        order_args = [_convert_to_expression(dialect, o) for o in order_by]
        order_clause = core.OrderByClause(dialect, order_args)
        return core.FunctionCall(dialect, "STRING_AGG", args, order=order_clause)
    
    return core.FunctionCall(dialect, "STRING_AGG", args)


def concat_ws(
    dialect: "SQLServerDialect",
    separator: str,
    *expressions: Any,
) -> "core.FunctionCall":
    """Creates a CONCAT_WS function call (SQL Server 2017+)."""
    sep = core.Literal(dialect, separator)
    args = [sep]
    args.extend(_convert_to_expression(dialect, e) for e in expressions)
    return core.FunctionCall(dialect, "CONCAT_WS", args)


def trim(
    dialect: "SQLServerDialect",
    expression: Union[str, "bases.BaseExpression"],
    characters: Optional[str] = None,
) -> "core.FunctionCall":
    """Creates a TRIM function call (SQL Server 2017+)."""
    expr = _convert_to_expression(dialect, expression)
    
    if characters:
        char_literal = core.Literal(dialect, characters)
        return core.FunctionCall(dialect, "TRIM", [expr, char_literal])
    
    return core.FunctionCall(dialect, "TRIM", [expr])


def format(
    dialect: "SQLServerDialect",
    value: Union[str, "bases.BaseExpression"],
    format: str,
    culture: Optional[str] = None,
) -> "core.FunctionCall":
    """Creates a FORMAT function call."""
    val_expr = _convert_to_expression(dialect, value)
    fmt = core.Literal(dialect, format)
    args = [val_expr, fmt]
    
    if culture:
        culture_expr = core.Literal(dialect, culture)
        args.append(culture_expr)
    
    return core.FunctionCall(dialect, "FORMAT", args)


def string_split(
    dialect: "SQLServerDialect",
    string: Union[str, "bases.BaseExpression"],
    separator: str,
    enable_ordinal: bool = False,
) -> "core.FunctionCall":
    """Creates a STRING_SPLIT function call (SQL Server 2016+)."""
    str_expr = _convert_to_expression(dialect, string)
    sep = core.Literal(dialect, separator)
    args = [str_expr, sep]
    
    if enable_ordinal and dialect.version >= (14, 0, 1):
        ordinal = core.Literal(dialect, True)
        args.append(ordinal)
    
    return core.FunctionCall(dialect, "STRING_SPLIT", args)