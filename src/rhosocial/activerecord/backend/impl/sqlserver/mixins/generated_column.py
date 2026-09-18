# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/generated_column.py


class SQLServerGeneratedColumnMixin:
    """SQL Server computed column capability declarations."""

    def supports_generated_column(self) -> bool:
        """SQL Server supports computed columns."""
        return True

    def supports_generated_columns(self) -> bool:
        """Whether generated (computed) columns are supported."""
        return self.supports_generated_column()

    def supports_stored_generated_columns(self) -> bool:
        """SQL Server supports PERSISTED computed columns."""
        return True

    def supports_virtual_generated_columns(self) -> bool:
        """SQL Server computed columns are virtual by default."""
        return True
