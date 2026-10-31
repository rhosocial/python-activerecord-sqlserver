# tests/rhosocial/activerecord_sqlserver_test/feature/backend/test_sqlserver_constraint_capabilities.py
"""SQL Server constraint capability switches, pinned to live measurements.

Every value asserted here was measured against the instance
``tests/config/sqlserver_scenarios.yaml`` names ``sqlserver_2019``:
**SQL Server 2019 (RTM-CU32-GDR), 15.0.4465.1, Developer Edition**, on
``127.0.0.1:11433``, through pyodbc 5.3.0 + ``ODBC Driver 17 for SQL
Server``. The statements and the server's own message numbers are recorded in
the docstrings of
``rhosocial.activerecord.backend.impl.sqlserver.mixins.constraint``; this
module pins the values and checks that they are load-bearing.

Four guards beyond the values themselves:

* **declared here, not inherited.** Each switch must be declared by a class in
  *this* package, so a change to a core default cannot silently move SQL
  Server's contract (the same discipline the master-probe guard applies).
* **the signature is ``(self)``.** A probe answers one question -- is this
  capability family present on this server -- and the kind is not part of it,
  so a parameterised probe is refused here on the bound method.
* **the docstring still quotes its measurement.** Every switch records the
  server's message number and the release it was measured on.
* **the answer decides the outcome.** For every switch core consults, the
  render/refuse behaviour must follow the value: ``ADD`` / ``DROP
  CONSTRAINT`` render, ``VALIDATE`` / ``ALTER CONSTRAINT`` / ``NOT VALID`` are
  refused by name, and the standard clause traits (``ENFORCED`` / ``NOT
  ENFORCED`` / ``DEFERRABLE`` / ``INITIALLY``) are refused at both the column
  and the table seam -- including on the PRIMARY KEY / UNIQUE column kinds that
  ``format_column_definition`` spells itself.

The trait walk is driven by the same pairs as
``test_clause_pair_guard_sqlserver.py`` but through the two public seams, so a
seam that stopped consulting the shared helper fails here.  The per-spelling
walk there also asserts the two refusals stay distinguishable; this file
asserts the seam, that one asserts the wording.

Not covered here, on purpose: the SQL-standard clauses SQL Server cannot
spell at all were already driven through the two-spelling pair walk in
``test_clause_pair_guard_sqlserver.py``; duplicating the assertions would
let the two files disagree.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddTableConstraintAction,
    AlterConstraintAction,
    DropTableConstraintAction,
    ValidateConstraintAction,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnConstraint,
    ColumnDefinition,
    ColumnForeignKeyConstraint,
    ColumnPrimaryKeyConstraint,
    ColumnUniqueConstraint,
    ConstraintValidation,
    TableCheckConstraint,
    TableConstraint,
    TableForeignKeyConstraint,
    TablePrimaryKeyConstraint,
)
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.impl.sqlserver.dialect import SQLServerDialect

SQL_SERVER_2019 = (15, 0, 0)

#: Every capability this package declares must come from this package.
BACKEND_PACKAGE = "rhosocial.activerecord.backend.impl.sqlserver."

#: (switch name, measured value) pairs. The value is hard-coded on purpose:
#: reading it back from the dialect would make the test unable to see a
#: moved default.
MEASURED_SWITCHES = (
    # SQL-standard clauses: none of them are T-SQL (Msg 102 / 156 syntax errors).
    ("supports_constraint_enforced", False),
    ("supports_deferrable_constraint", False),
    ("supports_fk_match", False),
    ("supports_constraint_novalidate", False),
    ("supports_validate_constraint", False),
    ("supports_alter_constraint_enforced", False),
    ("supports_enable_disable_constraint", False),
    ("supports_rename_constraint", False),
    # ALTER TABLE ... ADD/DROP CONSTRAINT themselves: all four kinds accepted.
    ("supports_add_constraint", True),
    ("supports_drop_constraint", True),
)


def _dialect():
    return SQLServerDialect(SQL_SERVER_2019)


def _declaring_class(switch_name):
    """The first class in the dialect's MRO that declares ``switch_name``."""
    for cls in SQLServerDialect.__mro__:
        if switch_name in cls.__dict__:
            return cls
    raise AssertionError(f"no class in the MRO declares {switch_name}()")


def _predicate(d):
    return ComparisonPredicate(d, "=", Column(d, "a"), Column(d, "b"))


def _check(d, **kwargs):
    return TableConstraint(d, branch=TableCheckConstraint(d, _predicate(d)), name="ck", **kwargs)


