# tests/rhosocial/activerecord_sqlserver_test/feature/backend/execute/introspection/test_introspection_data_profile.py
"""The data-profile family, measured against a real server.

Rendering these statements proves only that they are well-formed. What needs
checking is whether SQL Server accepts them, and whether the arithmetic the
parser performs -- ``null_count / row_count`` into a fraction, ``COUNT(DISTINCT
...)`` into a count, the two endpoints out of the union, the ``source`` label
carried through -- lands on values a hand count agrees with. That is only
answerable against a server.

The table is a hundred rows, built so every figure is arithmetic rather than
guesswork:

    id      INT PRIMARY KEY        i, unique             -> 100 distinct, no nulls
    code    NVARCHAR(8) NOT NULL   "a"/"b"/"c" by i % 3  -> 3 distinct, no nulls
    amount  DECIMAL(10,2)          i, unique             -> 100 distinct, no nulls
    note    NVARCHAR(8) NULL       "x" when i % 5 == 0, "y" when i % 5 == 1,
                                   NULL otherwise          -> 2 distinct, 60% null

The size is modest on purpose: this backend aggregates the rows rather than
reading a histogram, so the answer does not depend on a sample being large. It
only has to be big enough that a duplicate silently dropped by ``COUNT(DISTINCT
...)``, or a NULL miscounted by the ``SUM(CASE ...)`` arm, would move a number
off its hand-counted value -- which a hundred rows does.

Three shapes differ from PostgreSQL and are pinned here rather than left to be
discovered. First, SQL Server aggregates, so the profile is ``aggregate`` and
every figure is exact, while PostgreSQL reads ``pg_stats`` and answers
``estimate``. Second, the value listing is a ``GROUP BY`` over the column, and
SQL Server groups NULLs into a real row -- so a column containing NULLs has a
NULL entry in its listing, usually the most frequent one. Third, the endpoints
arrive as text: the union resolves one result type per column position by
data-type precedence, and an ``int`` beside a ``varchar`` would have the text
converted to a number and fail, so both endpoints are cast in the statement.
The figures are exact; only the Python type is the union's, which is why the
decimal endpoints are read through ``Decimal`` here.

The non-ASCII test is not decoration. The profile's ``column_name`` is the one
value in the statement that is caller data rather than a label, and this
backend binds it as a parameter rather than writing a string literal: a
non-prefixed literal is typed with the database's code page, so an identifier
outside that page would come back as question marks. The test fails if that
ever regresses to a literal.
"""

from decimal import Decimal

import pytest


TABLE = "intro_profile_orders"
CUSTOMERS = "intro_profile_customers"
UNICODE_TABLE = "intro_profile_unicode"
CODES = ("a", "b", "c")

ROWS = 100

#: ``note`` is NULL on 60 of the 100 rows, "x" on 20 and "y" on 20.
NULL_SHARE = 0.6
NOTE_COUNT = 20


def _rows():
    rows = []
    for i in range(1, ROWS + 1):
        if i % 5 == 0:
            note = "x"
        elif i % 5 == 1:
            note = "y"
        else:
            note = None
        rows.append((i, CODES[i % 3], i, note))
    return rows


def _setup(backend):
    for table in (TABLE, CUSTOMERS, UNICODE_TABLE):
        backend.execute(f"DROP TABLE IF EXISTS [{table}]")
    backend.execute(
        f"CREATE TABLE [{TABLE}] ("
        "[id] INT NOT NULL PRIMARY KEY, "
        "[code] NVARCHAR(8) NOT NULL, "
        "[amount] DECIMAL(10,2) NOT NULL, "
        "[note] NVARCHAR(8) NULL"
        ")"
    )
    backend.execute_many(
        f"INSERT INTO [{TABLE}] ([id], [code], [amount], [note]) "
        "VALUES (?, ?, ?, ?)",
        _rows(),
    )
    # The right side of every coverage measurement: four codes and one NULL.
    # The NULL is the point -- it must not count as a value of the domain, so
    # right coverage is 3/4 and not 3/5.
    backend.execute(
        f"CREATE TABLE [{CUSTOMERS}] ("
        "[id] INT NOT NULL PRIMARY KEY, "
        "[code] NVARCHAR(8) NULL"
        ")"
    )
    backend.execute_many(
        f"INSERT INTO [{CUSTOMERS}] ([id], [code]) VALUES (?, ?)",
        [(1, "a"), (2, "b"), (3, "c"), (4, "d"), (5, None)],
    )


def _teardown(backend):
    for table in (TABLE, CUSTOMERS, UNICODE_TABLE):
        backend.execute(f"DROP TABLE IF EXISTS [{table}]")


