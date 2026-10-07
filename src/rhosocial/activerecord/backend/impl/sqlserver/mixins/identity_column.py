# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/identity_column.py
"""SQL Server identity-column capability declarations and formatter.

SQL Server spells an identity column as a *property* of the column:
``IDENTITY(seed, increment)``. That is not the SQL-standard clause
``GENERATED {ALWAYS|BY DEFAULT} AS IDENTITY``, and the two carry different
parameter spaces. The dialect therefore declares exactly which parts of the
standard clause its own spelling can express:

* the mechanism itself (:meth:`supports_identity_column`) **is** this
  dialect's ``IDENTITY(seed, increment)`` -- measured to execute on SQL
  Server 2019 / 2022 / 2025;
* ``seed`` / ``increment`` are the two parameters the property takes;
* the generation mode ``ALWAYS`` and the sequence attributes
  MINVALUE / MAXVALUE / CYCLE / ORDER / CACHE have no spelling in the
  property at all. Every candidate spelling was measured refused by all
  three servers, so those probes answer ``False`` and the formatter refuses
  a request for them by name instead of silently dropping it.

``AUTO_INCREMENT`` is a different mechanism again -- a *parameterless* column
marker carried by ``AutoIncrementClause`` -- and SQL Server has no such
marker, so :meth:`supports_auto_increment_column` answers ``False``.
"""

from typing import TYPE_CHECKING, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.statements import IdentityClause


