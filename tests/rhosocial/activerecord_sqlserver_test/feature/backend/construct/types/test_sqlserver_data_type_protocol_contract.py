# tests/.../test_sqlserver_data_type_protocol_contract.py
"""This backend's own data-type protocol contract (D9 + substitutes).

Backend functionality is tested here, in this repository: nothing in this file
belongs in the shared testsuite. Core concepts are discovered, not listed, so a
concept added to core later cannot slip past a stale list.
"""

import pytest

from rhosocial.activerecord.backend.expression.types import DataType
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

#: Versions spanning the gates this backend declares.
VERSIONS = [(14, 0, 1000), (16, 0, 1000)]


def _dialect(version):
    return SQLServerDialect(version=version)


def _rendered_names(dialect):
    """Concept names this dialect renders: a formatter whose probe says yes.

    Core removed the old type-class mapping; the capability is now read straight
    off the ``format_data_type_*`` / ``supports_data_type_*`` method families.
    """
    names = set()
    for member in dir(dialect):
        if not member.startswith("format_data_type_"):
            continue
        name = member[len("format_data_type_"):]
        probe = getattr(dialect, f"supports_data_type_{name}", None)
        if probe is None or probe():
            names.add(name)
    return names


def _core_concepts():
    seen = set()
    stack = [DataType]
    while stack:
        klass = stack.pop()
        if klass in seen:
            continue
        seen.add(klass)
        stack.extend(klass.__subclasses__())
    return sorted(
        {
            klass.name
            for klass in seen
            if klass is not DataType
            and klass.__module__.startswith("rhosocial.activerecord.backend.expression.types")
            and klass.name
        }
    )


def _renderable_substitute(dialect, klass):
    """Minimum valid construction for substitutes that carry parameters.

    These three cannot be built with no arguments; the values are chosen only
    to exercise rendering, not to stand for any real column.
    """
    if klass.__name__ == "PostgresEnumColumnType":
        return klass(dialect, type_name="status", values=["a", "b"])
    if klass.__name__ == "MySQLVarBinaryType":
        return klass(dialect, length=16)
    if klass.__name__ == "CustomType":
        return klass(dialect, raw="ARRAY")
    return klass(dialect)


@pytest.mark.parametrize("version", VERSIONS)
def test_every_core_concept_is_declared(version):
    """D9: rendered or substituted -- silence is not an answer."""
    dialect = _dialect(version)
    supported = _rendered_names(dialect)
    substitutes = dialect.suggest_substitute_types().mapping
    undeclared = [
        name for name in _core_concepts() if name not in supported and name not in substitutes
    ]
    assert not undeclared, f"{version}: {undeclared} are neither rendered nor substituted"


@pytest.mark.parametrize("version", VERSIONS)
def test_substitutes_are_disjoint_and_renderable(version):
    """A substitute must be a DataType class this dialect really writes."""
    dialect = _dialect(version)
    supported = _rendered_names(dialect)
    substitutes = dialect.suggest_substitute_types().mapping
    assert not supported & set(substitutes)

    for key, klass in substitutes.items():
        assert isinstance(klass, type) and issubclass(klass, DataType), key
        sql, _ = dialect.format_data_type(_renderable_substitute(dialect, klass))
        assert sql, f"{version}: {key} -> {klass.__name__} renders nothing"


@pytest.mark.parametrize("version", VERSIONS)
def test_formatter_and_probe_families_are_one_to_one(version):
    """D10: a formatter has a probe, and an absent answer is an explicit probe.

    A version-gated concept may be absent; that is an answer only when its
    probe says False. A formatter with no probe at all,
    or a supported key with no formatter, breaks the 1:1 discipline.
    """
    dialect = _dialect(version)
    format_names = {
        member[len("format_data_type_") :]
        for member in dir(dialect)
        if member.startswith("format_data_type_")
    }
    probe_names = {
        member[len("supports_data_type_") :]
        for member in dir(dialect)
        if member.startswith("supports_data_type_")
    }
    assert format_names, "the dialect must implement a format_data_type_* family"
    assert format_names == probe_names, (
        f"format-only: {sorted(format_names - probe_names)}, "
        f"probe-only: {sorted(probe_names - format_names)}"
    )

    supported = {name for name in format_names
                 if getattr(dialect, f"supports_data_type_{name}")()}
    assert supported <= format_names
    for name in sorted(format_names - supported):
        probe = getattr(dialect, f"supports_data_type_{name}")
        assert probe() is False, f"{name} has a formatter but no False probe explains its absence"
