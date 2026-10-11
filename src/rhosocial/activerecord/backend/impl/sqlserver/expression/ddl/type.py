# src/rhosocial/activerecord/backend/impl/sqlserver/expression/ddl/type.py
"""SQL Server schema-level user-defined TYPE expressions."""

from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional, Sequence, Union

from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.expression.objects import Type
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
    """SQL Server user-defined table TYPE definition.

    ``constraints`` and ``table_constraints`` are two spellings of the same
    list (the latter exists to match the model-level naming) and are mutually
    exclusive. Both spellings reach the *same* rendering state, so the generic
    introspection-based ``get_params()`` is the whole serialization story:
    ``__init__`` stores the merged list under the slot belonging to the
    parameter the caller actually used and leaves the other slot ``None``, so
    ``get_params()`` emits ``constraints=[...], table_constraints=None`` (or
    the reverse) and the reconstruction takes the same branch. Renderers read
    :attr:`constraint_definitions`, never one particular spelling's slot.
    """

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
        self.indexes = index_list
        self.memory_optimized = memory_optimized
        # Fold the merged list into the slot named by the parameter the caller
        # used and leave the unused spelling at None ("not supplied"): both
        # spellings are mutually exclusive, so this is what makes the generic
        # get_params() round trip without an override.
        if table_constraints is None:
            self.constraints = constraint_list if constraints is not None else None
            self.table_constraints = None
        else:
            self.constraints = None
            self.table_constraints = constraint_list

    @property
    def constraint_definitions(self) -> List[TableConstraint]:
        """The declared table constraints, whichever spelling the caller used.

        ``constraints`` and ``table_constraints`` are two names for one list;
        only the spelling that was passed owns the corresponding attribute.
        Use this to read them back without caring which one that was.
        """
        if self.constraints is not None:
            return self.constraints
        return self.table_constraints or []


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
    """SQL Server DROP TYPE expression with explicit unsupported behavior flags.

    ``type`` is the :class:`~rhosocial.activerecord.backend.expression.objects.Type`
    being dropped, namespace and all; SQL Server has neither ``CASCADE`` nor
    ``RESTRICT`` for ``DROP TYPE``, and asking for one is an error here rather
    than a silently dropped token.
    """

    def __init__(
        self,
        dialect: Any,
        type: Type,
        *,
        if_exists: bool = False,
        cascade: bool = False,
        restrict: bool = False,
    ) -> None:
        if not isinstance(cascade, bool) or not isinstance(restrict, bool):
            raise TypeError("cascade and restrict must be bools")
        if cascade and restrict:
            raise ValueError("CASCADE and RESTRICT are mutually exclusive")
        super().__init__(dialect, type, if_exists=if_exists)
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