#: The SQL spelling each switch's docstring must quote as the evidence for its
#: value: the server's own message number or accepted verdict. A verdict that
#: cannot be traced to an observation is a guess with a name, so the check is
#: mechanical -- the substring must still be in the docstring.
DOCSTRING_EVIDENCE = {
    "supports_constraint_enforced": "156",
    "supports_deferrable_constraint": "102",
    "supports_fk_match": "102",
    "supports_constraint_novalidate": "156",
    "supports_validate_constraint": "102",
    "supports_alter_constraint_enforced": "156",
    "supports_enable_disable_constraint": "156",
    "supports_rename_constraint": "15248",
    "supports_add_constraint": "1779",
    "supports_drop_constraint": "3728",
}


class TestMeasuredConstraintSwitchValues:
    @pytest.mark.parametrize(
        "switch_name,expected", MEASURED_SWITCHES, ids=[s for s, _ in MEASURED_SWITCHES]
    )
    def test_matches_measurement(self, switch_name, expected):
        dialect = _dialect()
        assert getattr(dialect, switch_name)() is expected, (
            f"{switch_name}() no longer matches the 2019 measurement; see the "
            f"docstring in mixins/constraint.py for the statement that decided it."
        )

    @pytest.mark.parametrize(
        "switch_name,_expected", MEASURED_SWITCHES, ids=[s for s, _ in MEASURED_SWITCHES]
    )
    def test_declared_by_this_backend(self, switch_name, _expected):
        """A moved core default must not move SQL Server's contract silently."""
        declaring = _declaring_class(switch_name)
        assert declaring.__module__.startswith(BACKEND_PACKAGE), (
            f"{switch_name} is inherited from {declaring.__module__}; declare it "
            f"in this backend's mixins so the measured value is explicit."
        )

    @pytest.mark.parametrize(
        "switch_name,_expected", MEASURED_SWITCHES, ids=[s for s, _ in MEASURED_SWITCHES]
    )
    def test_declaring_class_precedes_the_core_constraint_mixin(
        self, switch_name, _expected
    ):
        """The backend's declaration reaches the MRO before core's.

        The locality check above says a class in this package answers; this says
        the *order* makes that class the one that answers.  A probe declared in
        both places, with core's mixin ordered first, would satisfy the first
        check and still have its value decided in another repository.
        """
        from rhosocial.activerecord.backend.dialect.mixins.ddl_table import (
            ConstraintMixin,
        )

        mro = SQLServerDialect.__mro__
        declaring_index = mro.index(_declaring_class(switch_name))
        assert declaring_index < mro.index(ConstraintMixin), (
            f"{switch_name} is declared by {mro[declaring_index].__name__}, which "
            f"follows core's ConstraintMixin in the MRO; core's default answers."
        )

    @pytest.mark.parametrize(
        "switch_name,_expected", MEASURED_SWITCHES, ids=[s for s, _ in MEASURED_SWITCHES]
    )
    def test_probe_takes_no_argument(self, switch_name, _expected):
        """``(self)`` and nothing else.

        Checked on the bound method so a defaulted parameter cannot slip back in:
        a probe answers one question -- is this capability family present on this
        server -- and the kind is not part of it. The per-kind answer belongs to
        the formatter, which can see the branch class.
        """
        import inspect

        bound = getattr(_dialect(), switch_name)
        parameters = list(inspect.signature(bound).parameters)
        assert parameters == [], (
            f"{switch_name} takes {parameters}; a probe carries no kind and must "
            f"be (self)."
        )

    @pytest.mark.parametrize(
        "switch_name,_expected", MEASURED_SWITCHES, ids=[s for s, _ in MEASURED_SWITCHES]
    )
    def test_docstring_quotes_the_measurement(self, switch_name, _expected):
        """The evidence for the value is still in the docstring.

        Pattern 6 of the reconciliation rules: every switch records the server
        version and the exact answer its value came from. A docstring that stops
        quoting its measurement fails here rather than quietly becoming a guess.
        """
        import inspect

        docstring = inspect.getdoc(getattr(SQLServerDialect, switch_name)) or ""
        evidence = DOCSTRING_EVIDENCE[switch_name]
        assert evidence in docstring, (
            f"{switch_name}'s docstring no longer quotes {evidence!r}; the value "
            f"cannot be traced back to a measurement."
        )
        assert "2019" in docstring, (
            f"{switch_name}'s docstring does not name the server version the "
            f"value was measured on."
        )

    def test_version_does_not_move_the_values(self):
        """The values are statement-level facts, not version gates.

        Measured on 2019 only; asserting they hold at 2022/2025 is a claim
        this backend has not made, so the check is just that no version
        branch exists for them.
        """
        for version in ((15, 0, 0), (16, 0, 0), (17, 0, 0)):
            dialect = SQLServerDialect(version)
            for switch_name, expected in MEASURED_SWITCHES:
                assert getattr(dialect, switch_name)() is expected, (
                    f"{switch_name} moved with version {version}"
                )


