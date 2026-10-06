# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_identity_clause_sqlserver.py
"""SQL Server's identity column: ``IDENTITY(seed, increment)`` and its gate.

Measured on live SQL Server 2019 / 2022 / 2025 (the execution confirmation
lives in ``test_identity_execution_confirmation.py``):

* ``IDENTITY(seed, increment)`` executes at every version. It is this
  dialect's identity expression, so ``supports_identity_column()`` is
  ``True`` -- it is not a fallback for the standard grammar, which every
  measured version refuses.
* The identity property has no generation mode: ``GENERATED ALWAYS AS
  IDENTITY`` is refused by the server, and so is appending ``ALWAYS`` to the
  property. ``supports_identity_generation_always()`` is therefore ``False``
  and the formatter refuses an ``ALWAYS`` request by name instead of
  rendering the bare property (which is byte-identical to ``BY DEFAULT``).
* ``seed`` / ``increment`` are the property's two arguments, so their probes
  are ``True``.
* MINVALUE / MAXVALUE / CYCLE have no spelling in the property at all; every
  candidate spelling was measured refused on all three versions, so their
  probes are ``False`` and the formatter refuses a request for them.
* ``AUTO_INCREMENT`` is a different mechanism (parameterless marker), which
  SQL Server has no spelling for.
"""

import pytest

from rhosocial.activerecord.base import IdentityAttribute
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import ColumnDefinition
from rhosocial.activerecord.backend.expression.statements import (
    AutoIncrementClause,
    IdentityClause,
)
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect


@pytest.fixture
def dialect():
    return SQLServerDialect((16, 0, 0))


def _withdrawn(probe_name: str) -> SQLServerDialect:
    """A dialect that answers one identity probe ``False``.

    The shape being modelled: a version of the engine whose identity property
    lost one parameter. The gate must refuse exactly that parameter and keep
    rendering the rest, or the per-option probes would be decorative.
    """
    subclass = type(
        f"SQLServerWithout_{probe_name}",
        (SQLServerDialect,),
        {probe_name: lambda self: False},
    )
    return subclass((16, 0, 0))


class TestIdentityProbeDeclarations:
    """The declared capability table, one probe at a time."""

    def test_mechanism_and_two_property_arguments_are_declared(self, dialect):
        assert dialect.supports_identity_column() is True
        assert dialect.supports_identity_start() is True
        assert dialect.supports_identity_increment() is True

    def test_always_is_declined(self, dialect):
        """The property has no generation mode; ALWAYS cannot be expressed."""
        assert dialect.supports_identity_generation_always() is False

    def test_sequence_attributes_are_declined(self, dialect):
        """MINVALUE / MAXVALUE / CYCLE have no spelling in the property."""
        assert dialect.supports_identity_minvalue() is False
        assert dialect.supports_identity_maxvalue() is False
        assert dialect.supports_identity_cycle() is False

    def test_auto_increment_marker_is_declined(self, dialect):
        """``IDENTITY(seed, inc)`` is not ``AUTO_INCREMENT``."""
        assert dialect.supports_auto_increment_column() is False


class TestIdentityRendering:
    """``IDENTITY(seed, increment)`` and the two parameters it carries."""

    def test_bare_renders_the_property_defaults(self, dialect):
        assert IdentityClause(dialect).to_sql() == (" IDENTITY(1, 1)", ())

    def test_by_default_renders_the_same_property(self, dialect):
        # SQL Server has one property; BY DEFAULT is its implied mode.
        assert IdentityClause(dialect, "BY DEFAULT").to_sql() == (" IDENTITY(1, 1)", ())

    def test_start_is_the_seed(self, dialect):
        assert IdentityClause(dialect, start=100).to_sql() == (" IDENTITY(100, 1)", ())

    def test_increment_is_the_increment(self, dialect):
        assert IdentityClause(dialect, increment=5).to_sql() == (" IDENTITY(1, 5)", ())

    def test_seed_and_increment_together(self, dialect):
        assert IdentityClause(dialect, start=100, increment=5).to_sql() == (
            " IDENTITY(100, 5)",
            (),
        )


