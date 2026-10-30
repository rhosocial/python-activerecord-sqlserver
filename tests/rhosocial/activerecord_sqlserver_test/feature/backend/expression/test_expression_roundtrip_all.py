# tests/rhosocial/activerecord_sqlserver_test/feature/backend/expression/test_expression_roundtrip_all.py
"""
Serialization and SQL coverage for every expression class SQL Server renders.

Two packages are in scope: the backend's own
``rhosocial.activerecord.backend.impl.sqlserver.expression``, and core's
``rhosocial.activerecord.backend.expression``. The second one used to be
absent, and its absence is why a core class with no SQL Server formatter could
sit in the tree unnoticed -- the backend matrix could not see it, and core's own
matrix renders against the Dummy dialect, where it renders.

Why ``to_sql()`` is classified rather than caught
================================================

This matrix used the testsuite's ``sql_consistent``, whose body was::

    try:
        expected = instance.to_sql()
    except Exception:
        return

Every render failure was therefore a green tick, and the three SQL comparisons
that follow never ran. A formatter reading a field that no longer existed was
indistinguishable from a formatter for a feature SQL Server does not have. The
cost was not abstract: this rewrite found a formatter whose signature no caller
could satisfy, so every ``LateralExpression`` on SQL Server raised ``TypeError``
and no test said so -- and, by collecting core's own classes, four core
expressions whose formatter this backend had shadowed with a different
signature. Both are described where they are fixed and, for the four, where they
are pinned.

Each outcome is now named and asserted:

* **renders** -- all three encodings must restore byte-identical SQL *and*
  byte-identical bind parameters.
* a member of :data:`LEGITIMATE_NON_RENDERS` -- a class that cannot render for a
  reason belonging to its own tree. Each entry pins the exception type *and* a
  message fragment, so a class that started failing for a different reason fails
  here instead of staying quietly green.
* ``UnsupportedFeatureError`` from a probe inside a formatter, for a class
  *not* named in the dict -- SQL Server does not model the feature. Asserted
  as exactly that type, so a subclass raised for an unrelated reason is still
  visible rather than passing.
* ``UnsupportedFeatureError`` from the dispatch, for a class not named in the
  dict -- the dialect declares no ``format_*`` method for it at all, which is
  a wiring fact about this backend rather than a capability answer. The
  method the dispatch names must be a row in :data:`UNMODELLED_FORMATTERS`,
  so the gap is a decision with a reason rather than an omission; see
  :func:`_dispatched_formatter`.
* **anything else** -- a failure naming the class and the exception.

The dict is read before the ``UnsupportedFeatureError`` branch, because core now
reports a *missing formatter* through that same type; see
:func:`assert_sql_roundtrip_classified`.

And when the artifact itself cannot carry a node
================================================

Rendering is one axis; the artifact is the other. A node whose parameter is a
plain ``Enum`` or a dataclass cannot be written as plain JSON at all -- the
serializer names the type and stops -- and a node whose parameter is an enum may
still fail on one *channel* even though the other two carry it: the XML codec
spells a member as ``Class.MEMBER`` and hands that word back to a constructor
that refuses it (the enum sub-registry that used to resolve it is gone). Neither
is a rendering answer, so neither is allowed to pass as one: every such class is
named in :data:`ARTIFACT_GAPS`, pinned by channel and by the exact failure, and
:meth:`TestMatrixIntegrity.test_artifact_gap_list_is_exact` pins that table in
both directions -- a class that starts travelling fails until its row goes, and
a class that stops travelling with no row fails the per-class assertion.

Why the dispatch's refusal is no longer allowed on its type alone
=================================================================

The two ``UnsupportedFeatureError`` outcomes above were one branch until core
turned ``trim``/``lpad``/``rpad``/``repeat`` into dedicated nodes. SQL Server
spells ``TRIM``/``LTRIM``/``RTRIM`` and has no ``LPAD``, ``RPAD`` or ``REPEAT``
at all, so those three nodes reach a dispatch that finds no formatter -- and
before this split, that refusal read as "SQL Server lacks the feature" and
passed, indistinguishable from a probe declining something SQL Server
genuinely declines. The exception itself records who is refusing: a probe
names the feature, while the dispatch frames the formatting method it could
not find as ``the '<method>' statement`` -- see :func:`_dispatched_formatter`.
Only the dispatch's refusal is a wiring fact about this backend, so only it
must be accounted for:
:meth:`TestMatrixIntegrity.test_unmodelled_formatter_list_is_exact` pins
:data:`UNMODELLED_FORMATTERS` in both directions, and a method nobody listed
fails the run.

And when a class cannot be constructed
======================================

``make_instance(...) is None`` becomes a skip, but only for a class named in
:data:`UNCONSTRUCTIBLE`, and :func:`test_unconstructible_list_is_exact` pins that
tuple against what the constructor really skips. Both directions fail: a class
that gains a constructor, and a class that starts failing to build.

Discovery does not read a process-global class index. That index grows as
sibling test modules import their own backends, so reading it made this
matrix's contents depend on which files pytest happened to import first.
:func:`collect_expression_classes` walks a package instead, which is
deterministic.
"""

import datetime
import inspect
import uuid as uuid_module
from decimal import Decimal
from typing import Any, Dict

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.core import Column, Literal
from rhosocial.activerecord.backend.expression.objects import (
    Database,
    Index,
    Schema,
    Sequence,
    Table,
    Trigger,
    Type,
    View,
)
from rhosocial.activerecord.backend.expression.predicates import (
    LikeOperator,
    ComparisonOperator,
    ComparisonPredicate,
)
from rhosocial.activerecord.backend.expression.sources import NamedRelationRef
from rhosocial.activerecord.backend.expression.operators import ArithmeticOperation
from rhosocial.activerecord.backend.expression.query_sources import SetOperation
from rhosocial.activerecord.backend.expression.statements import (
    ddl_alter,
    ddl_table,
    ddl_type,
    ddl_view,
    dml,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnCheckConstraint,
    ColumnConstraint,
    ColumnDefinition,
    ColumnGeneratedConstraint,
    ColumnNotNullConstraint,
    ForeignKeyConstraint,
    TableCheckConstraint,
    TableConstraint,
    TablePrimaryKeyConstraint,
)
from rhosocial.activerecord.backend.expression.statements.dml import (
    MergeAction,
    MergeActionType,
)
from rhosocial.activerecord.backend.expression.statements.dql import QueryStatement
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.expression.types.custom import CustomType
from rhosocial.activerecord.backend.expression.uuid import UUIDConstantExpression
# The harness is this module's sibling, and this module is itself loaded by path
# (from ``test_sqlserver_type_protocol.py``'s sweep) as well as by name (when
# pytest collects it here) -- a by-name import would only work in the second
# case, so the sibling is loaded by path and both callers get one module object.
import importlib.util as _importlib_util
from pathlib import Path as _Path

_harness_path = _Path(__file__).parent / "expression_roundtrip_harness.py"
_spec = _importlib_util.spec_from_file_location(
    "sqlserver_roundtrip_harness", _harness_path
)
_harness = _importlib_util.module_from_spec(_spec)
_spec.loader.exec_module(_harness)

assert_params_equal = _harness.assert_params_equal
collect_expression_classes = _harness.collect_expression_classes
make_instance = _harness.make_instance
register_all = _harness.register_all
register_special_constructor = _harness.register_special_constructor
roundtrip_expression = _harness.roundtrip_expression

SS_EXPR_PKG = "rhosocial.activerecord.backend.impl.sqlserver.expression"
CORE_EXPR_PKG = "rhosocial.activerecord.backend.expression"


def _collect(pkg: str) -> Dict[str, type]:
    """Every concrete expression class one package defines.

    Walked rather than read from the registry, for the reason in the module
    docstring. Two packages export the same class under different names in
    different places, so the first name in sorted order wins and the matrix does
    not assert one class twice.
    """
    collected = collect_expression_classes(pkg)
    by_identity: Dict[int, str] = {}
    for fqn, cls in sorted(collected.items()):
        by_identity.setdefault(id(cls), fqn)
    return {
        fqn: cls
        for cls in collected.values()
        if not inspect.isabstract(cls)
        for fqn in [by_identity[id(cls)]]
    }


CORE_REGISTERED = _collect(CORE_EXPR_PKG)
SS_REGISTERED = _collect(SS_EXPR_PKG)
REGISTERED: Dict[str, type] = {**CORE_REGISTERED, **SS_REGISTERED}
register_all(REGISTERED)
# Nothing else needs registering. The enum/dataclass sub-registries the old
# matrix filled existed only because an artifact carried ``__enum__`` /
# ``__dataclass__`` markers and had to resolve those class names on the way
# back in; the artifact is plain JSON now, an enum rides as its value, a
# dataclass as an object, and the kind whitelist has no name to resolve for
# either. Registering an enum here would therefore be a call to a method the
# core no longer ships, which is how this line got noticed.


# ---------------------------------------------------------------------------
# Special constructors: a real value where the introspective guess is a lie
# ---------------------------------------------------------------------------
#
# ``make_instance`` reads each required parameter's annotation and guesses:
# ``"x"`` for a string, ``[]`` for a list, ``IntegerType()`` for a type. That is
# right for a name and wrong for everything that wants a catalogue object -- a
# Table, an Index, a Type -- because a bare ``"x"`` is not one, and the formatter
# now refuses it by name. It is also wrong for the containers that require at
# least one member (CASE, WINDOW, temporal options), for the constraints that
# must render without bind parameters, and for the enums the guess supplies a
# string for.
#
# Every registration below replaces a guess that would otherwise have produced an
# instance SQL Server cannot render. Suffixes are relative to the expression
# package because ``make_instance`` matches with ``str.endswith`` and several
# modules export identically named classes.


def _table_obj(dialect, name="t"):
    """A table with a bare name and no namespace."""
    return Table(dialect, name)


def _schema_obj(dialect):
    """A Schema, for the CREATE/DROP SCHEMA statements the guess cannot name."""
    return Schema(dialect, "app")


def _database_obj(dialect):
    """A Database, for CREATE/DROP/ALTER DATABASE."""
    return Database(dialect, "app")


def _sequence_obj(dialect):
    """A Sequence, for the three SEQUENCE statements."""
    return Sequence(dialect, "s")


def _type_obj(dialect):
    """A Type, for CREATE/DROP TYPE."""
    return Type(dialect, "t")


def _index_obj(dialect, name="i"):
    """An Index, for the index statements."""
    return Index(dialect, name)


def _view_obj(dialect, name="v"):
    """A View, for the view statements."""
    return View(dialect, name)


def _alias_type_definition(dialect):
    """A SQL Server alias TYPE definition, bound to the dialect.

    The testsuite registers the Dummy backend's definition for CREATE TYPE,
    which SQL Server cannot spell: a TYPE definition is part of the statement,
    not a parameter, so its body must render as SQL rather than a bind value.
    """
    from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.type import (
        SQLServerAliasTypeDefinition,
    )

    return SQLServerAliasTypeDefinition(dialect, IntegerType(dialect), nullability=True)