class SQLServerIdentityColumnMixin:
    """SQL Server's ``IDENTITY(seed, increment)`` identity column.

    The probes are the dialect's declaration of what its identity spelling
    can express; the formatter consults every one of them and fails closed.
    """

    def supports_identity_column(self) -> bool:
        """SQL Server accepts ``IDENTITY(seed, increment)`` at every version.

        The override in :meth:`format_identity_clause` renders SQL Server's
        own spelling, and that spelling is this dialect's identity
        expression -- not a fallback for the standard grammar, which every
        measured version refuses (2019 / 2022 / 2025).
        """
        return True

    def supports_identity_generation_always(self) -> bool:
        """SQL Server's identity property has no ``ALWAYS`` generation mode.

        ``GENERATED ALWAYS AS IDENTITY`` is refused by the server on
        2019 / 2022 / 2025 (measured), and appending ``ALWAYS`` to the
        property is refused too. Answering ``False`` makes the formatter
        refuse an ``ALWAYS`` request by name; the request is never
        downgraded to a bare ``IDENTITY(seed, increment)``.
        """
        return False

    def supports_identity_start(self) -> bool:
        """The identity property's first argument is the seed (start value)."""
        return True

    def supports_identity_increment(self) -> bool:
        """The identity property's second argument is the increment."""
        return True

    def supports_identity_minvalue(self) -> bool:
        """SQL Server's identity property has no MINVALUE option.

        Measured on 2019 / 2022 / 2025: every candidate spelling (standard
        ``MINVALUE``, ``NO MINVALUE``, ``WITH MINVALUE``) is refused.
        """
        return False

    def supports_identity_maxvalue(self) -> bool:
        """SQL Server's identity property has no MAXVALUE option.

        Measured on 2019 / 2022 / 2025: every candidate spelling (standard
        ``MAXVALUE``, ``NO MAXVALUE``, ``WITH MAXVALUE``) is refused.
        """
        return False

    def supports_identity_cycle(self) -> bool:
        """SQL Server's identity property has no CYCLE option.

        Measured on 2019 / 2022 / 2025: every candidate spelling (``CYCLE``,
        ``NO CYCLE``, ``WITH CYCLE``) is refused.
        """
        return False

    def supports_identity_order(self) -> bool:
        """SQL Server's identity property has no ORDER option.

        Measured on 2019 / 2022 / 2025: both candidate spellings (``ORDER``,
        ``NO ORDER``) are refused as syntax errors.
        """
        return False

    def supports_identity_cache(self) -> bool:
        """SQL Server's identity property has no CACHE option.

        Measured on 2019 / 2022 / 2025: both candidate spellings
        (``CACHE <n>``, ``NO CACHE``) are refused as syntax errors.
        """
        return False

    def supports_auto_increment_column(self) -> bool:
        """SQL Server has no bare ``AUTO_INCREMENT`` column marker.

        Its generated-value spelling is the parameterised identity property,
        a different mechanism from the parameterless marker. Answering
        ``False`` keeps ``AutoIncrementClause`` fail-closed: it refuses
        rather than rendering a token the server rejects.
        """
        return False

    def format_identity_clause(self, expr: "IdentityClause") -> Tuple[str, tuple]:
        """Render SQL Server's ``IDENTITY(seed, increment)``.

        Every gate fails closed and refuses by name rather than dropping the
        clause or an option:

        * :meth:`supports_identity_column` gates the clause as a whole;
        * :meth:`supports_identity_generation_always` gates ``ALWAYS`` (this
          dialect's property has no generation mode, so an ``ALWAYS`` request
          is refused, never silently rendered as the bare property);
        * :meth:`supports_identity_start` / ``_increment`` gate the seed and
          increment, the two parameters the property actually takes;
        * :meth:`supports_identity_minvalue` / ``_maxvalue`` / ``_cycle`` /
          ``_order`` / ``_cache`` gate the sequence attributes the property
          cannot spell.

        Each two-spelling option carries one parameter per spelling --
        ``cycle`` / ``no_cycle``, ``cache`` / ``no_cache``, ``order`` /
        ``no_order``. An unset pair renders nothing; an explicit spelling whose
        probe is ``False`` is refused naming the requested spelling. The
        refusal never falls through to the bare property, which would be a
        silent downgrade.

        Args:
            expr: The ``IdentityClause`` carrying the identity parameters.

        Returns:
            A ``(sql, params)`` tuple with a leading space.

        Raises:
            UnsupportedFeatureError: If the dialect cannot express the
                clause, the requested generation mode, or one of the
                requested options.
        """
        if not self.supports_identity_column():
            raise UnsupportedFeatureError(
                self.name,  # type: ignore[attr-defined]
                "IDENTITY column",
                f"{self.name} does not support IDENTITY columns.",  # type: ignore[attr-defined]
            )
        generation = (expr.generation or "BY DEFAULT").upper()
        if generation == "ALWAYS" and not self.supports_identity_generation_always():
            raise UnsupportedFeatureError(
                self.name,  # type: ignore[attr-defined]
                "IDENTITY GENERATED ALWAYS",
                f"{self.name} cannot express GENERATED ALWAYS for an identity "  # type: ignore[attr-defined]
                f"column; its IDENTITY property has no generation mode.",
            )
        if expr.start is not None:
            if not self.supports_identity_start():
                raise UnsupportedFeatureError(
                    self.name,  # type: ignore[attr-defined]
                    "IDENTITY START",
                    f"{self.name} does not support the START WITH identity option.",  # type: ignore[attr-defined]
                )
        if expr.increment is not None:
            if not self.supports_identity_increment():
                raise UnsupportedFeatureError(
                    self.name,  # type: ignore[attr-defined]
                    "IDENTITY INCREMENT",
                    f"{self.name} does not support the INCREMENT BY identity option.",  # type: ignore[attr-defined]
                )
        if expr.minvalue is not None:
            if not self.supports_identity_minvalue():
                raise UnsupportedFeatureError(
                    self.name,  # type: ignore[attr-defined]
                    "IDENTITY MINVALUE",
                    f"{self.name} does not support the MINVALUE identity option.",  # type: ignore[attr-defined]
                )
        if expr.maxvalue is not None:
            if not self.supports_identity_maxvalue():
                raise UnsupportedFeatureError(
                    self.name,  # type: ignore[attr-defined]
                    "IDENTITY MAXVALUE",
                    f"{self.name} does not support the MAXVALUE identity option.",  # type: ignore[attr-defined]
                )
        if expr.cycle or expr.no_cycle:
            if not self.supports_identity_cycle():
                raise UnsupportedFeatureError(
                    self.name,
                    "IDENTITY CYCLE",
                    f"{self.name} does not support the "
                    f"{'CYCLE' if expr.cycle else 'NO CYCLE'} identity option.",
                )
        if expr.cache is not None:
            if not self.supports_identity_cache():
                raise UnsupportedFeatureError(
                    self.name,
                    "IDENTITY CACHE",
                    f"{self.name} does not support the CACHE identity option.",
                )
        if expr.no_cache:
            if not self.supports_identity_cache():
                raise UnsupportedFeatureError(
                    self.name,
                    "IDENTITY CACHE",
                    f"{self.name} does not support the NO CACHE identity option.",
                )
        if expr.order or expr.no_order:
            if not self.supports_identity_order():
                raise UnsupportedFeatureError(
                    self.name,
                    "IDENTITY ORDER",
                    f"{self.name} does not support the "
                    f"{'ORDER' if expr.order else 'NO ORDER'} identity option.",
                )
        seed = expr.start if expr.start is not None else 1
        increment = expr.increment if expr.increment is not None else 1
        return f" IDENTITY({seed}, {increment})", ()
