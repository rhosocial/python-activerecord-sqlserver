# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_sqlserver_dialect_security.py
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


def test_set_language_whitelist(dialect):
    """SET LANGUAGE accepts valid lang names, rejects invalid."""
    # Valid
    dialect._validate_set_language("us_english")  # no raise
    dialect._validate_set_language("简体中文")  # no raise
    # Invalid
    with pytest.raises(ValueError, match="Invalid SET LANGUAGE"):
        dialect._validate_set_language("malicious; DROP TABLE--")
    with pytest.raises(ValueError, match="Invalid SET LANGUAGE"):
        dialect._validate_set_language("")


def test_set_dateformat_whitelist(dialect):
    """SET DATEFORMAT accepts valid formats, rejects invalid."""
    for fmt in ("mdy", "dmy", "ymd", "ydm", "myd", "dym"):
        dialect._validate_set_dateformat(fmt)  # no raise
    with pytest.raises(ValueError, match="Invalid SET DATEFORMAT"):
        dialect._validate_set_dateformat("xyz")
    with pytest.raises(ValueError, match="Invalid SET DATEFORMAT"):
        dialect._validate_set_dateformat("mdY")


def test_set_deadlock_priority_whitelist(dialect):
    """SET DEADLOCK_PRIORITY accepts valid priorities, rejects invalid."""
    dialect._validate_set_deadlock_priority(-10)  # no raise
    dialect._validate_set_deadlock_priority(10)  # no raise
    dialect._validate_set_deadlock_priority("LOW")  # no raise
    dialect._validate_set_deadlock_priority("NORMAL")  # no raise
    dialect._validate_set_deadlock_priority("HIGH")  # no raise
    with pytest.raises(ValueError, match="Invalid DEADLOCK_PRIORITY"):
        dialect._validate_set_deadlock_priority(-11)
    with pytest.raises(ValueError, match="Invalid DEADLOCK_PRIORITY"):
        dialect._validate_set_deadlock_priority(11)
    with pytest.raises(ValueError, match="Invalid DEADLOCK_PRIORITY"):
        dialect._validate_set_deadlock_priority("INJECTION")
    with pytest.raises(ValueError, match="Invalid DEADLOCK_PRIORITY"):
        dialect._validate_set_deadlock_priority("")


# ── Identifier quoting ────────────────────────────────────────────────


def test_identifier_quoting_balanced(dialect):
    """format_identifier always produces balanced brackets."""
    payloads = ["]", "a]b", "a]]b", "a]b]c"]
    for payload in payloads:
        result = dialect.format_identifier(payload)
        opened = result.count("[")
        closed = result.count("]")  # includes escaped ]]
        # Each ]] is one escaped bracket, so real counting: every ] is either
        # part of ]] or a closing bracket. We just check it's parseable.
        assert result.startswith("["), f"starts with [: {result}"
        assert result.endswith("]"), f"ends with ]: {result}"
        # Embedded ]] pairs are escaped brackets; single ] closes group
        assert result.count("]") % 2 == 0 or result == "[]", \
            f"balanced brackets: {result}"
