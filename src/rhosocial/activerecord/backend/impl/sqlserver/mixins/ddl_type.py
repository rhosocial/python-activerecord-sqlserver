# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/ddl_type.py
"""SQL Server schema-level user-defined TYPE capabilities and formatting."""

from __future__ import annotations

from typing import Any, List, Optional, Tuple, Type, Union, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.base import SQLDialectBase
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.mixins.user_defined_type import UserDefinedTypeMixin
from rhosocial.activerecord.backend.expression.bases import ToSQLProtocol
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnConstraintType,
    ColumnDefinition,
    IndexDefinition,
    TableConstraint,
    TableConstraintType,
)
from rhosocial.activerecord.backend.expression.statements.ddl_type import (
    AlterTypeExpression,
    CreateTypeExpression,
    DropTypeExpression,
    TypeAlterAction,
    TypeDefinition,
)
from .version_constants import (
    SQL_SERVER_2005,
    SQL_SERVER_2008,
    SQL_SERVER_2016,
    SQL_SERVER_2017,
    SQL_SERVER_2019,
)
from ..expression.ddl.type import (
    SQLServerAliasTypeDefinition,
    SQLServerClrTypeDefinition,
    SQLServerDropTypeExpression,
    SQLServerRenameTypeExpression,
    SQLServerTableTypeDefinition,
)


