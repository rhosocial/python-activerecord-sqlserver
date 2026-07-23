# tests/providers/fixtures/__init__.py
"""SQL Server-specific DDL expression fixtures for the testsuite providers.

Each module in this package exposes a ``TABLE_EXPRESSIONS`` mapping of
table name -> factory callable ``Callable[[DialectLike, str], CreateTableExpression]``.

The factory functions build :class:`CreateTableExpression` instances that emit
SQL Server-compatible DDL (INT IDENTITY / NVARCHAR / DATETIME2 / TINYINT / JSON).
The pre-existing ``.sql`` schema files under
``tests/rhosocial/activerecord_sqlserver_test/feature/<feature>/schema/``
remain as the authoritative reference for what the expressions here must
produce; they are simply no longer read at runtime by the providers.
"""
