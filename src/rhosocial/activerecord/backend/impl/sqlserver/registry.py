# src/rhosocial/activerecord/backend/impl/sqlserver/registry.py
"""The SQL Server backend's expression registry.

SQL Server owns the kinds its own expression package declares. It does not own
core's kinds and it does not list any other backend's: the overlap with core is
expressed by composition — ``base=core_registry()`` — and there is no
cross-backend merge anywhere.

Every class in this package names its one dialect formatter through
``format_method``, which is what the assembly walk admits a class by; there is
no second registration path, so a node that stops naming a formatter drops out
of the table instead of being readmitted by hand.

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
        built.freeze()
        _backend_registry = built
    return _backend_registry
