# tests/rhosocial/activerecord_sqlserver_test/feature/connection/pool_definitions.py
"""The connection-pool tests' own tables.

The concurrent tests create and drop these tables through the pool itself, so
their DDL belongs here rather than in the conftest or in a test body: a
definition class receives only a ``dialect`` and knows nothing about backends,
databases, connection pools or execution.

The sync and async test sets each use their own pair of tables, and the only
difference between the two pairs is the column naming the worker
(``thread_id`` for threads, ``task_id`` for asyncio tasks).

Every type here is a core expression type: SQL Server renders ``VarChar`` as
``VARCHAR(n)``, ``Text`` as ``NVARCHAR(MAX)`` and ``TimestampType`` as
``DATETIME2``, and the primary key branch carries the ``IDENTITY(1,1)``
spelling the old hand-written DDL used -- the table set is unchanged, only
its ownership moved.
"""

from rhosocial.activerecord.backend.expression import (
    ColumnConstraint as Constraint,
    ColumnDefinition as Column,
    CreateTableStatement as CreateTable,
    DropTableStatement as DropTable,
    current_timestamp,
)
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefaultConstraint as Default,
    ColumnPrimaryKeyConstraint as PrimaryKey,
)
from rhosocial.activerecord.backend.expression.types import (
    IntegerType as Int,
    TextType as Text,
    TimestampType,
    VarCharType as VarChar,
)
from rhosocial.activerecord.testsuite.fixture_types import supports_drop_if_exists


class Definition:
    """Base class for the pool tests' table definitions."""

    table_name = ""

    def __init__(self, dialect):
        self.dialect = dialect
        self.create_table = CreateTable(
            self.dialect,
            table=Table(self.dialect, self.table_name),
            columns=self.columns(),
        )
        self.drop_table = DropTable(
            self.dialect,
            table=Table(self.dialect, self.table_name),
            if_exists=supports_drop_if_exists(self.dialect),
        )

    def columns(self):
        raise NotImplementedError

    def column(self, name, sql_type, constraints=None):
        return Column(self.dialect, name, sql_type, constraints=constraints or [])

    def auto_pk(self, name="id"):
        return self.column(
            name,
            Int(self.dialect),
            [
                Constraint(
                    self.dialect,
                    branch=PrimaryKey(self.dialect, is_auto_increment=True),
                )
            ],
        )

    def created_at(self, name="created_at"):
        return self.column(
            name,
            TimestampType(self.dialect),
            [
                Constraint(
                    self.dialect,
                    branch=Default(self.dialect, current_timestamp(self.dialect)),
                )
            ],
        )


class ConcurrentTestUsersDefinition(Definition):
    """The synchronized users table."""

    table_name = "concurrent_test_users"

    def columns(self):
        return [
            self.auto_pk(),
            self.column("thread_id", Int(self.dialect)),
            self.column("name", VarChar(self.dialect, 255)),
            self.created_at(),
        ]


class ConcurrentTestPostsDefinition(Definition):
    """The synchronized posts table."""

    table_name = "concurrent_test_posts"

    def columns(self):
        return [
            self.auto_pk(),
            self.column("thread_id", Int(self.dialect)),
            self.column("user_id", Int(self.dialect)),
            self.column("title", VarChar(self.dialect, 255)),
            self.column("content", Text(self.dialect)),
        ]


class AsyncConcurrentTestUsersDefinition(Definition):
    """The asyncio users table."""

    table_name = "concurrent_test_users"

    def columns(self):
        return [
            self.auto_pk(),
            self.column("task_id", Int(self.dialect)),
            self.column("name", VarChar(self.dialect, 255)),
            self.created_at(),
        ]


class AsyncConcurrentTestPostsDefinition(Definition):
    """The asyncio posts table."""

    table_name = "concurrent_test_posts"

    def columns(self):
        return [
            self.auto_pk(),
            self.column("task_id", Int(self.dialect)),
            self.column("user_id", Int(self.dialect)),
            self.column("title", VarChar(self.dialect, 255)),
            self.column("content", Text(self.dialect)),
        ]