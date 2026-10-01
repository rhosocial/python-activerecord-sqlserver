# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_cross_schema.py
"""SQL Server cross-schema behaviour, asserted against this dialect only.

Kept in this repository rather than the shared testsuite because schema
qualification is dialect-specific. On SQL Server a schema is a namespace
*inside* the database, created with ``CREATE SCHEMA`` and referenced with
``[schema].[table]``; Oracle treats the schema as the user, BigQuery
qualifies by dataset and never qualifies a column, PostgreSQL allows a
three-part reference for an unaliased range. A shared contract would have to
assert the lowest common denominator.

Two things make SQL Server worth its own file. The namespace is independent
of the login -- ``sa`` creates ``[ar_crm]`` and still reads ``dbo`` by
default, so isolation has to come from the rendered reference rather than
from who is connected. And the bracketed form is not cosmetic: an unquoted
``ar_crm.ar_soft_orders`` is a three-part reference, which SQL Server
rejects outright.
"""
import re

from typing import ClassVar, Optional

import pytest

from rhosocial.activerecord.base.field_proxy import FieldProxy
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType
from rhosocial.activerecord.field.soft_delete import (
    DefaultAsyncSoftDeleteMixin,
    DefaultSoftDeleteMixin,
)
from rhosocial.activerecord.model import ActiveRecord, AsyncActiveRecord

from providers.scenarios import get_enabled_scenarios, get_scenario

# Every test in this module shares the [ar_crm] / [ar_shop] schemas and tears
# them down afterwards, so the whole module has to land on a single xdist
# worker; --dist=loadgroup honours this mark.
pytestmark = pytest.mark.xdist_group("sqlserver_cross_schema")

SCHEMA_CRM = "ar_crm"
SCHEMA_SHOP = "ar_shop"
SOFT_TABLE = "ar_soft_orders"
CUSTOMER_TABLE = "ar_customers"


def _ddl_options() -> ExecutionOptions:
    return ExecutionOptions(stmt_type=StatementType.DDL)


def _provision_statements() -> list:
    """Create both schemas and the tables the models bind to.

    The soft-order table is created twice under one name -- once in the
    default ``dbo`` schema and once in ``[ar_crm]`` -- because that collision
    is the whole point: it is what a namespace-scoped bug corrupts.
    """
    soft_columns = (
        "id INT NOT NULL PRIMARY KEY, "
        "label NVARCHAR(100) NOT NULL, "
        "deleted_at DATETIME2 NULL"
    )
    # CREATE SCHEMA has to be the first statement in a batch, so the guarded
    # form has to go through EXEC -- a bare `IF ... CREATE SCHEMA` is a syntax
    # error near the keyword SCHEMA.
    statements = [
        f"IF SCHEMA_ID('{SCHEMA_CRM}') IS NULL EXEC('CREATE SCHEMA [{SCHEMA_CRM}]')",
        f"IF SCHEMA_ID('{SCHEMA_SHOP}') IS NULL EXEC('CREATE SCHEMA [{SCHEMA_SHOP}]')",
    ]
    for schema in (None, SCHEMA_CRM):
        prefix = f"[{schema}]." if schema else ""
        statements.append(f"DROP TABLE IF EXISTS {prefix}[{SOFT_TABLE}]")
        statements.append(f"CREATE TABLE {prefix}[{SOFT_TABLE}] ({soft_columns})")
    statements.append(f"DROP TABLE IF EXISTS [{SCHEMA_CRM}].[{CUSTOMER_TABLE}]")
    statements.append(
        f"CREATE TABLE [{SCHEMA_CRM}].[{CUSTOMER_TABLE}] ("
        "id INT NOT NULL PRIMARY KEY, name NVARCHAR(100) NOT NULL)"
    )
    return statements


def _drop_statements() -> list:
    statements = [
        f"DROP TABLE IF EXISTS [{SCHEMA_CRM}].[{CUSTOMER_TABLE}]",
        f"DROP TABLE IF EXISTS [{SCHEMA_CRM}].[{SOFT_TABLE}]",
        f"DROP TABLE IF EXISTS [{SOFT_TABLE}]",
    ]
    for schema in (SCHEMA_CRM, SCHEMA_SHOP):
        statements.append(f"DROP SCHEMA IF EXISTS [{schema}]")
    return statements


def _run(backend, statements) -> None:
    for sql in statements:
        backend.execute(sql, options=_ddl_options())


def _bind(model, config, backend_class, backend) -> None:
    model.__connection_config__ = config
    model.__backend_class__ = backend_class
    model.__backend__ = backend


