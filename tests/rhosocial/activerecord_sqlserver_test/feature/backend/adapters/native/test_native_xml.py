# tests/rhosocial/activerecord_sqlserver_test/feature/backend/adapters/native/test_native_xml.py
"""XML: a native XML column carried as text.

SQL Server parses and validates the document on write, and ``CAST(col AS
NVARCHAR(MAX))`` returns exactly what was stored. The adapter never builds an
element tree: ``str`` in, ``str`` out (``dict`` input only at the encode side).
"""
from rhosocial.activerecord.backend.impl.sqlserver.adapters import SQLServerXMLAdapter
from sqlserver_native_models import XmlRow

DOC = "<root><a>1</a><b>中文</b></root>"


def _stored(native_io, row_id=1):
    return native_io.raw("native_xml", "CAST(doc AS NVARCHAR(MAX))", row_id)


def test_column_is_the_native_xml_type(native_table, native_io):
    native_table("native_xml")
    assert native_io.column_type("native_xml", "doc") == "xml"


def test_adapter_semantic_round_trip():
    """S1 without a server: text in, text out; no XML parsing on the read side."""
    adapter = SQLServerXMLAdapter()

    assert adapter.to_database(DOC, str, None) == DOC
    assert adapter.from_database(DOC, str) == DOC

    encoded = adapter.to_database({"a": "1", "b": ["x", "y"]}, str, None)
    assert encoded.startswith("<root>")
    assert "<a>1</a>" in encoded
    assert "<b>x</b><b>y</b>" in encoded


def test_round_trip_s1(native_table, native_model):
    native_table("native_xml")
    model = native_model(XmlRow)

    model(id=1, doc=DOC).save()
    found = model.find_one(1)
    assert found.doc == DOC, "the document must come back verbatim, unicode included"
    assert isinstance(found.doc, str), "XML is carried as text, not as an element tree"


def test_raw_stored_form(native_table, native_io):
    native_table("native_xml")
    native_io.insert("native_xml", {"id": "1", "doc": f"'{DOC}'"})
    assert _stored(native_io) == DOC


def test_stored_form_is_stable_s2(native_table, native_model, native_io):
    native_table("native_xml")
    model = native_model(XmlRow)

    model(id=1, doc=DOC).save()
    read_back = model.find_one(1)
    model(id=2, doc=read_back.doc).save()
    assert _stored(native_io, 1) == _stored(native_io, 2)


def test_foreign_native_value_s3(native_table, native_model, native_io):
    native_table("native_xml")
    model = native_model(XmlRow)

    native_io.insert("native_xml", {"id": "9001", "doc": f"'{DOC}'"})
    foreign = model.find_one(9001)
    assert foreign.doc == DOC

    model(id=9002, doc=foreign.doc).save()
    assert _stored(native_io, 9001) == _stored(native_io, 9002)


def test_dict_input_is_rendered_as_xml(native_table, native_io):
    """The adapter's dict branch produces a document the column accepts."""
    native_table("native_xml")
    adapter = SQLServerXMLAdapter()

    document = adapter.to_database({"order": {"id": 7}}, str, None)
    native_io.insert("native_xml", {"id": "1", "doc": f"'{document}'"})
    assert _stored(native_io) == document
