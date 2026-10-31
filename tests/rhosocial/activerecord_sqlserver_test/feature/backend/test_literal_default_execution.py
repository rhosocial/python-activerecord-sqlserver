# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_literal_default_execution.py
"""Live confirmation that the dialect's DDL literals really execute.

The expression area asserts *what text the dialect writes*; this file asserts
that a server accepts that text and hands the same value back. It lives beside
the scenario-driven integration tests for exactly that reason -- the org rules
keep live connections out of the expression tests, and a DEFAULT clause is the
one place a literal is observable at all.

The sentinel comes first on purpose: a deliberately invalid statement must come
back REJECTED before any verdict from this file is trusted, then a CREATE TABLE
whose DEFAULT clauses embed the rendered literals is read back through
``INSERT ... DEFAULT VALUES`` and compared as Python values.

Written against the documented T-SQL grammar -- the ``0x<hex>`` constant form
and the string-to-UNIQUEIDENTIFIER / BIT conversions -- and not yet
server-verified: the scenario ports were refused while this was written, so a
reachable server is what confirms it.
"""

from rhosocial.activerecord.backend.expression.execution_testing import (
    ExecutionOutcome,
    classify_execution,
)


class TestLiteralDefaultsExecute:
    """The rendered literals as column DEFAULTs survive a read-back."""

    BINARY = b"\x01\x02"
    UUID_TEXT = "01234567-89ab-cdef-0123-456789abcdef"

    def test_sentinel_rejected_and_control_accepted(self, sqlserver_backend):
        """The classifier must see both answers before any verdict is trusted."""
        assert (
            classify_execution(sqlserver_backend, "THIS IS NOT SQL")
            is ExecutionOutcome.REJECTED
        )
        assert (
            classify_execution(sqlserver_backend, "SELECT 1")
            is ExecutionOutcome.ACCEPTED
        )

    def test_column_defaults_round_trip(self, sqlserver_backend):
        """The binary, UUID and boolean literals as DEFAULTs survive a read-back."""
        import uuid

        dialect = sqlserver_backend.dialect
        b_default = dialect.format_literal(self.BINARY)
        u_default = dialect.format_literal(uuid.UUID(self.UUID_TEXT))
        f_default = dialect.format_literal(True)

        table = "test_literal_defaults"
        sqlserver_backend.execute(f"""
            CREATE TABLE {table} (
                b VARBINARY(8) DEFAULT {b_default},
                u UNIQUEIDENTIFIER DEFAULT {u_default},
                f BIT DEFAULT {f_default}
            )
        """)
        try:
            sqlserver_backend.execute(f"INSERT INTO {table} DEFAULT VALUES")
            row = sqlserver_backend.fetch_one(
                f"SELECT b AS b, u AS u, f AS f FROM {table}"
            )
            assert row is not None
            assert bytes(row["b"]) == self.BINARY
            # A UNIQUEIDENTIFIER comes back in the server's own canonical
            # spelling, which is upper-case hex; the answer is parsed rather
            # than compared as text, so the casing is not part of what is
            # asserted and the value is what travels.
            assert uuid.UUID(str(row["u"])) == uuid.UUID(self.UUID_TEXT)
            assert bool(row["f"]) is True
        finally:
            sqlserver_backend.execute(f"DROP TABLE IF EXISTS {table}")