class PlainSoftOrder(DefaultSoftDeleteMixin, ActiveRecord):
    """Soft-delete model in the default (``dbo``) schema."""

    __table_name__ = SOFT_TABLE
    __pk_auto_generated__ = False
    c: ClassVar[FieldProxy] = FieldProxy()

    id: Optional[int] = None
    label: str


class CrmSoftOrder(DefaultSoftDeleteMixin, ActiveRecord):
    """Identical table and identical model, bound to ``[ar_crm]``."""

    __table_name__ = SOFT_TABLE
    __schema_name__ = SCHEMA_CRM
    __pk_auto_generated__ = False
    c: ClassVar[FieldProxy] = FieldProxy()

    id: Optional[int] = None
    label: str


class CrmCustomer(ActiveRecord):
    __table_name__ = CUSTOMER_TABLE
    __schema_name__ = SCHEMA_CRM
    __pk_auto_generated__ = False
    c: ClassVar[FieldProxy] = FieldProxy()

    id: Optional[int] = None
    name: str


class ShopOrder(ActiveRecord):
    """A third namespace, so a join can cross a schema boundary."""

    __table_name__ = SOFT_TABLE
    __schema_name__ = SCHEMA_SHOP
    __pk_auto_generated__ = False
    c: ClassVar[FieldProxy] = FieldProxy()

    id: Optional[int] = None
    label: str


class AsyncCrmSoftOrder(DefaultAsyncSoftDeleteMixin, AsyncActiveRecord):
    __table_name__ = SOFT_TABLE
    __schema_name__ = SCHEMA_CRM
    __pk_auto_generated__ = False
    c: ClassVar[FieldProxy] = FieldProxy()

    id: Optional[int] = None
    label: str


class AsyncPlainSoftOrder(DefaultAsyncSoftDeleteMixin, AsyncActiveRecord):
    __table_name__ = SOFT_TABLE
    __pk_auto_generated__ = False
    c: ClassVar[FieldProxy] = FieldProxy()

    id: Optional[int] = None
    label: str


@pytest.fixture(scope="module")
def cross_schema():
    """Provision both schemas on whichever scenario this job registered."""
    scenarios = get_enabled_scenarios()
    if not scenarios:
        pytest.skip("no SQL Server scenario registered for this job")
    backend_class, config = get_scenario(next(iter(scenarios)))
    backend = backend_class(connection_config=config)
    backend.connect()
    _run(backend, _provision_statements())
    for model in (
        PlainSoftOrder,
        CrmSoftOrder,
        CrmCustomer,
        ShopOrder,
        AsyncCrmSoftOrder,
        AsyncPlainSoftOrder,
    ):
        _bind(model, config, backend_class, backend)
    yield backend
    _run(backend, _drop_statements())
    backend.disconnect()


def _norm(sql: str) -> str:
    """Fold case and runs of whitespace, but keep the brackets.

    The brackets are the assertion: on SQL Server ``ar_crm.ar_orders`` is a
    three-part reference and the server rejects it, so a test that stripped
    the quoting would pass on a query that cannot run.
    """
    return re.sub(r"\s+", " ", sql).lower()


def test_range_is_bracket_qualified_but_columns_stay_two_part(cross_schema):
    """The namespace belongs on the range only.

    ``[ar_crm].[ar_soft_orders].[label]`` is a three-part column reference,
    which SQL Server does not accept -- a table has one schema, and the range
    already carries it.
    """
    sql, _ = CrmSoftOrder.query().select(CrmSoftOrder.c.label).to_sql()
    normed = _norm(sql)

    assert "from [ar_crm].[ar_soft_orders]" in normed, (
        f"Expected a bracketed qualified range, got: {sql}"
    )
    assert "[ar_crm].[ar_soft_orders].[label]" not in normed, (
        f"Column reference must not repeat the schema, got: {sql}"
    )
    assert "[ar_soft_orders].[label]" in normed, (
        f"Expected a two-part column reference, got: {sql}"
    )


def test_same_named_tables_coexist_and_pk_is_namespace_scoped(cross_schema):
    """One table name, two schemas, identical primary keys."""
    CrmSoftOrder(id=1, label="crm-row").save()
    PlainSoftOrder(id=1, label="dbo-row").save()

    assert CrmSoftOrder.query().where(CrmSoftOrder.c.id == 1).one().label == "crm-row"
    assert PlainSoftOrder.query().where(PlainSoftOrder.c.id == 1).one().label == "dbo-row"

    CrmSoftOrder.query().where(CrmSoftOrder.c.id == 1).delete_all()
    assert CrmSoftOrder.query().count() == 0
    assert PlainSoftOrder.query().count() == 1, (
        "deleting in [ar_crm] must not remove the identically keyed dbo row"
    )