class TestAddAndDropConstraintRender:
    """The two True switches decide these renders."""

    def test_add_table_constraint_renders(self):
        d = _dialect()
        sql, params = AddTableConstraintAction(d, _check(d)).to_sql()
        assert sql == "ADD CONSTRAINT [ck] CHECK ([a] = [b])"
        assert params == ()

    def test_add_primary_key_renders(self):
        d = _dialect()
        action = AddTableConstraintAction(
            d,
            TableConstraint(d, branch=TablePrimaryKeyConstraint(d, ["id"]), name="pk"),
        )
        sql, params = action.to_sql()
        assert sql == "ADD CONSTRAINT [pk] PRIMARY KEY ([id])"
        assert params == ()

    def test_drop_constraint_renders(self):
        d = _dialect()
        sql, params = DropTableConstraintAction(d, "ck").to_sql()
        assert sql == "DROP CONSTRAINT [ck]"
        assert params == ()

    def test_drop_constraint_if_exists_renders(self):
        """``IF EXISTS`` is the idempotent path: the plain form is Msg 3728."""
        d = _dialect()
        sql, params = DropTableConstraintAction(d, "ck", if_exists=True).to_sql()
        assert sql == "DROP CONSTRAINT IF EXISTS [ck]"
        assert params == ()


class TestAlterSideRefusals:
    """The False switches decide these refusals; none is T-SQL."""

    def test_validate_constraint_refused(self):
        d = _dialect()
        with pytest.raises(UnsupportedFeatureError):
            ValidateConstraintAction(d, "ck").to_sql()

    def test_alter_constraint_enforced_refused(self):
        d = _dialect()
        action = AlterConstraintAction(
            d, "ck", enforced=True, constraint_kind=TableCheckConstraint
        )
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()

    def test_alter_constraint_not_enforced_refused(self):
        d = _dialect()
        action = AlterConstraintAction(
            d,
            "ck",
            not_enforced=True,
            constraint_kind=TableForeignKeyConstraint,
        )
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()

    def test_add_constraint_not_valid_refused_on_the_add_path(self):
        d = _dialect()
        action = AddTableConstraintAction(
            d, _check(d, validation=ConstraintValidation.NOVALIDATE)
        )
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()


