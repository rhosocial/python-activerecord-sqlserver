# src/rhosocial/activerecord/backend/impl/sqlserver/functions/json.py
"""
SQL Server JSON function factories.

Functions: json_value, json_query, isjson, openjson, json_object, json_array
"""

from typing import Union, Optional, Any, TYPE_CHECKING

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


def json_value(
    dialect: "SQLServerDialect",
    json_doc: Union[str, "bases.BaseExpression"],
    path: str,
) -> "core.FunctionCall":
    """Creates a JSON_VALUE function call."""
    json_expr = _convert_to_expression(dialect, json_doc)
    path_literal = core.Literal(dialect, path)
    return core.FunctionCall(dialect, "JSON_VALUE", [json_expr, path_literal])


def json_query(
    dialect: "SQLServerDialect",
    json_doc: Union[str, "bases.BaseExpression"],
    path: str,
) -> "core.FunctionCall":
    """Creates a JSON_QUERY function call."""
    json_expr = _convert_to_expression(dialect, json_doc)
    path_literal = core.Literal(dialect, path)
    return core.FunctionCall(dialect, "JSON_QUERY", [json_expr, path_literal])


def is_json(
    dialect: "SQLServerDialect",
    json_doc: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Creates an ISJSON function call."""
    json_expr = _convert_to_expression(dialect, json_doc)
    return core.FunctionCall(dialect, "ISJSON", [json_expr])


def json_object(
    dialect: "SQLServerDialect",
    pairs: dict,
) -> "core.FunctionCall":
    """Creates a JSON_OBJECT function call (SQL Server 2022+)."""
    args = []
    for key, value in pairs.items():
        key_literal = core.Literal(dialect, key)
        value_expr = _convert_to_expression(dialect, value)
        args.extend([key_literal, value_expr])
    return core.FunctionCall(dialect, "JSON_OBJECT", args)


def json_array(
    dialect: "SQLServerDialect",
    *values: Any,
) -> "core.FunctionCall":
    """Creates a JSON_ARRAY function call (SQL Server 2022+)."""
    args = [_convert_to_expression(dialect, v) for v in values]
    return core.FunctionCall(dialect, "JSON_ARRAY", args)


def json_path_exists(
    dialect: "SQLServerDialect",
    json_doc: Union[str, "bases.BaseExpression"],
    path: str,
) -> "core.FunctionCall":
    """Creates a JSON_PATH_EXISTS function call (SQL Server 2022+)."""
    json_expr = _convert_to_expression(dialect, json_doc)
    path_literal = core.Literal(dialect, path)
    return core.FunctionCall(dialect, "JSON_PATH_EXISTS", [json_expr, path_literal])


def json_extract(
    dialect: "SQLServerDialect",
    json_doc: Union[str, "bases.BaseExpression"],
    path: str,
) -> "core.FunctionCall":
    """Creates a JSON_VALUE function call (SQL Server equivalent of JSON_EXTRACT).

    SQL Server's JSON_VALUE returns the scalar value at the given path,
    already unquoted.
    """
    json_expr = _convert_to_expression(dialect, json_doc)
    path_literal = core.Literal(dialect, path)
    return core.FunctionCall(dialect, "JSON_VALUE", [json_expr, path_literal])


def json_unquote(
    dialect: "SQLServerDialect",
    json_val: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Creates a JSON_UNQUOTE function call (approximation).

    SQL Server has no JSON_UNQUOTE; JSON_VALUE already returns scalar
    values without surrounding quotes.
    """
    return core.FunctionCall(dialect, "JSON_UNQUOTE", [_convert_to_expression(dialect, json_val)])


def json_contains(
    dialect: "SQLServerDialect",
    target: Union[str, "bases.BaseExpression"],
    candidate: Union[str, "bases.BaseExpression"],
    path: Optional[str] = None,
) -> "core.FunctionCall":
    """Creates a JSON_CONTAINS function call (approximation)."""
    args = [_convert_to_expression(dialect, target), _convert_to_expression(dialect, candidate)]
    if path is not None:
        args.append(core.Literal(dialect, path))
    return core.FunctionCall(dialect, "JSON_CONTAINS", args)


def json_set(
    dialect: "SQLServerDialect",
    json_doc: Union[str, "bases.BaseExpression"],
    path: str,
    value: Any,
    path_value_pairs: Optional[list] = None,
) -> "core.FunctionCall":
    """Creates a JSON_MODIFY function call (SQL Server equivalent of JSON_SET)."""
    args = [
        _convert_to_expression(dialect, json_doc),
        core.Literal(dialect, path),
        _convert_to_expression(dialect, value),
    ]
    if path_value_pairs:
        for p, v in path_value_pairs:
            args.append(core.Literal(dialect, p))
            args.append(_convert_to_expression(dialect, v))
    return core.FunctionCall(dialect, "JSON_MODIFY", args)


def json_remove(
    dialect: "SQLServerDialect",
    json_doc: Union[str, "bases.BaseExpression"],
    path: str,
    paths: Optional[list] = None,
) -> "core.FunctionCall":
    """Creates a JSON_MODIFY function call (SQL Server equivalent of JSON_REMOVE).

    SQL Server removes a property by setting it to NULL via JSON_MODIFY.
    """
    args = [_convert_to_expression(dialect, json_doc), core.Literal(dialect, path)]
    if paths:
        for p in paths:
            args.append(core.Literal(dialect, p))
    return core.FunctionCall(dialect, "JSON_MODIFY", args)


def json_type(
    dialect: "SQLServerDialect",
    json_val: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Creates a JSON_TYPE function call (approximation; SQL Server lacks one)."""
    return core.FunctionCall(dialect, "JSON_TYPE", [_convert_to_expression(dialect, json_val)])


def json_valid(
    dialect: "SQLServerDialect",
    json_val: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Creates an ISJSON function call (SQL Server equivalent of JSON_VALID)."""
    return core.FunctionCall(dialect, "ISJSON", [_convert_to_expression(dialect, json_val)])


def json_search(
    dialect: "SQLServerDialect",
    json_doc: Union[str, "bases.BaseExpression"],
    search_str: str,
    path: Optional[str] = None,
    all_: bool = False,
) -> "core.FunctionCall":
    """Creates a JSON_SEARCH function call (approximation; SQL Server lacks one)."""
    args = [_convert_to_expression(dialect, json_doc), core.Literal(dialect, search_str)]
    if path is not None:
        args.append(core.Literal(dialect, path))
    return core.FunctionCall(dialect, "JSON_SEARCH", args)