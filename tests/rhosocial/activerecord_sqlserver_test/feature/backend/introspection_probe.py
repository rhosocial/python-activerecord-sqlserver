# tests/rhosocial/activerecord_sqlserver_test/feature/backend/introspection_probe.py
"""Schema objects the live introspection tests share.

Both the CLI test and the introspector test need a table, a view, a
procedure, a function, a sequence, a trigger, a foreign key and an
``MS_Description`` to point at. Creating them here once keeps the two test
modules from drifting apart, and the names carry the process id so parallel
workers that share a database cannot collide.
"""

import os

from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

_SUFFIX = f"_{os.getpid()}"

PROBE_PARENT = f"zz_introspect_parent{_SUFFIX}"
PROBE_TABLE = f"zz_introspect_probe{_SUFFIX}"
PROBE_VIEW = f"zz_introspect_view{_SUFFIX}"
PROBE_PROCEDURE = f"zz_introspect_proc{_SUFFIX}"
PROBE_FUNCTION = f"zz_introspect_fn{_SUFFIX}"
PROBE_SEQUENCE = f"zz_introspect_seq{_SUFFIX}"
PROBE_TRIGGER = f"zz_introspect_trg{_SUFFIX}"
PROBE_TRIGGER_DISABLED = f"zz_introspect_trg_off{_SUFFIX}"
PROBE_DESCRIPTION = "introspection probe table"

DDL_OPTIONS = ExecutionOptions(stmt_type=StatementType.DDL)


def probe_statements():
    """The statements that install the probe objects, in dependency order."""
    return [
        f"IF OBJECT_ID('dbo.{PROBE_TRIGGER}', 'TR') IS NOT NULL "
        f"DROP TRIGGER dbo.{PROBE_TRIGGER}",
        f"IF OBJECT_ID('dbo.{PROBE_TRIGGER_DISABLED}', 'TR') IS NOT NULL "
        f"DROP TRIGGER dbo.{PROBE_TRIGGER_DISABLED}",
        f"IF OBJECT_ID('dbo.{PROBE_TABLE}', 'U') IS NOT NULL " f"DROP TABLE dbo.{PROBE_TABLE}",
        f"IF OBJECT_ID('dbo.{PROBE_PARENT}', 'U') IS NOT NULL " f"DROP TABLE dbo.{PROBE_PARENT}",
        f"IF OBJECT_ID('dbo.{PROBE_VIEW}', 'V') IS NOT NULL " f"DROP VIEW dbo.{PROBE_VIEW}",
        f"IF OBJECT_ID('dbo.{PROBE_PROCEDURE}', 'P') IS NOT NULL "
        f"DROP PROCEDURE dbo.{PROBE_PROCEDURE}",
        f"IF OBJECT_ID('dbo.{PROBE_FUNCTION}', 'FN') IS NOT NULL "
        f"DROP FUNCTION dbo.{PROBE_FUNCTION}",
        f"IF OBJECT_ID('dbo.{PROBE_SEQUENCE}', 'SO') IS NOT NULL "
        f"DROP SEQUENCE dbo.{PROBE_SEQUENCE}",
        f"CREATE TABLE dbo.{PROBE_PARENT} (id INT NOT NULL PRIMARY KEY)",
        (
            f"CREATE TABLE dbo.{PROBE_TABLE} ("
            "id INT NOT NULL PRIMARY KEY, "
            "label NVARCHAR(20) NULL, "
            "parent_id INT NULL "
            f"CONSTRAINT fk_{PROBE_TABLE} REFERENCES dbo.{PROBE_PARENT}(id))"
        ),
        f"CREATE VIEW dbo.{PROBE_VIEW} AS " f"SELECT id, label FROM dbo.{PROBE_TABLE}",
        f"CREATE PROCEDURE dbo.{PROBE_PROCEDURE} AS SELECT 1 AS one",
        (f"CREATE FUNCTION dbo.{PROBE_FUNCTION}(@x INT) RETURNS INT " "AS BEGIN RETURN @x + 1 END"),
        (f"CREATE SEQUENCE dbo.{PROBE_SEQUENCE} AS BIGINT " "START WITH 5 INCREMENT BY 2"),
        (
            f"CREATE TRIGGER dbo.{PROBE_TRIGGER} ON dbo.{PROBE_TABLE} "
            "AFTER INSERT AS BEGIN SET NOCOUNT ON; END"
        ),
        (
            f"CREATE TRIGGER dbo.{PROBE_TRIGGER_DISABLED} ON dbo.{PROBE_TABLE} "
            "AFTER UPDATE AS BEGIN SET NOCOUNT ON; END"
        ),
        f"DISABLE TRIGGER dbo.{PROBE_TRIGGER_DISABLED} ON dbo.{PROBE_TABLE}",
        (
            "EXEC sys.sp_addextendedproperty "
            "@name=N'MS_Description', "
            f"@value=N'{PROBE_DESCRIPTION}', "
            "@level0type=N'SCHEMA', @level0name=N'dbo', "
            f"@level1type=N'TABLE', @level1name=N'{PROBE_TABLE}'"
        ),
    ]


