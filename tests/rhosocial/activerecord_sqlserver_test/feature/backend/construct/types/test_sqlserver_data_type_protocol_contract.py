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
    supported = set(dialect.supports_data_types())
    substitutes = dialect.substitute_data_types()
    undeclared = [
        name for name in _core_concepts() if name not in supported and name not in substitutes
    ]
    assert not undeclared, f"{version}: {undeclared} are neither rendered nor substituted"


@pytest.mark.parametrize("version", VERSIONS)
def test_substitutes_are_disjoint_and_renderable(version):
    """A substitute must be a DataType class this dialect really writes."""
    dialect = _dialect(version)
    supported = set(dialect.supports_data_types())
    substitutes = dialect.substitute_data_types()
    assert not supported & set(substitutes)

    for key, klass in substitutes.items():
        assert isinstance(klass, type) and issubclass(klass, DataType), key
        sql, _ = dialect.format_data_type(_renderable_substitute(dialect, klass))
        assert sql, f"{version}: {key} -> {klass.__name__} renders nothing"
