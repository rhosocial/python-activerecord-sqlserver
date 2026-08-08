# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/protocol_support.py
"""SQL Server protocol support mixin.

Implements the SQL Server-specific protocol contracts declared in
``protocols/`` by delegating to the dialect's existing formatting
capabilities. This lets ``isinstance(dialect, SQLServerXxxSupport)``
checks succeed for features that were already able to generate valid
SQL but were previously left as empty protocol stubs.

Still-missing capabilities (temporal DDL, indexed views, SELECT INTO)
raise ``UnsupportedFeatureError`` with a clear message instead of
silently returning a stub.
"""

from typing import Any, Dict, List, Optional, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class SQLServerProtocolSupportMixin:
    """SQL Server protocol contract implementations delegating to dialect formatters."""

    def supports_output_clause(self) -> bool:
        """SQL Server supports the OUTPUT clause."""
        return True

    def format_output_clause(
        self, columns: List[str], clause_type: str = "inserted"
    ) -> Tuple[str, tuple]:
        """Format an OUTPUT clause delegating to format_returning_clause.

        Args:
            columns: Output column names.
            clause_type: Virtual table prefix, either ``inserted`` or ``deleted``.

        Returns:
            Tuple of (SQL string, params tuple), e.g. ``OUTPUT INSERTED.[id]``.
        """
        from rhosocial.activerecord.backend.expression.core import Column
        from rhosocial.activerecord.backend.expression.statements import ReturningClause

        default_table = clause_type.upper()
        expressions = [Column(self, col) for col in columns]
        clause = ReturningClause(self, expressions)
        return self.format_returning_clause(clause, default_table=default_table)

    def supports_offset_fetch(self) -> bool:
        """OFFSET FETCH pagination requires SQL Server 2012+."""
        return self.version >= (11, 0, 0)

    def supports_order_by_in_subquery(self) -> bool:
        """ORDER BY in subqueries is allowed with TOP/OFFSET FETCH (2012+)."""
        return self.version >= (11, 0, 0)

    def supports_fulltext_catalog(self) -> bool:
        """SQL Server supports FULLTEXT catalogs."""
        return True

    def format_create_fulltext_catalog_statement(self, catalog_name: str) -> str:
        """Format CREATE FULLTEXT CATALOG statement."""
        return f"CREATE FULLTEXT CATALOG {self.format_identifier(catalog_name)}"

    def format_contains_predicate(self, column: str, search_string: str) -> Tuple[str, tuple]:
        """Format a CONTAINS predicate delegating to format_fulltext_match."""
        return self.format_fulltext_match([column], search_string)

    def format_freetext_predicate(self, column: str, search_string: str) -> Tuple[str, tuple]:
        """Format a FREETEXT predicate."""
        from ..expression.functions import SQLServerFreetextPredicate

        return SQLServerFreetextPredicate(self, column, search_string).to_sql()

    def format_containstable_function(
        self, table: str, column: str, search_string: str, top_n: Optional[int] = None
    ) -> Tuple[str, tuple]:
        """Format a CONTAINSTABLE full-text table function."""
        escaped = search_string.replace("'", "''")
        sql = (
            f"CONTAINSTABLE({self.format_identifier(table)}, "
            f"{self.format_identifier(column)}, '{escaped}'"
        )
        if top_n is not None:
            sql += f", {top_n}"
        sql += ")"
        return sql, ()

    def supports_readpast(self) -> bool:
        """READPAST hint requires SQL Server 2019+."""
        return self.version >= (15, 0, 0)

    def format_table_hint_locking(self, hint_type: str) -> str:
        """Format a locking table hint delegating to SQLServerTableHintClause."""
        from ..expression.locking import SQLServerTableHint, SQLServerTableHintClause

        hint_type = hint_type.upper()
        hints = [SQLServerTableHint("UPDLOCK"), SQLServerTableHint("ROWLOCK")]
        if "READPAST" in hint_type and self.supports_readpast():
            hints.append(SQLServerTableHint("READPAST"))
        clause = SQLServerTableHintClause(self, hints)
        return clause.to_sql()[0]

    def supports_try_cast(self) -> bool:
        """TRY_CAST requires SQL Server 2012+."""
        return self.version >= (11, 0, 0)

    def supports_try_convert(self) -> bool:
        """TRY_CONVERT requires SQL Server 2012+."""
        return self.version >= (11, 0, 0)

    def format_try_cast_expression(self, expr_sql: str, target_type: str) -> Tuple[str, tuple]:
        """Format TRY_CAST(expr AS type)."""
        from ..expression.functions import SQLServerTryCastExpression

        return SQLServerTryCastExpression(self, expr_sql, target_type).to_sql()

    def format_try_convert_expression(
        self, expr_sql: str, target_type: str, style: Optional[int] = None
    ) -> Tuple[str, tuple]:
        """Format TRY_CONVERT(type, expr[, style])."""
        from ..expression.functions import SQLServerTryConvertExpression

        return SQLServerTryConvertExpression(self, target_type, expr_sql, style).to_sql()

    def supports_table_hints(self) -> bool:
        """SQL Server supports WITH (...) table hints."""
        return True

    def format_table_hint(self, hints: List[str]) -> str:
        """Format a WITH (hint1, hint2, ...) table hint clause."""
        from ..expression.locking import SQLServerTableHint, SQLServerTableHintClause

        clause = SQLServerTableHintClause(
            self, [SQLServerTableHint(hint) for hint in hints]
        )
        return clause.to_sql()[0]

    def supports_select_into(self) -> bool:
        """SQL Server supports SELECT INTO."""
        return True

    def supports_tablesample(self) -> bool:
        """SQL Server supports TABLESAMPLE since 2005."""
        return self.version >= (9, 0, 0)

    def format_tablesample_clause(
        self,
        sample: int,
        percentage: bool = False,
        repeatable: Optional[int] = None,
    ) -> str:
        """Format a TABLESAMPLE clause (SQL Server 2005+).

        SQL Syntax:
            TABLESAMPLE (n ROWS | n PERCENT) [REPEATABLE (seed)]

        Args:
            sample: Row count or percent value.
            percentage: If True, emit ``PERCENT`` instead of ``ROWS``.
            repeatable: Optional REPEATABLE seed for reproducible sampling.

        Returns:
            The TABLESAMPLE clause, e.g.
            ``TABLESAMPLE (10 ROWS) REPEATABLE (42)``.
        """
        unit = "PERCENT" if percentage else "ROWS"
        clause = f"TABLESAMPLE ({sample} {unit})"
        if repeatable is not None:
            clause += f" REPEATABLE ({repeatable})"
        return clause

    def format_select_into_statement(self, expr: Any) -> Tuple[str, tuple]:
        """Format a SELECT INTO statement (all SQL Server versions).

        SQL Syntax:
            SELECT ... INTO [new_table] FROM ... WHERE ...

        The target table is taken from ``expr.dialect_options["select_into_table"]``.
        The INTO clause is inserted between the select list and the FROM
        clause of the fully rendered query.
        """
        dialect_options = getattr(expr, "dialect_options", None) or {}
        into_table = dialect_options.get("select_into_table")
        if not into_table:
            raise ValueError(
                "dialect_options['select_into_table'] is required for SELECT INTO"
            )

        full_sql, params = expr.to_sql()
        select_head = self._format_select_head(expr)
        if full_sql.startswith(select_head):
            tail = full_sql[len(select_head):]
        else:
            from_index = full_sql.find(" FROM ")
            if from_index == -1:
                raise UnsupportedFeatureError(
                    self.name,
                    "SELECT INTO without FROM clause",
                    "SELECT INTO requires a FROM source.",
                )
            select_head = full_sql[:from_index]
            tail = full_sql[from_index:]

        into_sql = f"INTO {self.format_identifier(into_table)}"
        return f"{select_head} {into_sql}{tail}", tuple(params)

    def _format_select_head(self, expr: Any) -> str:
        """Render the SELECT head (modifier + select list) of a query.

        Mirrors the core ``DQLMixin.format_query_statement`` head so the
        rendered statement can be split at the same boundary.
        """
        select_parts = [item.to_sql()[0] for item in expr.select]
        modifier = f" {expr.select_modifier.value}" if expr.select_modifier else ""
        return f"SELECT{modifier} " + ", ".join(select_parts)

    def format_openjson_expression(
        self,
        json_doc: str,
        path: Optional[str] = None,
        schema: Optional[Dict[str, str]] = None,
        alias: Optional[str] = None,
    ) -> Tuple[str, tuple]:
        """Format an OPENJSON expression delegating to SQLServerOpenJsonExpression."""
        from ..expression.openjson import OpenJsonColumn, SQLServerOpenJsonExpression

        columns = []
        if schema:
            if isinstance(schema, dict):
                columns = [
                    OpenJsonColumn(name=name, type=type_name)
                    for name, type_name in schema.items()
                ]
            else:
                columns = list(schema)
        return SQLServerOpenJsonExpression(
            self, json_doc, path=path, schema=columns, alias=alias
        ).to_sql()

    def supports_system_versioning(self) -> bool:
        """Temporal table system-versioning requires SQL Server 2016+."""
        return self.version >= (13, 0, 0)

    def format_temporal_period_definition(self, start_column: str, end_column: str) -> str:
        """Format PERIOD FOR SYSTEM_TIME (start, end)."""
        from ..expression.temporal import SQLServerTemporalPeriodDefinition

        return SQLServerTemporalPeriodDefinition(
            self, start_column, end_column
        ).to_sql()[0]

    def format_create_temporal_table_statement(self, expr: Any) -> Tuple[str, tuple]:
        """Format CREATE TABLE with temporal options - not yet implemented."""
        raise UnsupportedFeatureError(
            self.name,
            "CREATE TABLE with temporal options",
            "Temporal table DDL is not yet implemented.",
        )

    def supports_merge_output(self) -> bool:
        """SQL Server MERGE supports an OUTPUT clause (2008+)."""
        return True

    def supports_merge_holdlock(self) -> bool:
        """SQL Server MERGE supports the WITH (HOLDLOCK) table hint (2008+)."""
        return True

    def format_merge_output_clause(
        self, columns: List[str], action_type: Optional[str] = None
    ) -> Tuple[str, tuple]:
        """Format a MERGE OUTPUT clause.

        Args:
            columns: OUTPUT columns, e.g. ``["inserted.*", "deleted.*"]``.
            action_type: Optional pseudo-column such as ``"$action"`` prepended
                to the output list.

        Returns:
            Tuple of (SQL string, params tuple), e.g.
            ``OUTPUT $action, inserted.*, deleted.*``.
        """
        parts = []
        if action_type:
            parts.append(action_type)
        parts.extend(columns)
        return f"OUTPUT {', '.join(parts)}", ()

    def supports_identity_insert(self) -> bool:
        """SQL Server supports SET IDENTITY_INSERT."""
        return True

    def format_set_identity_insert(self, table: str, on: bool) -> str:
        """Format SET IDENTITY_INSERT table {ON|OFF}."""
        state = "ON" if on else "OFF"
        return f"SET IDENTITY_INSERT {self.format_identifier(table)} {state}"

    def format_create_indexed_view_statement(self, expr: Any) -> Tuple[str, tuple]:
        """Format CREATE VIEW WITH SCHEMABINDING (indexed view) - not yet implemented."""
        raise UnsupportedFeatureError(
            self.name,
            "CREATE VIEW WITH SCHEMABINDING (indexed view)",
            "Indexed view DDL is not yet implemented.",
        )