def test_restore_writes_only_into_its_own_namespace(cross_schema):
    """``restore()`` has to carry the schema down to the UPDATE.

    An unqualified UPDATE resolves to the default schema, so it would clear
    ``deleted_at`` on the dbo row of the same primary key and leave the
    ``[ar_crm]`` row soft-deleted -- a silent cross-namespace write that no
    read-only assertion would catch.
    """
    scoped = CrmSoftOrder(id=7, label="scoped")
    plain = PlainSoftOrder(id=7, label="plain")
    scoped.save()
    plain.save()

    scoped.soft_delete()
    assert CrmSoftOrder.query_only_deleted().count() == 1
    assert PlainSoftOrder.query_only_deleted().count() == 0

    assert scoped.restore() == 1

    assert CrmSoftOrder.query().where(CrmSoftOrder.c.id == 7).count() == 1, (
        "restore() must clear deleted_at inside [ar_crm]"
    )
    assert plain.deleted_at is None, (
        "the default-schema row was never soft-deleted and must stay untouched"
    )
    assert PlainSoftOrder.query_only_deleted().count() == 0


def test_bulk_update_stays_inside_its_namespace(cross_schema):
    """A predicate on a schema-bound model must not widen to the sibling."""
    CrmSoftOrder(id=21, label="a").save()
    CrmSoftOrder(id=22, label="b").save()
    PlainSoftOrder(id=21, label="a").save()

    CrmSoftOrder.query().where(CrmSoftOrder.c.label == "a").update_all({"label": "z"})

    assert CrmSoftOrder.query().where(CrmSoftOrder.c.label == "z").count() == 1
    assert PlainSoftOrder.query().where(PlainSoftOrder.c.label == "a").count() == 1, (
        "bulk update leaked into the default schema"
    )


def test_join_across_two_namespaces(cross_schema):
    """``[ar_crm]`` joined to ``[ar_shop]``, both sides fully qualified."""
    CrmSoftOrder(id=31, label="from-crm").save()
    ShopOrder(id=31, label="from-shop").save()

    joined = CrmSoftOrder.query().join(ShopOrder, on=CrmSoftOrder.c.id == ShopOrder.c.id)
    assert joined.count() == 1, "Expected the join to match across both schemas"

    joined_sql, _ = joined.select(CrmSoftOrder.c.label).to_sql()
    normed = _norm(joined_sql)
    assert "[ar_crm].[ar_soft_orders]" in normed, f"Got: {joined_sql}"
    assert "[ar_shop].[ar_soft_orders]" in normed, (
        f"Expected the joined range to keep its own schema, got: {joined_sql}"
    )


def test_explain_against_a_qualified_range(cross_schema):
    """EXPLAIN has to resolve the range too, or it plans the wrong table."""
    CrmSoftOrder(id=51, label="explained").save()

    rows = CrmSoftOrder.query().explain().aggregate()
    assert isinstance(rows, list), (
        "EXPLAIN over a schema-bound model must return a plan; a range that "
        f"lost its schema would plan or fail against the wrong table (rows={rows!r})"
    )


@pytest.mark.asyncio
async def test_async_restore_writes_only_into_its_own_namespace(cross_schema):
    """Async mirror of the restore contract."""
    from rhosocial.activerecord.backend.impl.sqlserver.backend.async_backend import (
        AsyncSQLServerBackend,
    )

    scenarios = get_enabled_scenarios()
    backend_class, config = get_scenario(next(iter(scenarios)))
    backend = AsyncSQLServerBackend(connection_config=config)
    await backend.connect()
    try:
        for model in (AsyncCrmSoftOrder, AsyncPlainSoftOrder):
            _bind(model, config, AsyncSQLServerBackend, backend)

        scoped = AsyncCrmSoftOrder(id=41, label="scoped")
        plain = AsyncPlainSoftOrder(id=41, label="plain")
        await scoped.save()
        await plain.save()

        await scoped.soft_delete()
        assert await AsyncCrmSoftOrder.query_only_deleted().count() == 1
        assert await AsyncPlainSoftOrder.query_only_deleted().count() == 0

        assert await scoped.restore() == 1
        assert await AsyncCrmSoftOrder.query().where(
            AsyncCrmSoftOrder.c.id == 41
        ).count() == 1, "async restore() must clear deleted_at inside [ar_crm]"
        assert await AsyncPlainSoftOrder.query_only_deleted().count() == 0
    finally:
        try:
            await backend.disconnect()
        except Exception:
            pass
