# src/rhosocial/activerecord/backend/impl/sqlserver/mixins/memory_optimized.py
"""SQL Server In-Memory OLTP (memory-optimized table) mixin.

Memory-optimized tables were introduced in SQL Server 2014. Their DDL is
expressed through ``CREATE TABLE ... WITH (...)`` table options:

    CREATE TABLE t (...) WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_ONLY);
    CREATE TABLE t (... INDEX ix NONCLUSTERED HASH (id) WITH (BUCKET_COUNT = 100000))
        WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_AND_DATA);

This mixin provides the capability switch and the ``format_*`` helpers used
both standalone and from the dialect's ``format_create_table_statement``
path (via ``dialect_options``).
"""

from typing import Optional, Sequence

_SQL_SERVER_MEMORY_OPTIMIZED_VERSION = (12, 0, 0)

_DURABILITY_OPTIONS = ("SCHEMA_ONLY", "SCHEMA_AND_DATA")


class SQLServerMemoryOptimizedMixin:
    """SQL Server In-Memory OLTP capability and formatting implementation."""

    def supports_memory_optimized_tables(self) -> bool:
        """Memory-optimized tables require SQL Server 2014+."""
        return self.version >= _SQL_SERVER_MEMORY_OPTIMIZED_VERSION  # type: ignore[attr-defined]

    def format_memory_optimized_option(self, durability: str = "SCHEMA_ONLY") -> str:
        """Format the In-Memory OLTP table option clause (2014+).

        SQL Syntax:
            WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_ONLY)
            WITH (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_AND_DATA)

        Args:
            durability: Either ``SCHEMA_ONLY`` or ``SCHEMA_AND_DATA``.

        Returns:
            The ``WITH (...)`` table option clause.

        Raises:
            UnsupportedFeatureError: On SQL Server versions before 2014.
        """
        self.check_feature_support(  # type: ignore[attr-defined]
            "supports_memory_optimized_tables",
            "memory-optimized tables",
            "requires SQL Server 2014+ (In-Memory OLTP).",
        )
        durability = durability.upper()
        if durability not in _DURABILITY_OPTIONS:
            raise ValueError(
                f"durability must be one of {_DURABILITY_OPTIONS}, got {durability!r}"
            )
        return f"WITH (MEMORY_OPTIMIZED = ON, DURABILITY = {durability})"

    def format_hash_index_definition(
        self,
        columns: Sequence[str],
        bucket_count: int,
        name: Optional[str] = None,
        unique: bool = False,
    ) -> str:
        """Format an inline NONCLUSTERED HASH index definition (2014+).

        SQL Syntax:
            NONCLUSTERED HASH (id) WITH (BUCKET_COUNT = 100000)
            INDEX ix NONCLUSTERED HASH (id) WITH (BUCKET_COUNT = 100000)
            UNIQUE INDEX ix NONCLUSTERED HASH (id) WITH (BUCKET_COUNT = 100000)

        Args:
            columns: Index key column names.
            bucket_count: Number of buckets for the hash index.
            name: Optional index name (required inside CREATE TABLE bodies).
            unique: Whether the hash index enforces uniqueness.

        Returns:
            The inline hash index definition fragment.

        Raises:
            UnsupportedFeatureError: On SQL Server versions before 2014.
        """
        self.check_feature_support(  # type: ignore[attr-defined]
            "supports_memory_optimized_tables",
            "NONCLUSTERED HASH index",
            "requires SQL Server 2014+ (memory-optimized tables).",
        )
        if not columns:
            raise ValueError("at least one column is required for a hash index")
        if bucket_count is None or int(bucket_count) <= 0:
            raise ValueError("bucket_count must be a positive integer")

        parts = []
        if unique:
            parts.append("UNIQUE")
        if name:
            parts.append(f"INDEX {self.format_identifier(name)}")  # type: ignore[attr-defined]
        columns_str = ", ".join(
            self.format_identifier(col)  # type: ignore[attr-defined]
            for col in columns
        )
        parts.append(
            f"NONCLUSTERED HASH ({columns_str}) WITH (BUCKET_COUNT = {int(bucket_count)})"
        )
        return " ".join(parts)
