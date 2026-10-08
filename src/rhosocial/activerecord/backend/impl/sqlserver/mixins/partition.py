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

from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

from ..expression.objects import PartitionFunction, PartitionScheme

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
        The partition scheme is a typed field on
        ``SQLServerPartitionByRangeClause``.
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

        scheme = getattr(expr, "partition_scheme", None)
        if scheme:
            # The scheme is a named object of its own, not part of the table's
            # name: ``ON <scheme> (<keys>)`` names the scheme, and the table
            # this clause hangs off is named elsewhere in CREATE TABLE.
            return (
                f" ON {self.qualified_object_name(PartitionScheme, scheme)}"
                f" ({', '.join(parts)})",
                tuple(params),
            )

        keys_sql = ", ".join(parts)
        return f" ON partition_scheme_name ({keys_sql})", tuple(params)

    # --- Rendering SQL Server's own named objects -----------------------
    #
    # Partition functions and schemes are named catalogue entries with no
    # counterpart in the shared object tree, so the dialect supplies their two
    # formatters. Each is the same two calls every core ``*NameMixin`` makes:
    # refuse a namespace level this engine cannot express, then ask for the
    # spelling. They used to open with ``self.render_namespace(...)`` and
    # re-append the name themselves; core split that method into exactly these
    # two halves when the join character became the dialect's ``separator``, so
    # repeating the spelling here would have re-pinned the policy this backend
    # exists to express.
    #
    # The parameter types name the two kinds rather than ``Any``, for the same
    # reason the core mixins do: a partition scheme handed where a function
    # belongs would otherwise render as a well-formed statement naming the
    # wrong object.

    def format_partition_function_object(self, expr: PartitionFunction) -> Tuple[str, tuple]:
        """Render *expr* as a partition function name.

        Raises:
            UnsupportedFeatureError: *expr* carries a namespace level SQL
                Server cannot express.
        """
        self.validate_namespace(expr)
        return self.format_qualified_name(expr)

    def format_partition_scheme_object(self, expr: PartitionScheme) -> Tuple[str, tuple]:
        """Render *expr* as a partition scheme name.

        Raises:
            UnsupportedFeatureError: *expr* carries a namespace level SQL
                Server cannot express.
        """
        self.validate_namespace(expr)
        return self.format_qualified_name(expr)

    def format_sqlserver_partition_function(
        self, expr: "SQLServerPartitionFunctionExpression"
    ) -> Tuple[str, tuple]:
        """Format CREATE PARTITION FUNCTION statement.

        SQL Syntax:
            CREATE PARTITION FUNCTION function_name (data_type)
            AS RANGE [LEFT | RIGHT] FOR VALUES (v1, v2, ...)

        ``expr.function_name`` is *not* a stale attribute. It was listed as one
        because a reader compared this formatter with the ``Table``-shaped
        members core objectified, and found no field of that name. It belongs to
        :class:`SQLServerPartitionFunctionExpression`: a partition function is
        handed its name as text, optionally dotted, and
        ``qualified_object_name_from_dotted`` is what turns that into a
        :class:`PartitionFunction` rendered the way every other kind is.
        """
        boundary_parts = []
        for value in expr.boundary_values:
            boundary_parts.append(self.inline_sql_literal(value))

        quoted = self.qualified_object_name_from_dotted(
            PartitionFunction, expr.function_name
        )

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

        ``expr.function_name`` is the same deliberate text field as the one in
        :meth:`format_sqlserver_partition_function`: the partition function is
        named by text and objectified at the rendering boundary.
        """
        scheme_name = self.qualified_object_name(PartitionScheme, expr.scheme_name)
        func_name = self.qualified_object_name_from_dotted(
            PartitionFunction, expr.function_name
        )

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
