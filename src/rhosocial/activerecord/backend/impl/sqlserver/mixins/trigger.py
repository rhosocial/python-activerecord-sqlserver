# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/trigger.py
"""SQL Server trigger DDL mixin.

T-SQL triggers use a syntax distinct from the SQL:1999 form rendered by the
core ``TriggerMixin``: the body is an ``AS BEGIN ... END`` batch rather than
``EXECUTE FUNCTION``. This mixin provides the capability switches and the
formatters used by ``SQLServerCreateTriggerStatement`` /
``SQLServerDropTriggerStatement``.
"""

from typing import Any, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Table, Trigger

if TYPE_CHECKING:
    from ..expression.ddl.trigger import (
        SQLServerCreateTriggerStatement,
        SQLServerDropTriggerStatement,
    )


_SQL_SERVER_TRIGGER_VERSION = (9, 0, 0)

_SQL_SERVER_TRIGGER_IF_EXISTS_VERSION = (13, 0, 0)

_TRIGGER_TIMINGS = ("AFTER", "INSTEAD OF")

_TRIGGER_EVENTS = ("INSERT", "UPDATE", "DELETE")


class SQLServerTriggerDdlMixin:
    """SQL Server trigger capability and formatting implementation."""

    def supports_trigger(self) -> bool:
        """Triggers are supported since SQL Server 2005."""
        return self.version >= _SQL_SERVER_TRIGGER_VERSION  # type: ignore[attr-defined]

    def supports_create_trigger(self) -> bool:
        """CREATE TRIGGER is supported since SQL Server 2005."""
        return self.version >= _SQL_SERVER_TRIGGER_VERSION  # type: ignore[attr-defined]

    def supports_drop_trigger(self) -> bool:
        """DROP TRIGGER is supported since SQL Server 2005."""
        return self.version >= _SQL_SERVER_TRIGGER_VERSION  # type: ignore[attr-defined]

    def _get_trigger_name(self, expr: Any) -> str:
        # Every T-SQL trigger expression names itself through its declared
        # ``name`` field; the shadowed SQL:1999 statements have no such field
        # and fail here explicitly rather than reading as an empty name.
        return expr.name

    def format_create_trigger_statement(
        self, expr: "SQLServerCreateTriggerStatement"
    ) -> Tuple[str, tuple]:
        """Format CREATE TRIGGER for SQL Server (2005+).

        SQL Syntax:
            CREATE [OR ALTER] TRIGGER [schema.]name
            ON [table] [AFTER | INSTEAD OF] {INSERT | UPDATE | DELETE}
            AS BEGIN <body> END;

        Args:
            expr: The trigger expression. ``timing`` is either ``AFTER`` or
                ``INSTEAD OF``; ``events`` is a list of ``INSERT``/``UPDATE``/
                ``DELETE``; ``body`` is passed through verbatim.
        """
        self.check_feature_support(  # type: ignore[attr-defined]
            "supports_create_trigger",
            "CREATE TRIGGER",
            "requires SQL Server 2005+.",
        )
        # The T-SQL form is rendered from this dialect's own trigger node; the
        # SQL:1999 statement (no raw ``body`` -- it names a function instead)
        # is refused by class rather than probed for the field.
        from ..expression.ddl.trigger import SQLServerCreateTriggerStatement

        if not isinstance(expr, SQLServerCreateTriggerStatement):
            raise UnsupportedFeatureError(
                self.name,  # type: ignore[attr-defined]
                "SQL:1999 CREATE TRIGGER",
                "Use SQLServerCreateTriggerStatement for T-SQL trigger DDL.",
            )
        name = self._get_trigger_name(expr)
        if not name:
            raise ValueError("trigger name is required")
        table = expr.table
        if not table:
            raise ValueError("trigger table is required")

        timing = expr.timing.upper()
        if timing not in _TRIGGER_TIMINGS:
            raise ValueError(f"timing must be one of {_TRIGGER_TIMINGS}, got {timing!r}")

        events = [event.upper() for event in (expr.events or [])]
        if not events:
            raise ValueError("at least one trigger event is required")
        for event in events:
            if event not in _TRIGGER_EVENTS:
                raise ValueError(f"event must be one of {_TRIGGER_EVENTS}, got {event!r}")
        if not expr.body:
            raise ValueError("trigger body is required")

        parts = ["CREATE"]
        if expr.or_alter:
            parts.append("OR ALTER")
        parts.append("TRIGGER")
        # A trigger and the table it hangs off are both schema objects; a
        # trigger lives in the same schema as its table, so both names go
        # through the one qualified-name entry point.
        parts.append(
            self.qualified_object_name_from_dotted(Trigger, name, schema_name=expr.schema)
        )
        parts.append("ON")
        parts.append(self.qualified_object_name(Table, table, schema_name=expr.schema))
        parts.append(timing)
        parts.append(", ".join(events))
        parts.append(f"AS BEGIN {expr.body} END;")
        return " ".join(parts), ()

    def format_drop_trigger_statement(
        self, expr: "SQLServerDropTriggerStatement"
    ) -> Tuple[str, tuple]:
        """Format DROP TRIGGER for SQL Server (2005+).

        SQL Syntax:
            DROP TRIGGER [IF EXISTS] [schema.]name;

        T-SQL DROP TRIGGER does not accept an ON table clause; ``IF EXISTS``
        is rendered only on SQL Server 2016+.
        """
        self.check_feature_support(  # type: ignore[attr-defined]
            "supports_drop_trigger",
            "DROP TRIGGER",
            "requires SQL Server 2005+.",
        )
        name = self._get_trigger_name(expr)
        if not name:
            raise ValueError("trigger name is required")

        parts = ["DROP", "TRIGGER"]
        if expr.if_exists and self.version >= _SQL_SERVER_TRIGGER_IF_EXISTS_VERSION:  # type: ignore[attr-defined]
            parts.append("IF EXISTS")
        parts.append(
            self.qualified_object_name_from_dotted(Trigger, name, schema_name=expr.schema)
        )
        return " ".join(parts), ()

    # --- Additional trigger capability declarations (moved from dialect.py) ---

    def supports_instead_of_trigger(self) -> bool:
        """SQL Server supports INSTEAD OF triggers."""
        return True

    def supports_statement_trigger(self) -> bool:
        """SQL Server supports FOR EACH STATEMENT triggers."""
        return True

    def supports_trigger_referencing(self) -> bool:
        """SQL Server supports referencing OLD and NEW via inserted/deleted tables."""
        return True

    def supports_trigger_when(self) -> bool:
        """SQL Server supports WHEN condition in triggers (IF clause)."""
        return True
