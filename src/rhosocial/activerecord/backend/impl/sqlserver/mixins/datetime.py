# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/datetime.py
from typing import Any, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from ..dialect import SQLServerDialect


class SQLServerDateTimeMixin:
    """SQL Server datetime function implementations (DATEADD, DATEDIFF, DATETRUNC)."""

    def format_now_function(self, expr: "Any") -> Tuple[str, tuple]:
        """``NOW()`` in T-SQL is ``SYSDATETIME()``.

        A precision argument has no spelling here -- ``SYSDATETIME()`` takes
        none -- so it is refused rather than silently dropped.
        """
        if expr.precision is not None:
            raise UnsupportedFeatureError(
                self.name,
                "NOW with a precision",
                "SYSDATETIME() takes no precision argument.",
            )
        return self.apply_alias("SYSDATETIME()", (), expr)

    def format_current_date_function(self, expr: "Any") -> Tuple[str, tuple]:
        """``CURRENT_DATE`` in T-SQL is ``CAST(GETDATE() AS DATE)``.

        A precision argument has no spelling here, so it is refused rather
        than silently dropped.
        """
        if expr.precision is not None:
            raise UnsupportedFeatureError(
                self.name,
                "CURRENT_DATE with a precision",
                "CAST(GETDATE() AS DATE) takes no precision argument.",
            )
        return self.apply_alias("CAST(GETDATE() AS DATE)", (), expr)

    def format_current_time_function(self, expr: "Any") -> Tuple[str, tuple]:
        """``CURRENT_TIME`` in T-SQL is ``CAST(GETDATE() AS TIME)``.

        A precision argument has no spelling here, so it is refused rather
        than silently dropped.
        """
        if expr.precision is not None:
            raise UnsupportedFeatureError(
                self.name,
                "CURRENT_TIME with a precision",
                "CAST(GETDATE() AS TIME) takes no precision argument.",
            )
        return self.apply_alias("CAST(GETDATE() AS TIME)", (), expr)

    def format_date_trunc_expression(self, expr: "Any") -> Tuple[str, tuple]:
        source_sql, source_params = expr.source.to_sql()
        field = expr.field.value.upper()
        if field in {"YEAR", "MONTH", "DAY", "HOUR", "MINUTE", "SECOND"}:
            sql = f"DATETRUNC({field}, {source_sql})"
        else:
            raise UnsupportedFeatureError(self.name, f"date_trunc({expr.field.value})")
        return self.apply_alias(sql, source_params, expr)

    def format_interval_expression(self, expr: "Any") -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(
            self.name,
            "standalone INTERVAL expression",
            "Use date_add() or date_sub() for SQL Server date arithmetic.",
        )

    def format_datetime_add_expression(self, expr: "Any") -> Tuple[str, tuple]:
        source_sql, source_params = expr.source.to_sql()
        unit = expr.interval.unit.value.upper()
        sql = f"DATEADD({unit}, {self.p()}, {source_sql})"
        return self.apply_alias(
            sql, (expr.interval.value,) + source_params, expr
        )

    def format_datetime_subtract_expression(self, expr: "Any") -> Tuple[str, tuple]:
        source_sql, source_params = expr.source.to_sql()
        unit = expr.interval.unit.value.upper()
        sql = f"DATEADD({unit}, {self.p()}, {source_sql})"
        return self.apply_alias(
            sql, (-expr.interval.value,) + source_params, expr
        )

    def format_datetime_diff_expression(self, expr: "Any") -> Tuple[str, tuple]:
        start_sql, start_params = expr.start.to_sql()
        end_sql, end_params = expr.end.to_sql()
        sql = f"DATEDIFF({expr.unit.value.upper()}, {start_sql}, {end_sql})"
        return self.apply_alias(sql, start_params + end_params, expr)