def _column_predicate(dialect):
    """A predicate comparing two columns, so it renders with no bind parameters."""
    return ComparisonPredicate(dialect, "=", Column(dialect, "a"), Column(dialect, "b"))


def _one_column_query(dialect):
    """A single-column ``SELECT`` over a table, for CREATE VIEW and TABLE AS.

    Used by the CREATE VIEW and materialized-view registrations, where the
    guess would otherwise supply a bare string for the query slot.
    """
    return QueryStatement(
        dialect, select=[Column(dialect, "id")], from_=_table_obj(dialect)
    )


def _integer_column(dialect, name="col"):
    """A column definition carrying a *dialect-bound* type.

    The binding is load-bearing: ``to_sql()`` dispatches on the type through its
    own dialect, so an unbound ``IntegerType()`` raises the moment anything
    renders it.
    """
    return ddl_table.ColumnDefinition(dialect, name, IntegerType(dialect))


def _sqlserver_collation(dialect):
    from rhosocial.activerecord.backend.impl.sqlserver.collation import (
        SQLServerCollation,
    )

    return SQLServerCollation.LATIN1_GENERAL_CI_AS


def _string_fn(dialect, class_name, *operands):
    """One scalar string function node from ``expression.functions.string``."""
    import rhosocial.activerecord.backend.expression.functions.string as string_module

    return getattr(string_module, class_name)(dialect, *operands)


def _datetime_fn(dialect, class_name, field, source):
    """One EXTRACT-family node from ``expression.datetime``."""
    import rhosocial.activerecord.backend.expression.datetime as datetime_module

    return getattr(datetime_module, class_name)(dialect, field, source)


