# src/rhosocial/activerecord/backend/impl/sqlserver/expression/ddl/type.py
"""SQL Server schema-level user-defined TYPE expressions."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional, Sequence, Union, cast

from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.expression.serialization import ExpressionRegistry
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnDefinition,
    IndexDefinition,
    TableConstraint,
)
from rhosocial.activerecord.backend.expression.statements.ddl_type import (
    DropTypeExpression,
    TypeDefinition,
)
from rhosocial.activerecord.backend.expression.types import DataType
from ..column import SQLServerColumnDefinition
from ..index import SQLServerIndexDefinition


class SQLServerTypeNullability(Enum):
    """Nullability declaration accepted by a SQL Server alias type."""

    NULL = "NULL"
    NULLABLE = "NULL"
    NOT_NULL = "NOT NULL"


def _validate_name(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _validate_dotted_name(value: str, field_name: str) -> None:
    _validate_name(value, field_name)
    if any(not part.strip() for part in value.split(".")):
        raise ValueError(f"{field_name} must contain non-empty identifier segments")


def _normalise_nullability(value: Any) -> Optional[bool]:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, Enum):
        value = value.value
    if not isinstance(value, str):
        raise TypeError("nullability must be a bool, string, or nullability enum")
    normalized = " ".join(value.strip().upper().split())
    if normalized in {"NULL", "NULLABLE"}:
        return False
    if normalized in {"NOT NULL", "NOT_NULL"}:
        return True
    if normalized == "UNSPECIFIED":
        return None
    raise ValueError("nullability must be NULL, NOT NULL, or unspecified")


def _require_data_type(value: DataType, field_name: str) -> None:
    if not isinstance(value, DataType):
        raise TypeError(
            f"{field_name} must be a DataType instance, got {type(value).__name__}"
        )


class SQLServerAliasTypeDefinition(TypeDefinition):
    """SQL Server alias TYPE definition."""

    definition_kind = "alias"

    def __init__(
        self,
        dialect: Any,
        base_type: DataType,
        nullability: Optional[Union[bool, str, SQLServerTypeNullability]] = None,
    ) -> None:
        super().__init__(dialect)
        _require_data_type(base_type, "base_type")
        self.base_type = base_type
        self.nullability = _normalise_nullability(nullability)


class SQLServerTableTypeDefinition(TypeDefinition):
    """SQL Server user-defined table TYPE definition."""

    definition_kind = "table"

    def __init__(
        self,
        dialect: Any,
        columns: Sequence[ColumnDefinition],
        constraints: Optional[Sequence[TableConstraint]] = None,
        indexes: Optional[Sequence[IndexDefinition]] = None,
        memory_optimized: bool = False,
        *,
        table_constraints: Optional[Sequence[TableConstraint]] = None,
    ) -> None:
        super().__init__(dialect)
        if constraints is not None and table_constraints is not None:
            raise ValueError("constraints and table_constraints are mutually exclusive")
        column_list = list(columns or [])
        if not column_list:
            raise ValueError("table TYPE requires at least one column")
        constraint_list = list(
            constraints if constraints is not None else (table_constraints or [])
        )
        index_list = list(indexes or [])

        if any(not isinstance(column, ColumnDefinition) for column in column_list):
            raise TypeError("columns must contain ColumnDefinition instances")
        if any(not isinstance(constraint, TableConstraint) for constraint in constraint_list):
            raise TypeError("constraints must contain TableConstraint instances")
        if any(not isinstance(index, IndexDefinition) for index in index_list):
            raise TypeError("indexes must contain IndexDefinition instances")
        if not isinstance(memory_optimized, bool):
            raise TypeError("memory_optimized must be a bool")
        self.columns = column_list
        self.constraints = constraint_list
        self.table_constraints = constraint_list
        self.indexes = index_list
        self.memory_optimized = memory_optimized

    def get_params(self) -> Dict[str, Any]:
        params = cast(Dict[str, Any], super().get_params())
        params.pop("table_constraints", None)
        params["constraints"] = self.constraints
        return params


class SQLServerClrTypeDefinition(TypeDefinition):
    """SQL Server CLR user-defined TYPE definition."""

    definition_kind = "clr"

    def __init__(
        self,
        dialect: Any,
        assembly_name: str,
        class_name: Optional[str] = None,
    ) -> None:
        super().__init__(dialect)
        _validate_dotted_name(assembly_name, "assembly_name")
        if class_name is not None:
            _validate_dotted_name(class_name, "class_name")
        self.assembly_name = assembly_name
        self.class_name = class_name


class SQLServerDropTypeExpression(DropTypeExpression):
    """SQL Server DROP TYPE expression with explicit unsupported behavior flags."""

    def __init__(
        self,
        dialect: Any,
        type_name: str,
        *,
        schema_name: Optional[str] = None,
        if_exists: bool = False,
        cascade: bool = False,
        restrict: bool = False,
    ) -> None:
        if not isinstance(cascade, bool) or not isinstance(restrict, bool):
            raise TypeError("cascade and restrict must be bools")
        if cascade and restrict:
            raise ValueError("CASCADE and RESTRICT are mutually exclusive")
        super().__init__(
            dialect,
            type_name,
            schema_name=schema_name,
            if_exists=if_exists,
        )
        self.cascade = cascade
        self.restrict = restrict


class SQLServerRenameTypeExpression(BaseExpression):
    """SQL Server TYPE rename statement using ``sp_rename``."""

    @property
    def format_method(self) -> str:
        return "format_rename_type_statement"

    def __init__(
        self,
        dialect: Any,
        type_name: str,
        new_name: str,
        *,
        schema_name: Optional[str] = None,
    ) -> None:
        super().__init__(dialect)
        _validate_name(type_name, "type_name")
        _validate_name(new_name, "new_name")
        if "." in new_name:
            raise ValueError("new_name must be a one-part identifier")
        if schema_name is not None:
            _validate_dotted_name(schema_name, "schema_name")
        self.type_name = type_name
        self.new_name = new_name
        self.schema_name = schema_name


_SQLSERVER_TYPE_EXPRESSIONS = (
    SQLServerAliasTypeDefinition,
    SQLServerTableTypeDefinition,
    SQLServerClrTypeDefinition,
    SQLServerDropTypeExpression,
    SQLServerRenameTypeExpression,
    SQLServerColumnDefinition,
    SQLServerIndexDefinition,
)

for _expression_class in _SQLSERVER_TYPE_EXPRESSIONS:
    ExpressionRegistry.register(_expression_class)


__all__ = [
    "SQLServerTypeNullability",
    "SQLServerAliasTypeDefinition",
    "SQLServerTableTypeDefinition",
    "SQLServerClrTypeDefinition",
    "SQLServerDropTypeExpression",
    "SQLServerRenameTypeExpression",
]
