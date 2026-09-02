# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/trigger.py
"""SQL Server trigger DDL mixin.

T-SQL triggers use a syntax distinct from the SQL:1999 form rendered by the
core ``TriggerMixin``: the body is an ``AS BEGIN ... END`` batch rather than
``EXECUTE FUNCTION``. This mixin provides the capability switches and the
formatters used by ``SQLServerCreateTriggerExpression`` /
``SQLServerDropTriggerExpression``.
"""

from typing import Any, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from ..expression.ddl.trigger import (
        SQLServerCreateTriggerExpression,
        SQLServerDropTriggerExpression,
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
        return getattr(expr, "name", None) or getattr(expr, "trigger", "")

    def format_create_trigger_statement(
        self, expr: "SQLServerCreateTriggerExpression"
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
        if not hasattr(expr, "body"):
            raise UnsupportedFeatureError(
                self.name,  # type: ignore[attr-defined]
                "SQL:1999 CREATE TRIGGER",
                "Use SQLServerCreateTriggerExpression for T-SQL trigger DDL.",
            )
        name = self._get_trigger_name(expr)
        if not name:
            raise ValueError("trigger name is required")
        table = getattr(expr, "table", None) or getattr(expr, "table", None)
        if not table:
            raise ValueError("trigger table is required")

        timing = getattr(expr, "timing", "AFTER").upper()
        if timing not in _TRIGGER_TIMINGS:
            raise ValueError(f"timing must be one of {_TRIGGER_TIMINGS}, got {timing!r}")

        events = [event.upper() for event in (getattr(expr, "events", None) or [])]
        if not events:
            raise ValueError("at least one trigger event is required")
        for event in events:
            if event not in _TRIGGER_EVENTS:
                raise ValueError(f"event must be one of {_TRIGGER_EVENTS}, got {event!r}")
        if not getattr(expr, "body", None):
            raise ValueError("trigger body is required")

        parts = ["CREATE"]
        if getattr(expr, "or_alter", False):
            parts.append("OR ALTER")
        parts.append("TRIGGER")
        parts.append(self.format_identifier(name))  # type: ignore[attr-defined]
        parts.append("ON")
        parts.append(self.format_identifier(table))  # type: ignore[attr-defined]
        parts.append(timing)
        parts.append(", ".join(events))
        parts.append(f"AS BEGIN {expr.body} END;")
        return " ".join(parts), ()

    def format_drop_trigger_statement(
        self, expr: "SQLServerDropTriggerExpression"
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
        if getattr(expr, "if_exists", False) and self.version >= _SQL_SERVER_TRIGGER_IF_EXISTS_VERSION:  # type: ignore[attr-defined]
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(name))  # type: ignore[attr-defined]
        return " ".join(parts), ()
