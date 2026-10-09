# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_table_type_definition_roundtrip.py
"""Round-trip contract for ``SQLServerTableTypeDefinition``.

A SQL Server table TYPE has two spellings for the same list of table
constraints: ``constraints`` and the keyword-only ``table_constraints``
(named to match the model-level attribute). They are mutually exclusive. This
class used to override ``get_params()`` to always emit the list under
``constraints``; core's contract test
``test_expression_contract.py::TestInitParamAttributeContract::test_no_get_params_override``
forbids that, because the generic introspection path is the single
serialization path.

The repair is to fold the state into ``__init__``: it stores the merged list
under the slot matching the parameter the caller used and leaves the unused
spelling ``None``. These tests prove the generic path then reconstructs the
same expression — from *both* spellings — with identical SQL, and that it
never emits a key the constructor would reject.
"""

import inspect

import pytest

from rhosocial.activerecord.backend.expression.core import Literal
from rhosocial.activerecord.backend.expression.serialization import (
    deserialize,
    deserialize_json,
    serialize,
    serialize_json,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnConstraint,
    ColumnConstraintType,
    ColumnDefinition,
    TableConstraint,
    TableConstraintType,
)
from rhosocial.activerecord.backend.expression.types import IntegerType, VarCharType
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect
from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.type import (
    SQLServerTableTypeDefinition,
)
from rhosocial.activerecord.backend.impl.sqlserver.expression.index import (
    SQLServerIndexDefinition,
)
from rhosocial.activerecord.testsuite.utils.expression import assert_params_equal

SQL_SERVER_2014 = (12, 0, 0)


@pytest.fixture
def dialect():
    return SQLServerDialect(SQL_SERVER_2014)


def _columns(dialect):
    return [
        ColumnDefinition(
            dialect,
            "id",
            IntegerType(dialect),
            constraints=[ColumnConstraint(dialect, ColumnConstraintType.NOT_NULL)],
        ),
        ColumnDefinition(dialect, "name", VarCharType(dialect, length=100)),
    ]


def _constraints(dialect):
    return [TableConstraint(dialect, TableConstraintType.PRIMARY_KEY, columns=["id"])]


def _round_trip(expr, dialect):
    """get_params() -> reconstruct from those params alone -> prove fidelity.

    Returns the emitted params so the caller can inspect their shape.
    """
    params = expr.get_params()

    accepted = set(inspect.signature(type(expr).__init__).parameters)
    rejected = sorted((set(params) | set(serialize(expr)["params"])) - accepted)
    assert not rejected, (
        f"get_params() emitted keys the constructor would reject: {rejected}"
    )

    for restored in (
        deserialize(serialize(expr), dialect),
        deserialize_json(serialize_json(expr), dialect),
    ):
        rebuilt = type(expr)(dialect, **restored.get_params())
        assert_params_equal(rebuilt.get_params(), expr.get_params())
        assert rebuilt.to_sql() == expr.to_sql()

    return params


