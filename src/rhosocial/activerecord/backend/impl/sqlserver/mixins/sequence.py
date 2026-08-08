# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/sequence.py
"""SQL Server SEQUENCE capability mixin.

SQL Server 2012 introduced SEQUENCE objects. This mixin provides capability
detection and the ``NEXT VALUE FOR`` expression formatter used by
``SQLServerNextValueForExpression``.
"""

from typing import Any

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


_SQL_SERVER_NEXT_VALUE_FOR_VERSION = (11, 0, 0)


class SQLServerSequenceMixin:
    """SQL Server SEQUENCE / NEXT VALUE FOR implementation."""

    def supports_sequence_as_data_type(self) -> bool:
        """SQL Server sequences are not usable as column data types."""
        return False

    def format_next_value_for(self, sequence: Any) -> str:
        """Format NEXT VALUE FOR expression (SQL Server 2012+).

        Args:
            sequence: A ``SQLServerNextValueForExpression`` or a plain
                sequence name string.

        Returns:
            SQL string such as ``NEXT VALUE FOR [my_seq]``.
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

        if "." in sequence_name:
            quoted = ".".join(
                self.format_identifier(part) for part in sequence_name.split(".")  # type: ignore[attr-defined]
            )
        else:
            quoted = self.format_identifier(sequence_name)  # type: ignore[attr-defined]

        return f"NEXT VALUE FOR {quoted}"