class TestColumnLevelNarrowing:
    """The column-level refusal, and the coupling it works around.

    ``format_column_definition`` is this backend's override, so a column's
    constraints do not go through the standalone ``ColumnConstraint.to_sql()``
    dispatch -- they go through this path.  Each assertion below therefore
    renders a whole ``ColumnDefinition``, which is where a user's column lands.
    """

    def test_column_references_is_refused(self):
        """T-SQL has no column-level ``REFERENCES``; the table form is the only one.

        The coupling: core gates the column grammar on
        ``supports_foreign_key_constraint()``, the *table-level* probe, and SQL
        Server needs that probe True.  So the refusal lives in this backend's
        ``format_column_fk_constraint`` override rather than behind a probe.
        """
        d = _dialect()
        column = ColumnDefinition(
            d,
            "a",
            IntegerType(d),
            constraints=[
                ColumnConstraint(
                    d,
                    branch=ColumnForeignKeyConstraint(
                        d, (Table(d, "other"), ["id"])
                    ),
                )
            ],
        )
        with pytest.raises(UnsupportedFeatureError, match="column-level REFERENCES"):
            column.to_sql()

    def test_table_references_from_a_column_still_reachable(self):
        """The table-level probe stays True, which is why the override is needed."""
        assert _dialect().supports_foreign_key_constraint() is True

    @pytest.mark.parametrize(
        "kwargs,spelling",
        (
            ({"enforced": True}, "ENFORCED"),
            ({"not_enforced": True}, "NOT ENFORCED"),
            ({"deferrable": True}, "DEFERRABLE"),
            ({"not_deferrable": True}, "NOT DEFERRABLE"),
            ({"initially_deferred": True}, "INITIALLY DEFERRED"),
            ({"initially_immediate": True}, "INITIALLY IMMEDIATE"),
        ),
        ids=(
            "enforced",
            "not-enforced",
            "deferrable",
            "not-deferrable",
            "initially-deferred",
            "initially-immediate",
        ),
    )
    def test_primary_key_traits_are_refused_not_dropped(self, kwargs, spelling):
        """A trait on a PRIMARY KEY column is refused by name, never dropped.

        PRIMARY KEY and UNIQUE are spelled inside ``format_column_definition``
        rather than through the production formatter, so this is the path that
        would otherwise drop the request without a word -- which the old
        tag-switch formatter refused with a ``ValueError``.  The same helper
        backs both, so the two cannot drift apart.
        """
        d = _dialect()
        column = ColumnDefinition(
            d,
            "a",
            IntegerType(d),
            constraints=[
                ColumnConstraint(d, branch=ColumnPrimaryKeyConstraint(d), **kwargs)
            ],
        )
        with pytest.raises(UnsupportedFeatureError, match=spelling):
            column.to_sql()

    @pytest.mark.parametrize(
        "kwargs",
        (
            {"enforced": True},
            {"deferrable": True},
            {"initially_deferred": True},
        ),
        ids=("enforced", "deferrable", "initially-deferred"),
    )
    def test_unique_traits_are_refused_not_dropped(self, kwargs):
        """The same for UNIQUE, the other kind the shortcut spells."""
        d = _dialect()
        column = ColumnDefinition(
            d,
            "a",
            IntegerType(d),
            constraints=[
                ColumnConstraint(d, branch=ColumnUniqueConstraint(d), **kwargs)
            ],
        )
        with pytest.raises(UnsupportedFeatureError):
            column.to_sql()

    def test_primary_key_renders_when_no_trait_is_asked_for(self):
        """The refusal must not swallow the plain form: IDENTITY rides here."""
        d = _dialect()
        column = ColumnDefinition(
            d,
            "id",
            IntegerType(d),
            constraints=[
                ColumnConstraint(
                    d, branch=ColumnPrimaryKeyConstraint(d, is_auto_increment=True)
                )
            ],
        )
        sql, params = column.to_sql()
        assert sql == "[id] INT PRIMARY KEY IDENTITY(1,1)"
        assert params == ()


class TestTableLevelTraitRefusals:
    """The table seam refuses the same six spellings, by name.

    A table PRIMARY KEY is the branch used here because it is one of the kinds
    that can carry **both** traits (the enforcement one and the deferral one),
    so every spelling reaches the dialect's refusal rather than being turned
    away by the node's own construction-time check.
    """

    @pytest.mark.parametrize(
        "kwargs,spelling",
        (
            ({"enforced": True}, "ENFORCED"),
            ({"not_enforced": True}, "NOT ENFORCED"),
            ({"deferrable": True}, "DEFERRABLE"),
            ({"not_deferrable": True}, "NOT DEFERRABLE"),
            ({"initially_deferred": True}, "INITIALLY DEFERRED"),
            ({"initially_immediate": True}, "INITIALLY IMMEDIATE"),
        ),
        ids=(
            "enforced",
            "not-enforced",
            "deferrable",
            "not-deferrable",
            "initially-deferred",
            "initially-immediate",
        ),
    )
    def test_table_traits_are_refused(self, kwargs, spelling):
        d = _dialect()
        constraint = TableConstraint(
            d, branch=TablePrimaryKeyConstraint(d, ["a"]), name="pk", **kwargs
        )
        with pytest.raises(UnsupportedFeatureError, match=spelling):
            constraint.to_sql()

    def test_a_table_check_without_a_trait_renders(self):
        d = _dialect()
        sql, params = _check(d).to_sql()
        assert sql == "CONSTRAINT [ck] CHECK ([a] = [b])"
        assert params == ()

    def test_a_table_key_without_a_trait_renders(self):
        d = _dialect()
        sql, params = TableConstraint(
            d, branch=TablePrimaryKeyConstraint(d, ["a"]), name="pk"
        ).to_sql()
        assert sql == "CONSTRAINT [pk] PRIMARY KEY ([a])"
        assert params == ()

    def test_the_node_refuses_a_trait_the_kind_cannot_carry(self):
        """The deferral trait on a CHECK is the node's refusal, not the dialect's.

        Recorded here so the two layers stay distinguishable: this is a
        ``ValueError`` raised at construction by ``TableConstraint``, before any
        dialect code sees it, and it is why the walk above uses a PRIMARY KEY.
        """
        d = _dialect()
        with pytest.raises(ValueError, match="DEFERRABLE / INITIALLY"):
            _check(d, deferrable=True)
