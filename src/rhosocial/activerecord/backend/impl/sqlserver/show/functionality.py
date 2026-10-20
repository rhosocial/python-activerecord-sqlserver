# src/rhosocial/activerecord/backend/impl/sqlserver/show/functionality.py
"""
SQL Server SHOW compatibility layer.

SQL Server has no ``SHOW ...`` statements, so this module carries only the
*inbound* half of the MySQL vocabulary: it parses result sets whose column
names follow MySQL's SHOW spellings into the typed result dataclasses the
shared ``show()`` API returns, so a caller written against MySQL's vocabulary
can read SQL Server's catalogue.

It deliberately builds no SQL. The catalogue questions live in
``..query_nodes`` as expression nodes and are rendered by the dialect (org
guide §16.2), because a query written here would be a second place where
SQL Server's SQL is spelled, and a catalogue read written as text is exactly
what this wave removes. The translation this layer does own is the row shape:
MySQL names a result column ``Field``, SQL Server's catalogue names the same
value ``COLUMN_NAME``, and every parser below accepts either.
"""

from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..backend import SQLServerBackend


class SQLServerShowFunctionality:
    """Parses SHOW-shaped result sets into typed dataclasses.

    MySQL-compatible row names and SQL Server catalogue row names are both
    accepted, so the same parser reads either source. Supports version-aware
    feature detection.
    """

    def __init__(self, backend: "SQLServerBackend", version: Optional[Tuple[int, ...]] = None):
        """Initialize SQL Server SHOW functionality.

        Args:
            backend: SQLServerBackend instance for executing queries.
            version: SQL Server version tuple, e.g., (16, 0, 0) for SQL Server 2022.
        """
        self._backend = backend
        self._version = version
        self.dialect = getattr(backend, "dialect", None)
        self._supports_invisible_columns = version >= (8, 0, 0) if version else True

    # ========== Parsing Helper Methods ==========

    def _parse_create_table_result(self, result, table_name: str):
        """Parse a table definition result."""
        from .types import ShowCreateTableResult

        if not result.data or len(result.data) == 0:
            return None

        row = result.data[0]
        return ShowCreateTableResult(
            table_name=row.get("Table", row.get("TABLE", table_name)),
            create_statement=row.get("Create Table", row.get("CREATE TABLE", "")),
        )

    def _parse_create_view_result(self, result, view_name: str):
        """Parse a view definition result."""
        from .types import ShowCreateViewResult

        if not result.data or len(result.data) == 0:
            return None

        row = result.data[0]
        return ShowCreateViewResult(
            view_name=row.get("View", row.get("VIEW", view_name)),
            create_statement=row.get("Create View", row.get("CREATE VIEW", "")),
            character_set_client=row.get("character_set_client"),
            collation_connection=row.get("collation_connection"),
        )

    def _parse_columns_result(self, result):
        """Parse a columns result."""
        from .types import ShowColumnResult

        columns = []
        for row in result.data:
            col = ShowColumnResult(
                field=row.get("Field", row.get("COLUMN_NAME")),
                type=row.get("Type", row.get("COLUMN_TYPE")),
                null=row.get("Null", row.get("IS_NULLABLE")),
                key=row.get("Key", row.get("COLUMN_KEY")),
                default=row.get("Default", row.get("COLUMN_DEFAULT")),
                extra=row.get("Extra", row.get("EXTRA")),
            )
            if "Collation" in row or "Privileges" in row:
                col.privileges = row.get("Privileges")
                col.comment = row.get("Comment")
            columns.append(col)
        return columns

    def _parse_indexes_result(self, result):
        """Parse an indexes result."""
        from .types import ShowIndexResult

        indexes = []
        for row in result.data:
            indexes.append(
                ShowIndexResult(
                    table=row.get("Table", row.get("TABLE_NAME")),
                    non_unique=row.get("Non_unique", row.get("NON_UNIQUE")),
                    key_name=row.get("Key_name", row.get("INDEX_NAME")),
                    seq_in_index=row.get("Seq_in_index", row.get("SEQ_IN_INDEX")),
                    column_name=row.get("Column_name", row.get("COLUMN_NAME")),
                    collation=row.get("Collation", row.get("COLLATION")),
                    cardinality=row.get("Cardinality", row.get("CARDINALITY")),
                    sub_part=row.get("Sub_part", row.get("SUB_PART")),
                    packed=row.get("Packed", row.get("PACKED")),
                    null=row.get("Null", row.get("NULLABLE")),
                    index_type=row.get("Index_type") or row.get("INDEX_TYPE") or "BTREE",
                    comment=row.get("Comment", row.get("INDEX_COMMENT")),
                    index_comment=row.get("Index_comment", row.get("INDEX_COMMENT")),
                    visible=row.get("Visible", row.get("IS_VISIBLE")),
                    expression=row.get("Expression", row.get("EXPRESSION")),
                )
            )
        return indexes

    def _parse_tables_result(self, result):
        """Parse a tables result."""
        from .types import ShowTableResult

        tables = []
        for row in result.data:
            if len(row) == 1:
                tables.append(ShowTableResult(name=list(row.values())[0], table_type=None))
            else:
                name_key = next((k for k in row.keys() if k.startswith("Tables_in_")), None)
                if name_key:
                    tables.append(ShowTableResult(name=row[name_key], table_type=row.get("Table_type")))
        return tables

    def _parse_databases_result(self, result):
        """Parse a databases result."""
        from .types import ShowDatabaseResult

        return [ShowDatabaseResult(name=row.get("Database")) for row in result.data]

    def _parse_triggers_result(self, result):
        """Parse a triggers result."""
        from .types import ShowTriggerResult

        triggers = []
        for row in result.data:
            triggers.append(
                ShowTriggerResult(
                    trigger=row.get("Trigger", row.get("TRIGGER_NAME")),
                    event=row.get("Event", row.get("EVENT_MANIPULATION")),
                    table=row.get("Table", row.get("EVENT_OBJECT_TABLE")),
                    statement=row.get("Statement", row.get("ACTION_STATEMENT")),
                    timing=row.get("Timing", row.get("ACTION_TIMING")),
                    created=row.get("Created"),
                    sql_mode=row.get("sql_mode"),
                    definer=row.get("Definer"),
                    character_set_client=row.get("character_set_client"),
                    collation_connection=row.get("collation_connection"),
                    database_collation=row.get("Database Collation"),
                )
            )
        return triggers

    def _parse_variables_result(self, result):
        """Parse a variables result."""
        from .types import ShowVariableResult

        return [
            ShowVariableResult(
                variable_name=row.get("Variable_name"),
                value=row.get("Value"),
            )
            for row in result.data
        ]

    def _parse_status_result(self, result):
        """Parse a status result."""
        from .types import ShowStatusResult

        return [
            ShowStatusResult(
                variable_name=row.get("Variable_name"),
                value=row.get("Value"),
            )
            for row in result.data
        ]
