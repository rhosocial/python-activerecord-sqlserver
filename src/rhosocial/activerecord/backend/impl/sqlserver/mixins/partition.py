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

from typing import Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Table

from ..expression.objects import PartitionFunction, PartitionScheme
from ..expression.partition import SQLServerPartitionByRangeClause

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import PartitionClause
    from ..expression.partition import (
        SQLServerDropPartitionFunctionExpression,
        SQLServerDropPartitionSchemeExpression,
        SQLServerPartitionBoundaryQueryStatement,
        SQLServerPartitionFunctionExpression,
        SQLServerPartitionFunctionMergeExpression,
        SQLServerPartitionFunctionQueryStatement,
        SQLServerPartitionFunctionSplitExpression,
        SQLServerPartitionRangeQueryStatement,
        SQLServerPartitionSchemeExpression,
        SQLServerPartitionSchemeNextUsedExpression,
        SQLServerPartitionSchemeQueryStatement,
        SQLServerPartitionTableQueryStatement,
        SQLServerSwitchPartitionExpression,
    )


_SQL_SERVER_PARTITION_VERSION = (10, 0, 0)


def _partition_table_name(dialect, name: str, schema: Optional[str]) -> str:
    """Render a table name, with *schema* when the caller supplied one.

    Module-level rather than a mixin method because the partition formatters
    are copied onto :class:`SQLServerDialect`; only ``supports_`` and
    ``format_`` members travel, and a private helper would be left behind.
    """
    if schema:
        return dialect.qualified_object_name(Table, name, schema_name=schema)
    return dialect.qualified_object_name_from_dotted(Table, name)


def _partition_boundary_text(alias: str) -> str:
    """A readable, type-aware rendering of one ``sql_variant`` boundary.

    ``sys.partition_range_values.value`` is ``sql_variant`` and pyodbc cannot
    fetch it, so every projection casts it to text. Date/time values are
    rendered ISO-style rather than in the server's language-dependent default,
    so a report reads the same on any login. The text is for display only:
    boundary comparison is done by the server through
    ``SQLServerPartitionBoundaryQueryStatement``.
    """
    base = f"SQL_VARIANT_PROPERTY({alias}.value, 'BaseType')"
    return (
        f"CASE WHEN {base} = 'date' "
        f"THEN CONVERT(NVARCHAR(10), CAST({alias}.value AS date), 126) "
        f"WHEN {base} IN ('datetime', 'smalldatetime', 'datetime2') "
        f"THEN CONVERT(NVARCHAR(33), CAST({alias}.value AS datetime2), 126) "
        f"WHEN {base} = 'datetimeoffset' "
        f"THEN CONVERT(NVARCHAR(40), CAST({alias}.value AS datetimeoffset), 126) "
        f"WHEN {base} = 'time' "
        f"THEN CONVERT(NVARCHAR(20), CAST({alias}.value AS time), 126) "
        f"ELSE CONVERT(NVARCHAR(4000), CAST({alias}.value AS NVARCHAR(4000))) END"
    )


