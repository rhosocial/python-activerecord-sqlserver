# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/trim.py
"""SQL Server's TRIM spelling: the direction is the function name.

SQL Server's ``TRIM`` has no ANSI ``TRIM(BOTH ... FROM ...)`` form at every
compatibility level. Up to 2019 (15.x) -- and in Azure Synapse Analytics -- the
only spelling is ``TRIM([characters FROM] string)``, which always trims both
ends and puts the character set *before* the operand. SQL Server 2022 (16.x)
added the ``LEADING`` / ``TRAILING`` / ``BOTH`` keywords, but only at database
compatibility level 160, so the ANSI default form the core renderer emits is
not portable even on the newest server. The mapping therefore keeps the
operand order SQL Server had first and encodes the direction in the name:

    BOTH     -> ``TRIM(chars FROM x)`` / ``TRIM(x)``
    LEADING  -> ``LTRIM(x)`` / ``LTRIM(x, chars)``
    TRAILING -> ``RTRIM(x)`` / ``RTRIM(x, chars)``

``LTRIM`` / ``RTRIM`` accept a second, characters argument only from 2022
(16.x) at compatibility level 160 as well; on an earlier server that form is
refused by the engine. This mixin does not attempt to version-gate: the
dialect has no mechanism for a per-expression capability switch, and the
rendering is recorded here instead.

Everything else about the node (the operands' parameters in order, the
optional alias) is the default's.
"""
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ...expression.advanced_functions import TrimExpression


class SQLServerTrimMixin:
    """Mixin rendering the TRIM family as SQL Server's TRIM/LTRIM/RTRIM."""

    _TRIM_FUNCTIONS = {"BOTH": "TRIM", "LEADING": "LTRIM", "TRAILING": "RTRIM"}

    def format_trim_expression(self, expr: "TrimExpression") -> Tuple[str, Tuple]:
        """Format a TRIM node in SQL Server's form.

        Args:
            expr: Trim expression exposing ``expr``, ``chars``, ``direction``
                and an optional ``alias``.

        Returns:
            Tuple of (SQL string, parameters tuple), carrying the operands'
            parameters in order.

        Raises:
            ValueError: ``expr.direction`` is not one of the three the node
                allows.
        """
        target_sql, target_params = expr.expr.to_sql()
        function = self._TRIM_FUNCTIONS.get(expr.direction)
        if function is None:
            raise ValueError(
                f"Unsupported trim direction {expr.direction!r}; expected one of "
                f"{sorted(self._TRIM_FUNCTIONS)}"
            )
        if expr.chars is not None:
            chars_sql, chars_params = expr.chars.to_sql()
            if function == "TRIM":
                # The one spelling that is not the shared operand order: SQL
                # Server's non-ANSI form puts the character set first.
                sql = f"TRIM({chars_sql} FROM {target_sql})"
                params = tuple(chars_params) + tuple(target_params)
            else:
                sql = f"{function}({target_sql}, {chars_sql})"
                params = tuple(target_params) + tuple(chars_params)
        else:
            sql = f"{function}({target_sql})"
            params = tuple(target_params)
        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"
        return sql, params


__all__ = ['SQLServerTrimMixin']
