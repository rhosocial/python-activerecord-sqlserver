# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/introspection.py
"""Which catalogue questions SQL Server can answer.

This backend introspects fully -- catalog views, ``sys.tables``/``sys.columns``/
``sys.indexes``, ``OBJECT_DEFINITION`` for routine bodies, and the live CLI is
covered by tests against a real server. It nevertheless reported
``supports_introspection() = False`` and every per-kind answer with it, because
it never declared them and inherited core's default of ``False``.

That default is conservative on purpose: a backend that cannot answer says so,
and a caller gating on the switch is not misled. The cost is the opposite error
-- a backend that *can* answer but says it cannot, which is what happened here.
A caller gating on these switches would have concluded SQL Server has no
introspection at all, while its CLI offered twelve types.

So the switches are declared, one per family, and each says what SQL Server
actually answers. They are placed in a mixin of their own, because this
backend keeps its capability answers next to the concern they describe, and
because a caller should be able to find "what can I ask" in one place.

The mixin precedes the core bundle it overrides in ``SQLServerDialect``'s base
list; see the comment there for why the position matters.
"""

__all__ = ["SQLServerIntrospectionMixin"]


class SQLServerIntrospectionMixin:
    """SQL Server's answers to the shared catalogue capability questions."""

    def supports_introspection(self) -> bool:
        """SQL Server introspects through its catalog views."""

    def supports_procedure_introspection(self) -> bool:
        """SQL Server answers for its stored procedures from ``sys.procedures``.

        The capability for the ``introspect procedures`` family, with
        bodies from ``OBJECT_DEFINITION``."""
        return True
        return True

    def supports_database_info(self) -> bool:
        """``sys.databases`` and ``@@VERSION`` answer for the instance."""
        return True

    def supports_table_introspection(self) -> bool:
        """``sys.tables`` joined to ``sys.schemas``."""
        return True

    def supports_column_introspection(self) -> bool:
        """``sys.columns``, which also carries identity and nullable."""
        return True

    def supports_index_introspection(self) -> bool:
        """``sys.indexes`` with ``sys.index_columns`` for the ordering."""
        return True

    def supports_foreign_key_introspection(self) -> bool:
        """``sys.foreign_keys`` and ``sys.foreign_key_columns``."""
        return True

    def supports_view_introspection(self) -> bool:
        """``sys.views``, with the definition from ``OBJECT_DEFINITION``."""
        return True

    def supports_trigger_introspection(self) -> bool:
        """``sys.triggers``, which also distinguishes INSTEAD OF."""
        return True
