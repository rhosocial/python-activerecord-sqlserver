# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_introspection_backend_specific.py
"""Live tests for the questions core has no shape for.

Core's introspector models what every backend has (databases, tables,
columns, indexes, foreign keys, views, triggers) and the shared suites cover
those. SQL Server's catalogue answers four more questions -- which schemas
exist and who owns them, which extended properties (``MS_Description`` and
friends) an object carries, which stored procedures and functions live in a
schema, and which sequences are declared -- and those answers get their own
methods and types here rather than ``extra`` dictionaries.

The offline builder tests assert the SQL; this asserts what the server
answers through it, on the first scenario only, around probe objects
``introspection_probe`` installs. Sync and async run the very same
assertions: the two managers answer with the same SQL, the same parsers and
the same cache keys.
"""

import pytest
from decimal import Decimal

from tests.rhosocial.activerecord_sqlserver_test.feature.backend.introspection_probe import (
    PROBE_DESCRIPTION,
    PROBE_FUNCTION,
    PROBE_PROCEDURE,
    PROBE_SEQUENCE,
    create_probe_objects,
    create_probe_objects_async,
    drop_probe_objects,
    drop_probe_objects_async,
    probe_object_id,
    probe_object_id_async,
)


@pytest.fixture
def probed_backend(sqlserver_backend_single):
    create_probe_objects(sqlserver_backend_single)
    yield sqlserver_backend_single
    drop_probe_objects(sqlserver_backend_single)


@pytest.fixture
async def probed_async_backend(async_sqlserver_backend_single):
    await create_probe_objects_async(async_sqlserver_backend_single)
    yield async_sqlserver_backend_single
    await drop_probe_objects_async(async_sqlserver_backend_single)


def assert_schemas(schemas):
    """``dbo`` is there, with the id and principal the catalogue reports."""
    dbo = [s for s in schemas if s.name == "dbo"]
    assert dbo, [s.name for s in schemas]
    dbo = dbo[0]
    assert dbo.schema_id == 1
    assert dbo.owner == "dbo"
    # Every row carries its own id. The order is the server collation's, which
    # is not Python's code-point order (``db_*`` sorts before
    # ``INFORMATION_SCHEMA`` there), so only presence is asserted.
    assert all(isinstance(s.schema_id, int) for s in schemas)


def assert_procedures(procedures):
    found = [p for p in procedures if p.name == PROBE_PROCEDURE]
    assert found, [p.name for p in procedures]
    proc = found[0]
    assert proc.schema == "dbo"
    assert proc.type_code == "P"
    assert "PROCEDURE" in proc.type_desc.upper()
    assert proc.is_ms_shipped is False
    assert proc.created_at is not None and proc.modified_at is not None


def assert_functions(functions):
    found = [f for f in functions if f.name == PROBE_FUNCTION]
    assert found, [f.name for f in functions]
    fn = found[0]
    assert fn.schema == "dbo"
    assert fn.type_code == "FN"
    assert fn.is_ms_shipped is False


def assert_sequences(sequences):
    found = [s for s in sequences if s.name == PROBE_SEQUENCE]
    assert found, [s.name for s in sequences]
    seq = found[0]
    assert seq.schema == "dbo"
    assert seq.data_type == "bigint"
    # Exact numbers, not text the caller must re-parse and not floats that
    # would round a wide sequence's bounds.
    assert seq.start_value == Decimal("5")
    assert seq.increment == Decimal("2")
    assert seq.minimum_value is not None
    assert seq.maximum_value is not None
    assert seq.is_cycling is False


def assert_extended_properties(properties):
    found = [p for p in properties if p.name == "MS_Description"]
    assert found, [(p.name, p.value) for p in properties]
    prop = found[0]
    assert prop.value == PROBE_DESCRIPTION
    # OBJECT_OR_COLUMN is class 1; the probe property sits on the table
    # itself, so the column half of the key is 0.
    assert prop.class_id == 1
    assert prop.class_name == "OBJECT_OR_COLUMN"
    assert prop.major_id > 0
    assert prop.minor_id == 0


class TestSyncBackendSpecific:
    def test_list_schemas(self, probed_backend):
        assert_schemas(probed_backend.introspector.list_schemas())

    def test_list_procedures(self, probed_backend):
        assert_procedures(probed_backend.introspector.list_procedures(schema="dbo"))

    def test_list_functions(self, probed_backend):
        assert_functions(probed_backend.introspector.list_functions(schema="dbo"))

    def test_list_sequences(self, probed_backend):
        assert_sequences(probed_backend.introspector.list_sequences(schema="dbo"))

    def test_list_extended_properties(self, probed_backend):
        object_id = probe_object_id(probed_backend)
        properties = probed_backend.introspector.list_extended_properties(object_id, schema="dbo")
        assert_extended_properties(properties)

    def test_extended_properties_unknown_class_refused(self, probed_backend):
        with pytest.raises(ValueError):
            probed_backend.introspector.list_extended_properties(1, class_name="NOT_A_CLASS")

    def test_extended_properties_schema_only_narrows_objects(self, probed_backend):
        with pytest.raises(ValueError):
            probed_backend.introspector.list_extended_properties(
                1, class_name="DATABASE", schema="dbo"
            )


class TestAsyncBackendSpecific:
    async def test_list_schemas(self, probed_async_backend):
        assert_schemas(await probed_async_backend.introspector.list_schemas())

    async def test_list_procedures(self, probed_async_backend):
        assert_procedures(await probed_async_backend.introspector.list_procedures(schema="dbo"))

    async def test_list_functions(self, probed_async_backend):
        assert_functions(await probed_async_backend.introspector.list_functions(schema="dbo"))

    async def test_list_sequences(self, probed_async_backend):
        assert_sequences(await probed_async_backend.introspector.list_sequences(schema="dbo"))

    async def test_list_extended_properties(self, probed_async_backend):
        object_id = await probe_object_id_async(probed_async_backend)
        properties = await probed_async_backend.introspector.list_extended_properties(
            object_id, schema="dbo"
        )
        assert_extended_properties(properties)
