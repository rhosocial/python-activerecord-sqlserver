# src/rhosocial/activerecord/backend/impl/sqlserver/registry.py
"""The SQL Server backend's expression registry.

SQL Server owns the kinds its own expression package declares. It does not own
core's kinds and it does not list any other backend's: the overlap with core is
expressed by composition — ``base=core_registry()`` — and there is no
cross-backend merge anywhere.

The registry is built on first use, cached, and frozen. Freezing is what lets
the dialect hand the same table to every reader without one caller's
registration changing what another caller resolves.
"""

from rhosocial.activerecord.backend.expression.registry import ExpressionRegistry
from rhosocial.activerecord.backend.expression.serialization import (
    core_registry,
    registry_for_packages,
)

#: The SQL Server backend's own expression package.
_SQLSERVER_EXPRESSION_PACKAGE = "rhosocial.activerecord.backend.impl.sqlserver.expression"

_backend_registry = None


def _register_direct_renderers(registry: ExpressionRegistry) -> None:
    """Register package nodes that render through their own ``to_sql()``.

    The assembly walk admits a class only when it names a dialect formatter
    (``format_method``); a node that renders by overriding ``to_sql()`` names
    none, so the walk skips it. Such a node is still a SQL Server kind — this
    package owns it and the artifact matrix round-trips it — so the owner
    registers it here rather than leaving a shipped class unreadable.

    Only concrete classes this package defines are considered, and
    ``REGISTER_BY_DEFAULT`` keeps the raw-SQL opt-outs out exactly as the walk
    does. A class that also declares ``format_method`` is already in the table;
    re-registering it is a no-op.
    """
    import importlib
    import inspect
    import pkgutil

    from rhosocial.activerecord.backend.expression.bases import BaseExpression

    pkg = importlib.import_module(_SQLSERVER_EXPRESSION_PACKAGE)
    for _, modname, _ in pkgutil.walk_packages(
        path=pkg.__path__, prefix=_SQLSERVER_EXPRESSION_PACKAGE + ".", onerror=lambda x: None
    ):
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        for name in dir(mod):
            obj = getattr(mod, name, None)
            if not isinstance(obj, type) or obj.__module__ != modname:
                continue
            if (
                issubclass(obj, BaseExpression)
                and obj is not BaseExpression
                and not inspect.isabstract(obj)
                and getattr(obj, "REGISTER_BY_DEFAULT", False)
                and "to_sql" in vars(obj)
            ):
                registry.register_node(obj)


def backend_registry() -> ExpressionRegistry:
    """SQL Server's registry: core's kinds plus SQL Server's own, frozen and cached.

    Returns:
        The frozen registry ``SQLServerDialect.artifact_registry()`` exposes.
    """
    global _backend_registry
    if _backend_registry is None:
        # Build into a local and publish only on success: a half-populated
        # instance cached under the module global would make every later call
        # fail with a confusing "no such kind" instead of the real cause.
        built = registry_for_packages(
            _SQLSERVER_EXPRESSION_PACKAGE,
            base=core_registry(),
            freeze=False,
        )
        _register_direct_renderers(built)
        built.freeze()
        _backend_registry = built
    return _backend_registry
