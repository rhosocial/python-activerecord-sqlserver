# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/sequence.py
"""SQL Server SEQUENCE capability mixin.

SQL Server 2012 introduced SEQUENCE objects. This mixin provides capability
detection and the ``NEXT VALUE FOR`` expression formatter used by
``SQLServerNextValueForExpression``.
"""

from typing import Any, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Sequence


_SQL_SERVER_NEXT_VALUE_FOR_VERSION = (11, 0, 0)


class SQLServerSequenceMixin:
    """SQL Server SEQUENCE / NEXT VALUE FOR implementation."""

    def supports_sequence_as_data_type(self) -> bool:
        """SQL Server sequences are not usable as column data types."""
        return False

    def format_next_value_for(self, sequence: Any) -> Tuple[str, tuple]:
        """Format NEXT VALUE FOR expression (SQL Server 2012+).

        Args:
            sequence: A ``SQLServerNextValueForExpression`` or a plain
                sequence name string.

        Returns:
            Tuple of (SQL string, params tuple) such as
            ``(NEXT VALUE FOR [my_seq], ())``.
        """
        if self.version < _SQL_SERVER_NEXT_VALUE_FOR_VERSION:  # type: ignore[attr-defined]
            raise UnsupportedFeatureError(
                self.name,  # type: ignore[attr-defined]
                "NEXT VALUE FOR",
                "requires SQL Server 2012+",
            )

        sequence_name = getattr(sequence, "sequence_name", None)
        if sequence_name is None:
            sequence_name = str(sequence)

        # The sequence expressions hold one flat name string, and
        # ``NEXT VALUE FOR dbo.my_seq`` is the documented spelling for a
        # schema-qualified sequence. The namespace is therefore read out of the
        # text once, into a Sequence object, and rendered from there -- the
        # formatter itself never re-derives which part is the schema.
        quoted = self.qualified_object_name_from_dotted(Sequence, sequence_name)

        return f"NEXT VALUE FOR {quoted}", ()

    # --- Sequence capability declarations (moved from dialect.py) ---

    def supports_create_sequence(self) -> bool:
        """SQL Server 2012+ supports SEQUENCE objects."""
        return self.version >= _SQL_SERVER_NEXT_VALUE_FOR_VERSION  # type: ignore[attr-defined]

    def supports_drop_sequence(self) -> bool:
        """SQL Server 2012+ supports DROP SEQUENCE."""
        return self.version >= _SQL_SERVER_NEXT_VALUE_FOR_VERSION  # type: ignore[attr-defined]
