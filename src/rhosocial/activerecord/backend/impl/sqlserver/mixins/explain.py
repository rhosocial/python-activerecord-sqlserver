# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/explain.py
"""SQL Server EXPLAIN (SHOWPLAN/STATISTICS) capabilities and formatting.

SQL Server has no ``EXPLAIN`` statement and no ``EXPLAIN FORMAT`` clause: a
plan is obtained by switching a session setting on (``SET SHOWPLAN_TEXT`` /
``SET SHOWPLAN_XML``) or by enabling statistics output (``SET STATISTICS
PROFILE`` / ``SET STATISTICS XML``). The switches below therefore describe
which of those *settings* this dialect can drive, not a format vocabulary the
engine accepts on a statement.
"""

from typing import Any, Callable, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.statements import ExplainStatement


class SQLServerExplainMixin:
    """SQL Server EXPLAIN (SHOWPLAN/STATISTICS) implementation."""

    def supports_explain_analyze(self) -> bool:
        """SQL Server uses STATISTICS PROFILE for actual execution."""
        return True

    def supports_explain_verbose(self) -> bool:
        """SHOWPLAN_ALL is more detailed, but VERBOSE is not an option here."""
        return False

    def supports_explain_costs(self) -> bool:
        """Plan cost estimates are always shown; COSTS OFF has no equivalent."""
        return False

    def supports_explain_buffers(self) -> bool:
        """STATISTICS IO is not a BUFFERS option of EXPLAIN."""
        return False

    def supports_explain_timing(self) -> bool:
        """STATISTICS TIME is not a TIMING option of EXPLAIN."""
        return False

    def supports_explain_settings(self) -> bool:
        """SQL Server has no SETTINGS option."""
        return False

    def supports_explain_wal(self) -> bool:
        """SQL Server has no WAL concept."""
        return False

    def supports_explain_format_text(self) -> bool:
        """``SET SHOWPLAN_TEXT ON`` renders a text plan."""
        return True

    def supports_explain_format_xml(self) -> bool:
        """``SET SHOWPLAN_XML ON`` renders an XML plan."""
        return True

    def supports_explain_format_json(self) -> bool:
        """SQL Server has no JSON plan format."""
        return False

    def supports_explain_format_yaml(self) -> bool:
        """SQL Server has no YAML plan format."""
        return False

    def supports_explain_format_tree(self) -> bool:
        """SQL Server has no TREE plan format."""
        return False

    def supports_explain_format_traditional(self) -> bool:
        """SQL Server has no TRADITIONAL plan format."""
        return False

    def _format_switch(self, format_name: str) -> Optional[Callable[[], bool]]:
        """The switch that answers for an ``ExplainFormat`` member name."""
        return {
            "TEXT": self.supports_explain_format_text,
            "XML": self.supports_explain_format_xml,
            "JSON": self.supports_explain_format_json,
            "YAML": self.supports_explain_format_yaml,
            "TREE": self.supports_explain_format_tree,
            "TRADITIONAL": self.supports_explain_format_traditional,
        }.get(format_name)

    def _reject_unsupported_options(self, options: Any) -> None:
        """Raise when an option is requested that no T-SQL setting can honour.

        SQL Server drives plans through ``SET`` settings rather than EXPLAIN
        options, so an option this dialect cannot map must fail here instead of
        being silently dropped from the rendered batch.
        """
        if not getattr(options, "costs", True) and not self.supports_explain_costs():
            raise UnsupportedFeatureError(
                self.name,
                "EXPLAIN COSTS OFF",
                "SQL Server always includes cost estimates in a showplan.",
            )
        if getattr(options, "buffers", False) and not self.supports_explain_buffers():
            raise UnsupportedFeatureError(
                self.name,
                "EXPLAIN BUFFERS",
                "SQL Server reports I/O with SET STATISTICS IO, not an EXPLAIN option.",
            )
        if (
            getattr(options, "timing", False)
            and getattr(options, "analyze", False)
            and not self.supports_explain_timing()
        ):
            raise UnsupportedFeatureError(
                self.name,
                "EXPLAIN TIMING",
                "SQL Server reports timing with SET STATISTICS TIME, not an EXPLAIN option.",
            )
        if getattr(options, "verbose", False) and not self.supports_explain_verbose():
            raise UnsupportedFeatureError(
                self.name,
                "EXPLAIN VERBOSE",
                "Use SET SHOWPLAN_ALL for the detailed plan instead.",
            )
        if getattr(options, "settings", False) and not self.supports_explain_settings():
            raise UnsupportedFeatureError(self.name, "EXPLAIN SETTINGS")
        if getattr(options, "wal", False) and not self.supports_explain_wal():
            raise UnsupportedFeatureError(self.name, "EXPLAIN WAL")

    def format_explain_statement(self, expr: "ExplainStatement") -> Tuple[str, tuple]:
        """
        Format EXPLAIN for SQL Server.

        SQL Server uses:
        - SET SHOWPLAN_XML ON (estimated plan)
        - SET STATISTICS PROFILE ON (actual plan with statistics)
        - SET STATISTICS XML ON (actual plan in XML)

        Raises:
            UnsupportedFeatureError: an EXPLAIN option was requested that no
                T-SQL setting can render (see ``supports_explain_*``).
        """
        statement_sql, statement_params = expr.statement.to_sql()
        options = expr.options

        if options is None:
            return f"SET SHOWPLAN_TEXT ON; {statement_sql}", statement_params

        analyze = bool(options.analyze) or (
            getattr(getattr(options, "type", None), "name", None) == "ANALYZE"
        )
        if analyze and not self.supports_explain_analyze():
            raise UnsupportedFeatureError(self.name, "EXPLAIN ANALYZE")

        format_name = options.format.name if options.format is not None else None
        if format_name is not None:
            switch = self._format_switch(format_name)
            if switch is None or not switch():
                raise UnsupportedFeatureError(
                    self.name,
                    f"EXPLAIN FORMAT {format_name}",
                )

        self._reject_unsupported_options(options)

        if analyze:
            if format_name == "XML":
                return (
                    f"SET STATISTICS XML ON; {statement_sql}; SET STATISTICS XML OFF",
                    statement_params,
                )
            return (
                f"SET STATISTICS PROFILE ON; {statement_sql}; SET STATISTICS PROFILE OFF",
                statement_params,
            )

        if format_name == "XML":
            return f"SET SHOWPLAN_XML ON; {statement_sql}", statement_params

        return f"SET SHOWPLAN_TEXT ON; {statement_sql}", statement_params
