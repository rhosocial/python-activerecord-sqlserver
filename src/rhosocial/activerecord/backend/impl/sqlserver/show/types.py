# src/rhosocial/activerecord/backend/impl/sqlserver/show/types.py
"""
SQL Server SHOW functionality result types.

This module defines result dataclasses for SQL Server metadata queries.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ShowCreateTableResult:
    """Result from a SHOW CREATE TABLE-style query.

    Attributes:
        table_name: Name of the table.
        create_statement: Complete CREATE TABLE statement.
    """

    table_name: str
    create_statement: str


@dataclass
class ShowCreateViewResult:
    """Result from a SHOW CREATE VIEW-style query.

    Attributes:
        view_name: Name of the view.
        create_statement: Complete CREATE VIEW statement.
        character_set_client: Client character set.
        collation_connection: Connection collation.
    """

    view_name: str
    create_statement: str
    character_set_client: Optional[str] = None
    collation_connection: Optional[str] = None


@dataclass
class ShowColumnResult:
    """Result from a SHOW COLUMNS-style query.

    Attributes:
        field: Column name.
        type: Column data type.
        null: Whether the column allows NULL ('YES' or 'NO').
        key: Key type.
        default: Default value for the column.
        extra: Additional information.
        privileges: Column privileges (FULL mode only).
        comment: Column comment (FULL mode only).
    """

    field: str
    type: str
    null: str
    key: str
    default: Optional[str] = None
    extra: Optional[str] = None
    privileges: Optional[str] = None
    comment: Optional[str] = None


@dataclass
class ShowIndexResult:
    """Result from a SHOW INDEX-style query.

    Attributes:
        table: Table name.
        non_unique: 1 if index allows duplicates, 0 if unique.
        key_name: Index name.
        seq_in_index: Column sequence number in index.
        column_name: Column name.
        collation: Column sort order.
        cardinality: Estimated number of unique values.
        sub_part: Index prefix length.
        packed: How the key is packed.
        null: Whether the column allows NULL.
        index_type: Index type.
        comment: Index comment.
        index_comment: Index comment.
        visible: Whether index is visible to optimizer.
        expression: Expression for functional index.
    """

    table: str
    non_unique: int
    key_name: str
    seq_in_index: int
    column_name: Optional[str] = None
    collation: Optional[str] = None
    cardinality: Optional[int] = None
    sub_part: Optional[int] = None
    packed: Optional[str] = None
    null: Optional[str] = None
    index_type: str = "BTREE"
    comment: Optional[str] = None
    index_comment: Optional[str] = None
    visible: Optional[str] = None
    expression: Optional[str] = None


@dataclass
class ShowTableResult:
    """Result from a SHOW TABLES-style query.

    Attributes:
        name: Table name.
        table_type: Table type (BASE TABLE or VIEW).
    """

    name: str
    table_type: Optional[str] = None


@dataclass
class ShowDatabaseResult:
    """Result from a SHOW DATABASES-style query.

    Attributes:
        name: Database name.
    """

    name: str


@dataclass
class ShowTriggerResult:
    """Result from a SHOW TRIGGERS-style query.

    Attributes:
        trigger: Trigger name.
        event: Trigger event (INSERT, UPDATE, DELETE).
        table: Table name.
        statement: Trigger body.
        timing: Trigger timing.
        created: Creation time.
        sql_mode: SQL mode during creation.
        definer: Definer of the trigger.
        character_set_client: Client character set.
        collation_connection: Connection collation.
        database_collation: Database collation.
    """

    trigger: str
    event: str
    table: str
    statement: str
    timing: str
    created: Optional[str] = None
    sql_mode: Optional[str] = None
    definer: Optional[str] = None
    character_set_client: Optional[str] = None
    collation_connection: Optional[str] = None
    database_collation: Optional[str] = None


@dataclass
class ShowVariableResult:
    """Result from a SHOW VARIABLES-style query.

    Attributes:
        variable_name: Variable name.
        value: Variable value.
    """

    variable_name: str
    value: str


@dataclass
class ShowStatusResult:
    """Result from a SHOW STATUS-style query.

    Attributes:
        variable_name: Status variable name.
        value: Status value.
    """

    variable_name: str
    value: str
