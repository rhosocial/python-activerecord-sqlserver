# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_identifier_quoting.py
"""
Tests for SQL Server identifier quoting feature.

This module verifies SQLServerDialect.format_identifier bracket quoting,
reserved word detection, and warning behavior.
"""
import pytest
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.warnings import IdentifierQuotingWarning


class TestSQLServerIdentifierQuoting:
    """Test SQLServerDialect format_identifier and reserved words."""

    def test_format_identifier_default_bracket_quotes(self):
        d = SQLServerDialect()
        assert d.format_identifier("users") == "[users]"

    def test_format_identifier_need_quote_false(self):
        d = SQLServerDialect()
        assert d.format_identifier("users", need_quote=False) == "users"

    def test_format_identifier_escapes_internal_brackets(self):
        d = SQLServerDialect()
        assert d.format_identifier("my]table") == "[my]]table]"

    def test_format_identifier_need_quote_false_no_escaping(self):
        d = SQLServerDialect()
        assert d.format_identifier("my]table", need_quote=False) == "my]table"

    def test_reserved_words_is_frozenset(self):
        d = SQLServerDialect()
        assert isinstance(d.reserved_words, frozenset)

    def test_is_reserved_word_case_insensitive(self):
        d = SQLServerDialect()
        assert d.is_reserved_word("SELECT") is True
        assert d.is_reserved_word("select") is True

    def test_is_reserved_word_non_reserved(self):
        d = SQLServerDialect()
        assert d.is_reserved_word("users") is False

    def test_reserved_word_warning_emitted(self):
        d = SQLServerDialect()
        with pytest.warns(IdentifierQuotingWarning, match="select"):
            d.format_identifier("select", need_quote=False)

    def test_balanced_quotes_security(self):
        d = SQLServerDialect()
        for ident in ["users", "my]table", "a]]b"]:
            result = d.format_identifier(ident)
            assert result.startswith("["), f"Missing opening bracket: {result}"
            assert result.endswith("]"), f"Missing closing bracket: {result}"
            inner = result[1:-1]
            assert "]" not in inner.replace("]]", ""), (
                f"Unescaped bracket in: {result}"
            )