class SQLServerTypeDDLMixin(UserDefinedTypeMixin):
    """SQL Server user-defined TYPE DDL support."""

    if TYPE_CHECKING:
        name: str
        _version: Optional[Tuple[int, int, int]]
        deployment_target: str

        def format_identifier(self, identifier: str, need_quote: bool = True) -> str:
            ...

        def format_column_definition(
            self,
            column: ColumnDefinition,
            *,
            memory_optimized: bool = False,
        ) -> Tuple[str, tuple]:
            ...

        def format_table_constraint(
            self,
            constraint: TableConstraint,
            *,
            memory_optimized: bool = False,
        ) -> Tuple[str, tuple]:
            ...

        def supports_memory_optimized_tables(self) -> bool:
            ...

    _SQLSERVER_TYPE_DEFINITIONS = (
        SQLServerAliasTypeDefinition,
        SQLServerTableTypeDefinition,
        SQLServerClrTypeDefinition,
    )

    def _version_at_least(self, minimum: Tuple[int, int, int]) -> bool:
        version = getattr(self, "_version", None)
        return version is not None and tuple(version) >= minimum

    def _is_sqlserver_deployment_target(self) -> bool:
        target = getattr(self, "deployment_target", "sqlserver")
        if target is None:
            return False
        target = getattr(target, "value", target)
        normalized = "_".join(str(target).strip().lower().replace("-", " ").split())
        return normalized in {
            "sqlserver",
            "sql_server",
            "microsoft_sql_server",
            "sqlserver_linux",
            "sql_server_linux",
            "microsoft_sql_server_linux",
            "azure_sql_managed_instance",
            "azure_sql_mi",
            "sql_managed_instance",
            "on_premises",
            "sqlserver_on_premises",
            "on_premises_sql_server",
            "box",
        }

    def supports_type_objects(self) -> bool:
        return self._version_at_least(SQL_SERVER_2005)

    def supports_create_type(self) -> bool:
        return self.supports_type_objects()

    def supports_alter_type(self) -> bool:
        return False

    def supports_drop_type(self) -> bool:
        return self.supports_type_objects()

    def _definition_is_supported(self, definition_type: Type[TypeDefinition]) -> bool:
        try:
            if issubclass(definition_type, SQLServerAliasTypeDefinition):
                return self.supports_type_objects()
            if issubclass(definition_type, SQLServerTableTypeDefinition):
                return self._version_at_least(SQL_SERVER_2008)
            if issubclass(definition_type, SQLServerClrTypeDefinition):
                return self.supports_type_objects() and self._is_sqlserver_deployment_target()
        except TypeError:
            return False
        return False

    def supported_type_definitions(self) -> Tuple[Type[TypeDefinition], ...]:
        return tuple(
            definition
            for definition in self._SQLSERVER_TYPE_DEFINITIONS
            if self._definition_is_supported(definition)
        )

    def supports_type_definition(
        self,
        definition_type: Type[TypeDefinition],
    ) -> bool:
        try:
            return any(
                issubclass(definition_type, supported)
                for supported in self.supported_type_definitions()
            )
        except TypeError:
            return False

    def supports_type_alter_action(
        self,
        action_type: Type[TypeAlterAction],
    ) -> bool:
        return False

    def supports_create_type_if_not_exists(self) -> bool:
        return False

    def supports_create_type_or_replace(self) -> bool:
        return False

    def supports_alter_type_if_exists(self) -> bool:
        return False

    def supports_drop_type_if_exists(self) -> bool:
        return self._version_at_least(SQL_SERVER_2016)

    def supports_multiple_type_alter_actions(self) -> bool:
        return False

    def supports_drop_type_cascade(self) -> bool:
        return False

    def supports_drop_type_restrict(self) -> bool:
        return False

    def supports_clr_type_definition(self) -> bool:
        return self.supports_type_objects() and self._is_sqlserver_deployment_target()

    def supports_clr_user_defined_type(self) -> bool:
        return self.supports_clr_type_definition()

    def supports_memory_optimized_table_types(self) -> bool:
        return bool(self.supports_memory_optimized_tables())

    def supports_rename_type(self) -> bool:
        return self._version_at_least(SQL_SERVER_2005)

    def _format_type_name(
        self,
        type_name: str,
        schema_name: Optional[str] = None,
    ) -> str:
        if not isinstance(type_name, str) or not type_name.strip():
            raise ValueError("type_name must be a non-empty string")
        parts: List[str] = []
        if schema_name is not None:
            if not isinstance(schema_name, str):
                raise TypeError("schema_name must be a string or None")
            if not schema_name.strip():
                raise ValueError("schema_name must contain a non-empty identifier")
            parts.append(self.format_identifier(schema_name))
        if not type_name.strip():
            raise ValueError("type_name must contain a non-empty identifier")
        parts.append(self.format_identifier(type_name))
        return ".".join(parts)

    def _raw_type_name(
        self,
        type_name: str,
        schema_name: Optional[str] = None,
    ) -> str:
        formatted = self._format_type_name(type_name, schema_name)
        return formatted

    @staticmethod
    def _format_nstring(value: str) -> str:
        if not isinstance(value, str):
            raise TypeError("sp_rename arguments must be strings")
        return f"N'{value.replace(chr(39), chr(39) * 2)}'"

    def _format_table_type_column(
        self,
        column: ColumnDefinition,
        memory_optimized: bool,
    ) -> Tuple[str, tuple]:
        if not isinstance(column, ColumnDefinition):
            raise TypeError("table TYPE columns must be ColumnDefinition instances")
        if getattr(column, "comment", None) is not None:
            raise UnsupportedFeatureError(
                self.name,
                "TYPE table column comment",
                "SQL Server table TYPE definitions do not support inline column comments.",
            )
        if getattr(column, "generated_expression", None) is not None:
            raise UnsupportedFeatureError(
                self.name,
                "TYPE table computed column",
                "Use a SQL Server-specific computed-column expression for table TYPEs.",
            )
        if getattr(column, "sparse", None) or getattr(column, "rowguidcol", None):
            raise UnsupportedFeatureError(
                self.name,
                "TYPE table column storage attribute",
                "SPARSE and ROWGUIDCOL are not supported in table TYPE definitions.",
            )
        allowed = {
            ColumnConstraintType.PRIMARY_KEY,
            ColumnConstraintType.NOT_NULL,
            ColumnConstraintType.NULL,
            ColumnConstraintType.DEFAULT,
        }
        if not memory_optimized or self._version_at_least(SQL_SERVER_2016):
            allowed.update({
                ColumnConstraintType.UNIQUE,
                ColumnConstraintType.CHECK,
            })
        for constraint in column.constraints:
            if memory_optimized and constraint.constraint_type not in allowed:
                if constraint.constraint_type in {
                    ColumnConstraintType.UNIQUE,
                    ColumnConstraintType.CHECK,
                }:
                    raise UnsupportedFeatureError(
                        self.name,
                        f"memory-optimized TYPE table column constraint {constraint.constraint_type}",
                        "requires SQL Server 2016+.",
                    )
                raise UnsupportedFeatureError(
                    self.name,
                    f"memory-optimized TYPE table column constraint {constraint.constraint_type}",
                    "SQL Server memory-optimized table TYPEs allow only key constraints and DEFAULT.",
                )
            if constraint.constraint_type not in allowed:
                raise UnsupportedFeatureError(
                    self.name,
                    f"TYPE table column constraint {constraint.constraint_type}",
                )
            if constraint.constraint_type == ColumnConstraintType.CHECK:
                if constraint.check_condition is None:
                    raise ValueError("CHECK constraint must have a check condition")
            if constraint.constraint_type == ColumnConstraintType.DEFAULT:
                if constraint.default_value is None:
                    raise ValueError("DEFAULT constraint must have a default value")
        return self.format_column_definition(
            column,
            memory_optimized=memory_optimized,
        )

    def _format_table_type_constraint(
        self,
        constraint: TableConstraint,
        memory_optimized: bool,
    ) -> Tuple[str, tuple]:
        if not isinstance(constraint, TableConstraint):
            raise TypeError("table TYPE constraints must be TableConstraint instances")
        if memory_optimized:
            if constraint.constraint_type in {
                TableConstraintType.UNIQUE,
                TableConstraintType.CHECK,
            } and not self._version_at_least(SQL_SERVER_2016):
                raise UnsupportedFeatureError(
                    self.name,
                    f"memory-optimized TYPE table constraint {constraint.constraint_type}",
                    "requires SQL Server 2016+.",
                )
            if constraint.constraint_type not in {
                TableConstraintType.PRIMARY_KEY,
                TableConstraintType.UNIQUE,
                TableConstraintType.CHECK,
            }:
                raise UnsupportedFeatureError(
                    self.name,
                    f"memory-optimized TYPE table constraint {constraint.constraint_type}",
                    "SQL Server memory-optimized table TYPEs allow only key constraints and CHECK.",
                )
        supported_types = {
            TableConstraintType.PRIMARY_KEY,
            TableConstraintType.UNIQUE,
            TableConstraintType.CHECK,
        }
        if constraint.constraint_type not in supported_types:
            raise UnsupportedFeatureError(
                self.name,
                f"TYPE table constraint {constraint.constraint_type}",
            )
        if constraint.constraint_type in {
            TableConstraintType.PRIMARY_KEY,
            TableConstraintType.UNIQUE,
        }:
            if constraint.check_condition is not None:
                raise ValueError("key constraints cannot carry a check condition")
            if constraint.foreign_key_table is not None or constraint.foreign_key_columns:
                raise ValueError("key constraints cannot carry foreign key fields")
        elif (
            constraint.columns
            or constraint.foreign_key_table is not None
            or constraint.foreign_key_columns
        ):
            raise ValueError("CHECK constraints cannot carry key or foreign key fields")
        for field_name in ("deferrable", "initially_deferred", "validation", "enforced"):
            if getattr(constraint, field_name, None) is not None:
                raise UnsupportedFeatureError(
                    self.name,
                    f"TYPE table constraint option {field_name}",
                )
        if constraint.constraint_type in {
            TableConstraintType.PRIMARY_KEY,
            TableConstraintType.UNIQUE,
        } and not constraint.columns:
            raise ValueError("table TYPE key constraint requires columns")
        if constraint.constraint_type == TableConstraintType.CHECK:
            if constraint.check_condition is None:
                raise ValueError("table TYPE CHECK constraint requires a condition")
        sql, params = self.format_table_constraint(
            constraint,
            memory_optimized=memory_optimized,
        )
        if not sql:
            raise ValueError("table TYPE constraint did not render SQL")
        return sql, tuple(params)

    def _format_table_type_index(
        self,
        index: IndexDefinition,
        memory_optimized: bool,
    ) -> Tuple[str, tuple]:
        if not isinstance(index, IndexDefinition):
            raise TypeError("table TYPE indexes must be IndexDefinition instances")
        if not isinstance(index.name, str) or not index.name.strip():
            raise ValueError("table TYPE index name must be a non-empty string")
        if not index.columns:
            raise ValueError("table TYPE index requires at least one column")
        unsupported_values = (
            ("partial_condition", getattr(index, "partial_condition", None)),
            ("if_not_exists", getattr(index, "if_not_exists", None)),
            ("tablespace", getattr(index, "tablespace", None)),
            ("if_exists", getattr(index, "if_exists", None)),
            ("concurrent", getattr(index, "concurrent", None)),
        )
        for field_name, value in unsupported_values:
            if value:
                raise UnsupportedFeatureError(
                    self.name,
                    f"TYPE table index option {field_name}",
                )
        hash_index = bool(getattr(index, "hash_index", False))
        bucket_count = getattr(index, "bucket_count", None)
        if bucket_count is not None:
            if isinstance(bucket_count, bool) or not isinstance(bucket_count, int):
                raise TypeError("bucket_count must be an integer")
            if bucket_count <= 0 or bucket_count > 1_073_741_824:
                raise ValueError("bucket_count must be between 1 and 1073741824")
        if bucket_count is not None and not hash_index:
            raise UnsupportedFeatureError(
                self.name,
                "TYPE table index bucket_count",
                "bucket_count is valid only for a HASH index.",
            )
        if hash_index:
            if not memory_optimized:
                raise UnsupportedFeatureError(
                    self.name,
                    "TYPE table HASH index",
                    "HASH indexes require a memory-optimized table TYPE.",
                )
            if not self.supports_memory_optimized_table_types():
                raise UnsupportedFeatureError(
                    self.name,
                    "TYPE table HASH index",
                    "requires SQL Server 2014+.",
                )
            if bucket_count is None:
                raise ValueError("bucket_count is required for a HASH index")
        index_type = getattr(index, "type", None)
        if index_type is not None:
            if not isinstance(index_type, str):
                raise TypeError("index type must be a string or None")
            index_type = index_type.upper()
            if index_type not in {"CLUSTERED", "NONCLUSTERED"}:
                raise UnsupportedFeatureError(
                    self.name,
                    f"TYPE table index type {index_type}",
                )
            if memory_optimized and index_type == "CLUSTERED":
                raise UnsupportedFeatureError(
                    self.name,
                    "TYPE table CLUSTERED index",
                    "memory-optimized table TYPE indexes cannot be clustered.",
                )
        column_parts: List[str] = []
        params: List[Any] = []
        for column in index.columns:
            if isinstance(column, ToSQLProtocol):
                column_sql, column_params = column.to_sql()
                column_parts.append(column_sql)
                params.extend(column_params)
            elif isinstance(column, str):
                column_parts.append(self.format_identifier(column))
            else:
                raise TypeError("table TYPE index columns must be strings or expressions")
        parts: List[str] = []
        if index.unique:
            parts.append("UNIQUE")
        parts.extend(("INDEX", self.format_identifier(index.name)))
        if hash_index:
            parts.append("NONCLUSTERED HASH")
        elif index_type:
            parts.append(index_type)
        elif memory_optimized:
            parts.append("NONCLUSTERED")
        parts.append(f"({', '.join(column_parts)})")
        include_columns = getattr(index, "include_columns", None)
        if memory_optimized and include_columns and not self._version_at_least(SQL_SERVER_2019):
            raise UnsupportedFeatureError(
                self.name,
                "TYPE table index INCLUDE columns",
                "requires SQL Server 2019+.",
            )
        if hash_index and include_columns:
            raise UnsupportedFeatureError(
                self.name,
                "TYPE HASH index INCLUDE columns",
                "HASH indexes cannot use INCLUDE.",
            )
        if include_columns:
            included = []
            for column in include_columns:
                if not isinstance(column, str):
                    raise TypeError("INCLUDE columns must be strings")
                included.append(self.format_identifier(column))
            parts.append(f"INCLUDE ({', '.join(included)})")
        if hash_index:
            parts.append(f"WITH (BUCKET_COUNT = {bucket_count})")
        return " ".join(parts), tuple(params)

    def _format_table_type_definition(
        self,
        expr: SQLServerTableTypeDefinition,
    ) -> Tuple[str, tuple]:
        if expr.memory_optimized and not self.supports_memory_optimized_table_types():
            raise UnsupportedFeatureError(
                self.name,
                "memory-optimized TYPE table",
                "requires SQL Server 2014+.",
            )
        parts: List[str] = []
        params: List[Any] = []
        for column in expr.columns:
            column_sql, column_params = self._format_table_type_column(
                column,
                expr.memory_optimized,
            )
            parts.append(column_sql)
            params.extend(column_params)
        for constraint in expr.constraints:
            constraint_sql, constraint_params = self._format_table_type_constraint(
                constraint,
                expr.memory_optimized,
            )
            parts.append(constraint_sql)
            params.extend(constraint_params)
        for index in expr.indexes:
            index_sql, index_params = self._format_table_type_index(
                index,
                expr.memory_optimized,
            )
            parts.append(index_sql)
            params.extend(index_params)
        if expr.memory_optimized and not self._version_at_least(SQL_SERVER_2017):
            key_constraint_count = sum(
                constraint.constraint_type
                in {
                    ColumnConstraintType.PRIMARY_KEY,
                    ColumnConstraintType.UNIQUE,
                }
                for column in expr.columns
                for constraint in column.constraints
            ) + sum(
                constraint.constraint_type
                in {
                    TableConstraintType.PRIMARY_KEY,
                    TableConstraintType.UNIQUE,
                }
                for constraint in expr.constraints
            )
            if len(expr.indexes) + key_constraint_count > 8:
                raise UnsupportedFeatureError(
                    self.name,
                    "memory-optimized TYPE table index count",
                    "SQL Server 2014 and 2016 allow at most 8 indexes; use SQL Server 2017+.",
                )
        if expr.memory_optimized:
            has_key_constraint = any(
                constraint.constraint_type
                in {
                    ColumnConstraintType.PRIMARY_KEY,
                    ColumnConstraintType.UNIQUE,
                }
                for column in expr.columns
                for constraint in column.constraints
            ) or any(
                constraint.constraint_type
                in {
                    TableConstraintType.PRIMARY_KEY,
                    TableConstraintType.UNIQUE,
                }
                for constraint in expr.constraints
            )
            if not has_key_constraint and not expr.indexes:
                raise ValueError(
                    "memory-optimized table TYPE requires at least one index "
                    "or PRIMARY KEY/UNIQUE constraint"
                )
        definition = f"AS TABLE ({', '.join(parts)})"
        if expr.memory_optimized:
            definition += " WITH (MEMORY_OPTIMIZED = ON)"
        return definition, tuple(params)

    def format_create_type_statement(
        self,
        expr: CreateTypeExpression,
    ) -> Tuple[str, tuple]:
        if not isinstance(expr, CreateTypeExpression):
            raise TypeError("expr must be a CreateTypeExpression")
        if expr.if_not_exists and expr.or_replace:
            raise ValueError("CREATE TYPE IF NOT EXISTS and OR REPLACE are mutually exclusive")
        if not self.supports_type_objects() or not self.supports_create_type():
            raise UnsupportedFeatureError(self.name, "CREATE TYPE")
        if expr.if_not_exists and not self.supports_create_type_if_not_exists():
            raise UnsupportedFeatureError(self.name, "CREATE TYPE IF NOT EXISTS")
        if expr.or_replace and not self.supports_create_type_or_replace():
            raise UnsupportedFeatureError(self.name, "CREATE OR REPLACE TYPE")
        if not isinstance(expr.definition, TypeDefinition):
            raise TypeError("definition must be a TypeDefinition instance")
        if not self.supports_type_definition(type(expr.definition)):
            raise UnsupportedFeatureError(
                self.name,
                f"TYPE definition {expr.definition.definition_kind}",
            )
        definition_sql, definition_params = expr.definition.to_sql()
        if definition_params:
            raise ValueError("CREATE TYPE must render without bind parameters")
        name_sql = self._format_type_name(expr.type_name, expr.schema_name)
        return f"CREATE TYPE {name_sql} {definition_sql}", ()

    def format_alter_type_statement(
        self,
        expr: AlterTypeExpression,
    ) -> Tuple[str, tuple]:
        if not isinstance(expr, AlterTypeExpression):
            raise TypeError("expr must be an AlterTypeExpression")
        raise UnsupportedFeatureError(
            self.name,
            "ALTER TYPE",
            "SQL Server has no ALTER TYPE; drop and recreate the TYPE instead.",
        )

    def format_drop_type_statement(
        self,
        expr: Union[DropTypeExpression, SQLServerDropTypeExpression],
    ) -> Tuple[str, tuple]:
        if not isinstance(expr, DropTypeExpression):
            raise TypeError("expr must be a DropTypeExpression")
        if not self.supports_type_objects() or not self.supports_drop_type():
            raise UnsupportedFeatureError(self.name, "DROP TYPE")
        if expr.if_exists and not self.supports_drop_type_if_exists():
            raise UnsupportedFeatureError(
                self.name,
                "DROP TYPE IF EXISTS",
                "requires SQL Server 2016+.",
            )
        cascade = bool(getattr(expr, "cascade", False))
        restrict = bool(getattr(expr, "restrict", False))
        if cascade and restrict:
            raise ValueError("CASCADE and RESTRICT are mutually exclusive")
        if cascade:
            raise UnsupportedFeatureError(self.name, "DROP TYPE CASCADE")
        if restrict:
            raise UnsupportedFeatureError(self.name, "DROP TYPE RESTRICT")
        parts = ["DROP TYPE"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self._format_type_name(expr.type_name, expr.schema_name))
        return " ".join(parts), ()

    def format_type_definition(
        self,
        expr: TypeDefinition,
    ) -> Tuple[str, tuple]:
        if not isinstance(expr, TypeDefinition):
            raise TypeError("expr must be a TypeDefinition instance")
        if not self.supports_type_definition(type(expr)):
            raise UnsupportedFeatureError(
                self.name,
                f"TYPE definition {getattr(expr, 'definition_kind', type(expr).__name__)}",
            )
        if isinstance(expr, SQLServerAliasTypeDefinition):
            base_sql, base_params = expr.base_type.to_sql()
            if base_params:
                raise ValueError("TYPE base types must render without bind parameters")
            if not SQLDialectBase._validate_data_type(base_sql):
                raise ValueError("TYPE base types must render as a safe SQL type")
            parts = [f"FROM {base_sql}"]
            if expr.nullability is True:
                parts.append("NOT NULL")
            elif expr.nullability is False:
                parts.append("NULL")
            return " ".join(parts), ()
        if isinstance(expr, SQLServerClrTypeDefinition):
            assembly_sql = self.format_identifier(expr.assembly_name)
            if expr.class_name is None:
                return f"EXTERNAL NAME {assembly_sql}", ()
            class_sql = self.format_identifier(expr.class_name)
            return f"EXTERNAL NAME {assembly_sql}.{class_sql}", ()
        if isinstance(expr, SQLServerTableTypeDefinition):
            return self._format_table_type_definition(expr)
        raise UnsupportedFeatureError(
            self.name,
            f"TYPE definition {getattr(expr, 'definition_kind', type(expr).__name__)}",
        )

    def format_type_alter_action(
        self,
        expr: TypeAlterAction,
    ) -> Tuple[str, tuple]:
        if not isinstance(expr, TypeAlterAction):
            raise TypeError("expr must be a TypeAlterAction instance")
        raise UnsupportedFeatureError(
            self.name,
            f"ALTER TYPE action {getattr(expr, 'action_kind', type(expr).__name__)}",
        )

    def format_rename_type_statement(
        self,
        expr: SQLServerRenameTypeExpression,
    ) -> Tuple[str, tuple]:
        if not isinstance(expr, SQLServerRenameTypeExpression):
            raise TypeError("expr must be a SQLServerRenameTypeExpression")
        if not self.supports_rename_type():
            raise UnsupportedFeatureError(
                self.name,
                "RENAME TYPE",
                "requires SQL Server 2005+.",
            )
        old_name = self._raw_type_name(expr.type_name, expr.schema_name)
        return (
            f"EXECUTE sp_rename {self._format_nstring(old_name)}, "
            f"{self._format_nstring(expr.new_name)}, N'USERDATATYPE'",
            (),
        )


__all__ = ["SQLServerTypeDDLMixin"]
