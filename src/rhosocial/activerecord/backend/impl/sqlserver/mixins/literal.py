# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/literal.py
"""SQL Server's tier-2 value literals.

``SQLDialectBase.format_literal`` is the single entry point for writing a value
as SQL text, and it resolves in three tiers: the portable scalars it knows, the
types a backend spells for itself, and the literal-construction protocol. This
module is SQL Server's second tier. T-SQL differs from the portable spellings on
three types and no more:

* **bool** becomes ``1`` / ``0``. T-SQL's literal grammar has no ``TRUE`` /
  ``FALSE`` keywords -- unquoted ``TRUE`` parses as an identifier, not a
  value -- and the type that plays the boolean's role is ``BIT``, whose
  constants are numeric. (The strings ``'TRUE'`` / ``'FALSE'`` convert to
  BIT, but a literal position wants the numeric spelling.) The data
  position is untouched: pyodbc binds ``True`` / ``False`` to BIT natively,
  and this branch only ever runs for the text a literal position asks for.
* **bytes** becomes the unquoted hexadecimal constant, ``0x0102`` with
  uppercase hex -- the ``constant`` grammar's binary form. Quoting the bytes
  as text would store a string that reads back as the wrong type and the
  wrong length.
* **UUID** becomes the quoted canonical text: ``UNIQUEIDENTIFIER`` accepts a
  string literal and converts it, and there is no cast syntax to add.

**INTERVAL stays absent on purpose.** SQL Server has no interval type and no
interval literal, so the base implementation's explicit refusal is the right
answer: a position that needs an interval literal cannot be written for this
engine. Leaving the branch out is what makes the absence structural -- a
``timedelta`` reaches the base's ladder and fails loudly naming its type.

Not yet server-verified: the scenario servers this repository tests against
(``127.0.0.1:11433/11434/11435``, the 2019/2022/2025 entries of
``tests/config/sqlserver_scenarios.yaml``) were unreachable while this module
was written -- each dial measured connection refused after ~31 s -- so the
spellings above rest on the documented T-SQL grammar, and the live round-trip
cases in ``test_sqlserver_typed_values.py`` are waiting for a reachable server
to confirm them.
"""

import uuid
from typing import Any


class SQLServerLiteralValueMixin:
    """SQL Server's tier-2 branches of :meth:`format_literal`.

    Stands alone rather than inheriting the base, exactly like the SQLite
    mixin it mirrors: the dialect composes this class ahead of
    ``SQLDialectBase`` -- a mixin placed after the class it overrides never
    wins -- and every value this branch does not claim falls through to the
    base implementation, which is where the portable forms and the
    literal-construction protocol live.
    """

    def format_literal(self, value: Any) -> str:
        """Render *value* as inline SQL text, SQL Server's spelling where it has one.

        Args:
            value: The host value to write into the statement.

        Returns:
            The escaped literal text, without a bind parameter.

        Raises:
            TypeError: The base implementation refuses a type SQL Server has
                no literal form for -- ``timedelta`` among them -- and this
                is the same refusal.
        """
        # bool first: it is an int subclass, so the numeric branch would
        # otherwise claim it.
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (bytes, bytearray)):
            return f"0x{bytes(value).hex().upper()}"
        if isinstance(value, uuid.UUID):
            return self.format_literal(str(value))
        return super().format_literal(value)


__all__ = ["SQLServerLiteralValueMixin"]