class TestAlwaysIsRefusedNotDowngraded:
    """The behaviour change: ``ALWAYS`` fails closed instead of degrading."""

    def test_always_is_refused_by_name(self, dialect):
        with pytest.raises(UnsupportedFeatureError, match="IDENTITY GENERATED ALWAYS"):
            IdentityClause(dialect, "ALWAYS").to_sql()

    def test_always_does_not_render_the_by_default_sql(self, dialect):
        """The refusal is the only outcome; the bare property never comes out.

        Before this round ``ALWAYS`` rendered byte-identical to ``BY DEFAULT``
        (`` IDENTITY(1, 1)``), i.e. the request was silently degraded. Pin the
        difference: the same constructor arguments that render for ``BY
        DEFAULT`` must raise for ``ALWAYS``.
        """
        assert IdentityClause(dialect, "BY DEFAULT").to_sql()[0] == " IDENTITY(1, 1)"
        with pytest.raises(UnsupportedFeatureError):
            IdentityClause(dialect, "ALWAYS").to_sql()

    def test_always_with_parameters_is_still_refused(self, dialect):
        with pytest.raises(UnsupportedFeatureError, match="IDENTITY GENERATED ALWAYS"):
            IdentityClause(dialect, "ALWAYS", start=100, increment=5).to_sql()


class TestUnspellableOptionsAreRefusedByName:
    """Each parameter without a spelling is refused, never dropped."""

    @pytest.mark.parametrize(
        "kwargs,feature",
        [
            ({"minvalue": 1}, "IDENTITY MINVALUE"),
            ({"maxvalue": 100}, "IDENTITY MAXVALUE"),
            ({"cycle": True}, "IDENTITY CYCLE"),
            ({"cycle": False}, "IDENTITY CYCLE"),
        ],
        ids=["minvalue", "maxvalue", "cycle", "nocycle"],
    )
    def test_option_is_refused_by_name(self, dialect, kwargs, feature):
        with pytest.raises(UnsupportedFeatureError, match=feature):
            IdentityClause(dialect, **kwargs).to_sql()


class TestGatesAreLive:
    """Withdrawing one probe must change exactly that gate.

    These are the mutation checks: if the formatter ignored a probe, the
    refusal would not follow the declaration.
    """

    def test_master_switch_withdrawn_refuses_even_with_options(self):
        dialect = _withdrawn("supports_identity_column")
        with pytest.raises(UnsupportedFeatureError, match="IDENTITY column"):
            IdentityClause(dialect).to_sql()
        with pytest.raises(UnsupportedFeatureError, match="IDENTITY column"):
            IdentityClause(dialect, start=1, increment=1).to_sql()

    def test_start_withdrawn_refuses_start_but_not_increment(self):
        dialect = _withdrawn("supports_identity_start")
        with pytest.raises(UnsupportedFeatureError, match="IDENTITY START"):
            IdentityClause(dialect, start=100).to_sql()
        assert IdentityClause(dialect, increment=5).to_sql()[0] == " IDENTITY(1, 5)"

    def test_increment_withdrawn_refuses_increment_but_not_start(self):
        dialect = _withdrawn("supports_identity_increment")
        with pytest.raises(UnsupportedFeatureError, match="IDENTITY INCREMENT"):
            IdentityClause(dialect, increment=5).to_sql()
        assert IdentityClause(dialect, start=100).to_sql()[0] == " IDENTITY(100, 1)"

    def test_generation_always_gate_withdrawn_refuses_always(self):
        dialect = _withdrawn("supports_identity_generation_always")
        with pytest.raises(UnsupportedFeatureError, match="IDENTITY GENERATED ALWAYS"):
            IdentityClause(dialect, "ALWAYS").to_sql()
        assert IdentityClause(dialect, "BY DEFAULT").to_sql()[0] == " IDENTITY(1, 1)"


class TestAutoIncrementMarkerIsRefused:
    """The parameterless marker is a different mechanism and fails closed."""

    def test_marker_is_refused_by_name(self, dialect):
        with pytest.raises(UnsupportedFeatureError, match="AUTO_INCREMENT column"):
            AutoIncrementClause(dialect).to_sql()


class TestColumnDefinitionUsesTheIdentityClause:
    """The path a user hits: an ``IdentityAttribute`` on a column definition."""

    def test_identity_attribute_renders_the_property(self, dialect):
        column = ColumnDefinition(
            dialect,
            "id",
            IntegerType(dialect),
            attributes=[IdentityAttribute(start=100, increment=5)],
        )
        assert column.to_sql() == ("[id] INT IDENTITY(100, 5)", ())

    def test_always_identity_attribute_is_refused(self, dialect):
        column = ColumnDefinition(
            dialect,
            "id",
            IntegerType(dialect),
            attributes=[IdentityAttribute(generation="ALWAYS", start=100)],
        )
        with pytest.raises(UnsupportedFeatureError, match="IDENTITY GENERATED ALWAYS"):
            column.to_sql()

    def test_unspellable_identity_attribute_is_refused(self, dialect):
        column = ColumnDefinition(
            dialect,
            "id",
            IntegerType(dialect),
            attributes=[IdentityAttribute(minvalue=1)],
        )
        with pytest.raises(UnsupportedFeatureError, match="IDENTITY MINVALUE"):
            column.to_sql()
