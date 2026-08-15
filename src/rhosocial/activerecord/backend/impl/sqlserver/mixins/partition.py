# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/partition.py
"""SQL Server table partitioning mixin.

SQL Server supports RANGE partitioning via partition functions and
partition schemes. HASH and LIST are not supported as partitioning
strategies.

Version notes:
- Basic partitioning: SQL Server 2008+
- Partition functions/schemes: SQL Server 2008+
- Columnstore + partitioning: SQL Server 2012+
- SWITCH, SPLIT, MERGE: SQL Server 2008+
"""

from typing import Any, Sequence, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import PartitionClause
    from ..expression.partition import (
        SQLServerPartitionFunctionExpression,
        SQLServerPartitionSchemeExpression,
    )


_SQL_SERVER_PARTITION_VERSION = (10, 0, 0)


class SQLServerPartitionMixin:
    """SQL Server table partitioning implementation."""

    def supports_table_partitioning(self) -> bool:
        """SQL Server supports table partitioning (Enterprise Edition)."""
        return self.version >= _SQL_SERVER_PARTITION_VERSION  # type: ignore[attr-defined]

    def supports_partitioned_table_creation(self) -> bool:
        return self.supports_table_partitioning()

    def supports_partition_metadata_introspection(self) -> bool:
        return self.supports_table_partitioning()

    def supports_range_table_partitioning(self) -> bool:
        return self.supports_table_partitioning()

    def supports_range_right_partitioning(self) -> bool:
        return self.supports_table_partitioning()

    def supports_range_left_partitioning(self) -> bool:
        return self.supports_table_partitioning()

    def supports_list_table_partitioning(self) -> bool:
        return False

    def supports_hash_table_partitioning(self) -> bool:
        return False

    def supports_subpartitioning(self) -> bool:
        return False

    def supports_add_partition(self) -> bool:
        return False

    def supports_drop_partition(self) -> bool:
        return False

    def supports_truncate_partition(self) -> bool:
        return False

    def supports_reorganize_partition(self) -> bool:
        return False

    def supports_attach_partition(self) -> bool:
        return False

    def supports_detach_partition(self) -> bool:
        return False

    def supports_partition_function(self) -> bool:
        return self.supports_table_partitioning()

    def supports_partition_scheme(self) -> bool:
        return self.supports_table_partitioning()

    def supports_switch_partition(self) -> bool:
        return self.supports_table_partitioning()

    def supports_split_partition(self) -> bool:
        return self.supports_table_partitioning()

    def supports_merge_partition(self) -> bool:
        return self.supports_table_partitioning()

    def format_partition_clause(self, expr: "PartitionClause") -> Tuple[str, tuple]:
        """Format PARTITION BY clause for SQL Server.

        SQL Server uses ON partition_scheme(column) syntax.
        The core PartitionClause must reference a scheme via dialect_options.
        """
        self.check_feature_support(  # type: ignore[attr-defined]
            "supports_partitioned_table_creation",
            "PARTITION BY clause",
            "Use a SQL Server version that supports table partitioning.",
        )

        method_checks = {
            "RANGE": "supports_range_table_partitioning",
        }
        check_method = method_checks.get(expr.method)
        if check_method is None:
            raise UnsupportedFeatureError(
                getattr(self, "name", "SQL Server"),
                f"{expr.method} partitioning",
                "SQL Server only supports RANGE partitioning.",
            )
        self.check_feature_support(check_method, f"{expr.method} partitioning")  # type: ignore[attr-defined]

        parts = []
        params = []
        for key in expr.keys:
            key_sql, key_params = key.to_sql()
            parts.append(key_sql)
            params.extend(key_params)

        scheme = expr.dialect_options.get("partition_scheme")
        if scheme:
            return f" ON {self.format_identifier(scheme)} ({', '.join(parts)})", tuple(params)  # type: ignore[attr-defined]

        keys_sql = ", ".join(parts)
        return f" ON partition_scheme_name ({keys_sql})", tuple(params)

    def format_sqlserver_partition_function(
        self, expr: "SQLServerPartitionFunctionExpression"
    ) -> Tuple[str, tuple]:
        """Format CREATE PARTITION FUNCTION statement.

        SQL Syntax:
            CREATE PARTITION FUNCTION function_name (data_type)
            AS RANGE [LEFT | RIGHT] FOR VALUES (v1, v2, ...)
        """
        boundary_parts = []
        for value in expr.boundary_values:
            if value is None:
                boundary_parts.append("NULL")
            elif isinstance(value, str):
                escaped = value.replace("'", "''")
                boundary_parts.append(f"'{escaped}'")
            elif isinstance(value, bool):
                boundary_parts.append("1" if value else "0")
            else:
                boundary_parts.append(str(value))

        func_name = expr.function_name
        # Support schema-qualified names
        if "." in func_name:
            func_parts = func_name.split(".")
            quoted = ".".join(self.format_identifier(p) for p in func_parts)  # type: ignore[attr-defined]
        else:
            quoted = self.format_identifier(func_name)  # type: ignore[attr-defined]

        data_type = expr.data_type
        direction = expr.range_direction.value

        sql = (
            f"CREATE PARTITION FUNCTION {quoted} ({data_type}) "
            f"AS RANGE {direction} FOR VALUES ({', '.join(boundary_parts)})"
        )
        return sql, ()

    def format_sqlserver_partition_scheme(
        self, expr: "SQLServerPartitionSchemeExpression"
    ) -> Tuple[str, tuple]:
        """Format CREATE PARTITION SCHEME statement.

        SQL Syntax:
            CREATE PARTITION SCHEME scheme_name
            AS PARTITION function_name
            [ALL] TO (filegroup1, filegroup2, ...)
        """
        scheme_name = self.format_identifier(expr.scheme_name)  # type: ignore[attr-defined]
        func_name = self.format_identifier(expr.function_name)  # type: ignore[attr-defined]

        if expr.all_filegroup:
            fg_quoted = self.format_identifier(expr.all_filegroup)  # type: ignore[attr-defined]
            sql = (
                f"CREATE PARTITION SCHEME {scheme_name} "
                f"AS PARTITION {func_name} "
                f"ALL TO ({fg_quoted})"
            )
        else:
            if not expr.filegroups:
                raise ValueError("At least one filegroup is required")
            fg_list = ", ".join(
                self.format_identifier(fg) for fg in expr.filegroups  # type: ignore[attr-defined]
            )
            sql = (
                f"CREATE PARTITION SCHEME {scheme_name} "
                f"AS PARTITION {func_name} "
                f"TO ({fg_list})"
            )

        return sql, ()
