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
* MINVALUE / MAXVALUE / CYCLE / ORDER / CACHE have no spelling in the
  property at all; every candidate spelling was measured refused on all three
  versions, so their probes are ``False`` and the formatter refuses a request
  for them by name.
* ``TestNoOptionIsSilentlyDropped`` walks every option field read from
  ``IdentityClause.__init__`` and asserts the formatter renders each one or
  refuses it by name -- a field core adds later cannot be silently dropped
  the way ``order`` and ``cache`` were before the gates existed.
* ``AUTO_INCREMENT`` is a different mechanism (parameterless marker), which
  SQL Server has no spelling for.
"""

import inspect
import types
import typing

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
        """MINVALUE / MAXVALUE / CYCLE / ORDER / CACHE have no spelling."""
        assert dialect.supports_identity_minvalue() is False
        assert dialect.supports_identity_maxvalue() is False
        assert dialect.supports_identity_cycle() is False
        assert dialect.supports_identity_order() is False
        assert dialect.supports_identity_cache() is False

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
            ({"no_cycle": True}, "IDENTITY CYCLE"),
            ({"order": True}, "IDENTITY ORDER"),
            ({"no_order": True}, "IDENTITY ORDER"),
            ({"cache": 10}, "IDENTITY CACHE"),
            ({"no_cache": True}, "IDENTITY CACHE"),
        ],
        ids=[
            "minvalue",
            "maxvalue",
            "cycle",
            "nocycle",
            "order",
            "no-order",
            "cache",
            "no-cache",
        ],
    )
    def test_option_is_refused_by_name(self, dialect, kwargs, feature):
        with pytest.raises(UnsupportedFeatureError, match=feature):
            IdentityClause(dialect, **kwargs).to_sql()


# ``IdentityClause``'s option fields are read from the expression's own
# signature, not from a list here: a field core adds later is walked
# automatically, so it cannot be silently dropped the way ``order`` and
# ``cache`` were before the gates existed.
_OPTION_UNION_TYPES = (typing.Union,)
if hasattr(types, "UnionType"):  # Python 3.10+
    _OPTION_UNION_TYPES += (types.UnionType,)

# Sentinel floor, not the coverage list: the walk must at least see the
# options that existed when it was written. What is actually walked is
# whatever ``IdentityClause.__init__`` declares; this set only proves the
# signature introspection did not silently shrink to nothing.
_OPTIONS_AT_WALK_BIRTH = frozenset(
    {
        "start",
        "increment",
        "minvalue",
        "maxvalue",
        "cycle",
        "no_cycle",
        "order",
        "no_order",
        "cache",
        "no_cache",
    }
)


def _option_fields() -> dict:
    """The keyword-only option fields, read from the expression itself."""
    params = inspect.signature(IdentityClause.__init__).parameters
    return {
        name: param
        for name, param in params.items()
        if param.kind is inspect.Parameter.KEYWORD_ONLY
    }


def _probe_values(field_name: str, param: inspect.Parameter) -> tuple:
    """Non-default probe values for one option field.

    A bool option is one *spelling* of a two-spelling pair: ``True`` requests
    that spelling, ``False`` is the "not requested" state, so only ``True`` is
    a request worth probing. An int option takes a positive count; ``0`` is
    refused at construction (``cache must be a positive integer``) and is
    pinned by its own sentinel test, not probed here. A field with an unknown
    type fails the walk with the reason instead of being probed with a
    meaningless value.
    """
    annotation = param.annotation
    if annotation is inspect.Parameter.empty:
        raise AssertionError(
            f"IdentityClause option {field_name!r} is unannotated; this walk "
            f"cannot choose a probe value for it."
        )
    if typing.get_origin(annotation) in _OPTION_UNION_TYPES:
        args = tuple(
            arg for arg in typing.get_args(annotation) if arg is not type(None)
        )
        annotation = args[0] if args else annotation
    if annotation is bool:
        return (True,)
    if annotation is int:
        return (100,)
    raise AssertionError(
        f"no probe value is known for IdentityClause option {field_name!r} "
        f"(type {annotation!r}); extend this walk so the new option is still "
        f"rendered or refused by name, never dropped."
    )


def _walk_options(dialect) -> dict:
    """Render-or-refuse every option; return the verdicts, raise on a drop.

    The property under test: for every option field of ``IdentityClause``, a
    clause requesting that option either renders SQL that differs from the
    bare clause, or raises ``UnsupportedFeatureError`` naming the option.
    Rendering the bare clause byte-for-byte is the silent drop this walk
    exists to catch.
    """
    options = _option_fields()
    assert set(options) >= _OPTIONS_AT_WALK_BIRTH, (
        f"the signature walk found only {sorted(options)}; it must at least "
        f"see the options that existed when this test was written"
    )
    bare_sql, _ = IdentityClause(dialect).to_sql()
    verdicts = {}
    for name, param in options.items():
        # ``no_cycle`` is the NO CYCLE spelling of the ``cycle`` pair; the
        # refusal names the clause ("IDENTITY CYCLE"), not the parameter.
        option_name = name[3:] if name.startswith("no_") else name
        for value in _probe_values(name, param):
            clause = IdentityClause(dialect, **{name: value})
            try:
                sql, _ = clause.to_sql()
            except UnsupportedFeatureError as exc:
                if f"IDENTITY {option_name.upper()}" not in str(exc):
                    raise AssertionError(
                        f"option {name!r}={value!r} was refused without "
                        f"naming it: {exc}"
                    ) from exc
                verdicts[(name, value)] = "refused"
            else:
                if sql == bare_sql:
                    raise AssertionError(
                        f"option {name!r}={value!r} rendered {sql!r}, "
                        f"byte-identical to the bare clause {bare_sql!r}: "
                        f"the option was silently dropped."
                    )
                verdicts[(name, value)] = "rendered"
    return verdicts


class TestNoOptionIsSilentlyDropped:
    """Every ``IdentityClause`` option is rendered or refused by name.

    The option list is read from ``IdentityClause.__init__`` itself, so the
    walk covers a field core adds later the moment it exists -- it cannot be
    silently dropped the way ``order`` and ``cache`` were.
    """

    def test_every_option_is_rendered_or_refused_by_name(self, dialect):
        verdicts = _walk_options(dialect)
        # Sentinels: both branches of the walk must be exercised, or a walk
        # that only ever saw one of them could look healthy while blind.
        assert "refused" in verdicts.values(), verdicts
        assert "rendered" in verdicts.values(), verdicts
        # The fields this round split into pairs: every explicit spelling is
        # refused by name.
        for key in (
            ("order", True),
            ("no_order", True),
            ("cache", 100),
            ("no_cache", True),
        ):
            assert verdicts[key] == "refused", verdicts

    def test_cache_zero_is_refused_at_construction(self, dialect):
        """``cache=0`` is not a spelling of NO CACHE (round rule 4)."""
        with pytest.raises(ValueError, match="cache must be a positive integer"):
            IdentityClause(dialect, cache=0)

    def test_the_walk_rejects_a_formatter_that_drops_options(self):
        """The walk is live: a formatter that drops an option must fail it.

        The dropping formatter below is the shape this dialect had before the
        gates existed -- the bare property for every request. If the walk
        could not see that, it would certify the defect it was written to
        catch.
        """

        class DroppingDialect(SQLServerDialect):
            def format_identity_clause(self, expr):
                return " IDENTITY(1, 1)", ()

        with pytest.raises(AssertionError, match="silently dropped"):
            _walk_options(DroppingDialect((16, 0, 0)))


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
