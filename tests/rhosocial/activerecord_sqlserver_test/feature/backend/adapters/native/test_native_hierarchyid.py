# tests/rhosocial/activerecord_sqlserver_test/feature/backend/adapters/native/test_native_hierarchyid.py
"""HIERARCHYID: the CLR type holding a materialised path.

The write path works with plain text (``'/1/2/'`` is an accepted parameter for
the column). The read path does not: pyodbc 5.5.0 rejects ODBC type ``-151``
(``SQL_SS_UDT``), so a native ``SELECT hid`` cannot deliver a value at all.
``hid.ToString()`` is therefore both the stored-form assertion and the text the
adapter decodes.

This is also the test that pins the adapter's registration: the class existed
but the backend never registered it, so nothing could reach it.
"""
import pytest

from rhosocial.activerecord.backend.impl.sqlserver.adapters import SQLServerHierarchyIdAdapter
from sqlserver_native_models import HierarchyIdRow

PATH = "/1/2/"
ROOT = "/"


def _stored(native_io, row_id=1):
    return native_io.raw("native_hierarchyid", "hid.ToString()", row_id)


def test_adapter_is_in_the_backend_inventory(sqlserver_backend):
    """The registered inventory carries the hierarchyid adapter."""
    assert SQLServerHierarchyIdAdapter in {type(adapter) for adapter in sqlserver_backend.get_type_adapters()}


def test_model_declares_the_hierarchyid_adapter(native_model):
    model = native_model(HierarchyIdRow)
    adapter, target = model.get_field_type_adapters()["hid"]
    assert isinstance(adapter, SQLServerHierarchyIdAdapter)
    assert target is str


def test_adapter_semantic_round_trip():
    """S1 without a server: text in, text out; a list renders a path."""
    adapter = SQLServerHierarchyIdAdapter()

    assert adapter.to_database(PATH, str, None) == PATH
    assert adapter.to_database([1, 2], str, None) == PATH
    assert adapter.from_database(PATH, str) == PATH


def test_round_trip_s1(native_table, native_model, native_io):
    """S1 on the server: the write path works, the stored form is the path."""
    native_table("native_hierarchyid")
    model = native_model(HierarchyIdRow)

    model(id=1, hid=PATH).save()
    assert _stored(native_io) == PATH
    assert native_io.raw("native_hierarchyid", "hid.GetLevel()") == 2


def test_stored_form_is_stable_s2(native_table, native_model, native_io):
    native_table("native_hierarchyid")
    model = native_model(HierarchyIdRow)

    model(id=1, hid=PATH).save()
    read_back = SQLServerHierarchyIdAdapter().from_database(_stored(native_io), str)
    model(id=2, hid=read_back).save()
    assert _stored(native_io, 1) == _stored(native_io, 2)


def test_foreign_native_value_s3(native_table, native_model, native_io):
    """A literal the server wrote itself decodes and re-writes unchanged."""
    native_table("native_hierarchyid")
    model = native_model(HierarchyIdRow)

    native_io.insert("native_hierarchyid", {"id": "9001", "hid": "hierarchyid::Parse('/1/2/')"})
    foreign = SQLServerHierarchyIdAdapter().from_database(_stored(native_io, 9001), str)
    assert foreign == PATH

    model(id=9002, hid=foreign).save()
    assert _stored(native_io, 9002) == _stored(native_io, 9001)


def test_root_is_a_value(native_table, native_io):
    native_table("native_hierarchyid")
    native_io.insert("native_hierarchyid", {"id": "1", "hid": "hierarchyid::GetRoot()"})
    assert _stored(native_io) == ROOT
    assert SQLServerHierarchyIdAdapter().from_database(ROOT, str) == ROOT


@pytest.mark.xfail(
    strict=True,
    reason=(
        "A native HIERARCHYID column cannot be read through the ORM: pyodbc 5.5.0 "
        "rejects ODBC type -151 (SQL_SS_UDT), so 'SELECT hid' fails before any "
        "adapter runs. Reading needs a server-side projection such as "
        "hid.ToString(), which the execution layer does not offer for model "
        "columns (testing plan §4.7, §7.3)."
    ),
)
def test_orm_read_returns_the_path(native_table, native_model):
    native_table("native_hierarchyid")
    model = native_model(HierarchyIdRow)

    model(id=1, hid=PATH).save()
    assert model.find_one(1).hid == PATH
