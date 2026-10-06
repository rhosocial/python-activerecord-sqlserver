# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/sequence.py
"""SQL Server SEQUENCE capability mixin.

SQL Server 2012 introduced SEQUENCE objects. This mixin provides the capability
declarations that decide which sequence DDL a given version accepts, and the
``NEXT VALUE FOR`` expression formatter used by
``SQLServerNextValueForExpression``.
"""

from typing import TYPE_CHECKING, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Sequence

from .version_constants import SQL_SERVER_2012, SQL_SERVER_2016

if TYPE_CHECKING:  # pragma: no cover
    from ..expression.sequence import SQLServerNextValueForExpression


class SQLServerSequenceMixin:
    """SQL Server SEQUENCE / NEXT VALUE FOR implementation."""

    def supports_sequence_as_data_type(self) -> bool:
        """SQL Server sequences are not usable as column data types."""
        return False

    def format_next_value_for(
        self, expr: "SQLServerNextValueForExpression"
    ) -> Tuple[str, tuple]:
        """Format NEXT VALUE FOR expression (SQL Server 2012+).

        Args:
            expr: The ``SQLServerNextValueForExpression`` to render.

        Returns:
            Tuple of (SQL string, params tuple) such as
            ``(NEXT VALUE FOR [my_seq], ())``.
        """
        if self.version < SQL_SERVER_2012:  # type: ignore[attr-defined]
            raise UnsupportedFeatureError(
                self.name,  # type: ignore[attr-defined]
                "NEXT VALUE FOR",
                "requires SQL Server 2012+",
            )

        # The expression holds one flat name string, and
        # ``NEXT VALUE FOR dbo.my_seq`` is the documented spelling for a
        # schema-qualified sequence. The namespace is therefore read out of the
        # text once, into a Sequence object, and rendered from there -- the
        # formatter itself never re-derives which part is the schema.
        quoted = self.qualified_object_name_from_dotted(Sequence, expr.sequence_name)

        return f"NEXT VALUE FOR {quoted}", ()

    # --- Sequence capability declarations ---
    #
    # SQL Server 2012 introduced SEQUENCE. The master switch and every option
    # the engine spells are version-gated on that introduction; the options it
    # has no spelling for answer False at every version. Determined from the
    # CREATE/ALTER/DROP SEQUENCE (Transact-SQL) reference syntax:
    #
    #   CREATE: START WITH, INCREMENT BY, MINVALUE, MAXVALUE, CYCLE, CACHE
    #           -- no IF NOT EXISTS, no ORDER/NOORDER, no OWNED BY
    #   ALTER:  RESTART WITH, INCREMENT BY, MINVALUE, MAXVALUE, CYCLE, CACHE
    #           -- no START WITH, no ORDER/NOORDER, no OWNED BY
    #   DROP:   IF EXISTS applies from SQL Server 2016 (13.x) onwards
    #
    # The CACHE minimum of 2 and the cycling-sequence cache bound are value
    # constraints, not support questions; a probe answers whether the option
    # exists, so they are deliberately not answered here.

    def supports_sequence(self) -> bool:
        """SQL Server 2012+ has SEQUENCE objects."""
        return self.version >= SQL_SERVER_2012  # type: ignore[attr-defined]

    def supports_create_sequence(self) -> bool:
        """SQL Server 2012+ supports CREATE SEQUENCE."""
        return self.version >= SQL_SERVER_2012  # type: ignore[attr-defined]

    def supports_drop_sequence(self) -> bool:
        """SQL Server 2012+ supports DROP SEQUENCE."""
        return self.version >= SQL_SERVER_2012  # type: ignore[attr-defined]

    def supports_alter_sequence(self) -> bool:
        """SQL Server 2012+ supports ALTER SEQUENCE."""
        return self.version >= SQL_SERVER_2012  # type: ignore[attr-defined]

    def supports_sequence_if_not_exists(self) -> bool:
        """SQL Server has no CREATE SEQUENCE IF NOT EXISTS."""
        return False

    def supports_sequence_if_exists(self) -> bool:
        """DROP SEQUENCE IF EXISTS arrived in SQL Server 2016 (13.x)."""
        return self.version >= SQL_SERVER_2016  # type: ignore[attr-defined]

    def supports_sequence_start(self) -> bool:
        """CREATE SEQUENCE accepts START WITH from SQL Server 2012."""
        return self.version >= SQL_SERVER_2012  # type: ignore[attr-defined]

    def supports_sequence_increment(self) -> bool:
        """CREATE/ALTER SEQUENCE accept INCREMENT BY from SQL Server 2012."""
        return self.version >= SQL_SERVER_2012  # type: ignore[attr-defined]

    def supports_sequence_minvalue(self) -> bool:
        """CREATE/ALTER SEQUENCE accept MINVALUE from SQL Server 2012."""
        return self.version >= SQL_SERVER_2012  # type: ignore[attr-defined]

    def supports_sequence_maxvalue(self) -> bool:
        """CREATE/ALTER SEQUENCE accept MAXVALUE from SQL Server 2012."""
        return self.version >= SQL_SERVER_2012  # type: ignore[attr-defined]

    def supports_sequence_cycle(self) -> bool:
        """CREATE/ALTER SEQUENCE accept CYCLE / NO CYCLE from SQL Server 2012."""
        return self.version >= SQL_SERVER_2012  # type: ignore[attr-defined]

    def supports_sequence_cache(self) -> bool:
        """CREATE/ALTER SEQUENCE accept CACHE from SQL Server 2012."""
        return self.version >= SQL_SERVER_2012  # type: ignore[attr-defined]

    def supports_sequence_order(self) -> bool:
        """SQL Server has no ORDER / NOORDER sequence option."""
        return False

    def supports_sequence_owned_by(self) -> bool:
        """SQL Server has no OWNED BY sequence clause."""
        return False