class TestColumnDataProfile:
    """What the rows hold, counted by the server rather than read from a catalog."""

    def test_profile_matches_a_hand_count(self, sqlserver_backend):
        _setup(sqlserver_backend)
        try:
            profiles = {
                profile.column_name: profile
                for profile in sqlserver_backend.introspector.list_column_data_profiles(
                    TABLE
                )
            }
            assert set(profiles) == {"id", "code", "amount", "note"}

            # A unique key: 100 distinct values, none of them NULL.
            assert profiles["id"].null_fraction == 0.0
            assert profiles["id"].distinct_count == ROWS
            assert int(profiles["id"].min_value) == 1
            assert int(profiles["id"].max_value) == ROWS

            # Three values, none null. COUNT(DISTINCT ...) ignores NULL on its
            # own, so the count agrees with the listing below.
            assert profiles["code"].null_fraction == 0.0
            assert profiles["code"].distinct_count == len(CODES)
            assert profiles["code"].min_value == "a"
            assert profiles["code"].max_value == "c"

            # The endpoints arrive as text: the union needs one type per
            # position, and an int beside a varchar would fail the conversion
            # the other way round. The figure is exact; only the Python type
            # is the union's, which is why this goes through Decimal.
            assert profiles["amount"].null_fraction == 0.0
            assert profiles["amount"].distinct_count == ROWS
            assert Decimal(str(profiles["amount"].min_value)) == Decimal("1")
            assert Decimal(str(profiles["amount"].max_value)) == Decimal(ROWS)

            # 60 of 100 rows are NULL, so a profile that dropped the figure or
            # clamped it would still look plausible.
            assert profiles["note"].null_fraction == pytest.approx(NULL_SHARE)
            assert profiles["note"].distinct_count == 2
            assert profiles["note"].min_value == "x"
            assert profiles["note"].max_value == "y"
        finally:
            _teardown(sqlserver_backend)

    def test_every_profile_says_it_was_aggregated(self, sqlserver_backend):
        """The label rides the row, so a consumer never has to guess.

        SQL Server's statistics are keyed by statistics object, not by column,
        and carry no per-column null fraction or distinct count -- so every
        figure here is counted, and the row says so in ``source``. There is no
        ``collected_at``: an aggregate is current by construction, and
        borrowing a statistics object's ``last_updated`` would make a fresh
        count look like a stale estimate.
        """
        _setup(sqlserver_backend)
        try:
            profiles = sqlserver_backend.introspector.list_column_data_profiles(TABLE)
            assert profiles
            assert {profile.source for profile in profiles} == {"aggregate"}
            for profile in profiles:
                assert profile.collected_at is None
                assert profile.row_count == ROWS
        finally:
            _teardown(sqlserver_backend)

    def test_a_non_ascii_column_name_survives_the_round_trip(self, sqlserver_backend):
        """The label is caller data, so it is bound rather than written as text.

        A string literal in T-SQL without the ``N`` prefix is typed with the
        database's code page; on a Latin collation an identifier outside that
        page arrives as question marks. Binding it as a parameter makes the
        driver type it Unicode, so the name comes back as it was declared.
        """
        _setup(sqlserver_backend)
        backend = sqlserver_backend
        backend.execute(
            f"CREATE TABLE [{UNICODE_TABLE}] ([id] INT NOT NULL, [备注] NVARCHAR(8) NULL)"
        )
        backend.execute_many(
            f"INSERT INTO [{UNICODE_TABLE}] ([id], [备注]) VALUES (?, ?)",
            [(1, "一"), (2, None)],
        )
        try:
            profiles = backend.introspector.list_column_data_profiles(UNICODE_TABLE)
            names = {profile.column_name for profile in profiles}
            assert names == {"id", "备注"}
            note = next(p for p in profiles if p.column_name == "备注")
            assert note.null_fraction == pytest.approx(0.5)
            assert note.distinct_count == 1
        finally:
            _teardown(backend)

    def test_empty_table_answers_with_zero_rows_and_no_fraction(self, sqlserver_backend):
        """A profile of nothing is a row count of zero, not a fabricated 0.0.

        ``SUM`` over no rows is NULL, so ``null_count`` is NULL and the
        fraction is not derived. Saying 0.0 would claim the column holds no
        NULLs, which is not something an empty table establishes.
        """
        sqlserver_backend.execute(f"DROP TABLE IF EXISTS [{TABLE}]")
        sqlserver_backend.execute(f"CREATE TABLE [{TABLE}] ([id] INT NULL)")
        try:
            profiles = sqlserver_backend.introspector.list_column_data_profiles(TABLE)
            assert len(profiles) == 1
            profile = profiles[0]
            assert profile.column_name == "id"
            assert profile.row_count == 0
            assert profile.distinct_count == 0
            assert profile.null_fraction is None
            assert profile.min_value is None
            assert profile.max_value is None
            assert profile.source == "aggregate"
        finally:
            _teardown(sqlserver_backend)


