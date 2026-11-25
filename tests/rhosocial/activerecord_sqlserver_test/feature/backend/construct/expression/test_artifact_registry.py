# tests/rhosocial/activerecord_sqlserver_test/feature/backend/construct/expression/test_artifact_registry.py
"""SQL Server's artifact registry: core composed in, its own kinds only.

An expression artifact is data: parameters only, no dialect (§4.11.3). Reading
one needs a table that turns a kind back into a class, and each owner publishes
its own:

* SQL Server's table composes core's kinds as its base and adds the kinds its
  expression package declares — never a merge with another backend;
* the published table is frozen, so two readers cannot change each other's
  answers;
* a kind no package registered here is refused by name rather than guessed;
* a caller who trusts its artifacts widens a ``twin()``, never the shared table.
"""

import pytest

from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.expression.operators import RawSQLPredicate
from rhosocial.activerecord.backend.expression.registry import (
    RegistryError,
    RegistryReason,
)
from rhosocial.activerecord.backend.expression.serialization import (
    ExpressionDeserializationError,
    deserialize,
    serialize,
)
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.type import (
    SQLServerAliasTypeDefinition,
)
from rhosocial.activerecord.backend.impl.sqlserver.registry import backend_registry


def _alias_type(dialect):
    return SQLServerAliasTypeDefinition(dialect, IntegerType(dialect), nullability=True)


def test_the_dialect_publishes_core_plus_its_own_kinds_frozen(sqlserver_dialect):
    """One cached, frozen table: core's kinds plus SQL Server's, no other backend's."""
    registry = backend_registry()
    assert registry is backend_registry()
    assert registry is sqlserver_dialect.artifact_registry()
    assert registry.is_frozen

    # Core is the base of the composition, so a core kind resolves here.
    assert registry.resolve_node("column") is Column
    assert "sqlserver_alias_type_definition" in registry.node_kinds()

    # Another backend's kinds are not listed: ownership is compositional,
    # never a cross-backend merge.
    assert not [kind for kind in registry.node_kinds() if kind.startswith("sqlite_")]


def test_a_proprietary_kind_round_trips_through_the_dialects_registry(sqlserver_dialect):
    """``deserialize(spec, dialect)`` reads a SQL Server-only kind."""
    expression = _alias_type(sqlserver_dialect)
    restored = deserialize(serialize(expression), sqlserver_dialect)
    assert type(restored) is SQLServerAliasTypeDefinition

    # Without a dialect the read falls back to core, which refuses the backend
    # kind by name instead of guessing.
    with pytest.raises(ExpressionDeserializationError) as caught:
        deserialize(serialize(expression))
    assert SQLServerAliasTypeDefinition.kind() in str(caught.value)


def test_a_foreign_backend_kind_is_refused_by_name(sqlserver_dialect):
    """A kind owned by another backend is not resolvable here."""
    from rhosocial.activerecord.backend.impl.sqlite.registry import (
        backend_registry as sqlite_registry,
    )

    foreign = next(
        kind for kind in sqlite_registry().node_kinds() if kind.startswith("sqlite_")
    )
    assert foreign not in sqlserver_dialect.artifact_registry().node_kinds()

    with pytest.raises(RegistryError) as caught:
        sqlserver_dialect.artifact_registry().resolve_node(foreign)
    assert caught.value.reason is RegistryReason.KIND_NOT_REGISTERED
    assert foreign in str(caught.value)

    with pytest.raises(ExpressionDeserializationError) as read:
        deserialize({"kind": foreign, "params": {}}, sqlserver_dialect)
    assert foreign in str(read.value)


def test_the_published_registry_refuses_every_mutation(sqlserver_dialect):
    """A frozen table is a value; widening it means owning a twin."""
    registry = sqlserver_dialect.artifact_registry()
    with pytest.raises(RegistryError) as caught:
        registry.register_node(SQLServerAliasTypeDefinition)
    assert caught.value.reason is RegistryReason.REGISTRY_FROZEN
    assert SQLServerAliasTypeDefinition.kind() in str(caught.value)


def test_trusted_raw_sql_opt_in_is_a_twin_not_the_shared_table(sqlserver_dialect):
    """Raw SQL is caller-vouched text, so reading it needs an explicit opt-in."""
    spec = serialize(RawSQLPredicate(sqlserver_dialect, "1 = 1"))

    with pytest.raises(ExpressionDeserializationError) as caught:
        deserialize(spec, sqlserver_dialect)
    assert RawSQLPredicate.kind() in str(caught.value)

    trusted = backend_registry().twin()
    assert not trusted.is_frozen
    trusted.register_node(RawSQLPredicate)
    restored = deserialize(spec, sqlserver_dialect, registry=trusted)
    assert isinstance(restored, RawSQLPredicate)

    # The opt-in did not widen what everyone else reads.
    with pytest.raises(RegistryError) as refused:
        backend_registry().resolve_node(RawSQLPredicate.kind())
    assert refused.value.reason is RegistryReason.KIND_NOT_REGISTERED