class SQLServerPartitionMixin:
    """SQL Server table partitioning implementation."""

    def supports_table_partitioning(self) -> bool:
        """SQL Server supports table partitioning (Enterprise Edition)."""
        return self.version_at_least(_SQL_SERVER_PARTITION_VERSION)  # type: ignore[attr-defined]

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

        # The partition scheme is declared by the SQL Server clause node; the
        # generic ``PartitionClause`` has no such field, so the dispatch is on
        # the declared class and the generic clause takes the placeholder path.
        scheme = (
            expr.partition_scheme
            if isinstance(expr, SQLServerPartitionByRangeClause)
            else None
        )
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

    def format_partition_function_expression(
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

    def format_partition_scheme_expression(
        self, expr: "SQLServerPartitionSchemeExpression"
    ) -> Tuple[str, tuple]:
        """Format CREATE PARTITION SCHEME statement.

        SQL Syntax:
            CREATE PARTITION SCHEME scheme_name
            AS PARTITION function_name
            [ALL] TO (filegroup1, filegroup2, ...)

        ``expr.function_name`` is the same deliberate text field as the one in
        :meth:`format_partition_function_expression`: the partition function is
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

    # --- Maintenance: SPLIT, MERGE, SWITCH, NEXT USED and drops --------- #
    #
    # SQL Server removes a partition by merging its boundary away; it never
    # drops one. These formatters spell the four maintenance statements, plus
    # the two drops, so the maintenance executor only constructs nodes and
    # executes what comes back.



    def format_partition_function_split_expression(
        self, expr: "SQLServerPartitionFunctionSplitExpression"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER PARTITION FUNCTION ... SPLIT RANGE``."""
        self.check_feature_support(  # type: ignore[attr-defined]
            "supports_split_partition",
            "SPLIT RANGE",
            "Use a SQL Server version that supports table partitioning.",
        )
        name = self.qualified_object_name_from_dotted(
            PartitionFunction, expr.function_name
        )
        value = self.inline_sql_literal(expr.boundary_value)
        return f"ALTER PARTITION FUNCTION {name} () SPLIT RANGE ({value})", ()

    def format_partition_function_merge_expression(
        self, expr: "SQLServerPartitionFunctionMergeExpression"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER PARTITION FUNCTION ... MERGE RANGE``."""
        self.check_feature_support(  # type: ignore[attr-defined]
            "supports_merge_partition",
            "MERGE RANGE",
            "Use a SQL Server version that supports table partitioning.",
        )
        name = self.qualified_object_name_from_dotted(
            PartitionFunction, expr.function_name
        )
        value = self.inline_sql_literal(expr.boundary_value)
        return f"ALTER PARTITION FUNCTION {name} () MERGE RANGE ({value})", ()

    def format_partition_scheme_next_used_expression(
        self, expr: "SQLServerPartitionSchemeNextUsedExpression"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER PARTITION SCHEME ... NEXT USED``."""
        scheme = self.qualified_object_name(PartitionScheme, expr.scheme_name)
        filegroup = self.format_identifier(expr.filegroup)  # type: ignore[attr-defined]
        return f"ALTER PARTITION SCHEME {scheme} NEXT USED {filegroup}", ()

    def format_switch_partition_expression(
        self, expr: "SQLServerSwitchPartitionExpression"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER TABLE ... SWITCH [PARTITION n] TO ...``."""
        self.check_feature_support(  # type: ignore[attr-defined]
            "supports_switch_partition",
            "SWITCH PARTITION",
            "Use a SQL Server version that supports table partitioning.",
        )
        source = _partition_table_name(self, expr.table, expr.schema)
        target = _partition_table_name(self, expr.target_table, expr.target_schema)
        source_partition = (
            f" PARTITION {expr.source_partition}"
            if expr.source_partition is not None
            else ""
        )
        target_partition = (
            f" PARTITION {expr.target_partition}"
            if expr.target_partition is not None
            else ""
        )
        return (
            f"ALTER TABLE {source} SWITCH{source_partition} "
            f"TO {target}{target_partition}",
            (),
        )

    def format_drop_partition_function_expression(
        self, expr: "SQLServerDropPartitionFunctionExpression"
    ) -> Tuple[str, tuple]:
        """Render ``DROP PARTITION FUNCTION``."""
        name = self.qualified_object_name_from_dotted(
            PartitionFunction, expr.function_name
        )
        return f"DROP PARTITION FUNCTION {name}", ()

    def format_drop_partition_scheme_expression(
        self, expr: "SQLServerDropPartitionSchemeExpression"
    ) -> Tuple[str, tuple]:
        """Render ``DROP PARTITION SCHEME``."""
        name = self.qualified_object_name(PartitionScheme, expr.scheme_name)
        return f"DROP PARTITION SCHEME {name}", ()

    # --- Catalogue questions ------------------------------------------- #
    #
    # The text is fixed apart from one optional name filter, so each formatter
    # builds it directly; the statement carries the filter and the executor
    # runs what comes back.

    def format_partition_function_query_statement(
        self, expr: "SQLServerPartitionFunctionQueryStatement"
    ) -> Tuple[str, tuple]:
        """Render the partition-function listing, one row per boundary."""
        where = ""
        params: tuple = ()
        if expr.function_name:
            where = "WHERE pf.name = ?"
            params = (expr.function_name,)
        sql = (
            "SELECT pf.name AS function_name, tp.name AS data_type, "
            "pf.boundary_value_on_right AS boundary_value_on_right, "
            "pf.fanout AS partition_count, prv.boundary_id AS boundary_id, "
            f"{_partition_boundary_text('prv')} AS boundary_value "
            "FROM sys.partition_functions AS pf "
            "JOIN sys.partition_parameters AS pp "
            "ON pf.function_id = pp.function_id AND pp.parameter_id = 1 "
            "JOIN sys.types AS tp "
            "ON pp.system_type_id = tp.system_type_id "
            "AND pp.user_type_id = tp.user_type_id "
            "LEFT JOIN sys.partition_range_values AS prv "
            "ON pf.function_id = prv.function_id "
            f"{where} ORDER BY pf.name, prv.boundary_id"
        )
        return sql, params

    def format_partition_scheme_query_statement(
        self, expr: "SQLServerPartitionSchemeQueryStatement"
    ) -> Tuple[str, tuple]:
        """Render the partition-scheme listing, one row per destination."""
        conditions = []
        params: tuple = ()
        if expr.scheme_name:
            conditions.append("ps.name = ?")
            params += (expr.scheme_name,)
        if expr.function_name:
            conditions.append("pf.name = ?")
            params += (expr.function_name,)
        where = f"WHERE {' AND '.join(conditions)} " if conditions else ""
        sql = (
            "SELECT ps.name AS scheme_name, pf.name AS function_name, "
            "pf.fanout AS partition_count, dds.destination_id AS destination_id, "
            "ds.name AS filegroup_name "
            "FROM sys.partition_schemes AS ps "
            "JOIN sys.partition_functions AS pf "
            "ON ps.function_id = pf.function_id "
            "JOIN sys.destination_data_spaces AS dds "
            "ON ps.data_space_id = dds.partition_scheme_id "
            "JOIN sys.data_spaces AS ds "
            "ON dds.data_space_id = ds.data_space_id "
            f"{where} ORDER BY ps.name, dds.destination_id"
        )
        return sql, params

    def format_partition_table_query_statement(
        self, expr: "SQLServerPartitionTableQueryStatement"
    ) -> Tuple[str, tuple]:
        """Render the listing of tables built on a partition scheme."""
        conditions = []
        params: tuple = ()
        if expr.schema:
            conditions.append("s.name = ?")
            params += (expr.schema,)
        if expr.table_name:
            conditions.append("t.name = ?")
            params += (expr.table_name,)
        if expr.scheme_name:
            conditions.append("ps.name = ?")
            params += (expr.scheme_name,)
        where = f"WHERE {' AND '.join(conditions)} " if conditions else ""
        sql = (
            "SELECT t.name AS table_name, s.name AS schema_name, "
            "ps.name AS scheme_name, pf.name AS function_name, "
            "c.name AS partition_column, pf.fanout AS partition_count "
            "FROM sys.tables AS t "
            "JOIN sys.schemas AS s ON t.schema_id = s.schema_id "
            "JOIN sys.indexes AS i "
            "ON t.object_id = i.object_id AND i.index_id IN (0, 1) "
            "JOIN sys.partition_schemes AS ps ON i.data_space_id = ps.data_space_id "
            "JOIN sys.partition_functions AS pf "
            "ON ps.function_id = pf.function_id "
            "LEFT JOIN sys.index_columns AS ic "
            "ON ic.object_id = i.object_id AND ic.index_id = i.index_id "
            "AND ic.partition_ordinal = 1 "
            "LEFT JOIN sys.columns AS c "
            "ON c.object_id = ic.object_id AND c.column_id = ic.column_id "
            f"{where}GROUP BY t.name, s.name, ps.name, pf.name, c.name, pf.fanout "
            "ORDER BY t.name"
        )
        return sql, params

    def format_partition_range_query_statement(
        self, expr: "SQLServerPartitionRangeQueryStatement"
    ) -> Tuple[str, tuple]:
        """Render one table's partitions, with bounds, rows and bytes."""
        conditions = ["t.name = ?"]
        params: tuple = (expr.table_name,)
        if expr.schema:
            conditions.insert(0, "s.name = ?")
            params = (expr.schema,) + params
        sql = (
            "WITH boundary_text AS ("
            "SELECT prv.function_id, prv.boundary_id, "
            f"{_partition_boundary_text('prv')} AS boundary_value "
            "FROM sys.partition_range_values AS prv"
            ") "
            "SELECT t.name AS table_name, s.name AS schema_name, "
            "stats.partition_number AS partition_number, "
            "stats.row_count AS row_count, "
            "stats.used_page_count AS used_page_count, "
            "low_b.boundary_value AS low_boundary, "
            "high_b.boundary_value AS high_boundary "
            "FROM sys.tables AS t "
            "JOIN sys.schemas AS s ON t.schema_id = s.schema_id "
            "JOIN sys.indexes AS i "
            "ON t.object_id = i.object_id AND i.index_id IN (0, 1) "
            "JOIN sys.partition_schemes AS ps ON i.data_space_id = ps.data_space_id "
            "JOIN sys.partition_functions AS pf ON ps.function_id = pf.function_id "
            "JOIN sys.dm_db_partition_stats AS stats "
            "ON stats.object_id = i.object_id AND stats.index_id = i.index_id "
            "LEFT JOIN boundary_text AS low_b "
            "ON low_b.function_id = pf.function_id "
            "AND low_b.boundary_id = stats.partition_number - 1 "
            "LEFT JOIN boundary_text AS high_b "
            "ON high_b.function_id = pf.function_id "
            "AND high_b.boundary_id = stats.partition_number "
            f"WHERE {' AND '.join(conditions)} "
            "ORDER BY stats.partition_number"
        )
        return sql, params

    def format_partition_boundary_query_statement(
        self, expr: "SQLServerPartitionBoundaryQueryStatement"
    ) -> Tuple[str, tuple]:
        """Render the question "does this boundary already exist?"."""
        sql = (
            "SELECT CASE WHEN EXISTS ("
            "SELECT 1 FROM sys.partition_range_values AS prv "
            "JOIN sys.partition_functions AS pf "
            "ON prv.function_id = pf.function_id "
            "WHERE pf.name = ? "
            f"AND prv.value = CAST(? AS {expr.data_type})"
            ") THEN 1 ELSE 0 END AS boundary_exists"
        )
        return sql, (expr.function_name, expr.boundary_value)