class TestColumnValueSample:
    """The grouped scan, which unlike PostgreSQL's list can contain NULL."""

    def test_listing_is_ordered_by_frequency(self, sqlserver_backend):
        _setup(sqlserver_backend)
        try:
            samples = sqlserver_backend.introspector.sample_column_values(
                TABLE, "code", limit=10
            )
            # CODES[i % 3] puts "b" on 34 rows (i % 3 == 1) and "a"/"c" on 33
            # each, so the order is frequency first and then the tie-break by
            # value -- which is why "a" precedes "c" despite equal counts.
            assert [item.value for item in samples] == ["b", "a", "c"]
            assert [item.count for item in samples] == [34, 33, 33]
            # The engine reports a count, not a fraction. A formatter that
            # divided for it would have had to assume the row count.
            assert all(item.frequency is None for item in samples)
        finally:
            _teardown(sqlserver_backend)

    def test_limit_bounds_the_listing(self, sqlserver_backend):
        _setup(sqlserver_backend)
        try:
            assert (
                len(
                    sqlserver_backend.introspector.sample_column_values(
                        TABLE, "code", limit=2
                    )
                )
                == 2
            )
        finally:
            _teardown(sqlserver_backend)

    def test_null_is_a_value_of_the_domain(self, sqlserver_backend):
        """SQL Server groups NULLs, so the listing has a NULL row -- usually first.

        This is the shape that differs from PostgreSQL, whose most-common list
        never contains NULL because ``null_frac`` holds that fact separately.
        A caller reading a listing for "what is in this column" must therefore
        not assume every entry is a value; the profile's ``null_fraction`` is
        the cross-engine answer, and this test is what says so for SQL Server.
        """
        _setup(sqlserver_backend)
        try:
            samples = sqlserver_backend.introspector.sample_column_values(
                TABLE, "note", limit=10
            )
            # NULL at 60 rows, then "x" and "y" at 20 each.
            assert samples[0].value is None
            assert samples[0].count == ROWS - 2 * NOTE_COUNT
            assert {item.value for item in samples if item.value is not None} == {
                "x",
                "y",
            }
            assert sum(item.count for item in samples) == ROWS
        finally:
            _teardown(sqlserver_backend)


class TestJoinCoverage:
    """Overlap measured over distinct values, on both sides."""

    def test_coverage_is_measured_over_distinct_values(self, sqlserver_backend):
        """3 of orders' 3 codes exist among customers' 4 non-null codes.

        Row counts would say something else entirely: 100 order rows map onto
        4 customer rows. Counting distinct values is what makes the number a
        statement about the domains rather than about repetition, and the
        ``1.0`` the statement multiplies by is what keeps SQL Server from
        answering the integer division -- 0 -- instead.
        """
        _setup(sqlserver_backend)
        try:
            coverage = sqlserver_backend.introspector.estimate_join_coverage(
                TABLE, "code", CUSTOMERS, "code"
            )
            assert coverage is not None
            assert coverage.left_coverage == pytest.approx(1.0)
            assert coverage.right_coverage == pytest.approx(0.75)
            assert coverage.left_table == TABLE
            assert coverage.right_table == CUSTOMERS
        finally:
            _teardown(sqlserver_backend)

    def test_the_measurement_is_not_symmetric(self, sqlserver_backend):
        """Reversing the sides swaps the fractions, it does not copy them."""
        _setup(sqlserver_backend)
        try:
            coverage = sqlserver_backend.introspector.estimate_join_coverage(
                CUSTOMERS, "code", TABLE, "code"
            )
            assert coverage is not None
            assert coverage.left_coverage == pytest.approx(0.75)
            assert coverage.right_coverage == pytest.approx(1.0)
        finally:
            _teardown(sqlserver_backend)

    def test_an_empty_domain_is_no_measurement_rather_than_zero(self, sqlserver_backend):
        """``NULLIF(..., 0)`` is the difference between "none" and "unmeasurable".

        With no customer rows there is nothing to divide by, and answering
        ``0.0`` would read as "none of these values join" -- a different claim.
        The left side still has a real denominator, so its 0.0 is a genuine
        zero and must survive.
        """
        _setup(sqlserver_backend)
        try:
            sqlserver_backend.execute(f"DELETE FROM [{CUSTOMERS}]")
            coverage = sqlserver_backend.introspector.estimate_join_coverage(
                TABLE, "code", CUSTOMERS, "code"
            )
            assert coverage is not None
            assert coverage.left_coverage == pytest.approx(0.0)
            assert coverage.right_coverage is None
        finally:
            _teardown(sqlserver_backend)