def register_specials():
    """Replace every introspective guess that would cost a real assertion."""
    # -- the FROM side ------------------------------------------------------
    register_special_constructor(
        "sources.relation.NamedRelationRef",
        lambda d: NamedRelationRef(d, _table_obj(d)),
    )
    # CREATE VIEW needs a query, and the guess supplies the string "x" for it.
    register_special_constructor(
        "statements.ddl_view.CreateViewStatement",
        lambda d: ddl_view.CreateViewStatement(
            d, view=_view_obj(d), query=_one_column_query(d)
        ),
    )

    # -- column pieces ------------------------------------------------------
    # Overrides the shared testsuite factory, which binds no dialect to its type.
    register_special_constructor(
        "statements.ddl_table.ColumnDefinition", _integer_column
    )

    # -- containers that must not be empty ----------------------------------
    from rhosocial.activerecord.backend.expression.advanced_functions import (
        CaseExpression,
        WindowClause,
        WindowDefinition,
        WindowSpecification,
    )

    # -- closed word sets: the guess supplies a bare string -------------------
    # ``op`` on both nodes is validated against a closed set at construction
    # (add/sub/mul/div/mod and union/union_all/intersect/except), so the
    # introspective guess raises ValueError before a formatter is reached.
    register_special_constructor(
        "operators.ArithmeticOperation",
        lambda d: ArithmeticOperation(d, "add", Column(d, "a"), Column(d, "b")),
    )
    register_special_constructor(
        "query_sources.SetOperation",
        lambda d: SetOperation(
            d,
            op="union",
            left=QueryStatement(d, select=[Column(d, "id")]),
            right=QueryStatement(d, select=[Column(d, "id")]),
        ),
    )

    register_special_constructor(
        "advanced_functions.CaseExpression",
        lambda d: CaseExpression(
            d, cases=[(_column_predicate(d), Literal(d, 1))], else_result=Literal(d, 0)
        ),
    )
    register_special_constructor(
        "advanced_functions.WindowSpecification",
        lambda d: WindowSpecification(d, partition_by=["a"]),
    )
    register_special_constructor(
        "advanced_functions.WindowDefinition",
        lambda d: WindowDefinition(d, "w", WindowSpecification(d, partition_by=["a"])),
    )
    register_special_constructor(
        "advanced_functions.WindowClause",
        lambda d: WindowClause(d, [WindowDefinition(d, "w", WindowSpecification(d, partition_by=["a"]))]),
    )
    # An empty options dict is refused by the formatter, so a time-travel clause
    # needs an actual option.
    register_special_constructor(
        "datetime.TemporalOptionsExpression",
        lambda d: __import__(
            "rhosocial.activerecord.backend.expression.datetime",
            fromlist=["TemporalOptionsExpression"],
        ).TemporalOptionsExpression(d, {"as_of": "2020-01-01"}),
    )
    # The guess supplies the string "x", which SQL Server's collation validator
    # rightly refuses.
    register_special_constructor(
        "collation.CollateFunction",
        lambda d: __import__(
            "rhosocial.activerecord.backend.expression.collation",
            fromlist=["CollateFunction"],
        ).CollateFunction(d, Column(d, "a"), _sqlserver_collation(d)),
    )

    # -- ALTER TABLE actions ------------------------------------------------
    register_special_constructor(
        "ddl_alter.AddColumnAction", lambda d: ddl_alter.AddColumnAction(d, _integer_column(d))
    )
    register_special_constructor(
        "ddl_alter.AddTableConstraintAction",
        lambda d: ddl_alter.AddTableConstraintAction(
            d, TableConstraint(d, branch=TablePrimaryKeyConstraint(d, ["a"]), name="c")
        ),
    )
    register_special_constructor(
        "ddl_alter.AddIndexAction",
        lambda d: ddl_alter.AddIndexAction(d, ddl_table.IndexDefinition(d, "i", ["a"])),
    )

    # -- constraints that must render without bind parameters ----------------
    register_special_constructor(
        "ddl_table.ColumnConstraint",
        lambda d: ColumnConstraint(d, branch=ColumnNotNullConstraint(d), name="c"),
    )
    register_special_constructor(
        "ddl_table.TableConstraint",
        lambda d: TableConstraint(d, branch=TablePrimaryKeyConstraint(d, ["a"]), name="c"),
    )
    # REFERENCES needs at least one referenced column; the guess supplies none.
    register_special_constructor(
        "ddl_table.ReferencesClause",
        lambda d: ddl_table.ReferencesClause(d, Table(d, "other"), ["b"]),
    )

    # -- predicates whose operand slots are value nodes ----------------------
    # Core's wildcard-split commit calls these out: the operand slots are
    # annotated as forward references (or ``Any``), so the generic guess fills
    # them with plain strings and the instance cannot render. Both factories are
    # the ones core's own dummy2 matrix registers, so the matrices agree.
    # ``LikePredicate`` carries the operator as a parameter, so the guess's
    # ``"x"`` would become the operator rather than the operand.
    from rhosocial.activerecord.backend.expression.predicates import (
        ILikePredicate,
        LikePredicate,
    )

    register_special_constructor(
        "predicates.LikePredicate",
        lambda d: LikePredicate(d, LikeOperator.LIKE, Column(d, "a"), Literal(d, "%x%")),
    )
    register_special_constructor(
        "predicates.ILikePredicate",
        lambda d: ILikePredicate(d, Column(d, "a"), "%x%"),
    )

    # -- statements holding objects the guess cannot name --------------------
    # Each of these was found by running the matrix, not by reading it: the
    # introspective guess hands the statement a bare ``"x"``, and the formatter
    # now refuses that by name.
    #
    # The keys are spelled *identically* to the testsuite's own where they
    # overlap, because ``make_instance`` returns the **first** registry key whose
    # suffix matches -- and the testsuite populates its registry at import time,
    # so a new, shorter key is never consulted for a class an earlier, longer key
    # already claims. Registering ``ddl_type.CreateTypeStatement`` next to the
    # testsuite's ``statements.ddl_type.CreateTypeStatement`` would be silent
    # dead code; re-using the key replaces the entry. That is why the two TYPE
    # registrations below keep the ``statements.`` prefix.
    from rhosocial.activerecord.backend.expression.statements import (
        ddl_comment,
        ddl_index,
        ddl_truncate,
    )

    register_special_constructor(
        "ddl_truncate.TruncateStatement",
        lambda d: ddl_truncate.TruncateStatement(d, _table_obj(d)),
    )
    register_special_constructor(
        "ddl_table.CreateTableStatement",
        lambda d: ddl_table.CreateTableStatement(d, _table_obj(d), [_integer_column(d)]),
    )
    register_special_constructor(
        "ddl_table.DropTableStatement",
        lambda d: ddl_table.DropTableStatement(d, _table_obj(d)),
    )
    register_special_constructor(
        "ddl_view.DropViewStatement",
        lambda d: ddl_view.DropViewStatement(d, _view_obj(d)),
    )
    register_special_constructor(
        "ddl_index.DropFulltextIndexStatement",
        lambda d: ddl_index.DropFulltextIndexStatement(
            d, _index_obj(d), _table_obj(d)
        ),
    )
    register_special_constructor(
        "ddl_index.CreateFulltextIndexStatement",
        lambda d: ddl_index.CreateFulltextIndexStatement(
            d, index=_index_obj(d), table=_table_obj(d), columns=["a"]
        ),
    )
    # A COMMENT ON is DDL: its comment must render as a literal rather than a
    # bind parameter, so the guess's bare string is replaced by one with a name.
    register_special_constructor(
        "ddl_comment.CommentOnStatement",
        lambda d: ddl_comment.CommentOnStatement(d, "table", _table_obj(d), comment="c"),
    )
    register_special_constructor(
        "ddl_trigger.DropTriggerStatement",
        lambda d: __import__(
            "rhosocial.activerecord.backend.expression.statements.ddl_trigger",
            fromlist=["DropTriggerStatement"],
        ).DropTriggerStatement(d, Trigger(d, "trg")),
    )
    # A TYPE definition must be a definition object, and the one the testsuite
    # registers is the Dummy's -- which SQL Server cannot spell, so the statement
    # reports the feature as unsupported rather than rendering. SQL Server's own
    # alias definition is used instead, so it renders and the round-trip is
    # asserted. Same key as the testsuite's, deliberately.
    register_special_constructor(
        "statements.ddl_type.CreateTypeStatement",
        lambda d: ddl_type.CreateTypeStatement(
            d, _type_obj(d), _alias_type_definition(d)
        ),
    )

    # -- MERGE ---------------------------------------------------------------
    register_special_constructor(
        "dml.MergeAction",
        lambda d: MergeAction(
            d,
            MergeActionType.UPDATE,
            {"a": Literal(d, 1)},
            _column_predicate(d),
            "matched",
        ),
    )
    register_special_constructor(
        "dml.MergeStatement",
        lambda d: dml.MergeStatement(
            d,
            target_table=_table_obj(d),
            source=NamedRelationRef(d, Table(d, "src")),
            on_condition=_column_predicate(d),
            when_matched=[
                MergeAction(
                    d,
                    MergeActionType.UPDATE,
                    {"a": Literal(d, 1)},
                    _column_predicate(d),
                    "matched",
                )
            ],
        ),
    )

    # -- SQL Server's own expressions ---------------------------------------
    def pivot(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.pivot import (
            Pivot,
        )

        return Pivot(d, aggregate_function="SUM", value_column="amount", pivot_column="q")

    def columnstore(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.columnstore import (
            SQLServerColumnstoreIndexStatement,
        )

        return SQLServerColumnstoreIndexStatement(d, "cci", "t", columns=["a"])

    def partition_range(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.partition import (
            SQLServerPartitionByRangeClause,
        )

        return SQLServerPartitionByRangeClause(
            d, keys=[Column(d, "id")], partition_scheme="ps"
        )

    def partition_function(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.partition import (
            SQLServerPartitionFunctionExpression,
        )

        return SQLServerPartitionFunctionExpression(d, "pf_sales", "DATE", ["2020-01-01"])

    def partition_scheme(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.partition import (
            SQLServerPartitionSchemeExpression,
        )

        return SQLServerPartitionSchemeExpression(d, "ps_sales", "pf_sales", ["PRIMARY"])

    def alias_type(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.type import (
            SQLServerAliasTypeDefinition,
        )

        return SQLServerAliasTypeDefinition(d, IntegerType(d), nullability=True)

    def table_type(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.type import (
            SQLServerTableTypeDefinition,
        )
        from rhosocial.activerecord.backend.impl.sqlserver.expression.index import (
            SQLServerIndexDefinition,
        )

        return SQLServerTableTypeDefinition(
            d,
            columns=[
                ColumnDefinition(
                    d,
                    "id",
                    IntegerType(d),
                    constraints=[ColumnConstraint(d, branch=ColumnNotNullConstraint(d))],
                )
            ],
            constraints=[
                TableConstraint(d, branch=TablePrimaryKeyConstraint(d, ["id"]))
            ],
            indexes=[SQLServerIndexDefinition(d, "ix_id", ["id"])],
        )

    def clr_type(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.type import (
            SQLServerClrTypeDefinition,
        )

        return SQLServerClrTypeDefinition(d, "assembly", "Namespace.Class")

    def drop_type(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.type import (
            SQLServerDropTypeExpression,
        )

        return SQLServerDropTypeExpression(d, Type(d, "type_name"))

    def rename_type(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.type import (
            SQLServerRenameTypeStatement,
        )

        return SQLServerRenameTypeStatement(d, "old_name", "new_name")

    def column_definition(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.column import (
            SQLServerColumnDefinition,
        )

        return SQLServerColumnDefinition(d, "id", IntegerType(d))

    def alter_column(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.alter_column import (
            SQLServerAlterColumn,
        )

        return SQLServerAlterColumn(d, "c", data_type="INT")

    def comparison(d):
        """A predicate whose operator is a member, not a word.

        The operator normalises at construction, so a word is *accepted* -- but
        the restored node is handed the artifact's word and answers with the
        member, and a class whose own params disagree with that is exactly what
        this matrix exists to see. Building from the member makes the two sides
        the same object and the comparison honest; a word would hide the
        difference instead of measuring it.
        """
        return ComparisonPredicate(
            d, ComparisonOperator.EQ, Column(d, "a"), Column(d, "b")
        )

    def check_constraint(d):
        """A CHECK whose condition compares two columns.

        A DDL condition may not carry a bind parameter -- the checker says so by
        name -- so the guess's ``Literal(d, 1)`` is refused there. Two columns
        render with no parameters at all, which is the position this class is
        actually used in.
        """
        return TableCheckConstraint(d, condition=_column_predicate(d))

    def column_check_constraint(d):
        return ColumnCheckConstraint(d, condition=_column_predicate(d))

    def generated_constraint(d):
        """A generated column whose expression inlines its literal.

        Same DDL rule as the CHECK constraint, and the storage word travels as
        the plain string it is: an enum parameter in a *core* node is the core's
        spelling to settle, so this factory supplies the one form the artifact
        can carry and leaves the rest to the class.
        """
        expression = ArithmeticOperation(
            d, "add", Column(d, "a"), Literal(d, 1, inline=True)
        )
        return ColumnGeneratedConstraint(
            d, expression=expression, storage_type="STORED"
        )

    def foreign_key(d):
        """A foreign key whose referential actions are words, not members.

        The core node stores an enum member when the caller passes nothing, and
        a plain ``Enum`` param is the one thing a plain-JSON artifact cannot
        carry -- the serializer names the type and stops. Passing the words keeps
        the class on the side of the contract this matrix asserts; the default
        path is pinned in :data:`ARTIFACT_GAPS`.
        """
        return ForeignKeyConstraint(
            d,
            columns=["a"],
            foreign_key_table=Table(d, "parent"),
            foreign_key_columns=["id"],
            on_delete="NO ACTION",
            on_update="NO ACTION",
        )

    def create_table(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.create_table import (
            SQLServerCreateTableStatement,
        )

        return SQLServerCreateTableStatement(d, _table_obj(d), [_integer_column(d)])

    def as_graph_table(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.graph import (
            SQLServerAsGraphTableExpression,
            SQLServerGraphTableKind,
        )

        return SQLServerAsGraphTableExpression(d, SQLServerGraphTableKind.NODE)

    def create_function(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.routine import (
            SQLServerCreateFunctionStatement,
        )

        return SQLServerCreateFunctionStatement(
            d, "fn", returns="INT", body="SELECT 1"
        )

    def create_procedure(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.routine import (
            SQLServerCreateProcedureStatement,
        )

        return SQLServerCreateProcedureStatement(d, "p", body="SELECT 1")

    def create_trigger(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.ddl.trigger import (
            SQLServerCreateTriggerStatement,
        )

        return SQLServerCreateTriggerStatement(
            d, "trg", "t", timing="AFTER", events=["INSERT"], body="SELECT 1",
        )

    def sqlserver_merge(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.dml import (
            SQLServerMergeExpression,
        )

        return SQLServerMergeExpression(
            d,
            target_table=_table_obj(d),
            source=NamedRelationRef(d, Table(d, "src")),
            on_condition=_column_predicate(d),
        )

    def option_hint(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.option_hint import (
            maxdop_hint,
            SQLServerOptionHintClause,
        )

        return SQLServerOptionHintClause(d, [maxdop_hint(4)])

    def pseudo_column(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.graph import (
            SQLServerGraphPseudoColumn,
        )

        return SQLServerGraphPseudoColumn(d, "$node_id", table="g")

    def graph_pattern(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.graph import (
            SQLServerGraphEdgeRef,
            SQLServerGraphNodeRef,
            SQLServerGraphPattern,
        )

        return SQLServerGraphPattern(
            d,
            SQLServerGraphNodeRef(d, "people"),
            [(SQLServerGraphEdgeRef(d, "knows"), SQLServerGraphNodeRef(d, "friends"))],
        )

    def match_predicate(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.graph import (
            SQLServerMatchPredicate,
        )

        return SQLServerMatchPredicate(d, graph_pattern(d))

    def shortest_path(d):
        from rhosocial.activerecord.backend.impl.sqlserver.expression.graph import (
            SQLServerShortestPathExpression,
        )

        return SQLServerShortestPathExpression(d, graph_pattern(d), 1, 3)

    # Core also has a ``pivot.Pivot`` of its own, and ``make_instance`` matches
    # suffixes with ``str.endswith``, so the longer suffix keeps this
    # registration on the SQL Server class instead of capturing core's as well.
    # Core's generic Pivot and Unpivot render on this dialect now -- they are
    # rows in the rendered half of the matrix, not in LEGITIMATE_NON_RENDERS --
    # and SQL Server's own spelling rides its own class and its own
    # constructor.
    register_special_constructor(
        "sqlserver.expression.pivot.Pivot", pivot
    )
    register_special_constructor(
        "columnstore.SQLServerColumnstoreIndexStatement", columnstore
    )
    register_special_constructor(
        "partition.SQLServerPartitionByRangeClause", partition_range
    )
    register_special_constructor(
        "partition.SQLServerPartitionFunctionExpression", partition_function
    )
    register_special_constructor(
        "partition.SQLServerPartitionSchemeExpression", partition_scheme
    )
    register_special_constructor("type.SQLServerAliasTypeDefinition", alias_type)
    register_special_constructor("type.SQLServerTableTypeDefinition", table_type)
    register_special_constructor("type.SQLServerClrTypeDefinition", clr_type)
    register_special_constructor("type.SQLServerDropTypeExpression", drop_type)
    register_special_constructor("type.SQLServerRenameTypeStatement", rename_type)
    register_special_constructor("column.SQLServerColumnDefinition", column_definition)
    register_special_constructor("alter_column.SQLServerAlterColumn", alter_column)
    # -- predicates and constraints that must render with no bind parameters ---
    # The operator normalises, the CHECK condition is a DDL position, and the
    # generated expression inlines its literal: three places the guess's bound
    # ``Literal`` is refused by name.
    register_special_constructor("predicates.ComparisonPredicate", comparison)
    register_special_constructor("ddl_table.TableCheckConstraint", check_constraint)
    register_special_constructor(
        "ddl_table.ColumnCheckConstraint", column_check_constraint
    )
    register_special_constructor(
        "ddl_table.ColumnGeneratedConstraint", generated_constraint
    )
    # A core node whose own default is an enum member cannot travel: the words
    # are supplied here so the class is constructible on the side of the
    # contract this matrix asserts, and the default path stays recorded in
    # ARTIFACT_GAPS rather than being quietly un-testable.
    register_special_constructor(
        "statements.ddl_table.ForeignKeyConstraint", foreign_key
    )
    register_special_constructor(
        "create_table.SQLServerCreateTableStatement", create_table
    )
    register_special_constructor(
        "ddl.graph.SQLServerAsGraphTableExpression", as_graph_table
    )
    register_special_constructor(
        "ddl.routine.SQLServerCreateFunctionStatement", create_function
    )
    register_special_constructor(
        "ddl.routine.SQLServerCreateProcedureStatement", create_procedure
    )
    register_special_constructor(
        "ddl.trigger.SQLServerCreateTriggerStatement", create_trigger
    )
    register_special_constructor("dml.SQLServerMergeExpression", sqlserver_merge)
    register_special_constructor("option_hint.SQLServerOptionHintClause", option_hint)
    register_special_constructor("graph.SQLServerGraphPseudoColumn", pseudo_column)
    register_special_constructor("graph.SQLServerGraphPattern", graph_pattern)
    register_special_constructor("graph.SQLServerMatchPredicate", match_predicate)
    register_special_constructor(
        "graph.SQLServerShortestPathExpression", shortest_path
    )
    # -- two core classes that build as soon as they get a valid argument ----
    # Both were measured before being named here: with ``raw`` carrying a real
    # type name CUSTOM renders it, and with ``which="nil"`` the UUID constant
    # renders the nil literal cast to UNIQUEIDENTIFIER. Neither is a skip, and
    # neither belongs in UNCONSTRUCTIBLE -- a constructor is the honest answer
    # for a class that constructs fine once its own slot is filled.
    register_special_constructor(
        "types.custom.CustomType", lambda d: CustomType(d, raw="VARCHAR(10)")
    )
    register_special_constructor(
        "uuid.UUIDConstantExpression", lambda d: UUIDConstantExpression(d, "nil")
    )
    # -- one backend-specific question, answered in the form a name allows -----
    # The extended-properties statement names its object one of two ways -- the
    # catalogue id or the table name -- and refuses a statement that names
    # neither, because "the properties of nothing" is not a question. The
    # introspective guess invents neither, so the table-name form is filled in
    # here: it is the one a caller holding only a name uses, and the one the
    # CLI asks.
    from rhosocial.activerecord.backend.impl.sqlserver.expression.introspection import (
        SQLServerExtendedPropertyListQueryStatement,
    )

    register_special_constructor(
        "introspection.SQLServerExtendedPropertyListQueryStatement",
        lambda d: SQLServerExtendedPropertyListQueryStatement(d, table_name="users"),
    )
    # -- scalar string functions whose parameters are typed operands ----------
    # The introspective guess supplies a bare string where these classes take
    # SQLValue / BaseExpression operands, so the constructor refuses; each
    # one renders as soon as a real operand rides in the slot.
    register_special_constructor(
        "functions.string.ChrFunction",
        lambda d: _string_fn(d, "ChrFunction", Literal(d, 65)),
    )
    register_special_constructor(
        "functions.string.LeftFunction",
        lambda d: _string_fn(d, "LeftFunction", Column(d, "a"), Literal(d, 3)),
    )
    register_special_constructor(
        "functions.string.RightFunction",
        lambda d: _string_fn(d, "RightFunction", Column(d, "a"), Literal(d, 3)),
    )
    register_special_constructor(
        "functions.string.SpaceFunction",
        lambda d: _string_fn(d, "SpaceFunction", Literal(d, 3)),
    )
    register_special_constructor(
        "functions.string.SubstringExpression",
        lambda d: _string_fn(d, "SubstringExpression", Column(d, "a"), Literal(d, 1)),
    )
    register_special_constructor(
        "functions.string.OverlayExpression",
        lambda d: _string_fn(
            d, "OverlayExpression", Column(d, "a"), Column(d, "b"), Literal(d, 1)
        ),
    )
    # -- the EXTRACT family's shared base and its concrete node ---------------
    # Both take a field plus a BaseExpression source; the guess supplies a
    # bare string for the source and the class refuses it.
    register_special_constructor(
        "datetime.ExtractFieldExpression",
        lambda d: _datetime_fn(d, "ExtractFieldExpression", "YEAR", Column(d, "ts")),
    )
    register_special_constructor(
        "datetime._ExtractBase",
        lambda d: _datetime_fn(d, "_ExtractBase", "YEAR", Column(d, "ts")),
    )


register_specials()


# ---------------------------------------------------------------------------
# Lists that cannot grow or shrink silently
# ---------------------------------------------------------------------------

#: Classes the introspective constructor cannot build.
#:
#: Each is a real coverage gap, named here so it is visible rather than lost.
#: :func:`test_unconstructible_list_is_exact` pins the tuple against what the
#: constructor really skips, in both directions: a class that gains a
#: constructor fails here until this entry is removed, and a class that starts
#: failing to build fails here too. Neither can become a quiet skip.
#:
#: The reasons are grouped by cause, not by module, and all four are now the same
#: cause: a required parameter the introspective guess cannot satisfy, because it
#: sits behind a defaulted positional or is a member of a closed set. Registering a
#: constructor is the way to retire any of them.
#:
#: The four XML classes this tuple used to hold were never a gap in the classes.
#: ``XMLTableExpression`` wants ``columns: Sequence[XMLTableColumn]`` and the three
#: forest-shaped ones each want a ``Sequence`` of their own item type; the guess
#: read that annotation's *alias* name, ``"Sequence"``, decided it named a
#: catalogue object and handed the parameter a ``Sequence`` instead of a list. The
#: classes were fine and the harness was wrong. They construct now, and each one
#: turns out to be a genuine capability gap rather than a render, which is why all
#: four moved to :data:`LEGITIMATE_NON_RENDERS` rather than to a render assertion.
UNCONSTRUCTIBLE = (
    # ALTER CONSTRAINT (renamed AlterConstraintAction by the core's "name an
    # action by what it is" wave). `name` and `constraint_type` sit behind
    # defaulted positionals and are keyword-only, so the introspective
    # constructor skips them and the class refuses an incomplete action
    # (`ValueError: constraint_name must be a non-empty string`, because the
    # defaulted `constraint_name` stays None).
    "rhosocial.activerecord.backend.expression.statements.ddl_alter.AlterConstraintAction",
    # ADD DOMAIN CHECK. Widens a SQLPredicate into a DomainCheckConstraint and
    # needs one; the guess supplies a bare comparison whose literal would have
    # to render as a bind parameter, which DDL cannot carry. (It supplies a bare
    # *string* in fact: the annotation names a `DomainCheckConstraint`, whose
    # `\bDomain\b` fragment does not match inside the longer word, so the guess
    # falls through to its name-based default and the class raises
    # `TypeError: check must be a DomainCheckConstraint instance, got str`.)
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.AddDomainCheckAction",
)

#: Message fragments the pins below match on.
_NO_FORMATTER = "does not declare its dialect formatting method name"
#: The *dispatch* failure -- ``format_method`` named a method the dialect does
#: not define, so ``to_sql()`` never called anything. Core reported that as
#: ``AttributeError`` and now reports it as ``UnsupportedFeatureError``, which is
#: the type a dialect uses when it *knows* a statement and refuses it. The two are
#: the same type now, so the fragment is what separates them: this is the one
#: phrase only the dispatch's suggestion contains, offering to mix in a mixin.
#: A class that stopped being a dispatch failure and became a genuine refusal
#: would raise the same type and fail on the fragment instead.
_NO_SUCH_METHOD = "mix in the mixin that provides it"
_NO_SUCH_TYPE = "does not support the generic type"

#: Classes that construct but cannot render, for a reason belonging to their own
#: tree rather than to a defect. Each entry pins the exception type *and* a
#: message fragment, so a class that starts failing for a *different* reason
#: fails here instead of passing quietly -- which is the whole point, given that
#: this matrix used to swallow every one of these.
LEGITIMATE_NON_RENDERS = {
    # ---- bases that name an expression category, not a renderable thing ----
    # Each of these is a base class that deliberately declares no `format_method`,
    # so `to_sql()` reports that there is nothing to dispatch. They are not
    # `inspect.isabstract` -- they are concrete enough to construct -- so the
    # registry keeps them, and each is pinned to its exact message so a base that
    # started rendering fails here instead of passing quietly.
    "rhosocial.activerecord.backend.expression.bases.SQLPredicate": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.bases.SQLValue": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    # The roots of the object tree. Each concrete object overrides `format_method`
    # with its own `format_*_object`; the base names only what every catalogue
    # object has in common.
    "rhosocial.activerecord.backend.expression.objects.base.SchemaObject": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.objects.relation.RelationObject": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.objects.routine.RoutineObject": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.objects.type_.TypeObject": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    # Expression-category bases whose concrete members each name their own
    # formatter: an ALTER TABLE action, an INSERT row source, a transaction
    # step, a temporal value, an introspection query, a DDL column clause.
    "rhosocial.activerecord.backend.expression.statements.ddl_alter.AlterTableAction": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.statements.dml.InsertDataSource": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.transaction.TransactionStatement": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.datetime._TemporalValue": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_table.ColumnClause": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_table."
    "ColumnConstraintBranch": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_table."
    "TableConstraintBranch": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    "rhosocial.activerecord.backend.expression.introspection.IntrospectionExpression": (
        NotImplementedError,
        _NO_FORMATTER,
    ),
    # Two introspection statements ask for a *bundle* -- a table with its
    # columns, indexes and keys; a trigger with its table and definition -- and
    # this backend answers each part with a statement of its own (the column,
    # index and foreign-key queries; ``sys.triggers`` filtered by name). It
    # declares neither bundle formatter, so the core stub refuses it by name.
    # Pinned rather than implemented: a formatter nobody asks for would be SQL
    # this backend never runs.
    "rhosocial.activerecord.backend.expression.introspection."
    "TableInfoQueryStatement": (
        NotImplementedError,
        "Subclass must implement format_table_info_query_statement",
    ),
    "rhosocial.activerecord.backend.expression.introspection."
    "TriggerInfoQueryStatement": (
        NotImplementedError,
        "Subclass must implement format_trigger_info_query_statement",
    ),

    # ---- the root of the row-source tree ----
    # No concrete source renders through `format_table_source`; each overrides
    # `format_method`. Rendering the base would mean inventing SQL for an object
    # that carries nothing but an alias. Dispatch failure, so UnsupportedFeatureError.
    "rhosocial.activerecord.backend.expression.sources.base.TableSource": (
        UnsupportedFeatureError,
        _NO_SUCH_METHOD,
    ),

    # ---- features SQL Server does not model ----
    # Each of these names a `format_method` the dialect does not define, so the
    # dispatch fails before any formatter is called: `to_sql()` reports that the
    # dialect declares no such method, not that it knows the statement and refuses
    # it. Those are now the *same* exception type -- core raised AttributeError
    # for the first and unified it to UnsupportedFeatureError with everything
    # else -- so the pinned type no longer tells the two apart and the pinned
    # fragment does. See _NO_SUCH_METHOD.
    #
    # SQL/XML (thirteen): SQL Server's native XML/Xquery is not the SQL/XML
    # feature set, which is why every SQLXML* protocol is in the dialect's
    # negative list.
    #
    # Nine are the XMLAGG / XMLCOMMENT / XMLElement / XMLEXISTS / XMLPARSE /
    # XMLPI / XMLQUERY / XMLROOT / XMLSERIALIZE family; four more are XMLTABLE,
    # XMLATTRIBUTES, XMLCONCAT and XMLFOREST. All thirteen give the same answer
    # to the same question -- `SQLServerDialect` declares no `format_xml*` method
    # at all, so the dispatch refuses each by name before any formatter is
    # reached. The second four only became visible when the testsuite's
    # introspective constructor stopped reading a `Sequence[...]` annotation as a
    # request for a `Sequence` catalogue object; see the note above
    # UNCONSTRUCTIBLE. They are not a new gap in SQL Server -- the other nine
    # had been saying the same thing all along.
    "rhosocial.activerecord.backend.expression.xml.XMLAggExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLAttributesExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLCommentExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLConcatExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLElementExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLExistsPredicate": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLForestExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLPIExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLParseExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLQueryExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLRootExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLSerializeExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.xml.XMLTableExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    # CREATE/ALTER/DROP DOMAIN (nine): SQL Server has no DOMAIN. The three
    # statements and their five actions plus the check constraint and the domain
    # value all name a formatter the dialect does not have.
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.CreateDomainStatement": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.AlterDomainStatement": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.DropDomainStatement": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.DomainCheckConstraint": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.DomainValueExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.DropDomainCheckAction": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.DropDomainDefaultAction": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.DropDomainNotNullAction": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.RenameDomainAction": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.SetDomainDefaultAction": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.SetDomainNotNullAction": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    # SQL/PGQ property graphs (eight): no GRAPH_TABLE, so no graph DDL either.
    # The negative list records GraphTableSupport; these are the same gap seen
    # from the expression tree.
    "rhosocial.activerecord.backend.expression.graph.GraphTableExpression": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.graph.VertexTable": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    # ``graph.EdgeTable`` used to be pinned here; the class now lives in
    # ``objects.relation`` and renders through the same format_table_object
    # every table uses, so the row is gone.
    "rhosocial.activerecord.backend.expression.graph.ColumnsClause": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.graph.TablePropertiesClause": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.graph.CreatePropertyGraphStatement": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.graph.AlterPropertyGraphStatement": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    "rhosocial.activerecord.backend.expression.graph.DropPropertyGraphStatement": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),
    # COMMENT ON: SQL Server has no standalone COMMENT ON statement, which the
    # dialect's negative list records as CommentSupport.
    "rhosocial.activerecord.backend.expression.statements.ddl_comment.CommentOnStatement": (
        UnsupportedFeatureError, _NO_SUCH_METHOD
    ),

    # ---- the root of the type tree ----
    # Every concrete type declares its own generic `name`, which is what
    # `format_data_type` dispatches on; the root declares none, so there is
    # nothing to dispatch. TypeError, not UnsupportedFeatureError, because the
    # class is incomplete rather than the dialect being unable. The message
    # names the missing concept rather than the missing declaration: a bare
    # DataType carries no name to dispatch, so the refusal speaks of the
    # generic type it could not resolve.
    "rhosocial.activerecord.backend.expression.types._base.DataType": (
        TypeError,
        "does not support the generic type",
    ),
    # Core types with no SQL Server spelling (eight). SQL Server has no ARRAY,
    # no JSONB, no TIMESTAMPTZ, and spells BINARY as its own types, so these
    # declare a generic name the dialect does not implement. This is a
    # capability gap in this backend's type table, not a defect in the class.
    "rhosocial.activerecord.backend.expression.types.array.ArrayType": (
        TypeError, _NO_SUCH_TYPE
    ),
    "rhosocial.activerecord.backend.expression.types.binary.BinaryType": (
        TypeError, _NO_SUCH_TYPE
    ),
    "rhosocial.activerecord.backend.expression.types.binary.VarBinaryType": (
        TypeError, _NO_SUCH_TYPE
    ),
    "rhosocial.activerecord.backend.expression.types.datetime_.IntervalType": (
        TypeError, _NO_SUCH_TYPE
    ),
    "rhosocial.activerecord.backend.expression.types.datetime_.TimeTzType": (
        TypeError, _NO_SUCH_TYPE
    ),
    "rhosocial.activerecord.backend.expression.types.json_.JsonBType": (
        TypeError, _NO_SUCH_TYPE
    ),
    "rhosocial.activerecord.backend.expression.types.uuid_.UUIDType": (
        TypeError, _NO_SUCH_TYPE
    ),
    # ENUM (nine, and the ninth is this one's reason to exist): the class
    # constructs now that its keyword-only ``values`` gets a list from the
    # guess, and the render refuses exactly what the eight above refuse --
    # SQL Server has no ENUM generic, and the dialect says so while
    # suggesting the VARCHAR it actually uses.
    "rhosocial.activerecord.backend.expression.types.enum_.EnumType": (
        TypeError, _NO_SUCH_TYPE
    ),
    # The declared-result annotations: the base and every concrete member of
    # it. Each carries only the node it annotates; the alias the core's
    # ``format_declared_result`` reads belongs to the concrete named
    # annotations, so the guessed instance -- a bare ``Literal`` -- has none,
    # and the formatter fails naming it. The core formatter reading it is the
    # moving edge of the value-literal rework (a narrowed ``Literal`` no longer
    # carries ``alias`` at all); these rows record what the tree actually does
    # today, one per class, because the concrete annotations are collected in
    # their own right and an unnamed failure is a defect by this matrix's rule.
    "rhosocial.activerecord.backend.expression.declared._Annotation": (
        AttributeError,
        "has no attribute 'alias'",
    ),
    "rhosocial.activerecord.backend.expression.declared.ArrayAnnotation": (
        AttributeError,
        "has no attribute 'alias'",
    ),
    "rhosocial.activerecord.backend.expression.declared.BinaryAnnotation": (
        AttributeError,
        "has no attribute 'alias'",
    ),
    "rhosocial.activerecord.backend.expression.declared.BooleanAnnotation": (
        AttributeError,
        "has no attribute 'alias'",
    ),
    "rhosocial.activerecord.backend.expression.declared.IntegerAnnotation": (
        AttributeError,
        "has no attribute 'alias'",
    ),
    "rhosocial.activerecord.backend.expression.declared.JSONAnnotation": (
        AttributeError,
        "has no attribute 'alias'",
    ),
    "rhosocial.activerecord.backend.expression.declared.NumberAnnotation": (
        AttributeError,
        "has no attribute 'alias'",
    ),
    "rhosocial.activerecord.backend.expression.declared.TemporalAnnotation": (
        AttributeError,
        "has no attribute 'alias'",
    ),
    "rhosocial.activerecord.backend.expression.declared.TextAnnotation": (
        AttributeError,
        "has no attribute 'alias'",
    ),
    "rhosocial.activerecord.backend.expression.declared.UUIDAnnotation": (
        AttributeError,
        "has no attribute 'alias'",
    ),
    "rhosocial.activerecord.backend.expression.declared.XMLAnnotation": (
        AttributeError,
        "has no attribute 'alias'",
    ),

    # ---- core expressions SQL Server has no T-SQL spelling for ----
    #
    # The full-text and routine rows below are gone: SQL Server's own T-SQL DDL
    # used to take over the *core formatter names* --
    # ``format_create_fulltext_index_statement`` took ``(table, columns,
    # key_index, catalog_name)`` where core's takes the expression, so the core
    # expression dispatched into a signature it could not satisfy. The
    # statement/name unification renamed the backend's formatters to their own
    # spelling (``format_create_full_text_index_statement`` and friends),
    # which freed the core names: the core expressions now reach core's generic
    # formatters and render, so there is nothing left to pin here.
    #
    # The two rows below changed shape when the formatters stopped probing
    # for ``name`` and started reading it: the probe's default (``""``) used
    # to turn a node with no ``name`` field into "the name is missing", and
    # the direct read says what is actually wrong -- the shadowed SQL:1999
    # statements carry no ``name`` field at all.
    "rhosocial.activerecord.backend.expression.statements.ddl_function.CreateFunctionStatement": (
        AttributeError,
        "has no attribute 'name'",
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_trigger.DropTriggerStatement": (
        AttributeError,
        "has no attribute 'name'",
    ),
}


# ---------------------------------------------------------------------------
# The artifact gap: a node the plain-JSON payload cannot carry, or one channel
# of it cannot read back
# ---------------------------------------------------------------------------
#
# Rendering is this matrix's first axis; travelling is its second, and a class
# can answer "yes" to one and "no" to the other. Two shapes, both named here
# rather than swallowed:
#
# * a parameter whose type is not a JSON scalar. The serializer names the type
#   and stops -- "is not one of the value kinds this package can write" -- and
#   that is a decision on the *node*'s side, not this dialect's. Where the node
#   can be built with a scalar in that slot, the matrix's constructor does so
#   and the class asserts normally; the rows below are the ones where it cannot
#   (``CreateViewStatement`` normalises ``options=None`` into a
#   ``ViewOptions()`` no matter what the caller passes).
# * one channel failing where the others succeed. The XML codec used to spell
#   an enum parameter as ``Class.MEMBER`` while the dict and JSON codecs spelled
#   it as the member's own value, which every one of these constructors
#   accepts; no reader turned the word back into a member, so the constructor
#   refused it. That was a core-side gap, recorded here with the channel name
#   so the day core spells it as the value, the row goes -- and the rows have
#   gone: core spells the enum as its value on every channel now, so the
#   EXTRACT family, the interval arithmetic and the XML document-type
#   expressions all travel.
#
# Each entry is ``(channels, exception type, message fragment)``. ``channels``
# is one of ``"dict"`` / ``"json"`` / ``"xml"``, a tuple of them, or ``"all"``;
# a type of ``None`` names the other shape of gap, where the channel carries the
# node but restores a different *spelling* of one parameter. Either way the row
# is asserted against the tree: a class that starts travelling fails until its
# row goes, and a class that stops travelling with no row fails the per-class
# assertion.

#: Nodes whose artifact cannot be written or read back, by channel and reason.
ARTIFACT_GAPS = {
    # CREATE VIEW: ``options`` is a dataclass parameter and the constructor
    # normalises a missing one into ``ViewOptions()``, so the class cannot be
    # built with a scalar there. SQL Server has no view options of its own --
    # the dialect renders the statement and ignores them -- but the artifact
    # still has to carry what the constructor stored.
    "rhosocial.activerecord.backend.expression.statements.ddl_view."
    "CreateViewStatement": (
        "all",
        TypeError,
        "not one of the value kinds",
    ),
    # SQL/PGQ property graphs: ``GraphColumn`` is a dataclass, and a dataclass
    # parameter is the other thing a plain-JSON artifact cannot carry. No
    # construction choice avoids it -- a COLUMNS clause is made of columns.
    "rhosocial.activerecord.backend.expression.graph.GraphTableExpression": (
        "all",
        TypeError,
        "not one of the value kinds",
    ),
    # CREATE TABLE ... CLONE: ``mode`` is a ``(str, Enum)`` but the constructor
    # refuses the bare word the artifact carries ("mode must be a
    # CreateTableCloneMode, got str") -- the dict channel keeps the Python
    # member and round-trips, so only the two JSON-family channels are pinned.
    "rhosocial.activerecord.backend.expression.statements.ddl_table."
    "CreateTableCloneStatement": (
        ("json", "xml"),
        TypeError,
        "must be a CreateTableCloneMode",
    ),
}

#: The channels a row's ``channels`` field may name.
_ARTIFACT_CHANNELS = ("dict", "json", "xml")

#: The codec pair each channel runs, in one place because three call sites
#: need the same mapping and a drift between them would let one channel be
#: tested on a codec another channel rendered with.
_ARTIFACT_CODECS = {}


def _artifact_codecs():
    """(encode, decode) per channel, imported here rather than at module level.

    The serialization module is the only place these names live, and the matrix
    imports them where it uses them -- the same discipline the rest of this file
    follows for ``UnsupportedFeatureError``.
    """
    if not _ARTIFACT_CODECS:
        from rhosocial.activerecord.backend.expression.serialization import (
            deserialize,
            deserialize_json,
            deserialize_xml,
            serialize,
            serialize_json,
            serialize_xml,
        )

        _ARTIFACT_CODECS.update(
            {
                "dict": (serialize, deserialize),
                "json": (serialize_json, deserialize_json),
                "xml": (serialize_xml, deserialize_xml),
            }
        )
    return _ARTIFACT_CODECS


def _channel_channels(channels):
    """The channel names one pin row covers.

    ``"all"`` covers every channel, because a node whose parameter is not a
    JSON scalar cannot be written on any of them -- the three codecs agree
    about what a scalar is.
    """
    if channels == "all":
        return _ARTIFACT_CHANNELS
    if isinstance(channels, str):
        return (channels,)
    return tuple(channels)


def _record_channel(fqn: str, channel: str, exc: Exception) -> None:
    """Assert *exc* on this channel is the pin :data:`ARTIFACT_GAPS` names.

    Raises:
        AssertionError: The class has no row, its row names other channels, or
            the exception is not the row's type and fragment -- any of which
            means the failure is new and this matrix must not absorb it.
    """
    row = ARTIFACT_GAPS.get(fqn)
    assert row is not None, (
        f"{fqn}: the {channel} channel could not carry this node "
        f"({type(exc).__name__}: {exc}) and the class is not in ARTIFACT_GAPS."
    )
    pinned_channels, pinned_type, fragment = row
    assert channel in _channel_channels(pinned_channels), (
        f"{fqn}: the {channel} channel failed but the pin names "
        f"{pinned_channels!r}. Either the gap moved to another channel or the "
        "row needs its channels updated."
    )
    assert type(exc) is pinned_type and fragment in str(exc), (
        f"{fqn}: ARTIFACT_GAPS pins {pinned_type.__name__} containing "
        f"{fragment!r}, but the {channel} channel raised "
        f"{type(exc).__name__}: {exc}"
    )


# ---------------------------------------------------------------------------
# The dispatch gap: a missing formatter is a decision, not an omission
# ---------------------------------------------------------------------------
#
# ``to_sql()`` reports a dialect that names no formatter for a class through
# the same ``UnsupportedFeatureError`` a capability probe uses, so the type
# alone cannot say "this backend never wired the feature in". The frame the
# dispatch puts around the method name can, and it is the only place in the
# tree that opens it -- see :func:`_dispatched_formatter`.

#: The two ends of the frame ``to_sql()`` puts around a formatting method name
#: in the ``feature_name`` of the ``UnsupportedFeatureError`` it raises for a
#: dialect that has no such formatter.
_DISPATCH_FEATURE_PREFIX = "the '"
_DISPATCH_FEATURE_SUFFIX = "' statement"


def _dispatched_formatter(exc):
    """The formatting method *exc* says the dialect does not have, or ``None``.

    ``None`` means *exc* is not the dispatch reporting a missing formatter --
    it is a probe inside a formatter that refused a feature, which is the
    ``"unsupported"`` branch and needs no row anywhere.

    Args:
        exc: An :class:`UnsupportedFeatureError` raised out of ``to_sql()``.

    Returns:
        The method name out of the ``feature_name`` frame, or ``None`` when
        *exc* came from a probe rather than from the dispatch.
    """
    feature = exc.feature_name
    if not feature.startswith(_DISPATCH_FEATURE_PREFIX):
        return None
    if not feature.endswith(_DISPATCH_FEATURE_SUFFIX):
        return None
    method = feature[len(_DISPATCH_FEATURE_PREFIX) : len(feature) - len(_DISPATCH_FEATURE_SUFFIX)]
    return method if method else None


#: Formatters SQL Server declares no implementation of, grouped by the feature
#: that is absent, each group naming every method the matrix's classes need.
#:
#: A class needing one of these fails with ``UnsupportedFeatureError`` naming
#: the method it wanted, and :func:`assert_sql_roundtrip_classified` asserts
#: that method is a row here. :meth:`TestMatrixIntegrity.\
#: test_unmodelled_formatter_list_is_exact` pins the table in both directions:
#: a formatter that starts existing moves its classes out of the table and the
#: pin fails until the entry goes, and a class that starts needing a method
#: outside the table fails outright instead of passing as "unsupported".
#:
#: These are not defects: they are features SQL Server does not have, which the
#: shared renderer reports by naming the method it could not find. The
#: pad/repeat group is the one that made the accounting necessary: SQL Server
#: has no ``LPAD``/``RPAD``/``REPEAT`` functions, the nodes dispatch to
#: formatters no base in this dialect provides, and before the table existed
#: those refusals were allowed on their type alone.
UNMODELLED_FORMATTERS = {
    "SQL/XML (SQL Server's native XML/XQuery is not the SQL/XML feature set, "
    "so the dialect declares no ``format_xml*`` method at all; the PASSING "
    "clause rides that same family)": (
        "format_xml_agg_expression",
        "format_xml_attributes_expression",
        "format_xml_comment_expression",
        "format_xml_concat_expression",
        "format_xml_element_expression",
        "format_xmlexists_predicate",
        "format_xml_forest_expression",
        "format_xmlpi_expression",
        "format_xml_parse_expression",
        "format_xml_query_expression",
        "format_xml_root_expression",
        "format_xml_serialize_expression",
        "format_xml_table_expression",
        "format_passing_clause",
    ),
    "DOMAIN (SQL Server has no DOMAIN object, so no domain statement or "
    "action renders)": (
        "format_create_domain_statement",
        "format_alter_domain_statement",
        "format_drop_domain_statement",
        "format_domain_alter_action",
        "format_domain_check_constraint",
        "format_domain_value_expression",
    ),
    "SQL/PGQ property graphs (no GRAPH_TABLE, so no graph DDL either)": (
        "format_create_property_graph_statement",
        "format_alter_property_graph_statement",
        "format_drop_property_graph_statement",
        "format_graph_table_expression",
        "format_vertex_table",
        "format_edge_table_definition",
        "format_graph_columns_clause",
        "format_table_properties_clause",
    ),
    "COMMENT ON (SQL Server has no standalone COMMENT ON; extended properties "
    "spell it, and the dialect's negative list records CommentSupport)": (
        "format_comment_on_statement",
    ),
    "LPAD / RPAD (SQL Server has no pad functions; padding is spelled with "
    "REPLICATE together with RIGHT / LEFT)": (
        "format_lpad_expression",
        "format_rpad_expression",
    ),
    "REPEAT (SQL Server spells it REPLICATE)": ("format_repeat_expression",),
    "the TableSource root (every concrete row source overrides its formatter; "
    "the root carries nothing but an alias and is never rendered)": ("format_table_source",),
}


def _unmodelled_methods():
    """The flat set of formatter names in :data:`UNMODELLED_FORMATTERS`."""
    return {method for methods in UNMODELLED_FORMATTERS.values() for method in methods}


# ---------------------------------------------------------------------------
# The local SQL assertion: classify the outcome instead of swallowing it
# ---------------------------------------------------------------------------


def assert_sql_roundtrip_classified(
    fqn: str, instance, dialect
) -> str:
    """Assert an expression's SQL survives the round-trip, or say precisely why not.

    Four outcomes, each asserted:

    * **renders** -- all three encodings must restore byte-identical SQL *and*
      byte-identical bind parameters.
    * a member of :data:`LEGITIMATE_NON_RENDERS` -- unrenderable by design,
      asserted as its exact type *and* message fragment.
    * ``UnsupportedFeatureError`` from a class *not* named in the dict -- SQL
      Server does not model the feature. Asserted as exactly that type, so a
      subclass raised for an unrelated reason is still visible rather than passing.
    * ``UnsupportedFeatureError`` naming a formatting method, for a class not
      named in the dict -- the dispatch found nothing, which is a wiring fact
      about this backend rather than a capability answer. The method must be
      in :data:`UNMODELLED_FORMATTERS`; the table entry is the reason.
    * **anything else** -- a failure naming the class and the exception.

    A channel that cannot carry the node is not a render answer either: it is
    asserted against :data:`ARTIFACT_GAPS` by :func:`_record_channel`, and the
    class is reported as ``"artifact-gap"`` rather than as ``"rendered"`` so the
    distribution does not claim three channels where one is pinned.

    The dict is consulted before the ``UnsupportedFeatureError`` branch, not
    after. A missing formatter is now reported through that same type, so with the
    ``except`` clause in front a pinned dispatch-failure entry would never be
    looked up: its type and message would go unasserted on this path and the
    table would have stopped saying which of the two causes each class has.
    Checking the pin first keeps both halves of it load-bearing.

    Args:
        fqn: Fully qualified name of the class, used in every message.
        instance: The expression to render.
        dialect: The dialect to render it against.

    Returns:
        A short string naming the branch taken -- ``"rendered"``,
        ``"artifact-gap"``, ``"non-render"``, ``"unsupported"`` or
        ``"unmodelled"`` -- so the classification distribution can be reported.

    Raises:
        AssertionError: On a round-trip mismatch, on an unexpected exception
            type, or when a class's rendering outcome changed.
    """
    try:
        expected_sql, expected_params = instance.to_sql()
    except Exception as exc:
        if fqn in LEGITIMATE_NON_RENDERS:
            expected_type, fragment = LEGITIMATE_NON_RENDERS[fqn]
            assert type(exc) is expected_type, (
                f"{fqn}: LEGITIMATE_NON_RENDERS pins this class as a legitimate "
                f"non-render raising {expected_type.__name__}, but it raised "
                f"{type(exc).__name__}: {exc}"
            )
            assert fragment in str(exc), (
                f"{fqn}: expected {expected_type.__name__} and was expected to say "
                f"{fragment!r}, but it said: {exc}"
            )
            return "non-render"
        if type(exc) is UnsupportedFeatureError:
            method = _dispatched_formatter(exc)
            if method is not None:
                assert method in _unmodelled_methods(), (
                    f"{fqn}: to_sql() reported that {exc.dialect_name} declares no "
                    f"{method!r}, which is not in UNMODELLED_FORMATTERS.\n"
                    f"  Either SQL Server now needs that formatter -- in which "
                    f"case the class should render and this entry should go -- "
                    f"or the feature is absent and the method belongs in that "
                    f"table with its reason."
                )
                return "unmodelled"
            return "unsupported"
        raise AssertionError(
            f"{fqn}: to_sql() raised {type(exc).__name__}, which is neither a "
            f"render nor a classified non-render, and this is a defect.\n"
            f"  UnsupportedFeatureError means the dialect lacks the feature and "
            f"is always allowed.\n"
            f"  A class that cannot render for a reason belonging to its own "
            f"tree belongs in LEGITIMATE_NON_RENDERS.\n"
            f"  Exception: {exc}"
        ) from exc

    gapped = []
    for channel, codec in ((name, _artifact_codecs()[name]) for name in _ARTIFACT_CHANNELS):
        encode, decode = codec
        try:
            decoded = decode(encode(instance), dialect)
            decoded_sql, decoded_params = decoded.to_sql()
        except Exception as exc:
            # A channel that cannot carry the node is recorded, not swallowed:
            # _record_channel asserts the pin's type and fragment, so a new
            # failure on a new class fails here.
            _record_channel(fqn, channel, exc)
            gapped.append(channel)
            continue
        assert decoded_sql == expected_sql, (
            f"{fqn}: {channel} round-trip changed the SQL.\n"
            f"  original: {expected_sql!r}\n"
            f"  {channel}: {decoded_sql!r}"
        )
        # A tuple goes out as an array -- JSON draws no distinction -- and a
        # constructor handed a list may keep it as one. The artifact promised
        # the members, so the members are what is compared.
        assert list(decoded_params) == list(expected_params) and len(
            decoded_params
        ) == len(expected_params), (
            f"{fqn}: {channel} round-trip changed the bind parameters.\n"
            f"  original: {expected_params!r}\n"
            f"  {channel}: {decoded_params!r}"
        )
    if gapped:
        return "artifact-gap"
    return "rendered"


@pytest.fixture(params=sorted(REGISTERED), ids=sorted(REGISTERED))
def sqlserver_expr_case(request, sqlserver_dialect):
    """One expression instance per collected class, or a pinned skip.

    A class that cannot be built is a skip only if it is named in
    :data:`UNCONSTRUCTIBLE`; anything else fails here rather than disappearing,
    because an unnamed skip is a coverage hole with no marker.
    """
    fqn = request.param
    cls = REGISTERED[fqn]
    instance, source = make_instance(cls, sqlserver_dialect)
    if instance is None:
        assert fqn in UNCONSTRUCTIBLE, (
            f"{fqn} cannot be built by the generic constructor ({source}) and is "
            f"not in UNCONSTRUCTIBLE. Either register a special constructor for "
            f"it or add it to the tuple with a reason -- do not let it disappear "
            f"into a skip."
        )
        pytest.skip(f"{fqn}: pinned in UNCONSTRUCTIBLE, cannot be constructed ({source})")
    return fqn, instance


def _same_host_value(restored: Any, original: Any) -> bool:
    """Whether a round-tripped host value still names the same value.

    Two shapes are not ``==`` to themselves after a round-trip: NaN, and a
    tuple, which the JSON-family channels hand back as a list because JSON draws
    no distinction between the two -- while the dict channel, which never leaves
    Python, keeps the tuple. Both spell the same sequence, and the harness's own
    comparison allows both; this is the same tolerance asked of one value.
    """
    if isinstance(original, (tuple, list)):
        return isinstance(restored, (tuple, list)) and list(original) == list(
            restored
        )
    if isinstance(original, float) and original != original:
        return restored != restored
    return restored == original


class TestLiteralValueKinds:
    """Every value kind travels as a plain JSON scalar, and inlines as text.

    One ``Literal`` class carries every value, so a class-level matrix has one
    row for it -- but an artifact is keyed by *kind*, and the sixteen kinds are
    sixteen shapes. The table below is that registration: the spelling each kind
    packs its host value into, so a kind that started travelling as anything but
    a scalar fails here, and so does one whose inline spelling this dialect
    changed. NaN and +/-Infinity have kinds of their own now (``nan_value`` /
    ``infinity_value``, carrying the words ``"nan"`` / ``"+inf"`` /
    ``"-inf"``) rather than being finite floats a text spelling would corrupt.
    """

    #: (host value, kind, the JSON spelling the artifact carries)
    VALUE_KINDS = (
        (None, "null_value", None),
        (True, "boolean_value", True),
        (1, "integer_value", 1),
        (2.5, "float_value", 2.5),
        (Decimal("1.5"), "decimal_value", "1.5"),
        (float("nan"), "nan_value", "nan"),
        (float("inf"), "infinity_value", "+inf"),
        (float("-inf"), "infinity_value", "-inf"),
        ("x", "string_value", "x"),
        (b"\x01\x02", "binary_value", "AQI="),
        (datetime.date(2026, 1, 2), "date_value", "2026-01-02"),
        (
            datetime.datetime(2026, 1, 2, 3, 4, 5),
            "timestamp_value",
            "2026-01-02 03:04:05",
        ),
        (datetime.timedelta(days=1), "interval_value", "P1D"),
        ([1, 2], "list_value", [1, 2]),
        ((1, 2), "tuple_value", [1, 2]),
        (
            uuid_module.UUID("01234567-89ab-cdef-0123-456789abcdef"),
            "uuid_value",
            "01234567-89ab-cdef-0123-456789abcdef",
        ),
    )

    @pytest.mark.parametrize(
        "value,kind,spelling",
        VALUE_KINDS,
        ids=[kind for _value, kind, _spelling in VALUE_KINDS],
    )
    def test_the_artifact_carries_the_plain_spelling(
        self, value, kind, spelling, sqlserver_dialect
    ):
        import json

        from rhosocial.activerecord.backend.expression.serialization import (
            serialize,
            serialize_json,
        )

        literal = Literal(sqlserver_dialect, value)
        artifact = serialize(literal)
        assert artifact == {
            "kind": kind,
            "params": {"value": spelling, "inline": False},
        }, f"{kind}: the artifact is not the spelling the table names"
        assert json.loads(serialize_json(literal)) == artifact, (
            f"{kind}: the JSON text does not decode to the same artifact"
        )

    @pytest.mark.parametrize(
        "value,kind,spelling",
        VALUE_KINDS,
        ids=[kind for _value, kind, _spelling in VALUE_KINDS],
    )
    def test_every_kind_round_trips_through_all_three_channels(
        self, value, kind, spelling, sqlserver_dialect
    ):
        from rhosocial.activerecord.backend.expression.serialization import (
            deserialize,
            deserialize_json,
            deserialize_xml,
            serialize,
            serialize_json,
            serialize_xml,
        )

        literal = Literal(sqlserver_dialect, value)
        for name, encode, decode in (
            ("dict", serialize, deserialize),
            ("json", serialize_json, deserialize_json),
            ("xml", serialize_xml, deserialize_xml),
        ):
            restored = decode(encode(literal), sqlserver_dialect)
            # Re-encoding rather than reading the class's own kind(): one
            # Literal class carries every value kind, so the *artifact* is what
            # names it, and a restored node must still encode as the same kind.
            assert serialize(restored)["kind"] == kind, (
                f"{kind}: {name} restored another kind"
            )
            assert _same_host_value(restored.value, value), (
                f"{kind}: {name} changed the host value: {restored.value!r}"
            )
            assert restored.inline is False, f"{kind}: {name} changed the position"

    def test_an_inline_position_writes_text_not_a_parameter(self, sqlserver_dialect):
        """The DDL position: the value reaches SQL as text and takes no bind.

        Each kind's *rendered* spelling is the dialect's business and is pinned
        in ``test_sqlserver_typed_values.py``; what this row pins is the
        position -- ``inline=True`` must give text and no parameters for every
        kind that has an inline form on this dialect. The ones with none are
        refusals rather than guesses: the non-finite floats, which no SQL text
        may carry (``nan_value`` / ``infinity_value`` exist so those payloads
        can travel in an artifact *without* ever reaching SQL text); the
        interval, whose absence this dialect keeps structural; and the two
        sequence kinds, which are a host container rather than a scalar SQL
        literal -- SQL Server spells a list as a ``VALUES`` clause or a
        table-valued parameter, not as a literal.
        """
        refused = {
            "nan_value": ValueError,
            "infinity_value": ValueError,
            "interval_value": TypeError,
            "list_value": TypeError,
            "tuple_value": TypeError,
        }
        for value, kind, _spelling in self.VALUE_KINDS:
            if kind in refused:
                with pytest.raises(refused[kind]):
                    Literal(sqlserver_dialect, value, inline=True).to_sql()
                continue
            sql, params = Literal(sqlserver_dialect, value, inline=True).to_sql()
            assert params == (), f"{kind}: an inline literal took a bind parameter"
            assert sql, f"{kind}: an inline literal rendered nothing"

    def test_the_position_travels_with_the_literal(self, sqlserver_dialect):
        """``inline`` is part of the artifact: a position is not a class.

        The class-level strategy wave moved this decision onto the instance, so
        a DDL-position literal must come back a DDL-position literal.
        """
        from rhosocial.activerecord.backend.expression.serialization import (
            deserialize,
            deserialize_json,
            deserialize_xml,
            serialize,
            serialize_json,
            serialize_xml,
        )

        inline = Literal(sqlserver_dialect, 1, inline=True)
        for encode, decode in (
            (serialize_json, deserialize_json),
            (serialize, deserialize),
            (serialize_xml, deserialize_xml),
        ):
            restored = decode(encode(inline), sqlserver_dialect)
            assert restored.inline is True
            assert restored.to_sql() == ("1", ())


class TestSQLServerExpressionRoundtrip:
    """All constructible expression classes round-trip through all encodings."""

    def test_get_params_roundtrip(self, sqlserver_expr_case, sqlserver_dialect):
        fqn, instance = sqlserver_expr_case
        row = ARTIFACT_GAPS.get(fqn)
        if row is None:
            roundtrip_expression(fqn, instance, sqlserver_dialect)
            return
        channels, exc_type, fragment = row
        pinned = _channel_channels(channels)
        codecs = _artifact_codecs()
        # A pinned class runs its channels one at a time rather than through
        # the three-channel helper: the pinned channel's outcome is the
        # assertion here -- it must fail in exactly the recorded way, or the
        # row is stale -- while the unpinned ones keep asserting normally.
        for name in _ARTIFACT_CHANNELS:
            encode, decode = codecs[name]
            is_pinned = name in pinned
            try:
                restored = decode(encode(instance), sqlserver_dialect)
                restored_params = restored.get_params()
            except Exception as exc:
                if is_pinned:
                    _record_channel(fqn, name, exc)
                    continue
                raise AssertionError(
                    f"{fqn}: the {name} channel cannot carry this node "
                    f"({type(exc).__name__}: {exc}) and the pin names "
                    f"{channels!r}."
                ) from exc
            if exc_type is not None:
                # the row names an exception, so a channel that carries the
                # node contradicts it
                assert not is_pinned, (
                    f"{fqn}: ARTIFACT_GAPS pins {exc_type.__name__} on "
                    f"{channels!r} but the {name} channel carried the node -- "
                    "the row is stale"
                )
                assert_params_equal(restored_params, instance.get_params())
                continue
            if is_pinned:
                # the spelling gap: the channel carries the node and hands back
                # the same parameter under the XML codec's member spelling. The
                # strict comparison must refuse it -- that is the thing the row
                # records -- and the tolerant one must accept it, which proves
                # the difference is only the spelling and nothing else.
                with pytest.raises(AssertionError):
                    assert_params_equal(restored_params, instance.get_params())
                assert_params_equal(
                    restored_params,
                    instance.get_params(),
                    allow_enum_names=True,
                )
                continue
            assert_params_equal(restored_params, instance.get_params())

    def test_to_sql_roundtrip_classified(self, sqlserver_expr_case, sqlserver_dialect):
        """A render must survive the round-trip; a non-render must be classified."""
        fqn, instance = sqlserver_expr_case
        assert_sql_roundtrip_classified(fqn, instance, sqlserver_dialect)


class TestMatrixIntegrity:
    """Guards on the matrix and its lists, so neither can quietly change."""

    def test_unconstructible_list_is_exact(self, sqlserver_dialect):
        """Pin the unconstructible tuple against what the constructor really skips.

        Two directions are checked. A class named here that now builds has gained
        a constructor and the entry is stale; a class that fails to build without
        being named would become a silent skip. Both fail here.
        """
        actual = tuple(
            sorted(
                fqn
                for fqn in REGISTERED
                if make_instance(REGISTERED[fqn], sqlserver_dialect)[0] is None
            )
        )
        assert actual == tuple(sorted(UNCONSTRUCTIBLE)), (
            "the set of expression classes the generic constructor cannot build "
            "changed.\n"
            f"  now skipped but not named: "
            f"{sorted(set(actual) - set(UNCONSTRUCTIBLE))}\n"
            f"  named but now built: "
            f"{sorted(set(UNCONSTRUCTIBLE) - set(actual))}\n"
            "Each new entry needs a reason in the comment above UNCONSTRUCTIBLE."
        )

    def test_unconstructible_entries_are_real_classes(self):
        """Every entry names a class that was actually collected.

        A typo in the tuple would otherwise exempt nothing while still reading as
        a deliberate decision.
        """
        unknown = set(UNCONSTRUCTIBLE) - set(REGISTERED)
        assert not unknown, (
            f"UNCONSTRUCTIBLE names classes that were not registered: {sorted(unknown)}"
        )

    def test_legitimate_non_renders_are_real_classes(self):
        """Every pinned non-render names a class that was actually collected."""
        unknown = set(LEGITIMATE_NON_RENDERS) - set(REGISTERED)
        assert not unknown, (
            f"LEGITIMATE_NON_RENDERS names classes that were not registered: "
            f"{sorted(unknown)}"
        )

    def test_pinned_non_render_really_does_not_render(self, sqlserver_dialect):
        """Each pinned entry still raises what it claims, for the stated reason.

        Without this, an entry could sit in the dict for a class that renders
        perfectly well, and the matrix would be asserting nothing about it.
        """
        for fqn, (expected_type, fragment) in LEGITIMATE_NON_RENDERS.items():
            instance, source = make_instance(REGISTERED[fqn], sqlserver_dialect)
            assert instance is not None, (
                f"{fqn} is pinned as a non-render but could not be constructed "
                f"({source})"
            )
            with pytest.raises(expected_type) as exc_info:
                instance.to_sql()
            assert fragment in str(exc_info.value), (
                f"{fqn}: expected the message to mention {fragment!r}, got: "
                f"{exc_info.value}"
            )

    def test_unmodelled_formatter_list_is_exact(self, sqlserver_dialect):
        """Pin the unmodelled-formatter table against what the dialect lacks.

        Observed rather than assumed: for each class the matrix covers, either
        it renders or it fails, and every dispatch refusal is attributed to the
        method it named -- including the classes pinned in
        :data:`LEGITIMATE_NON_RENDERS`, whose dispatch failures those pins
        record class by class. Then the table is compared with the set
        observed, in both directions, so:

        * a method in the table that SQL Server now implements fails here,
          because its classes render and are no longer attributed to it --
          which is the moment to delete the entry rather than leave a lie in
          the table;
        * a class that starts needing a method outside the table fails the
          per-class assertion in :func:`assert_sql_roundtrip_classified`
          instead of being absorbed into "unsupported".

        This is the regression test for the pad/trim incident. Core turned
        ``trim``/``lpad``/``rpad``/``repeat`` into dedicated nodes; SQL Server
        renders ``trim`` and has no ``LPAD``, ``RPAD`` or ``REPEAT``, so those
        three nodes are exactly the shape this test exists for: classes whose
        formatter no base in this dialect provides, which before the split
        were allowed through as "SQL Server lacks the feature" without
        anything asking whether the feature was even claimed.
        """
        observed = set()
        for fqn in sorted(REGISTERED):
            instance, source = make_instance(REGISTERED[fqn], sqlserver_dialect)
            if instance is None:
                continue
            try:
                instance.to_sql()
            except UnsupportedFeatureError as exc:
                method = _dispatched_formatter(exc)
                if method is not None:
                    observed.add(method)
                continue
            except Exception:
                continue

        declared = _unmodelled_methods()
        assert not (observed - declared), (
            "classes need formatters that are not in UNMODELLED_FORMATTERS: "
            f"{sorted(observed - declared)}. Add each with the feature that is "
            f"absent and why -- or mix the formatter in, in which case the "
            f"classes render and the entry is not needed."
        )
        assert not (declared - observed), (
            "UNMODELLED_FORMATTERS names formatters no class actually needs: "
            f"{sorted(declared - observed)}. SQL Server may have gained one of "
            f"these, in which case the classes needing it now render and the "
            f"entry should go."
        )

    def test_matrix_covers_both_packages(self):
        """The matrix covers every concrete class both packages define.

        Re-walked here rather than trusting the module-level collection, so a
        class that appeared after import is caught. The package walk is used
        rather than the registry because the registry also holds whatever
        backends other test modules happened to import -- which is exactly the
        non-determinism this matrix moved off.
        """
        for pkg in (CORE_EXPR_PKG, SS_EXPR_PKG):
            expected = set(_collect(pkg))
            covered = {
                fqn for fqn in REGISTERED if fqn.startswith(f"{pkg}.")
            }
            assert expected == covered, (
                f"the set of classes {pkg} defines changed after collection.\n"
                f"  now defined but not covered: {sorted(expected - covered)}\n"
                f"  covered but no longer defined: {sorted(covered - expected)}"
            )
        assert len(REGISTERED) > 300, (
            f"only {len(REGISTERED)} classes collected; the package walk may "
            f"have stopped early"
        )

    def test_every_covered_class_is_registered_for_deserialization(self):
        """A class in the matrix can be found again when deserializing.

        Deserialization resolves a kind through the framework's default
        registry -- the same whitelist ``register_all`` filled at import --
        so a class the matrix renders but the registry cannot resolve would
        round-trip into the wrong thing or nothing at all.
        """
        from rhosocial.activerecord.backend.expression.serialization import (
            default_registry,
        )

        registry = default_registry()
        unresolved = sorted(
            fqn
            for fqn, cls in REGISTERED.items()
            if registry.resolve_node(cls.kind()) is not cls
        )
        assert not unresolved, (
            f"the matrix covers classes the kind whitelist cannot resolve: {unresolved}"
        )

    def test_artifact_gap_list_is_exact(self, sqlserver_dialect):
        """Pin the artifact-gap table against what the channels really carry.

        Both directions, and each row is checked against the tree right here: a
        row naming no collected class, a channel outside the three the matrix
        runs, or a *typed* row whose channel now carries the node is a typo that
        would exempt nothing while reading as a decision. The ``None``-typed
        rows are checked by the per-class test, which asserts both that the
        strict comparison refuses the restored params and that the tolerant one
        accepts them.
        """
        unknown = set(ARTIFACT_GAPS) - set(REGISTERED)
        assert not unknown, (
            f"ARTIFACT_GAPS names classes that were not collected: "
            f"{sorted(unknown)}"
        )
        codecs = _artifact_codecs()
        for fqn, (channels, exc_type, _fragment) in ARTIFACT_GAPS.items():
            for name in _channel_channels(channels):
                assert name in _ARTIFACT_CHANNELS, (
                    f"{fqn}: ARTIFACT_GAPS names channel {name!r}; the matrix "
                    f"runs {list(_ARTIFACT_CHANNELS)}"
                )
            instance, _source = make_instance(REGISTERED[fqn], sqlserver_dialect)
            assert instance is not None, (
                f"{fqn} is pinned as an artifact gap but cannot be built"
            )
            if exc_type is None:
                continue  # the spelling rows are pinned by the per-class test
            for name in _channel_channels(channels):
                encode, decode = codecs[name]
                try:
                    decode(encode(instance), sqlserver_dialect).to_sql()
                except Exception as exc:
                    _record_channel(fqn, name, exc)
                    break
            else:
                raise AssertionError(
                    f"{fqn} is pinned in ARTIFACT_GAPS with "
                    f"{exc_type.__name__} but the {channels} channel carried "
                    "it -- remove the row"
                )

    def test_coverage_report(self, sqlserver_dialect):
        """Surface what the matrix covers, so coverage stays transparent."""
        branches = {
            "rendered": 0,
            "unsupported": 0,
            "unmodelled": 0,
            "non-render": 0,
            "artifact-gap": 0,
        }
        constructible = []
        for fqn in sorted(REGISTERED):
            instance, source = make_instance(REGISTERED[fqn], sqlserver_dialect)
            if instance is None:
                continue
            constructible.append(fqn)
            branches[
                assert_sql_roundtrip_classified(fqn, instance, sqlserver_dialect)
            ] += 1
        assert constructible
        print(
            f"\nexpression matrix: {len(REGISTERED)} collected, "
            f"{len(constructible)} constructible, "
            f"{len(UNCONSTRUCTIBLE)} pinned-unconstructible; "
            f"rendered {branches['rendered']}, "
            f"unsupported {branches['unsupported']}, "
            f"unmodelled {branches['unmodelled']} (pinned in "
            f"UNMODELLED_FORMATTERS), "
            f"pinned non-render {branches['non-render']}, "
            f"artifact gap {branches['artifact-gap']}"
        )
        for fqn in UNCONSTRUCTIBLE:
            print(f"  not constructible: {fqn}")
        for feature, methods in sorted(UNMODELLED_FORMATTERS.items()):
            print(f"  not modelled: {feature} ({len(methods)} formatters)")
        for fqn in sorted(ARTIFACT_GAPS):
            channel, _type, _fragment = ARTIFACT_GAPS[fqn]
            print(f"  artifact gap: {fqn} ({channel} channel)")