def teardown_statements():
    """The statements that remove them, children first."""
    return [
        f"IF OBJECT_ID('dbo.{PROBE_TRIGGER}', 'TR') IS NOT NULL "
        f"DROP TRIGGER dbo.{PROBE_TRIGGER}",
        f"IF OBJECT_ID('dbo.{PROBE_TRIGGER_DISABLED}', 'TR') IS NOT NULL "
        f"DROP TRIGGER dbo.{PROBE_TRIGGER_DISABLED}",
        f"IF OBJECT_ID('dbo.{PROBE_VIEW}', 'V') IS NOT NULL " f"DROP VIEW dbo.{PROBE_VIEW}",
        f"IF OBJECT_ID('dbo.{PROBE_PROCEDURE}', 'P') IS NOT NULL "
        f"DROP PROCEDURE dbo.{PROBE_PROCEDURE}",
        f"IF OBJECT_ID('dbo.{PROBE_FUNCTION}', 'FN') IS NOT NULL "
        f"DROP FUNCTION dbo.{PROBE_FUNCTION}",
        f"IF OBJECT_ID('dbo.{PROBE_SEQUENCE}', 'SO') IS NOT NULL "
        f"DROP SEQUENCE dbo.{PROBE_SEQUENCE}",
        f"IF OBJECT_ID('dbo.{PROBE_TABLE}', 'U') IS NOT NULL " f"DROP TABLE dbo.{PROBE_TABLE}",
        f"IF OBJECT_ID('dbo.{PROBE_PARENT}', 'U') IS NOT NULL " f"DROP TABLE dbo.{PROBE_PARENT}",
    ]


def create_probe_objects(backend):
    """Install the probe objects on a synchronous backend."""
    for statement in probe_statements():
        backend.execute(statement, options=DDL_OPTIONS)


async def create_probe_objects_async(backend):
    """Install the probe objects on an asynchronous backend."""
    for statement in probe_statements():
        await backend.execute(statement, options=DDL_OPTIONS)


def drop_probe_objects(backend):
    """Remove the probe objects, ignoring individual failures."""
    for statement in teardown_statements():
        try:
            backend.execute(statement, options=DDL_OPTIONS)
        except Exception:
            pass


async def drop_probe_objects_async(backend):
    """Remove the probe objects, ignoring individual failures."""
    for statement in teardown_statements():
        try:
            await backend.execute(statement, options=DDL_OPTIONS)
        except Exception:
            pass


def probe_object_id(backend):
    """The ``object_id`` of the probe table, for extended-property lookups."""
    result = backend.execute("SELECT OBJECT_ID(?) AS oid", (f"dbo.{PROBE_TABLE}",))
    return result.data[0]["oid"]


async def probe_object_id_async(backend):
    """``probe_object_id`` against an asynchronous backend."""
    result = await backend.execute("SELECT OBJECT_ID(?) AS oid", (f"dbo.{PROBE_TABLE}",))
    return result.data[0]["oid"]
