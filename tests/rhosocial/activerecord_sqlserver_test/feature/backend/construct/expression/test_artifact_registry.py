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

import ast
import inspect
import pathlib

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
    # Written as a literal on purpose: importing a peer backend's registry would
    # make this backend's test suite depend on that backend's implementation.
    foreign = "sqlite_alias_type_definition"
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


# ---------------------------------------------------------------------------
# One formatter per node: the property the walk admits a class by
# ---------------------------------------------------------------------------
#
# The table used to need a second registration path: a node that rendered
# itself through an ``to_sql()`` override named no formatter, so the assembly
# walk skipped it and the owner registered it by hand. That path is gone, and
# these two tests are what keep it gone -- a node that starts rendering itself
# fails the source scan, and a node whose kind is missing from the table fails
# the admission test.


def _expression_package_dir() -> pathlib.Path:
    """The source directory of this backend's expression package."""
    import rhosocial.activerecord.backend.impl.sqlserver.expression as pkg

    return pathlib.Path(pkg.__file__).parent


def test_no_node_in_this_package_renders_itself():
    """Every node names its dialect formatter; none renders SQL on its own.

    Checked on the source rather than on an instance: an override that no test
    happens to call is exactly the shape this rule exists to catch. Formatting
    and validation live on the dialect, and rendering flows through
    ``BaseExpression._render`` after a ``format_method`` lookup.
    """
    offenders = []
    for path in sorted(_expression_package_dir().rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(module):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if (
                    isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and item.name in ("to_sql", "_render")
                ):
                    offenders.append(f"{path.name}:{node.name}.{item.name}")

    assert not offenders, (
        "these classes render themselves instead of naming a dialect "
        f"formatter: {offenders}"
    )


def test_every_concrete_node_the_package_defines_is_a_registered_kind():
    """The package walk admits every node it defines -- no hand registration.

    ``registry_for_packages`` admits a class only when it resolves a
    ``format_method``, which a self-rendering node names none of. The hand
    registration that used to cover for those nodes is gone, so a node that
    forgets its formatter would silently vanish from the readable kinds; this
    test names it instead.
    """
    import importlib
    import pkgutil

    from rhosocial.activerecord.backend.expression.bases import BaseExpression

    package = "rhosocial.activerecord.backend.impl.sqlserver.expression"
    pkg = importlib.import_module(package)
    registry = backend_registry()

    missing = []
    for _, modname, _ in pkgutil.walk_packages(
        path=pkg.__path__, prefix=package + ".", onerror=lambda x: None
    ):
        module = importlib.import_module(modname)
        for name in dir(module):
            obj = getattr(module, name, None)
            if not isinstance(obj, type) or obj.__module__ != modname:
                continue
            if (
                issubclass(obj, BaseExpression)
                and obj is not BaseExpression
                and not inspect.isabstract(obj)
                and getattr(obj, "REGISTER_BY_DEFAULT", False)
            ):
                kind = obj.kind()
                try:
                    registered = registry.resolve_node(kind)
                except RegistryError:
                    missing.append(f"{modname}.{name} -> {kind} (not registered)")
                    continue
                if registered is not obj:
                    missing.append(f"{modname}.{name} -> {kind} (resolved elsewhere)")

    assert not missing, (
        "these nodes declare a formatter but are not in the dialect's "
        f"registry: {missing}"
    )


def test_a_converted_node_renders_without_being_handed_a_dialect(sqlserver_dialect):
    """A node built with no dialect renders through ``to_sql(dialect)``.

    This is the capability the conversion buys, and the reason a self-rendering
    node could not have it: ``to_sql()`` used to take no argument at all, so a
    node assembled before a backend existed had no way to be rendered
    afterwards. Both shapes converted here are covered: one that only delegated
    to its formatter (the columnstore statement) and one whose body used to
    build SQL itself (the full-text catalog statement).
    """
    from rhosocial.activerecord.backend.impl.sqlserver.expression.columnstore import (
        SQLServerColumnstoreIndexStatement,
    )
    from rhosocial.activerecord.backend.impl.sqlserver.expression.fulltext import (
        SQLServerCreateFullTextCatalogStatement,
    )

    columnstore = SQLServerColumnstoreIndexStatement(
        None, "cci", "t", clustered=True, order_columns=["c1", "c2"]
    )
    assert columnstore.to_sql(sqlserver_dialect) == (
        "CREATE CLUSTERED COLUMNSTORE INDEX [cci] ON [t] ORDER ([c1], [c2])",
        (),
    )

    catalog = SQLServerCreateFullTextCatalogStatement(None, "ftc", is_default=True)
    assert catalog.to_sql(sqlserver_dialect) == (
        "CREATE FULLTEXT CATALOG [ftc] AS DEFAULT",
        (),
    )
