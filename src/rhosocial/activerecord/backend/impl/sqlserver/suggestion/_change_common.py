# src/rhosocial/activerecord/backend/impl/sqlserver/suggestion/_change_common.py
"""Shared projection readers for the four migration change-point suggestions.

The core freezes a declaration projection with ``_freeze``: a mapping becomes
``("params", ((key, value), ...))`` and a value it cannot reduce further becomes
``("repr", ...)``. Callers may also hand a real expression node or a plain
mapping. These readers give the four ``suggest_*`` mixins one way to look at
either shape without rendering SQL or guessing a class the projection does not
carry. An opaque ``repr`` projection answers no fields, which is what lets a
mixin refuse honestly instead of inventing a node.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict, Optional

from ....expression.bases import BaseExpression

__all__ = [
    "ChangeProjection",
    "projection_name",
    "projection_node",
    "projection_param",
    "projection_params",
]


def _params_of(value: Any) -> Optional[Dict[str, Any]]:
    """Read a projection's named fields, or ``None`` when it carries none."""
    if isinstance(value, BaseExpression):
        getter = getattr(value, "get_params", None)
        if callable(getter):
            try:
                return dict(getter())
            except (TypeError, ValueError):  # pragma: no cover - defensive
                return {}
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, tuple) and len(value) == 2 and value[0] == "params":
        inner = value[1]
        if isinstance(inner, Mapping):
            return dict(inner)
        if isinstance(inner, (tuple, list)):
            try:
                return dict(inner)
            except (TypeError, ValueError):
                return {}
        return {}
    if isinstance(value, (tuple, list)):
        try:
            return dict(value)
        except (TypeError, ValueError):
            return {}
    return None


class ChangeProjection:
    """A read-only view over a frozen projection, mapping or live node."""

    def __init__(self, value: Any):
        self.value = value
        self._params = _params_of(value)
        self._node = value if isinstance(value, BaseExpression) else None

    def get(self, name: str, default: Any = None) -> Any:
        if self._params is not None and name in self._params:
            return self._params[name]
        if self._node is not None:
            return getattr(self._node, name, default)
        return default

    @property
    def node(self) -> Optional[BaseExpression]:
        """The live expression node, when the projection handed one over."""
        return self._node

    @property
    def params(self) -> Dict[str, Any]:
        """The named fields, empty when the projection is opaque."""
        return dict(self._params or {})


def projection_params(value: Any) -> Dict[str, Any]:
    """Named fields of *value*, empty for an opaque ``repr`` projection."""
    return ChangeProjection(value).params


def projection_param(value: Any, name: str, default: Any = None) -> Any:
    """One named field of *value*."""
    return ChangeProjection(value).get(name, default)


def projection_node(value: Any) -> Optional[BaseExpression]:
    """The live expression node behind *value*, when there is one."""
    return ChangeProjection(value).node


def projection_name(value: Any) -> Optional[str]:
    """The name a constraint/index projection carries, or ``None``.

    A bare string is itself the name; a node or a frozen projection carries it
    under ``name``. Only a non-empty string counts -- an opaque ``repr`` value
    yields no name and lets the caller refuse instead of guessing one.
    """
    if isinstance(value, str):
        return value if value.strip() else None
    name = projection_param(value, "name")
    return name if isinstance(name, str) and name.strip() else None
