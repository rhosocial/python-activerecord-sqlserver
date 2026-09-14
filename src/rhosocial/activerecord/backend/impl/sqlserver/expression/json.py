# src/rhosocial/activerecord/backend/impl/sqlserver/expression/json.py
"""SQL Server JSON expression classes for format_* signature compliance."""

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import SQLValueExpression
from rhosocial.activerecord.backend.expression.mixins import (
    AliasableMixin,
    ComparisonMixin,
)

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class SQLServerJSONExtractExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server JSON_VALUE expression for extracting scalar values.

    Example:
        >>> expr = SQLServerJSONExtractExpression(dialect, "data", "$.name")
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        json_doc: str,
        path: str,
        *,
        paths: Optional[List[str]] = None,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.json_doc = json_doc
        self.path = path
        self.paths = paths or []
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_json_extract"


class SQLServerJSONUnquoteExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server JSON_UNQUOTE expression.

    Note: SQL Server's JSON_VALUE returns scalar values already unquoted,
    so this raises UnsupportedFeatureError.

    Example:
        >>> expr = SQLServerJSONUnquoteExpression(dialect, "data")
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        json_val: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.json_val = json_val
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_json_unquote"


class SQLServerJSONObjectExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server JSON_OBJECT expression (2022+).

    Example:
        >>> expr = SQLServerJSONObjectExpression(dialect, [("name", "Alice"), ("age", 30)])
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        key_value_pairs: Optional[List[Tuple[str, Any]]] = None,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.key_value_pairs = key_value_pairs or []
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_json_object"


class SQLServerJSONArrayExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server JSON_ARRAY expression (2022+).

    Example:
        >>> expr = SQLServerJSONArrayExpression(dialect, [1, "two", True])
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        values: Optional[List[Any]] = None,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.values = values or []
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_json_array"


class SQLServerJSONContainsExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server JSON containment check using OPENJSON (2016+).

    Example:
        >>> expr = SQLServerJSONContainsExpression(dialect, "data", "value")
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        target: str,
        candidate: str,
        path: Optional[str] = None,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.target = target
        self.candidate = candidate
        self.path = path
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_json_contains"


class SQLServerJSONSetExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server JSON_MODIFY expression (single path-value pair only).

    Example:
        >>> expr = SQLServerJSONSetExpression(dialect, "data", "$.name", "Bob")
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        json_doc: str,
        path: str,
        value: Any,
        *,
        path_value_pairs: Optional[List[Tuple[str, Any]]] = None,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.json_doc = json_doc
        self.path = path
        self.value = value
        self.path_value_pairs = path_value_pairs or []
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_json_set"


class SQLServerJSONRemoveExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server JSON property removal using JSON_MODIFY (single path only).

    Example:
        >>> expr = SQLServerJSONRemoveExpression(dialect, "data", "$.name")
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        json_doc: str,
        path: str,
        *,
        paths: Optional[List[str]] = None,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.json_doc = json_doc
        self.path = path
        self.paths = paths or []
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_json_remove"


class SQLServerJSONTypeExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server JSON_TYPE expression.

    Note: SQL Server has no JSON_TYPE; classify values via OPENJSON.

    Example:
        >>> expr = SQLServerJSONTypeExpression(dialect, "data")
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        json_val: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.json_val = json_val
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_json_type"


class SQLServerJSONValidExpression(AliasableMixin, ComparisonMixin, SQLValueExpression):
    """SQL Server ISJSON function (equivalent of JSON_VALID).

    Example:
        >>> expr = SQLServerJSONValidExpression(dialect, "data")
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        json_val: str,
        *,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.json_val = json_val
        self.alias = alias

    @property
    def format_method(self) -> str:
        return "format_json_valid"
