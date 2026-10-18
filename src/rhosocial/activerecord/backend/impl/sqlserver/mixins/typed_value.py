# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/typed_value.py
"""SQL Server's spellings for the value types whose literal form is its own.

SQL Server agrees with the base on NULL, numbers, strings and the quoted
ISO-8601 date/time forms, so nothing is overridden for those. Where T-SQL's
grammar differs from the base's portable spellings:

* **boolean** -- T-SQL's literal grammar has no ``TRUE``/``FALSE`` keywords:
  unquoted ``TRUE`` parses as an identifier, not a value. The type that
  plays the boolean's role is ``BIT``, whose constants are ``1`` and ``0``
  (the strings ``'TRUE'``/``'FALSE'`` convert to BIT, but a DDL position
  wants the numeric spelling). :meth:`format_literal` therefore intercepts
  the boolean branch and spells ``1``/``0``; the data position is
  untouched, because pyodbc binds ``True``/``False`` to BIT natively.
* **binary** -- ``0x0102``, the unquoted hexadecimal *constant* form from
  T-SQL's ``constant`` grammar. Quoting the bytes as text would store a
  string that reads back as the wrong type and the wrong length.
* **UUID** -- the bare quoted canonical text. ``UNIQUEIDENTIFIER`` accepts
  a string literal and converts it; there is no cast syntax to add and no
  UUID literal keyword.

**INTERVAL stays unimplemented on purpose.** SQL Server has no interval
type and no interval literal, so the core mixin's explicit
``NotImplementedError`` is the right answer: a DDL position that needs one
cannot be written for this engine. That is why this module defines no
``format_interval_value`` -- leaving the method absent is what makes the
absence structural, the same fail-closed choice the dialect makes for
features T-SQL has no grammar for.

Not yet server-verified: the scenario servers this repository tests against
(``127.0.0.1:11433/11434/11435``, the 2019/2022/2025 entries of
``tests/config/sqlserver_scenarios.yaml``) were unreachable while this
module was written -- each dial measured connection refused after ~31 s --
so the spellings above rest on the documented T-SQL grammar, and the live
round-trip cases in ``test_sqlserver_typed_values.py`` are waiting for a
reachable server to confirm them.
"""

from typing import TYPE_CHECKING, Any, Tuple

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.values import TypedValue


class SQLServerTypedValueMixin:
    """SQL Server's value literals.

    Stands alone rather than inheriting :class:`TypedValueMixin`, exactly
    like the SQLite and PostgreSQL mixins it mirrors: the dialect composes
    this class ahead of the core one, and these methods win by that
    position. Inheriting would put the base ahead of the other generic
    mixins and make the ordering the dialect has to reason about depend on
    this class instead.
    """

    def format_literal(self, value: Any) -> str:
        """A boolean inlines as ``1``/``0``; every other value is the base's.

        T-SQL has no ``TRUE``/``FALSE`` literal keywords -- ``BIT`` takes the
        numeric constants -- so the boolean branch is intercepted here rather
        than left to the base's portable spelling. The delegation keeps the
        base's three-level construction authoritative for everything else
        (NULL, numbers, dates, strings, the literal-construction protocol),
        so the two spellings cannot drift apart.

        The dialect composes this mixin ahead of ``SQLDialectBase`` in its
        base list; that position, not this definition, is what makes the
        intercept win.
        """
        if isinstance(value, bool):
            return "1" if value else "0"
        return super().format_literal(value)

    def format_binary_value(self, expr: "TypedValue") -> Tuple[str, tuple]:
        """A binary constant: ``0x0102``, unquoted uppercase hex.

        Rendered from the bytes the node holds rather than from the base64
        spelling the artifact carries: T-SQL cannot decode base64 in SQL, so
        the conversion has to happen somewhere, and the dialect is the only
        layer that knows which literal form its engine accepts.
        """
        if not type(expr).inline_params:
            return self._bind_value(expr)
        return f"0x{bytes(expr.value).hex().upper()}", ()

    def format_uuid_value(self, expr: "TypedValue") -> Tuple[str, tuple]:
        """A UUID as quoted text -- ``UNIQUEIDENTIFIER`` converts strings."""
        if not type(expr).inline_params:
            return self._bind_value(expr)
        return self.format_literal(str(expr.value)), ()


__all__ = ["SQLServerTypedValueMixin"]
