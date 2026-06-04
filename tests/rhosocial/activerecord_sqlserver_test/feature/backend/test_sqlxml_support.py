# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_sqlxml_support.py
"""Tests for SQL Server SQL/XML standard support boundaries."""

from rhosocial.activerecord.backend.dialect.protocols import SQLXMLSupport
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


class TestSQLServerSQLXMLSupport:
    """Test SQL Server does not claim standard SQL/XML support."""

    def test_sqlserver_does_not_implement_standard_sqlxml_protocol(self):
        """Native XML/XQuery methods are not standard SQL/XML support."""
        dialect = SQLServerDialect((16, 0, 0))

        assert not isinstance(dialect, SQLXMLSupport)

    def test_standard_sqlxml_formatters_are_not_exposed(self):
        """Standard SQL/XML formatters require explicit protocol support."""
        dialect = SQLServerDialect((16, 0, 0))

        assert not hasattr(dialect, "supports_xmlparse")
        assert not hasattr(dialect, "format_xmlparse_expression")
