# tests/rhosocial/activerecord_sqlserver_test/feature/backend/sqlserver/test_uuid_and_json_truth.py
"""UUID values and JSON honesty on SQL Server.

Three things this backend got wrong, all of the same shape: a probe or a
factory that named SQL Server does not have. ``NEWID()`` was absent
entirely, four JSON factories emitted MySQL function names, and
``supports_json_table`` claimed a capability the formatter refused.

No database is needed: every assertion is on rendered SQL.
"""

# tests/rhosocial/activerecord_sqlserver_test/feature/backend/sqlserver/test_uuid_and_json_truth.py
import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import (
    Column,
    ColumnBase,
    Literal,
    UUIDCastExpression,
    UUIDConstantExpression,
    UUIDGenerationExpression,
)
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression.types import (
    SQLServerUniqueIdentifierType,
)
from rhosocial.activerecord.backend.impl.sqlserver.functions import json as json_functions


def _dialect(version=(16, 0, 0)):
    dialect = SQLServerDialect()
    dialect._version = version
    return dialect


# ---------------------------------------------------------------------------
# UUID values
# ---------------------------------------------------------------------------


def test_generation_uses_newid():
    assert UUIDGenerationExpression(_dialect()).to_sql() == ("NEWID()", ())


def test_generation_carries_its_alias():
    dialect = _dialect()
    ident = dialect.format_identifier("u")
    assert UUIDGenerationExpression(dialect, alias="u").to_sql() == (
        f"NEWID() AS {ident}",
        (),
    )


def test_generation_needs_no_extension():
    """NEWID() is a core function from SQL Server 2005."""
    assert _dialect((9, 0, 0)).supports_uuid_generation() is True


@pytest.mark.parametrize(
    "which, expected",
    [
        (
            "nil",
            "CAST('00000000-0000-0000-0000-000000000000' AS UNIQUEIDENTIFIER)",
        ),
        (
            "max",
            "CAST('ffffffff-ffff-ffff-ffff-ffffffffffff' AS UNIQUEIDENTIFIER)",
        ),
    ],
)
def test_constants_are_cast_literals(which, expected):
    assert UUIDConstantExpression(_dialect(), which).to_sql() == (expected, ())


def test_cast_uses_the_t_sql_form():
    dialect = _dialect()
    expr = UUIDCastExpression(dialect, Literal(dialect, "not-a-uuid"))
    assert expr.to_sql() == ("CAST(? AS UNIQUEIDENTIFIER)", ("not-a-uuid",))


# ---------------------------------------------------------------------------
# UNIQUEIDENTIFIER as a real column type
# ---------------------------------------------------------------------------


def test_uniqueidentifier_renders():
    assert _dialect().format_data_type(SQLServerUniqueIdentifierType()) == (
        "UNIQUEIDENTIFIER",
        (),
    )


def test_type_name_is_namespaced_to_this_backend():
    """The prefix keeps format_data_type_<name> families from colliding."""
    assert SQLServerUniqueIdentifierType.name == "sqlserver_uniqueidentifier"


def test_suggestion_does_not_point_at_a_type_this_dialect_renders():
    """A suggestion exists precisely for types the dialect cannot render."""
    dialect = _dialect()
    suggestions = dialect.suggested_data_types()
    assert suggestions["uuid"] is SQLServerUniqueIdentifierType
    assert suggestions["uuid"].name != "uuid"


def test_introspection_round_trips():
    dialect = _dialect()
    parsed = dialect.parse_type("UNIQUEIDENTIFIER")
    assert isinstance(parsed, SQLServerUniqueIdentifierType)
    assert dialect.format_data_type(parsed) == ("UNIQUEIDENTIFIER", ())


# ---------------------------------------------------------------------------
# JSON factories that used to emit MySQL
# ---------------------------------------------------------------------------


def test_json_unquote_becomes_json_value():
    """T-SQL has no JSON_UNQUOTE; JSON_VALUE already returns a bare scalar."""
    expr = json_functions.json_unquote(_dialect(), "data", path="$.name")
    assert type(expr).__name__ == "SQLServerJSONExtractExpression"
    assert "JSON_VALUE" in expr.to_sql()[0]


def test_json_unquote_without_a_path_is_refused():
    """There is nothing to extract, so the request cannot be expressed."""
    with pytest.raises(UnsupportedFeatureError, match="without a path"):
        json_functions.json_unquote(_dialect(), "data")


def test_json_contains_becomes_an_openjson_predicate():
    expr = json_functions.json_contains(_dialect(), "data", "x", path="$.tags")
    assert type(expr).__name__ == "SQLServerJSONContainsExpression"
    sql, params = expr.to_sql()
    assert "OPENJSON" in sql and "EXISTS" in sql
    assert params == ("$.tags", "x")


@pytest.mark.parametrize("factory, args", [("json_type", ("data",)), ("json_search", ("data", "x"))])
def test_functions_sql_server_lacks_are_refused(factory, args):
    with pytest.raises(UnsupportedFeatureError):
        getattr(json_functions, factory)(_dialect(), *args)


def test_no_factory_emits_a_mysql_function_name():
    """The four factories bypassed the formatter that already refused these."""
    dialect = _dialect()
    for name in ("JSON_UNQUOTE", "JSON_CONTAINS", "JSON_TYPE", "JSON_SEARCH"):
        assert name not in _collect_sql(dialect), f"{name} still reachable"


def _collect_sql(dialect):
    """Render every JSON factory that takes a plain document argument."""
    produced = []
    for name in dir(json_functions):
        if not name.startswith("json_"):
            continue
        factory = getattr(json_functions, name)
        for args in (("data",), ("data", "x")):
            try:
                result = factory(dialect, *args)
                produced.append(result.to_sql()[0])
            except (UnsupportedFeatureError, TypeError):
                continue
    return " ".join(produced)


# ---------------------------------------------------------------------------
# JSON_TABLE
# ---------------------------------------------------------------------------


def test_json_table_is_not_claimed():
    """The formatter always refused, so the probe claiming True was a trap."""
    assert _dialect().supports_json_table() is False


def test_json_table_error_points_at_openjson():
    with pytest.raises(UnsupportedFeatureError, match="OPENJSON"):
        _dialect().format_json_table_expression(None)


# ---------------------------------------------------------------------------
# OUTPUT clause accepts typed columns
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("column_class", [Column, ColumnBase])
def test_output_clause_recognises_both_column_kinds(column_class):
    """A typed column must not fall through to the expressions branch."""
    from rhosocial.activerecord.backend.expression.statements.dml import ReturningClause

    dialect = _dialect()
    clause = ReturningClause(
        dialect, expressions=[column_class(dialect, "id", table="INSERTED")]
    )
    sql, params = dialect.format_returning_clause(clause)
    assert sql.startswith("OUTPUT INSERTED.")
    assert params == ()