class TestSQLServerTableTypeDefinitionRoundTrip:
    """Both spellings survive the generic get_params() round trip."""

    def test_constraints_spelling_round_trips(self, dialect):
        constraints = _constraints(dialect)
        indexes = [SQLServerIndexDefinition(dialect, "ix_name", ["name"], type="NONCLUSTERED")]
        expr = SQLServerTableTypeDefinition(
            dialect,
            columns=_columns(dialect),
            constraints=constraints,
            indexes=indexes,
            memory_optimized=True,
        )

        params = _round_trip(expr, dialect)

        # The used spelling carries the list; the unused one says "not supplied".
        assert params["constraints"] == constraints
        assert params["table_constraints"] is None
        assert expr.constraints == constraints
        assert expr.table_constraints is None
        assert expr.constraint_definitions == constraints
        sql, bind_params = expr.to_sql()
        assert sql == (
            "AS TABLE ([id] INT NOT NULL, [name] VARCHAR(100), "
            "PRIMARY KEY NONCLUSTERED ([id]), INDEX [ix_name] NONCLUSTERED ([name])) "
            "WITH (MEMORY_OPTIMIZED = ON)"
        )
        assert bind_params == ()

    def test_table_constraints_spelling_round_trips(self, dialect):
        constraints = _constraints(dialect)
        indexes = [SQLServerIndexDefinition(dialect, "ix_name", ["name"], type="NONCLUSTERED")]
        expr = SQLServerTableTypeDefinition(
            dialect,
            columns=_columns(dialect),
            indexes=indexes,
            memory_optimized=True,
            table_constraints=constraints,
        )

        params = _round_trip(expr, dialect)

        assert params["table_constraints"] == constraints
        assert params["constraints"] is None
        assert expr.table_constraints == constraints
        assert expr.constraints is None
        assert expr.constraint_definitions == constraints
        # Byte-identical to the `constraints=` spelling.
        assert expr.to_sql() == SQLServerTableTypeDefinition(
            dialect,
            columns=_columns(dialect),
            constraints=constraints,
            indexes=indexes,
            memory_optimized=True,
        ).to_sql()

    def test_neither_spelling_round_trips(self, dialect):
        expr = SQLServerTableTypeDefinition(
            dialect, columns=[ColumnDefinition(dialect, "id", IntegerType(dialect))]
        )

        params = _round_trip(expr, dialect)

        assert params["constraints"] is None
        assert params["table_constraints"] is None
        assert expr.constraint_definitions == []
        assert expr.to_sql() == ("AS TABLE ([id] INT)", ())

    def test_empty_constraints_sequence_round_trips(self, dialect):
        expr = SQLServerTableTypeDefinition(
            dialect, columns=_columns(dialect), constraints=[]
        )

        params = _round_trip(expr, dialect)

        assert params["constraints"] == []
        assert params["table_constraints"] is None
        assert expr.to_sql() == ("AS TABLE ([id] INT NOT NULL, [name] VARCHAR(100))", ())

    def test_memory_optimized_key_constraint_path_uses_merged_list(self, dialect):
        """The memory-optimized index/key budget must see the constraints."""
        expr = SQLServerTableTypeDefinition(
            dialect,
            columns=[ColumnDefinition(dialect, "id", IntegerType(dialect))],
            memory_optimized=True,
            table_constraints=[
                TableConstraint(dialect, TableConstraintType.PRIMARY_KEY, columns=["id"])
            ],
        )

        params = _round_trip(expr, dialect)

        assert params["constraints"] is None
        assert [c.constraint_type for c in params["table_constraints"]] == [
            TableConstraintType.PRIMARY_KEY
        ]
        assert expr.to_sql() == (
            "AS TABLE ([id] INT, PRIMARY KEY NONCLUSTERED ([id])) "
            "WITH (MEMORY_OPTIMIZED = ON)",
            (),
        )

    def test_both_spellings_at_once_still_rejected(self, dialect):
        with pytest.raises(ValueError, match="mutually exclusive"):
            SQLServerTableTypeDefinition(
                dialect,
                columns=_columns(dialect),
                constraints=_constraints(dialect),
                table_constraints=_constraints(dialect),
            )

    def test_check_constraint_condition_survives(self, dialect):
        condition = Literal(dialect, 1, inline_literals=True) > Literal(
            dialect, 0, inline_literals=True
        )
        check = TableConstraint(
            dialect,
            TableConstraintType.CHECK,
            check_condition=condition,
        )
        expr = SQLServerTableTypeDefinition(
            dialect,
            columns=_columns(dialect),
            constraints=[check],
        )

        params = _round_trip(expr, dialect)

        assert params["constraints"] == [check]
        assert params["table_constraints"] is None
        assert expr.to_sql()[0].endswith("CHECK (1 > 0))")

    def test_class_does_not_override_get_params(self):
        from rhosocial.activerecord.backend.expression.bases import BaseExpression

        assert SQLServerTableTypeDefinition.get_params is BaseExpression.get_params