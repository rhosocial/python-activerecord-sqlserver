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
        """FULLTEXT catalogs require SQL Server 2005+."""
        return self.version >= (9, 0, 0)

    def format_create_fulltext_catalog_statement(
        self, catalog_name: str, as_default: bool = False
    ) -> str:
        """Format CREATE FULLTEXT CATALOG statement (2005+).

        SQL Syntax:
            CREATE FULLTEXT CATALOG catalog_name [AS DEFAULT]

        Args:
            catalog_name: Name of the full-text catalog.
            as_default: If True, append ``AS DEFAULT`` to make the catalog the
                database default.

        Returns:
            The CREATE FULLTEXT CATALOG statement.
        """
        self.check_feature_support(
            "supports_fulltext_catalog",
            "FULLTEXT catalogs",
            "requires SQL Server 2005+.",
        )
        sql = f"CREATE FULLTEXT CATALOG {self.format_identifier(catalog_name)}"
        if as_default:
            sql += " AS DEFAULT"
        return sql

    def format_drop_fulltext_catalog_statement(self, catalog_name: str) -> str:
        """Format DROP FULLTEXT CATALOG statement (2005+).

        SQL Syntax:
            DROP FULLTEXT CATALOG catalog_name
        """
        self.check_feature_support(
            "supports_fulltext_catalog",
            "FULLTEXT catalogs",
            "requires SQL Server 2005+.",
        )
        return f"DROP FULLTEXT CATALOG {self.format_identifier(catalog_name)}"

    def format_create_fulltext_index_statement(
        self,
        table: str,
        columns: List[str],
        key_index: str,
        catalog_name: str,
    ) -> str:
        """Format CREATE FULLTEXT INDEX statement (2005+).

        SQL Syntax:
            CREATE FULLTEXT INDEX ON table (column, ...)
            KEY INDEX unique_index ON catalog_name
        """
        self.check_feature_support(
            "supports_fulltext_catalog",
            "FULLTEXT indexes",
            "requires SQL Server 2005+.",
        )
        columns_str = ", ".join(self.format_identifier(col) for col in columns)
        return (
            f"CREATE FULLTEXT INDEX ON {self.format_identifier(table)} "
            f"({columns_str}) KEY INDEX {self.format_identifier(key_index)} "
            f"ON {self.format_identifier(catalog_name)}"
        )

    def format_drop_fulltext_index_statement(self, table: str) -> str:
        """Format DROP FULLTEXT INDEX statement (2005+).

        SQL Syntax:
            DROP FULLTEXT INDEX ON table
        """
        self.check_feature_support(
            "supports_fulltext_catalog",
            "FULLTEXT indexes",
            "requires SQL Server 2005+.",
        )
        return f"DROP FULLTEXT INDEX ON {self.format_identifier(table)}"

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
        select_head = self.format_select_head(expr)
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

    def format_select_head(self, expr: Any) -> str:
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
        """Format CREATE VIEW WITH SCHEMABINDING (indexed view) (2005+).

        SQL Server has no materialized views; the official equivalent is an
        indexed view: a ``WITH SCHEMABINDING`` view backed by a unique
        clustered index.

        SQL Syntax:
            CREATE VIEW view_name [(column_aliases)]
            WITH SCHEMABINDING AS <query>

        Args:
            expr: A ``CreateViewExpression`` whose ``query`` supplies the
                select statement.

        Returns:
            Tuple of (SQL string, params tuple).
        """
        self.check_feature_support(
            "supports_indexed_view",
            "indexed views",
            "requires SQL Server 2005+.",
        )
        parts = ["CREATE VIEW"]
        parts.append(self.format_identifier(expr.view_name))

        if expr.column_aliases:
            cols = ", ".join(self.format_identifier(c) for c in expr.column_aliases)
            parts.append(f"({cols})")

        query_sql, query_params = expr.query.to_sql()
        parts.append(f"WITH SCHEMABINDING AS {query_sql}")
        return " ".join(parts), query_params

    # ========== JSON Function Support ==========

    _JSON_FUNCTION_MIN_VERSION = (13, 0, 0)
    _JSON_FUNCTION_2022 = {"JSON_PATH_EXISTS", "JSON_OBJECT", "JSON_ARRAY"}
    _JSON_FUNCTION_UNSUPPORTED = {"JSON_TABLE"}

    def supports_json_function(self, function_name: str) -> bool:
        """Check whether a JSON function is supported based on version.

        SQL Server JSON support begins with 2016 (13.0): JSON_VALUE,
        JSON_QUERY, ISJSON, JSON_MODIFY, OPENJSON. JSON_OBJECT, JSON_ARRAY
        and JSON_PATH_EXISTS require 2022 (16.0). JSON_TABLE is never
        supported (SQL Server uses OPENJSON).
        """
        name = function_name.upper()
        if name in self._JSON_FUNCTION_UNSUPPORTED:
            return False
        if name in self._JSON_FUNCTION_2022:
            return self.version >= (16, 0, 0)
        return self.version >= self._JSON_FUNCTION_MIN_VERSION

    def format_json_extract(
        self, json_doc: str, path: str, paths: Optional[List[str]] = None
    ) -> Tuple[str, tuple]:
        """Format a JSON extraction as JSON_VALUE (single path only).

        SQL Server's JSON_VALUE returns the scalar value at the path, already
        unquoted. Multi-path extraction has no direct T-SQL equivalent.
        """
        if paths:
            raise UnsupportedFeatureError(
                self.name,
                "JSON_EXTRACT with multiple paths",
                "SQL Server's JSON_VALUE extracts a single scalar path only.",
            )
        return f"JSON_VALUE({json_doc}, {self.get_parameter_placeholder()})", (path,)

    def format_json_unquote(self, json_val: str) -> Tuple[str, tuple]:
        """Format JSON_UNQUOTE - not needed in SQL Server.

        JSON_VALUE already returns scalar values without surrounding quotes,
        so there is no T-SQL equivalent of JSON_UNQUOTE.
        """
        raise UnsupportedFeatureError(
            self.name,
            "JSON_UNQUOTE",
            "SQL Server's JSON_VALUE returns scalar values already unquoted.",
        )

    def format_json_object(self, key_value_pairs: List[Tuple[str, Any]]) -> Tuple[str, tuple]:
        """Format a JSON_OBJECT function (SQL Server 2022+).

        SQL Syntax:
            JSON_OBJECT('key1' : value1, 'key2' : value2, ...)
        """
        if not key_value_pairs:
            return "JSON_OBJECT()", ()

        parts = []
        params: List[Any] = []
        placeholder = self.get_parameter_placeholder()
        for key, value in key_value_pairs:
            parts.append(f"{placeholder} : {placeholder}")
            params.append(key)
            params.append(value)

        return f"JSON_OBJECT({', '.join(parts)})", tuple(params)

    def format_json_array(self, values: List[Any]) -> Tuple[str, tuple]:
        """Format a JSON_ARRAY function (SQL Server 2022+)."""
        if not values:
            return "JSON_ARRAY()", ()
        placeholder = self.get_parameter_placeholder()
        return f"JSON_ARRAY({', '.join([placeholder] * len(values))})", tuple(values)

    def format_json_contains(
        self, target: str, candidate: str, path: Optional[str] = None
    ) -> Tuple[str, tuple]:
        """Format a JSON containment check using OPENJSON (2016+).

        SQL Server has no JSON_CONTAINS; membership of ``candidate`` in the
        JSON array/object at ``path`` is checked with an OPENJSON predicate.
        """
        placeholder = self.get_parameter_placeholder()
        json_path = path if path is not None else "$"
        sql = (
            f"EXISTS (SELECT 1 FROM OPENJSON({target}, {placeholder}) "
            f"WHERE value = {placeholder})"
        )
        return sql, (json_path, candidate)

    def format_json_set(
        self,
        json_doc: str,
        path: str,
        value: Any,
        path_value_pairs: Optional[List[Tuple[str, Any]]] = None,
    ) -> Tuple[str, tuple]:
        """Format a JSON_MODIFY function (single path-value pair only).

        SQL Server's JSON_MODIFY accepts exactly one path-value pair.
        """
        if path_value_pairs:
            raise UnsupportedFeatureError(
                self.name,
                "JSON_SET with multiple path-value pairs",
                "SQL Server's JSON_MODIFY accepts a single path-value pair.",
            )
        placeholder = self.get_parameter_placeholder()
        return f"JSON_MODIFY({json_doc}, {placeholder}, {placeholder})", (path, value)

    def format_json_remove(
        self, json_doc: str, path: str, paths: Optional[List[str]] = None
    ) -> Tuple[str, tuple]:
        """Format a JSON property removal using JSON_MODIFY (single path only).

        SQL Server removes a property by setting it to NULL with JSON_MODIFY.
        """
        if paths:
            raise UnsupportedFeatureError(
                self.name,
                "JSON_REMOVE with multiple paths",
                "SQL Server's JSON_MODIFY accepts a single path.",
            )
        placeholder = self.get_parameter_placeholder()
        return f"JSON_MODIFY({json_doc}, {placeholder}, NULL)", (path,)

    def format_json_type(self, json_val: str) -> Tuple[str, tuple]:
        """Format JSON_TYPE - not supported by SQL Server."""
        raise UnsupportedFeatureError(
            self.name,
            "JSON_TYPE",
            "SQL Server has no JSON_TYPE; classify values via OPENJSON.",
        )

    def format_json_valid(self, json_val: str) -> Tuple[str, tuple]:
        """Format an ISJSON function (SQL Server equivalent of JSON_VALID)."""
        return f"ISJSON({json_val})", ()

    def format_json_search(
        self, json_doc: str, search_str: str, path: Optional[str] = None, all_: bool = False
    ) -> Tuple[str, tuple]:
        """Format JSON_SEARCH - not supported by SQL Server."""
        raise UnsupportedFeatureError(
            self.name,
            "JSON_SEARCH",
            "SQL Server has no JSON_SEARCH; use OPENJSON with a LIKE predicate.",
        )

    # ========== SET Type Support ==========

    def supports_set_type(self) -> bool:
        """SQL Server has no MySQL-style SET column type."""
        return False

    def format_set_literal(
        self, values: List[str], column_values: Optional[List[str]] = None
    ) -> Tuple[str, tuple]:
        """Format a comma-separated value as a bind parameter.

        SQL Server stores comma-separated values in VARCHAR columns; the
        literal is passed as a single parameter.
        """
        if len(values) > 64:
            raise ValueError("SQL Server SET approximation supports maximum 64 members")

        if column_values is not None:
            invalid_values = [v for v in values if v not in column_values]
            if invalid_values:
                raise ValueError(
                    f"Invalid SET values: {invalid_values}. Allowed values: {column_values}"
                )

        if not values:
            return self.get_parameter_placeholder(), ("",)

        sorted_values = sorted(values)
        return self.get_parameter_placeholder(), (",".join(sorted_values),)

    def format_find_in_set(self, value: str, set_column: str) -> Tuple[str, tuple]:
        """Format a comma-separated membership check.

        SQL Server has no FIND_IN_SET; membership is checked with a LIKE
        predicate over the comma-delimited column value.
        """
        placeholder = self.get_parameter_placeholder()
        col_sql = self.format_identifier(set_column)
        return f"(',' + {col_sql} + ',' LIKE '%,' + {placeholder} + ',%')", (value,)

    def format_set_contains(self, column: str, values: List[str]) -> Tuple[str, tuple]:
        """Format a set-containment predicate as AND-ed membership checks."""
        conditions = []
        params: List[str] = []
        for value in values:
            condition, value_params = self.format_find_in_set(value, column)
            conditions.append(condition)
            params.extend(value_params)
        return " AND ".join(conditions), tuple(params)

    # ========== Spatial Type Support ==========

    _SPATIAL_TYPES = {
        "GEOMETRY",
        "GEOGRAPHY",
        "POINT",
        "LINESTRING",
        "POLYGON",
        "MULTIPOINT",
        "MULTILINESTRING",
        "MULTIPOLYGON",
        "GEOMETRYCOLLECTION",
    }

    def supports_spatial_type(self, type_name: str) -> bool:
        """SQL Server supports geometry/geography since 2008 (10.0)."""
        return self.version >= (10, 0, 0) and type_name.upper() in self._SPATIAL_TYPES

    def supports_spatial_index(self) -> bool:
        """SQL Server supports spatial indexes since 2008 (10.0)."""
        return self.version >= (10, 0, 0)

    def supports_geojson(self) -> bool:
        """STAsGeoJSON is not available in the installed SQL Server types assembly."""
        return False

    def format_spatial_literal(
        self, wkt: str, srid: Optional[int] = None
    ) -> Tuple[str, tuple]:
        """Format a WKT literal using geometry::STGeomFromText."""
        return self.format_st_geom_from_text(wkt, srid)

    def format_st_geom_from_text(
        self, wkt: str, srid: Optional[int] = None
    ) -> Tuple[str, tuple]:
        """Format a geometry::STGeomFromText call.

        SQL Server requires the SRID argument; it defaults to 0.

        SQL Syntax:
            geometry::STGeomFromText(?, ?)
        """
        placeholder = self.get_parameter_placeholder()
        if srid is None:
            srid = 0
        return f"geometry::STGeomFromText({placeholder}, {placeholder})", (wkt, srid)

    def format_st_as_text(self, geom: str) -> Tuple[str, tuple]:
        """Format a geometry STAsText method call: ``geom.STAsText()``."""
        return f"{geom}.STAsText()", ()

    def format_st_as_geojson(self, geom: str) -> Tuple[str, tuple]:
        """Format a geometry STAsGeoJSON method call: ``geom.STAsGeoJSON()``."""
        return f"{geom}.STAsGeoJSON()", ()

    def format_st_distance(self, geom1: str, geom2: str) -> Tuple[str, tuple]:
        """Format a geometry STDistance method call: ``g1.STDistance(g2)``."""
        return f"{geom1}.STDistance({geom2})", ()

    def format_st_within(self, geom1: str, geom2: str) -> Tuple[str, tuple]:
        """Format a geometry STWithin method call: ``g1.STWithin(g2)``."""
        return f"{geom1}.STWithin({geom2})", ()

    def format_st_contains(self, geom1: str, geom2: str) -> Tuple[str, tuple]:
        """Format a geometry STContains method call: ``g1.STContains(g2)``."""
        return f"{geom1}.STContains({geom2})", ()

    def format_st_distance_sphere(self, geom1: str, geom2: str) -> Tuple[str, tuple]:
        """Format a spherical distance check.

        SQL Server has no ST_Distance_Sphere; STDistance is used for the
        planar distance between the two geometries.
        """
        return f"{geom1}.STDistance({geom2})", ()

    def format_st_intersects(self, geom1: str, geom2: str) -> Tuple[str, tuple]:
        """Format a geometry STIntersects method call: ``g1.STIntersects(g2)``."""
        return f"{geom1}.STIntersects({geom2})", ()

    def format_create_spatial_index(
        self, index_name: str, table_name: str, column: str
    ) -> Tuple[str, tuple]:
        """Format a CREATE SPATIAL INDEX statement.

        SQL Syntax:
            CREATE SPATIAL INDEX idx ON table (column)
            WITH (BOUNDING_BOX = (0, 0, 100, 100))

        A BOUNDING_BOX is required for geometry columns.
        """
        self.check_feature_support(
            "supports_spatial_index",
            "spatial indexes",
            "requires SQL Server 2008+.",
        )
        sql = (
            f"CREATE SPATIAL INDEX {self.format_identifier(index_name)} "
            f"ON {self.format_identifier(table_name)} ({self.format_identifier(column)}) "
            f"WITH (BOUNDING_BOX = (0, 0, 100, 100))"
        )
        return sql, ()
