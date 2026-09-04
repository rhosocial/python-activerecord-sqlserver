# tests/rhosocial/activerecord_sqlserver_test/feature/backend/sqlserver/test_sqlserver_dialect_security.py
"""
Tests for SQL Server dialect SQL injection security.

This module verifies that identifier quoting properly escapes
bracket characters and prevents SQL injection via breakout.
"""
import pytest

from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


@pytest.fixture
def dialect():
    """Create a SQL Server test dialect."""
    return SQLServerDialect(version=(16, 0, 0))


def test_format_identifier_normal(dialect):
    """Normal identifier is bracket-quoted."""
    result = dialect.format_identifier("users")
    assert result == "[users]"


def test_format_identifier_with_bracket(dialect):
    """Identifier with embedded closing bracket is properly escaped."""
    result = dialect.format_identifier("table]name")
    assert result == "[table]]name]"


def test_format_identifier_injection_payload(dialect):
    """Identifier with injection payload is safely contained (brackets escaped)."""
    payload = "users]; DROP TABLE users--"
    result = dialect.format_identifier(payload)
    # One opening bracket and exactly one closing bracket at the end
    assert result.count("[") == 1, f"Should have exactly one opening bracket: {result}"
    assert result.endswith("]"), f"Should end with closing bracket: {result}"
    # The interior ] is escaped as ]], so SQL Server sees the whole thing as one identifier
    assert "]]" in result, f"Should have escaped brackets: {result}"
    assert result == "[users]]; DROP TABLE users--]"


def test_format_identifier_naive_vs_proper_safe(dialect):
    """For safe input, naive and proper quoting produce same structure."""
    names = ["users", "orders", "products", "table_1", "camelCase"]
    for name in names:
        naive = f"[{name}]"
        proper = dialect.format_identifier(name)
        assert naive == proper, f"Mismatch for '{name}': naive={naive}, proper={proper}"


def test_format_identifier_naive_vs_proper_malicious(dialect):
    """For malicious input, proper quoting prevents breakout that naive allows."""
    payloads = [
        'x]; DROP TABLE users--',
        'y]; DELETE FROM t--',
        'z]; UPDATE t SET a=1--',
    ]
    for payload in payloads:
        naive = f"[{payload}]"
        proper = dialect.format_identifier(payload)

        # Naive: the ] in the payload prematurely closes the bracket => breakout
        # naive ends with "--]" where ] came from the f-string, not the payload
        # SQL Server sees: [x] as the identifier, then "; DROP TABLE users--]" as dangling SQL
        assert naive.endswith("]"), f"Naive should end with bracket: {naive}"
        assert proper.count("[") == 1, f"Proper should have 1 opening bracket: {proper}"
        assert proper.endswith("]"), f"Proper should end with closing bracket: {proper}"
        # Proper escapes interior ] as ]] so the whole thing stays inside one bracket pair
        assert "]]" in proper, f"Proper should have escaped brackets: {proper}"


def test_format_identifier_empty_string(dialect):
    """Empty identifier produces empty brackets."""
    assert dialect.format_identifier("") == "[]"


def test_escape_sql_string_inherited(dialect):
    """Test SQL Server inherits _escape_sql_string from base dialect."""
    result = dialect._escape_sql_string("test's value")
    assert result == "test''s value"


# ── SET statement whitelist ───────────────────────────────────────────


def test_set_language_whitelist():
    """SET LANGUAGE whitelist rejects invalid names, accepts valid ones."""
    from rhosocial.activerecord.backend.impl.sqlserver.mixins.backend_mixin import _SQLSERVER_LANGUAGES
    # Valid languages
    assert "us_english" in _SQLSERVER_LANGUAGES
    assert "simplified chinese" in _SQLSERVER_LANGUAGES
    # Invalid / injection payloads must NOT be in the whitelist
    for payload in ("malicious; DROP TABLE--", "", "us_english; DROP TABLE--"):
        assert payload.strip().lower() not in _SQLSERVER_LANGUAGES, \
            f"injection payload must not be in whitelist: {payload!r}"


def test_set_dateformat_whitelist():
    """SET DATEFORMAT whitelist rejects invalid formats."""
    from rhosocial.activerecord.backend.impl.sqlserver.mixins.backend_mixin import _SQLSERVER_DATE_FORMATS
    for fmt in ("mdy", "dmy", "ymd", "ydm", "myd", "dym"):
        assert fmt in _SQLSERVER_DATE_FORMATS
    # Validation lowercases input, so mdY == mdy is valid
    assert "mdY".strip().lower() in _SQLSERVER_DATE_FORMATS
    # Genuinely invalid formats
    for payload in ("xyz", "XYZ; DROP TABLE--", ""):
        assert payload.strip().lower() not in _SQLSERVER_DATE_FORMATS, \
            f"invalid format must not be in whitelist: {payload!r}"


def test_set_deadlock_priority_whitelist():
    """SET DEADLOCK_PRIORITY whitelist rejects invalid values."""
    from rhosocial.activerecord.backend.impl.sqlserver.mixins.backend_mixin import (
        _SQLSERVER_DEADLOCK_PRIORITIES,
    )
    for name in ("LOW", "NORMAL", "HIGH"):
        assert name in _SQLSERVER_DEADLOCK_PRIORITIES
    for payload in ("INJECTION", "", "HIGH; DROP TABLE--"):
        assert payload.upper() not in _SQLSERVER_DEADLOCK_PRIORITIES, \
            f"invalid priority must not be in whitelist: {payload!r}"


# ── Identifier quoting ────────────────────────────────────────────────


def test_identifier_quoting_balanced(dialect):
    """format_identifier always produces syntactically valid brackets."""
    payloads = ["]", "a]b", "a]]b", "a]b]c"]
    for payload in payloads:
        result = dialect.format_identifier(payload)
        assert result.startswith("["), f"starts with [: {result}"
        assert result.endswith("]"), f"ends with ]: {result}"
        # Every ] inside the brackets must be escaped as ]] to be valid
        inner = result[1:-1]  # strip outer brackets
        i = 0
        while i < len(inner):
            if inner[i] == "]":
                # an embedded ] must be part of an escaped ]] pair
                assert i + 1 < len(inner) and inner[i + 1] == "]", \
                    f"unescaped ] in {result} for payload {payload!r}"
                i += 2  # skip the ]] pair
            else:
                i += 1
